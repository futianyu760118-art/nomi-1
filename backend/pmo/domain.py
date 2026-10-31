import math
import re
import hashlib
import json
from datetime import date, timedelta

WEIGHTS = {"P0": 5, "P1": 3, "P2": 1}
STATUSES = ("TODO", "IN_PROGRESS", "REVIEW", "TESTING", "DONE", "BLOCKED")

def requirement_fingerprint(description, criteria):
    return hashlib.sha256(json.dumps([description, criteria], ensure_ascii=False).encode()).hexdigest()


def reference_ids(text):
    return set(re.findall(r"(?<![A-Z0-9])REQ-\d+(?![A-Z0-9])", text.upper()))


def progress(item):
    if item["status"] == "DONE":
        return 100
    value = 30 if item["status"] in ("IN_PROGRESS", "REVIEW", "TESTING") else 0
    git = item.get("git") or {}
    inspection = item.get("inspection")
    if git.get("mr"):
        value = max(value, 50)
    if inspection and not inspection.get("stale"):
        if inspection["status"] in ("IMPLEMENTED", "PARTIAL") and inspection["implementation_score"] >= 70:
            value = max(value, 70)
        # A green pipeline alone is not evidence that tests exist or passed.
        if inspection["status"] in ("IMPLEMENTED", "PARTIAL") and inspection["implementation_score"] >= 70 and inspection["tests"]["status"] == "PASSED" and git.get("pipeline") == "PASSED":
            value = max(value, 90)
    if item["status"] == "BLOCKED":
        value = max(value, item.get("blockedProgress", 0))
    return min(value, 100)


def weighted_progress(items, weights=None):
    weights = weights or WEIGHTS
    denominator = sum(weights.get(item["priority"], 1) for item in items)
    if not denominator:
        return 0
    return round(sum(weights.get(item["priority"], 1) * progress(item) for item in items) / denominator)


def is_delayed(item, today):
    return bool(item.get("due") and item["due"] < today.isoformat() and item["status"] != "DONE")


def risk_rules(item, today, current_week):
    rules = []

    def add(rule, level, title, action, source="自动规则"):
        rules.append(dict(rule=rule, level=level, title=title, action=action, source=source))

    if is_delayed(item, today):
        add("DEADLINE", "HIGH", "超过计划完成日期", "确认剩余工作并在需求详情更新排期")
    if item["status"] == "BLOCKED":
        add("BLOCKED", "HIGH", "需求处于阻塞状态", "联系负责人解除依赖或记录替代方案")
    if item["status"] == "TODO" and item["priority"] == "P0" and item["week"] <= current_week:
        add("P0_TODO", "HIGH", "当前阶段 P0 需求尚未开始", "确认优先级和启动时间")
    if item["week"] == current_week and today.weekday() >= 3 and progress(item) < 50:
        add("WEEK_LOW", "MEDIUM", "本周临近结束，需求进度低于 50%", "确认本周交付范围")
    git = item.get("git") or {}
    if git.get("pipeline") == "FAILED":
        add("PIPELINE", "HIGH", "关联 Pipeline 失败", "检查失败的 Job 并重新运行", "GitLab")
    if git.get("mrState") == "opened" and git.get("updatedAt"):
        if git["updatedAt"][:10] < (today - timedelta(days=3)).isoformat():
            add("MR_STALE", "MEDIUM", "MR 超过 3 天未更新或合并", "安排评审，核实阻塞点", "GitLab")
    inspection = item.get("inspection")
    if inspection and not inspection.get("stale"):
        for entry in inspection.get("risks", []):
            if entry["level"] == "HIGH":
                add("AI_HIGH", "HIGH", entry["description"][:500], "复核代码证据并处理 AI 提示", "AI 核验")
                break
        if any(c["status"] in ("MISSING", "PARTIAL") for c in inspection["acceptance_criteria"]):
            add("AC_MISSING", "MEDIUM", "存在未覆盖的验收项", "逐项补齐验收证据", "AI 核验")
        if inspection["tests"]["status"] in ("MISSING", "PARTIAL"):
            add("TEST_MISSING", "MEDIUM", "测试证据不足", "补充关键路径及异常场景测试", "AI 核验")
    return rules


def counts(items, today):
    return {
        "total": len(items),
        "done": sum(i["status"] == "DONE" for i in items),
        "inProgress": sum(i["status"] in ("IN_PROGRESS", "REVIEW", "TESTING") for i in items),
        "todo": sum(i["status"] == "TODO" for i in items),
        "blocked": sum(i["status"] == "BLOCKED" for i in items),
        "delayed": sum(is_delayed(i, today) for i in items),
    }


def dashboard(project, items, risks, weights=None, today=None):
    today = today or date.today()
    start = date.fromisoformat(project.start_date)
    end = date.fromisoformat(project.end_date)
    total_weeks = max(1, math.ceil(((end - start).days + 1) / 7))
    current = min(total_weeks, max(1, (today - start).days // 7 + 1))
    modules = []
    for name in sorted(set(i["module"] for i in items)):
        group = [i for i in items if i["module"] == name]
        modules.append(dict(name=name, progress=weighted_progress(group, weights), **counts(group, today)))
    weeks = []
    for week in range(1, total_weeks + 1):
        group = [i for i in items if i["week"] == week]
        week_start = start + timedelta(days=(week - 1) * 7)
        weeks.append(dict(week=week, start=week_start.isoformat(),
                          end=min(end, week_start + timedelta(days=6)).isoformat(),
                          progress=weighted_progress(group, weights), **counts(group, today)))
    members = []
    for owner in sorted(set(i["owner"] for i in items)):
        members.append(dict(name=owner, **counts([i for i in items if i["owner"] == owner], today)))
    return {
        "project": {"id": project.id, "name": project.name, "stage": "Phase 1",
                    "mode": project.mode, "week": current, "weeks": total_weeks,
                    "startDate": project.start_date, "endDate": project.end_date,
                    "remainingDays": max(0, (end - today).days),
                    "progress": weighted_progress(items, weights), "lastSync": project.last_sync},
        "requirements": counts(items, today), "modules": modules, "weeks": weeks, "members": members,
        "currentWeek": counts([i for i in items if i["week"] == current], today),
        "riskSummary": {level: sum(r["level"] == level and r["status"] == "OPEN" for r in risks)
                        for level in ("HIGH", "MEDIUM", "LOW")},
    }
