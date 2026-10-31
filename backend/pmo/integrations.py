"""Provider boundaries for reads and explicit user-authorized workflow writes."""
import json
import os
import re
import socket
import ipaddress
from abc import ABC, abstractmethod
from datetime import date, timedelta
from html.parser import HTMLParser
from urllib.parse import quote, urlsplit

import requests
from .domain import reference_ids


class IntegrationError(Exception):
    def __init__(self, source, message, status=None):
        super().__init__(message)
        self.source, self.status = source, status


class PartialWriteError(IntegrationError):
    def __init__(self, message):
        super().__init__("Plane", message)


class HttpClient:
    def __init__(self, source, base, headers):
        if not base:
            raise IntegrationError(source, "服务地址未配置")
        # Defense in depth next to the settings-level validation: only plain
        # HTTP(S) URLs without embedded credentials may ever be requested.
        parsed = urlsplit(base)
        if parsed.scheme not in ("http", "https") or not parsed.hostname or parsed.username or parsed.password:
            raise IntegrationError(source, "服务地址必须是有效的 HTTP(S) URL")
        self.source, self.base, self.headers = source, base.rstrip("/"), headers

    def _assert_target(self, url):
        # SSRF guard: an explicit internal-host allowlist (the bundled engine
        # and self-hosted GitLab/LLM run on private addresses, set via
        # PMO_INTERNAL_TARGETS), and every other hostname must resolve to a
        # globally routable address — private/loopback/link-local targets are
        # rejected. Combined with the constructor checks and
        # allow_redirects=False this closes the request-side surface.
        parsed = urlsplit(url)
        host = (parsed.hostname or "").lower()
        allowed_internal = {h.strip().lower() for h in os.getenv("PMO_INTERNAL_TARGETS", "").split(",") if h.strip()}
        if host in allowed_internal:
            return
        try:
            infos = socket.getaddrinfo(host, parsed.port or (443 if parsed.scheme == "https" else 80), proto=socket.IPPROTO_TCP)
        except OSError:
            raise IntegrationError(self.source, "服务地址无法解析，请检查配置")
        for info in infos:
            ip = ipaddress.ip_address(info[4][0])
            if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved or ip.is_multicast:
                raise IntegrationError(self.source, "内网地址不在允许清单（PMO_INTERNAL_TARGETS）内")

    def request(self, path, params=None, body=None, text=False, limit=8_000_000, method=None):
        try:
            self._assert_target(self.base + path)
            with requests.request(method or ("POST" if body is not None else "GET"), self.base + path,
                                  headers=self.headers, params=params, json=body,
                                  timeout=(5, 60), allow_redirects=False, stream=True) as response:
                if not 200 <= response.status_code < 300:
                    raise IntegrationError(self.source, "{} 返回 HTTP {}".format(self.source, response.status_code), response.status_code)
                chunks, size = [], 0
                for chunk in response.iter_content(8192):
                    size += len(chunk)
                    if size > limit:
                        raise IntegrationError(self.source, "响应超过安全大小限制")
                    chunks.append(chunk)
                content = b"".join(chunks).decode("utf-8", errors="replace")
                return (content if text else json.loads(content) if content.strip() else None), dict(response.headers)
        except (requests.RequestException, ValueError) as exc:
            # Never persist raw response bodies, request URLs, or tokens in failure logs.
            suffix = "；写入结果未确认，请刷新核对，勿重复创建" if body is not None or method in ("PATCH", "DELETE", "PUT") else ""
            raise IntegrationError(self.source, "{} 连接失败或响应格式无效{}".format(self.source, suffix)) from exc


class PlainText(HTMLParser):
    def __init__(self):
        super().__init__()
        self.parts = []

    def handle_starttag(self, tag, attrs):
        if tag in ("p", "li", "br", "div", "h1", "h2", "h3"):
            self.parts.append("\n")

    def handle_data(self, data):
        self.parts.append(data)


