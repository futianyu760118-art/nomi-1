import threading
from sqlalchemy import select
from .models import Project, ExternalProject, SystemSetting
from .settings import read_settings
from .services import scan_risks, sync_project, log, generate_summary


def start_scheduler(app):
    """One scheduler in the single Waitress process, sharing its mutation lock."""
    stop = threading.Event()
    app.extensions["scheduler_stop"] = stop

    def loop():
        import time
        from datetime import date
        attempted = {}
        summary_attempted = {}
        while not stop.wait(60):
            lock = app.extensions["mutation_lock"]
            if not lock.acquire(blocking=False):
                continue
            try:
                with app.extensions["sessions"]() as db:
                    cfg = read_settings(db, app.secret_key)
                    identity = cfg["planeUrl"].rstrip("/") + "/" + cfg["workspace"] + "/" + cfg["planeProject"]
                    external = db.scalar(select(ExternalProject).where(ExternalProject.external_id == identity, ExternalProject.provider == "plane"))
                    for project in db.scalars(select(Project)).all():
                        scan_risks(db, project)
                        if cfg["autoSync"] and external and external.project_id == project.id:
                            if time.monotonic() - attempted.get(project.id, 0) >= cfg["syncInterval"]:
                                attempted[project.id] = time.monotonic()
                                try:
                                    sync_project(db, project, cfg)
                                except Exception as exc:
                                    db.rollback()
                                    log(db, project.id, "定时同步", "FAILED", "同步失败: " + type(exc).__name__)
                            summary = db.get(SystemSetting, "summary:{}".format(project.id))
                            day = date.today().isoformat()
                            if cfg["llmUrl"] and cfg["model"] and summary_attempted.get(project.id) != day and (not summary or summary.data.get("day") != day):
                                summary_attempted[project.id] = day
                                try:
                                    generate_summary(db, project, cfg)
                                except Exception as exc:
                                    db.rollback()
                                    log(db, project.id, "AI Summary", "FAILED", "每日摘要生成失败: " + type(exc).__name__)
            except Exception:
                app.logger.error("Scheduled refresh failed; retrying next interval")
            finally:
                lock.release()
    thread = threading.Thread(target=loop, name="pmo-sync", daemon=True)
    thread.start()
