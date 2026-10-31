import os
from datetime import date, timedelta
from sqlalchemy import select
from werkzeug.security import generate_password_hash
from .models import Project, Requirement, GitLink, Inspection, User, timestamp
from .domain import requirement_fingerprint

TITLES = [
    "项目骨架与部署", "统一需求标识", "Plane 项目连接", "GitLab 只读连接", "工作区登录",
    "Agent 会话存储", "Skill 配置读取", "知识文档索引", "前端工作区导航", "需求缓存映射",
    "Agent 上下文恢复", "动态加载 Skill", "知识检索结果回溯", "项目成员工作量视图", "状态权重计算",
    "MR 自动关联", "风险规则引擎", "周计划汇总", "同步错误恢复", "验收证据追踪",
    "Skill 异常回滚", "知识索引增量更新", "需求详情适配", "Webhook 幂等处理", "测试结果聚合",
    "AI PMO 摘要", "敏感配置保护", "端到端验收", "部署文档", "项目交付验收",
]
OWNERS = ["吴杨鹏", "汪华正", "陈巧霞", "朱文祥"]
MODULES = ["Agent 中枢", "Skill 系统", "知识系统", "前端"]


def seed(db, demo=True):
    if not db.scalar(select(User.id).limit(1)):
        admin = os.getenv("ADMIN_USERNAME") or ("demo" if demo else "admin")
        password = os.getenv("ADMIN_PASSWORD") or ("demo" if demo else "")
        member_password = os.getenv("MEMBER_PASSWORD") or ("member" if demo else "")
        if not password or (not demo and len(password) < 12):
            raise RuntimeError("Live mode requires ADMIN_PASSWORD with at least 12 characters")
        if member_password and not demo and len(member_password) < 12:
            raise RuntimeError("Live mode requires MEMBER_PASSWORD with at least 12 characters or an empty value")
        db.add(User(username=admin, password_hash=generate_password_hash(password, method="pbkdf2:sha256"), role="admin"))
        if member_password:
            db.add(User(username="member", password_hash=generate_password_hash(member_password, method="pbkdf2:sha256"), role="member"))
    if not demo or db.scalar(select(Project.id).where(Project.mode == "demo").limit(1)):
        db.commit()
        return
    today = date.today()
    start = today - timedelta(days=today.weekday() + 14)
    project = Project(name="示例项目一期", mode="demo", start_date=start.isoformat(),
                      end_date=(start + timedelta(days=41)).isoformat(), last_sync=timestamp())
    db.add(project)
    db.flush()
    for index, title in enumerate(TITLES):
        week = index // 5 + 1
        status = "DONE" if week < 3 else ["REVIEW", "IN_PROGRESS", "BLOCKED", "DONE", "TESTING"][index % 5] if week == 3 else "TODO"
        key = "REQ-{:03d}".format(index + 1)
        due = start + timedelta(days=(week - 1) * 7 + 4)
        if status == "BLOCKED":
            due = today - timedelta(days=1)
        row = Requirement(project_id=project.id, key=key, title=title, module=MODULES[index % 4],
                          owner=OWNERS[index % 4], priority=["P0", "P1", "P2"][index % 3], status=status,
                          week=week, start=(start + timedelta(days=(week - 1) * 7)).isoformat(), due=due.isoformat(),
                          description="完成「{}」并提供可复现的验收证据。演示数据，不代表真实仓库实现。".format(title),
                          criteria=["{}主流程可用".format(title), "异常路径可恢复并记录错误", "关键场景具备自动化测试"],
                          blocked_progress=50 if status == "BLOCKED" else 0)
        db.add(row)
        db.flush()
        if week <= 3:
            git = dict(repository="demo-service", branch="feat/{}-implementation".format(key), mr=index + 1,
                       mrState="merged" if status == "DONE" else "opened", pipeline="FAILED" if status == "BLOCKED" else "PASSED",
                       sha="demo-{:07d}".format(index + 1), updatedAt=timestamp(), author=row.owner,
                       commits=[dict(sha="demo-{:07d}".format(index + 1), message="{}: {}".format(key, title), author=row.owner)],
                       url=None, manual=False, source="demo")
            db.add(GitLink(requirement_id=row.id, data=git))
            full = status == "DONE"
            result = dict(requirement_id=key, implementation_score=100 if full else 78 if status != "BLOCKED" else 54,
                          status="IMPLEMENTED" if full else "PARTIAL", acceptance_criteria=[
                              dict(criterion=c, status="IMPLEMENTED" if full or j == 0 else "MISSING",
                                   evidence=["demo/requirement_{}.py:{}".format(index + 1, 10 + j)] if full or j == 0 else [])
                              for j, c in enumerate(row.criteria)],
                          risks=[] if full else [dict(level="HIGH", description="缺少异常恢复的代码证据")],
                          tests=dict(status="PASSED" if full else "PARTIAL", summary="演示测试结果，未实际执行代码"),
                          summary="演示核验：{}".format("验收项全部覆盖" if full else "主体可用，异常路径与测试证据不足"))
            result["input_hash"] = requirement_fingerprint(row.description, row.criteria)
            db.add(Inspection(requirement_id=row.id, source="demo", commit_sha=git["sha"], data=result))
    db.commit()