def description_text(value):
    parser = PlainText()
    parser.feed(value or "")
    return "\n".join(s.strip() for s in "".join(parser.parts).splitlines() if s.strip())


def plane_status(state):
    name = state.get("name", "").lower()
    if any(s in name for s in ("block", "阻塞")):
        return "BLOCKED"
    if any(s in name for s in ("review", "待检查", "评审")):
        return "REVIEW"
    if any(s in name for s in ("testing", "测试")):
        return "TESTING"
    return {"completed": "DONE", "started": "IN_PROGRESS", "unstarted": "TODO", "backlog": "TODO"}.get(state.get("group"), "TODO")


def map_plane(item, states, members, module_name, week, settings):
    sequence = int(item["sequence_id"])
    state = item.get("state") or {}
    state = state if isinstance(state, dict) else states.get(state, {})
    owners = []
    for entry in item.get("assignees", []):
        member = entry if isinstance(entry, dict) else members.get(entry, {})
        owners.append(member.get("display_name") or member.get("first_name") or "未分配")
    full_description = description_text(item.get("description_html") or item.get("description_stripped") or item.get("description", ""))
    criteria, description_lines, in_criteria = [], [], False
    for line in full_description.splitlines():
        if re.search(r"acceptance criteria|验收标准|验收条件", line, re.I):
            in_criteria = True
            continue
        if in_criteria and line.strip():
            criteria.append(line.lstrip("-* ").strip())
        elif not in_criteria:
            description_lines.append(line)
    return dict(key="REQ-{:03d}".format(sequence), external_id=item["id"], title=item["name"],
                description="\n".join(description_lines), criteria=criteria, module=module_name or "未分组", owner="、".join(owners) or "未分配",
                priority={"urgent": "P0", "high": "P1"}.get(item.get("priority"), "P2"),
                status=plane_status(state), week=week,
                start=item.get("start_date"), due=item.get("target_date"),
                plane_url="{}/{}/projects/{}/issues/{}".format(settings["planeUrl"].rstrip("/"),
                          quote(settings["workspace"], safe=""), quote(settings["planeProject"], safe=""), quote(item["id"], safe="")),
                active=0 if state.get("group") == "cancelled" else 1)


