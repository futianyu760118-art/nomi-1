import hmac
import os
import re
import secrets
import threading
import time
from datetime import timedelta
from functools import wraps
from pathlib import Path

from dotenv import load_dotenv
from flask import Flask, g, jsonify, request, session
from sqlalchemy import select
from werkzeug.exceptions import HTTPException
from werkzeug.security import check_password_hash

from .models import Project, Requirement, Risk, User, Inspection, GitLink
from .storage import database
from .seed import seed
from .settings import read_settings, save_settings
from .services import (
    snapshot, scan_risks, sync_project, sync_plane, sync_git, requirement_data, set_link, log,
    generate_summary, update_requirement, create_requirement, management_options, ensure_project_binding,
    projects_overview, project_overview, create_local_project, update_local_project,
)
from .integrations import IntegrationError, PartialWriteError, GitLabProvider
from .inspector import inspect_requirement
from .domain import requirement_fingerprint
from .person_lifecycle import is_user_active, register_person_lifecycle


def create_app(test_config=None):
    load_dotenv(Path(__file__).resolve().parents[2] / ".env")
    app = Flask(__name__)
    demo = os.getenv("DEMO_MODE", "true").lower() == "true"
    secret = os.getenv("SECRET_KEY")
    if not secret:
        if not demo and not test_config:
            raise RuntimeError("Live mode requires a persistent SECRET_KEY")
        path = Path(__file__).resolve().parents[1] / "data" / "session.key"
        path.parent.mkdir(exist_ok=True)
        if not path.exists():
            path.write_text(secrets.token_hex(32), encoding="ascii")
        secret = path.read_text(encoding="ascii").strip()
    if not demo and not test_config and len(secret) < 32:
        raise RuntimeError("Live mode requires SECRET_KEY with at least 32 characters")
    app.config.update(SECRET_KEY=secret, SESSION_COOKIE_HTTPONLY=True, SESSION_COOKIE_SAMESITE="Lax",
                      SESSION_COOKIE_SECURE=os.getenv("COOKIE_SECURE", "false").lower() == "true",
                      PERMANENT_SESSION_LIFETIME=timedelta(hours=12), MAX_CONTENT_LENGTH=1_000_000)
    if test_config:
        app.config.update(test_config)
    engine, sessions = database(app.config.get("DATABASE_URL"))
    app.extensions["sessions"], app.extensions["engine"] = sessions, engine
    mutation_lock = threading.Lock()
    app.extensions["mutation_lock"] = mutation_lock
    attempts = {}
    with sessions() as db:
        seed(db, demo)
        for project in db.scalars(select(Project)).all():
            scan_risks(db, project)

    @app.before_request
    def begin():
        g.db = sessions()
        if request.method in ("POST", "PATCH", "DELETE", "PUT") and not request.path.startswith("/api/webhooks/") and request.path != "/internal/aeos/person-lifecycle":
            if request.headers.get("X-PMO-Request") != "1" or not request.is_json:
                return jsonify(error="请求缺少安全校验头或 JSON Content-Type"), 403

    @app.teardown_request
    def end(_error):
        if getattr(g, "db", None):
            g.db.close()

    def require_user(admin=False):
        def decorate(fn):
            @wraps(fn)
            def wrapped(*args, **kwargs):
                user = g.db.get(User, session.get("user_id")) if session.get("user_id") else None
                if not user:
                    return jsonify(error="请先登录"), 401
                if not is_user_active(g.db, user):
                    return jsonify(error="账号已停用，不能继续使用"), 401
                if admin and user.role != "admin":
                    return jsonify(error="该操作需要管理员权限"), 403
                g.user = user
                return fn(*args, **kwargs)
            return wrapped
        return decorate

    def settings():
        return read_settings(g.db, app.secret_key)

    def project():
        project_id = request.args.get("project", type=int)
        row = g.db.get(Project, project_id) if project_id else g.db.scalar(select(Project).order_by(Project.id).limit(1))
        if not row:
            raise ValueError("项目不存在，请先在系统设置中导入 Plane 项目")
        return row

    def requirement(key):
        row = g.db.scalar(select(Requirement).where(Requirement.project_id == project().id, Requirement.key == key, Requirement.active == 1))
        if not row:
            from flask import abort
            abort(404, description="需求不存在")
        return row

    def serialized(fn):
        @wraps(fn)
        def wrapped(*args, **kwargs):
            if not mutation_lock.acquire(blocking=False):
                return jsonify(error="另一个同步或核验正在执行，请稍后重试"), 409
            try:
                return fn(*args, **kwargs)
            finally:
                mutation_lock.release()
        return wrapped

    @app.errorhandler(Exception)
    def error(exc):
        if getattr(g, "db", None):
            g.db.rollback()
        if isinstance(exc, IntegrationError):
            return jsonify(error=str(exc), source=exc.source, partial=isinstance(exc, PartialWriteError)), 502
        if isinstance(exc, (ValueError, TypeError)):
            return jsonify(error=str(exc)), 400
        if isinstance(exc, HTTPException):
            return jsonify(error=exc.description), exc.code
        app.logger.error("Unhandled API error: %s", type(exc).__name__)
        return jsonify(error="服务暂时不可用，已有数据未被替换"), 500

    @app.get("/api/health")
    def health():
        return jsonify(status="ok")

    @app.post("/api/auth/login")
    def login():
        ip = request.remote_addr
        now = time.monotonic()
        for address in list(attempts):
            attempts[address] = [t for t in attempts[address] if t > now - 60]
            if not attempts[address]:
                del attempts[address]
        if len(attempts.get(ip, [])) >= 10:
            return jsonify(error="登录尝试过多，请一分钟后重试"), 429
        attempts.setdefault(ip, []).append(now)
        body = request.get_json()
        if not isinstance(body, dict) or not isinstance(body.get("username"), str) or not isinstance(body.get("password"), str):
            raise ValueError("请输入账号和密码")
        user = g.db.scalar(select(User).where(User.username == body["username"]))
        if not user or not check_password_hash(user.password_hash, body["password"]) or not is_user_active(g.db, user):
            return jsonify(error="账号或密码错误"), 401
        session.clear()
        session["user_id"] = user.id
        session.permanent = True
        attempts.pop(ip, None)
        return jsonify(username=user.username, role=user.role)

    @app.get("/api/auth/me")
    @require_user()
    def me():
        return jsonify(username=g.user.username, role=g.user.role)

    @app.post("/api/auth/logout")
    def logout():
        session.clear()
        return jsonify(status="ok")

    @app.get("/api/projects")
    @require_user()
    def projects():
        return jsonify(items=projects_overview(g.db, settings()))

    @app.post("/api/projects")
    @require_user(admin=True)
    def create_project_route():
        project = create_local_project(g.db, request.get_json())
        return jsonify(project_overview(g.db, project, settings())), 201

    @app.patch("/api/projects/<int:project_id>")
    @require_user(admin=True)
    def update_project_route(project_id):
        row = g.db.get(Project, project_id)
        if not row:
            return jsonify(error="项目不存在"), 404
        update_local_project(g.db, row, request.get_json())
        return jsonify(project_overview(g.db, row, settings()))

    @app.get("/api/bootstrap")
    @require_user()
    def bootstrap():
        return jsonify(snapshot(g.db, project(), settings()))

    @app.get("/api/dashboard")
    @require_user()
    def dashboard():
        return jsonify(snapshot(g.db, project(), settings())["dashboard"])

    @app.get("/api/requirements")
    @require_user()
    def requirements():
        data = snapshot(g.db, project(), settings())["requirements"]
        query = request.args.get("q", "").lower()
        return jsonify(items=[r for r in data if query in (r["id"] + r["title"] + r["owner"] + r["module"]).lower()])

    @app.get("/api/requirements/<key>")
    @require_user()
    def detail(key):
        return jsonify(requirement_data(g.db, requirement(key)))

    @app.get("/api/management/options")
    @require_user(admin=True)
    def management_catalog():
        return jsonify(management_options(g.db, project()))

    @app.get("/api/risks")
    @require_user()
    def risks():
        return jsonify(items=snapshot(g.db, project(), settings())["risks"])

    @app.get("/api/weekly")
    @require_user()
    def weekly():
        data = snapshot(g.db, project(), settings())
        return jsonify(weeks=data["dashboard"]["weeks"], items=data["requirements"])

    @app.post("/api/sync")
    @require_user(admin=True)
    @serialized
    def sync():
        p = project()
        try:
            return jsonify(sync_project(g.db, p, settings()))
        except (IntegrationError, ValueError) as exc:
            g.db.rollback()
            log(g.db, p.id, getattr(exc, "source", "同步"), "FAILED", str(exc))
            raise

    @app.post("/api/connections/plane")
    @require_user(admin=True)
    @serialized
    def connect_plane():
        p = sync_plane(g.db, settings())
        return jsonify(id=p.id, name=p.name)

    @app.post("/api/connections/git")
    @require_user(admin=True)
    @serialized
    def connect_git():
        p = project()
        if p.mode != "live":
            raise ValueError("真实仓库只能关联到导入 Plane 的项目；本地项目暂不接入 GitLab")
        return jsonify(linked=sync_git(g.db, p, settings()))

    @app.patch("/api/requirements/<key>")
    @require_user(admin=True)
    @serialized
    def update_requirement_route(key):
        row = requirement(key)
        body = request.get_json()
        return jsonify(update_requirement(g.db, row, body, settings()))

    @app.post("/api/requirements")
    @require_user(admin=True)
    @serialized
    def create_requirement_route():
        body = request.get_json()
        return jsonify(create_requirement(g.db, project(), body, settings())), 201

    def git_write_context():
        p, cfg = project(), settings()
        if p.mode != "live":
            raise ValueError("分支与 MR 操作需要导入连接 Plane 的真实项目")
        external = ensure_project_binding(g.db, p, cfg)
        binding = (external.data or {}).get("gitBinding")
        identity = dict(url=cfg["gitUrl"].rstrip("/"), repository=cfg["repository"])
        if binding and binding != identity:
            raise ValueError("仓库设置不属于所选项目，已阻止跨仓库写入")
        provider = GitLabProvider(cfg)
        # Pin the repository before any remote side effect.
        external.data = dict(external.data or {}, gitBinding=identity)
        g.db.commit()
        return p, provider

    @app.post("/api/requirements/<key>/branch")
    @require_user(admin=True)
    @serialized
    def create_requirement_branch(key):
        row = requirement(key)
        p, provider = git_write_context()
        body = request.get_json() or {}
        if not isinstance(body, dict):
            raise ValueError("分支参数无效")
        name = body.get("name") or "feat/{}-development".format(key.lower())
        if not isinstance(name, str) or not re.match(r"^[A-Za-z0-9._/-]{2,120}$", name):
            raise ValueError("分支名称无效")
        from .domain import reference_ids
        if key not in reference_ids(name):
            raise ValueError("分支名称必须包含当前需求编号")
        if body.get("ref") is not None and not isinstance(body["ref"], str):
            raise ValueError("来源分支无效")
        existing = g.db.scalar(select(GitLink).where(GitLink.requirement_id == row.id))
        if existing:
            raise ValueError("需求已关联开发分支，请先使用现有分支")
        branch = provider.create_branch(name, body.get("ref"))
        commit = branch.get("commit") or {}
        set_link(g.db, row, dict(repository=provider.repository, branch=name, mr=None, mrState=None,
                                pipeline="UNKNOWN", sha=commit.get("id"), author=commit.get("author_name"),
                                updatedAt=commit.get("committed_date"), url=branch.get("web_url"), source="gitlab", manual=False,
                                commits=[dict(sha=commit.get("id", ""), message=commit.get("message", ""), author=commit.get("author_name", ""))]))
        g.db.commit()
        log(g.db, p.id, "GitLab Write", "SUCCESS", "{} 创建开发分支 {}".format(key, name))
        return jsonify(branch=name, status="created")

    @app.post("/api/requirements/<key>/merge-request")
    @require_user(admin=True)
    @serialized
    def create_requirement_merge_request(key):
        row = requirement(key)
        p, provider = git_write_context()
        body = request.get_json() or {}
        if not isinstance(body, dict):
            raise ValueError("MR 参数无效")
        branch = body.get("branch")
        if not isinstance(branch, str) or not branch.strip():
            raise ValueError("请填写源分支")
        existing = g.db.scalar(select(GitLink).where(GitLink.requirement_id == row.id))
        if existing and existing.data.get("mr"):
            raise ValueError("需求已关联 MR，请使用已有 MR")
        if not existing or existing.data.get("branch") != branch.strip():
            raise ValueError("请先创建或同步当前需求的开发分支")
        target = body.get("target")
        if target is not None and not isinstance(target, str):
            raise ValueError("目标分支无效")
        link = provider.create_merge_request(branch.strip(), "{} {}".format(row.key, row.title)[:500], row.description[:5000], target)
        link["manual"] = True
        set_link(g.db, row, link)
        g.db.commit()
        scan_risks(g.db, p)
        log(g.db, p.id, "GitLab Write", "SUCCESS", "{} 创建 MR !{}".format(key, link["mr"]))
        return jsonify(requirement_data(g.db, row))

    @app.get("/api/settings")
    @require_user(admin=True)
    def get_settings():
        return jsonify(read_settings(g.db, app.secret_key, public=True))

    @app.patch("/api/settings")
    @require_user(admin=True)
    def put_settings():
        return jsonify(save_settings(g.db, app.secret_key, request.get_json()))

    @app.post("/api/risks/scan")
    @require_user(admin=True)
    @serialized
    def scan():
        scan_risks(g.db, project())
        return jsonify(snapshot(g.db, project(), settings()))

    @app.patch("/api/risks/<int:risk_id>")
    @require_user(admin=True)
    def acknowledge(risk_id):
        row = g.db.get(Risk, risk_id)
        if not row or row.project_id != project().id:
            return jsonify(error="风险不存在"), 404
        status = request.get_json().get("status")
        if status not in ("OPEN", "ACKNOWLEDGED") and not (row.source == "人工" and status == "RESOLVED"):
            raise ValueError("只允许确认或重新打开；规则消失后自动关闭")
        row.status = status
        g.db.commit()
        return jsonify(status=status)

    @app.post("/api/risks")
    @require_user(admin=True)
    def manual_risk():
        body = request.get_json()
        row = requirement(body.get("requirementId"))
        level, title, action = body.get("level"), body.get("title"), body.get("action")
        if level not in ("HIGH", "MEDIUM", "LOW") or not isinstance(title, str) or not 1 <= len(title.strip()) <= 500 or not isinstance(action, str) or not 1 <= len(action.strip()) <= 2000:
            raise ValueError("请填写风险等级、名称和建议动作")
        risk = Risk(project_id=row.project_id, requirement_id=row.id, rule="MANUAL_" + secrets.token_hex(8),
                    level=level, title=title.strip(), action=action.strip(), source="人工")
        g.db.add(risk)
        g.db.commit()
        return jsonify(id=risk.id), 201

    @app.post("/api/summary")
    @require_user(admin=True)
    @serialized
    def summary():
        p = project()
        try:
            return jsonify(generate_summary(g.db, p, settings()))
        except (IntegrationError, ValueError) as exc:
            g.db.rollback()
            log(g.db, p.id, "AI Summary", "FAILED", str(exc))
            raise

    @app.post("/api/requirements/<key>/git-link")
    @require_user(admin=True)
    @serialized
    def bind(key):
        p, row = project(), requirement(key)
        if p.mode == "demo":
            raise ValueError("演示项目不可绑定真实 MR")
        iid = request.get_json().get("mr")
        if type(iid) is not int or iid < 1:
            raise ValueError("MR 编号必须为正整数")
        p, provider = git_write_context()
        data = provider.mr_link(iid)
        data["manual"] = True
        set_link(g.db, row, data)
        g.db.commit()
        scan_risks(g.db, p)
        return jsonify(requirement_data(g.db, row))

    def run_inspection(row, p):
        cfg = settings()
        if p.mode != "live":
            raise ValueError("AI 核验需要导入 Plane 项目并关联真实 GitLab MR；本地/演示项目不调用模型")
        ensure_project_binding(g.db, p, cfg)
        link = g.db.scalar(select(GitLink).where(GitLink.requirement_id == row.id))
        if not link or not link.data.get("mr"):
            raise ValueError("请先关联 MR")
        provider = GitLabProvider(cfg)
        fresh = provider.mr_link(link.data["mr"])
        fresh["manual"] = link.data.get("manual", False)
        set_link(g.db, row, fresh)
        result = inspect_requirement(row, fresh, provider, cfg)
        result["input_hash"] = requirement_fingerprint(row.description, row.criteria)
        g.db.add(Inspection(requirement_id=row.id, source="llm", commit_sha=fresh["sha"], data=result))
        g.db.commit()
        scan_risks(g.db, p)
        return requirement_data(g.db, row)

    @app.post("/api/requirements/<key>/inspect")
    @require_user(admin=True)
    @serialized
    def inspect(key):
        p = project()
        try:
            return jsonify(run_inspection(requirement(key), p))
        except (IntegrationError, ValueError) as exc:
            g.db.rollback()
            log(g.db, p.id, "AI Inspector", "FAILED", str(exc))
            raise

    @app.post("/api/webhooks/gitlab")
    @serialized
    def gitlab_webhook():
        expected = os.getenv("WEBHOOK_SECRET", "")
        if not expected or not hmac.compare_digest(request.headers.get("X-Gitlab-Token", ""), expected):
            return jsonify(error="Webhook 签名无效"), 401
        body = request.get_json()
        cfg = settings()
        from .models import ExternalProject
        identity = cfg["planeUrl"].rstrip("/") + "/" + cfg["workspace"] + "/" + cfg["planeProject"]
        external = g.db.scalar(select(ExternalProject).where(ExternalProject.external_id == identity, ExternalProject.provider == "plane"))
        hook_project = body.get("project") or {}
        repository_matches = str(hook_project.get("id")) == cfg["repository"] if cfg["repository"].isdigit() else hook_project.get("path_with_namespace") == cfg["repository"]
        if not external or not repository_matches:
            raise ValueError("Webhook 项目与当前设置不匹配")
        p = g.db.get(Project, external.project_id)
        kind = body.get("object_kind")
        if kind not in ("merge_request", "push", "pipeline"):
            return jsonify(status="ignored")
        sync_git(g.db, p, cfg)
        # No model calls for push events. Identical MR SHA is not inspected twice.
        if kind == "merge_request" and cfg["llmUrl"] and cfg["model"]:
            iid = (body.get("object_attributes") or {}).get("iid")
            for row in g.db.scalars(select(Requirement).where(Requirement.project_id == p.id, Requirement.active == 1)).all():
                link = g.db.scalar(select(GitLink).where(GitLink.requirement_id == row.id))
                if link and link.data.get("mr") == iid:
                    prior = g.db.scalar(select(Inspection.id).where(Inspection.requirement_id == row.id, Inspection.commit_sha == link.data.get("sha")).limit(1))
                    if not prior and row.criteria:
                        run_inspection(row, p)
        return jsonify(status="ok")

    register_person_lifecycle(app)
    return app