class PlaneAdapter:
    def __init__(self, settings):
        self.settings = settings
        if not all(settings.get(k) for k in ("planeUrl", "planeToken", "workspace", "planeProject")):
            raise IntegrationError("Plane", "请先配置 Plane URL、Token、Workspace 和 Project ID")
        # PLANE_SERVER_URL lets a containerized backend reach Plane over the docker
        # network while plane_url links keep the browser-facing address.
        api_base = os.getenv("PLANE_SERVER_URL") or settings["planeUrl"]
        self.http = HttpClient("Plane", api_base, {"X-API-Key": settings["planeToken"]})
        self.path = "/api/v1/workspaces/{}/projects/{}/".format(quote(settings["workspace"], safe=""), quote(settings["planeProject"], safe=""))

    def list(self, path):
        items, cursor, seen = [], None, set()
        for _ in range(100):
            data, _headers = self.http.request(self.path + path, {"per_page": 100, **({"cursor": cursor} if cursor else {})})
            if isinstance(data, list):
                return items + data
            if not isinstance(data, dict) or not isinstance(data.get("results"), list):
                raise IntegrationError("Plane", "无法识别分页响应，未替换现有缓存")
            items.extend(data["results"])
            if not data.get("next_page_results"):
                return items
            cursor = data.get("next_cursor")
            if not cursor or cursor in seen:
                raise IntegrationError("Plane", "分页游标无效，未替换现有缓存")
            seen.add(cursor)
        raise IntegrationError("Plane", "分页超过上限，未替换现有缓存")

    def work_items(self, prefix=""):
        try:
            return self.list(prefix + "work-items/")
        except IntegrationError as exc:
            if exc.status != 404:
                raise
            return self.list(prefix + "issues/")

    def fetch(self):
        project, _ = self.http.request(self.path)
        states = {s["id"]: s for s in self.list("states/")}
        members = {}
        for member in self.list("members/"):
            member = member.get("member", member)
            members[member["id"]] = member
        modules, cycles = self.list("modules/"), self.list("cycles/")
        module_map, cycle_map = {}, {}
        for module in modules:
            for item in self.list("modules/{}/module-issues/".format(module["id"])):
                related = item.get("issue") or item.get("work_item") or item["id"]
                module_map[related["id"] if isinstance(related, dict) else related] = module["name"]
        cycles.sort(key=lambda c: c.get("start_date") or "9999")
        for index, cycle in enumerate(cycles):
            for item in self.list("cycles/{}/cycle-issues/".format(cycle["id"])):
                related = item.get("issue") or item.get("work_item") or item["id"]
                cycle_map[related["id"] if isinstance(related, dict) else related] = index + 1
        items = self.work_items()
        start = (project.get("start_date") or next((c["start_date"] for c in cycles if c.get("start_date")), date.today().isoformat()))[:10]
        end = (project.get("target_date") or next((c["end_date"] for c in reversed(cycles) if c.get("end_date")), (date.fromisoformat(start) + timedelta(days=41)).isoformat()))[:10]
        rows = [map_plane(item, states, members, module_map.get(item["id"]), cycle_map.get(item["id"], 1), self.settings) for item in items]
        if len(set(row["key"] for row in rows)) != len(rows):
            raise IntegrationError("Plane", "需求编号重复，未替换现有缓存")
        return dict(name=project["name"], start=start, end=max(start, end), rows=rows,
                    modules=modules, cycles=cycles, members=list(members.values()), states=list(states.values()))

    def _catalog(self):
        states = self.list("states/")
        members = self.list("members/")
        modules = self.list("modules/")
        cycles = self.list("cycles/")
        members = [member.get("member", member) for member in members]
        cycles.sort(key=lambda cycle: cycle.get("start_date") or "9999")
        return states, members, modules, cycles

    @staticmethod
    def _state_for(status, states):
        for state in states:
            if state.get("group") != "cancelled" and plane_status(state) == status:
                return state.get("id")
        raise IntegrationError("Plane", "找不到与 {} 对应的状态".format(status))

    @staticmethod
    def _member_for(owner, members):
        if not owner or owner == "未分配":
            return None
        owner = owner.strip()
        matches = [member for member in members if (member.get("display_name") or member.get("first_name")) == owner]
        if len(matches) == 1:
            return matches[0]["id"]
        if len(matches) > 1:
            raise ValueError("存在同名负责人，不能确定人员，请先在 Plane 中区分显示名称")
        raise IntegrationError("Plane", "找不到负责人 {}".format(owner))

    def _write(self, remote_id, body):
        path = "work-items/{}/".format(quote(str(remote_id), safe=""))
        try:
            data, _ = self.http.request(self.path + path, body=body, method="PATCH")
            return data
        except IntegrationError as exc:
            if exc.status != 404:
                raise
            return self.http.request(self.path + "issues/{}/".format(quote(str(remote_id), safe="")),
                                     body=body, method="PATCH")[0]

    def _write_payload(self, changes):
        states, members, modules, cycles = self._catalog()
        body, relations = {}, []
        if "title" in changes:
            body["name"] = changes["title"].strip()
        if "description" in changes:
            body["description_html"] = changes["description"]
        if "status" in changes:
            body["state"] = self._state_for(changes["status"], states)
        if "priority" in changes:
            body["priority"] = {"P0": "urgent", "P1": "high", "P2": "medium"}[changes["priority"]]
        if "owner" in changes:
            body["assignees"] = [self._member_for(owner, members) for owner in changes["owner"].split("、")
                                 if owner.strip() and owner != "未分配"]
        if "start" in changes:
            body["start_date"] = changes["start"] or None
        if "due" in changes:
            body["target_date"] = changes["due"] or None
        if "module" in changes:
            module = next((item for item in modules if item.get("name") == changes["module"]), None)
            if not module:
                raise IntegrationError("Plane", "找不到模块 {}".format(changes["module"]))
            relations.append("modules/{}/module-issues/".format(quote(str(module["id"]), safe="")))
        if "week" in changes:
            index = int(changes["week"]) - 1
            if index < 0 or index >= len(cycles):
                raise IntegrationError("Plane", "找不到 Week {}".format(changes["week"]))
            relations.append("cycles/{}/cycle-issues/".format(quote(str(cycles[index]["id"]), safe="")))
        return body, relations

    def _assign(self, remote_id, relations):
        for path in relations:
            self.http.request(self.path + path, body={"issues": [remote_id]})

    def update_item(self, remote_id, changes):
        body, relations = self._write_payload(changes)
        if not body and not relations:
            raise ValueError("没有可更新的需求字段")
        applied = False
        try:
            result = self._write(remote_id, body) if body else {"id": remote_id}
            applied = bool(body)
            for path in relations:
                self._assign(remote_id, [path])
                applied = True
            return result
        except IntegrationError as exc:
            if applied:
                raise PartialWriteError("需求部分字段已写入 Plane，模块或周期关联未完成。请刷新核对后仅重试未完成字段。") from exc
            raise

    def create_item(self, changes):
        body, relations = self._write_payload(changes)
        try:
            data, _ = self.http.request(self.path + "work-items/", body=body)
        except IntegrationError as exc:
            if exc.status != 404:
                raise
            data = self.http.request(self.path + "issues/", body=body)[0]
        try:
            if not isinstance(data, dict) or not data.get("id"):
                raise IntegrationError("Plane", "创建响应缺少需求 ID")
            self._assign(data["id"], relations)
        except IntegrationError as exc:
            raise PartialWriteError("需求已在 Plane 创建，关联未完成。请刷新查找新需求，不要再次创建。") from exc
        return data


class GitProvider(ABC):
    @abstractmethod
    def get_repository(self): ...
    @abstractmethod
    def get_branch(self, name): ...
    @abstractmethod
    def get_commits(self, ref): ...
    @abstractmethod
    def get_merge_request(self, iid): ...
    @abstractmethod
    def get_diff(self, iid): ...
    @abstractmethod
    def get_file(self, path, ref): ...
    @abstractmethod
    def get_pipeline_status(self, iid): ...
    @abstractmethod
    def search_requirement_reference(self, key): ...


def map_gitlab(mr, commits, repository):
    pipeline = (mr.get("head_pipeline") or {}).get("status", "")
    return dict(repository=repository, branch=mr.get("source_branch"), mr=mr["iid"], mrState=mr["state"],
                pipeline={"success": "PASSED", "failed": "FAILED"}.get(pipeline, "RUNNING" if pipeline in ("running", "pending") else "UNKNOWN"),
                sha=mr.get("sha") or (mr.get("diff_refs") or {}).get("head_sha"), updatedAt=mr.get("updated_at"),
                pipelineId=(mr.get("head_pipeline") or {}).get("id"),
                author=(mr.get("author") or {}).get("name", ""), url=mr.get("web_url"), source="gitlab", manual=False,
                commits=[dict(sha=c["id"], message=c.get("message", ""), author=c.get("author_name", "")) for c in commits])


class GitLabProvider(GitProvider):
    def __init__(self, settings):
        if settings.get("gitProvider") != "gitlab":
            raise IntegrationError("GitLab", "GitHub / Gitea 尚未实现，可通过 GitProvider 扩展")
        if not all(settings.get(k) for k in ("gitUrl", "gitToken", "repository")):
            raise IntegrationError("GitLab", "请先配置 Git URL、Token 和 Repository")
        self.repository = settings["repository"]
        self.http = HttpClient("GitLab", settings["gitUrl"], {"PRIVATE-TOKEN": settings["gitToken"]})
        self.path = "/api/v4/projects/" + quote(self.repository, safe="")

    def get(self, path, params=None, text=False, limit=8_000_000):
        return self.http.request(self.path + path, params, text=text, limit=limit)[0]

    def list(self, path, params=None):
        result = []
        for page in range(1, 101):
            data, headers = self.http.request(self.path + path, {**(params or {}), "per_page": 100, "page": page})
            if not isinstance(data, list):
                raise IntegrationError("GitLab", "分页返回格式无效")
            result.extend(data)
            if not headers.get("X-Next-Page") and len(data) < 100:
                return result
        raise IntegrationError("GitLab", "分页超过安全上限，未替换现有缓存")

    def get_repository(self):
        return self.get("")

    def get_branch(self, name):
        return self.get("/repository/branches/" + quote(name, safe=""))

    def get_commits(self, ref):
        return self.list("/repository/commits", {"ref_name": ref})

    def get_merge_request(self, iid):
        return self.get("/merge_requests/" + str(int(iid)))

    def get_diff(self, iid):
        return self.list("/merge_requests/{}/diffs".format(int(iid)))

    def get_file(self, path, ref):
        return self.get("/repository/files/{}/raw".format(quote(path, safe="")), {"ref": ref}, text=True, limit=500_000)

    def get_pipeline_status(self, iid):
        return self.get_merge_request(iid).get("head_pipeline")

    def get_test_report(self, pipeline_id):
        if not pipeline_id:
            return None
        try:
            report = self.get("/pipelines/{}/test_report_summary".format(int(pipeline_id)))
            return report.get("total")
        except IntegrationError as exc:
            if exc.status in (403, 404):
                return None
            raise

    def create_branch(self, name, ref=None):
        repository = self.get_repository()
        body = {"branch": name, "ref": ref or repository.get("default_branch") or "main"}
        data, _ = self.http.request(self.path + "/repository/branches", body=body)
        return data

    def create_merge_request(self, source_branch, title, description="", target_branch=None):
        repository = self.get_repository()
        target = target_branch or repository.get("default_branch") or "main"
        existing = self.list("/merge_requests", {"source_branch": source_branch, "target_branch": target, "state": "opened", "scope": "all"})
        if existing:
            return self.mr_link(existing[0]["iid"])
        body = {
            "source_branch": source_branch,
            "target_branch": target,
            "title": title,
            "description": description,
        }
        data, _ = self.http.request(self.path + "/merge_requests", body=body)
        return map_gitlab(data, [], self.repository)

    def mr_link(self, iid):
        mr = self.get_merge_request(iid)
        commits = self.list("/merge_requests/{}/commits".format(int(iid)))
        return map_gitlab(mr, commits, self.repository)

    def search_requirement_reference(self, key):
        # Branch/commit association without an MR remains visible but does not grant 50% progress.
        mrs = self.list("/merge_requests", {"scope": "all", "state": "all", "order_by": "updated_at", "sort": "desc"})
        for mr in mrs:
            text = " ".join(str(mr.get(k) or "") for k in ("title", "description", "source_branch"))
            commits = self.list("/merge_requests/{}/commits".format(mr["iid"]))
            text += " " + " ".join(c.get("message", "") for c in commits)
            if key in reference_ids(text):
                return map_gitlab(self.get_merge_request(mr["iid"]), commits, self.repository)
        for branch in self.list("/repository/branches", {"search": key}):
            commit = branch.get("commit") or {}
            if key in reference_ids(branch["name"] + " " + commit.get("message", "")):
                return dict(repository=self.repository, branch=branch["name"], mr=None, mrState=None, pipeline="UNKNOWN",
                            sha=commit.get("id"), author=commit.get("author_name"), updatedAt=commit.get("committed_date"),
                            url=branch.get("web_url"), commits=[dict(sha=commit.get("id", ""), message=commit.get("message", ""), author=commit.get("author_name", ""))],
                            source="gitlab", manual=False)
        return None
