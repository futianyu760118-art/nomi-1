import copy
import json
import os
import secrets
import tempfile
import unittest
from unittest.mock import patch
from sqlalchemy import select
from pmo import create_app
from pmo.models import Inspection
from pmo.integrations import PlaneAdapter, HttpClient, IntegrationError


class IntegrationWorkflowTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.env = patch.dict(os.environ, {"DEMO_MODE": "true", "ADMIN_USERNAME": "demo", "ADMIN_PASSWORD": "demo", "WEBHOOK_SECRET": "test-hook"})
        self.env.start()
        self.app = create_app(dict(TESTING=True, SECRET_KEY=secrets.token_hex(16),
                                   DATABASE_URL="sqlite:///" + self.temp.name.replace("\\", "/") + "/test.db"))
        self.client = self.app.test_client()
        self.headers = {"X-PMO-Request": "1"}
        self.client.post("/api/auth/login", json=dict(username="demo", password="demo"), headers=self.headers)
        self.cfg = dict(planeUrl="https://plane.test", planeToken="test", workspace="team", planeProject="p",
                        gitUrl="https://git.test", gitToken="test", repository="team/repo",
                        llmUrl="https://llm.test/v1", model="test-model")
        self.client.patch("/api/settings", json=self.cfg, headers=self.headers)
        self.sha = "abc123"
        self.broken_json = False
        self.fail_page = False
        self.criteria = ["支持动态加载", "支持异常回滚"]
        self.llm_calls = 0
        self.writes = []
        self.remote_changes = {}
        self.created_item = None
        self.fail_write = False
        self.fail_relation = False
        self.git_writes = []
        self.branch_created = None
        self.mr_created = False
        self.mock = patch.object(HttpClient, "request", autospec=True, side_effect=self.http)
        self.mock.start()

    def tearDown(self):
        self.mock.stop()
        self.app.extensions["engine"].dispose()
        self.env.stop()
        self.temp.cleanup()

    def http(self, client, path, params=None, body=None, text=False, limit=None, method=None):
        if client.source == "Plane":
            prefix = "/api/v1/workspaces/team/projects/p/"
            resource = path.removeprefix(prefix)
            if body is not None:
                self.writes.append((resource, method or "POST", body))
                if self.fail_write:
                    raise IntegrationError("Plane", "写入失败", 403)
                if resource == "work-items/i21/" and method == "PATCH":
                    self.remote_changes.update(body)
                    return dict(id="i21"), {}
                if resource == "work-items/":
                    self.created_item = dict(id="i22", sequence_id=22, **body)
                    return self.created_item, {}
                if resource in ("modules/m/module-issues/", "cycles/c/cycle-issues/"):
                    if self.fail_relation:
                        raise IntegrationError("Plane", "关联失败", 403)
                    return [], {}
                raise AssertionError("Unexpected Plane write: " + resource)
            if resource == "":
                return dict(name="Live project", start_date="2026-09-01", target_date="2026-10-12"), {}
            items = {
                "states/": [dict(id="s", name="In progress", group="started"),
                            dict(id="todo", name="Todo", group="unstarted"),
                            dict(id="testing", name="Testing", group="started")],
                "members/": [dict(id="u", display_name="Alice")],
                "modules/": [dict(id="m", name="Skills")],
                "cycles/": [dict(id="c", start_date="2026-09-01", end_date="2026-10-12")],
                "modules/m/module-issues/": [dict(id="i21")],
                "cycles/c/cycle-issues/": [dict(id="membership21", issue="i21")],
            }
            if resource == "work-items/":
                if params.get("cursor"):
                    if self.fail_page:
                        raise IntegrationError("Plane", "page failed")
                    return dict(results=[], next_page_results=False), {}
                item = dict(id="i21", sequence_id=21, name="Dynamic Skill", state="s", assignees=["u"], priority="urgent",
                                          description_html="<h2>Acceptance Criteria</h2><ul><li>支持动态加载</li><li>支持异常回滚</li></ul>",
                                          target_date="2026-09-20")
                item.update(self.remote_changes)
                return dict(results=[item] + ([self.created_item] if self.created_item else []), next_page_results=True, next_cursor="p2"), {}
            if resource in items:
                return dict(results=items[resource], next_page_results=False), {}
            raise AssertionError("Unexpected Plane resource: " + resource)
        if client.source == "GitLab":
            resource = path.removeprefix("/api/v4/projects/team%2Frepo")
            mr = dict(iid=38, title="REQ-021 dynamic skills", description="Acceptance", source_branch="feat/REQ-021-skill",
                      state="opened", sha=self.sha, updated_at="2026-09-18T00:00:00Z", author=dict(name="Alice"),
                      web_url="https://git.test/team/repo/-/merge_requests/38", head_pipeline=dict(id=9, status="success"))
            if body is not None:
                self.git_writes.append((resource, body))
                if resource == "/repository/branches":
                    self.branch_created = body["branch"]
                    return dict(name=body["branch"], commit=dict(id=self.sha, message="Initial", author_name="Alice")), {}
                if resource == "/merge_requests":
                    self.mr_created = True
                    return dict(mr, source_branch=body["source_branch"], title=body["title"]), {}
                raise AssertionError("Unexpected GitLab write: " + resource)
            if resource == "":
                return dict(id=10, default_branch="main"), {}
            if resource == "/merge_requests":
                if params.get("source_branch") and not self.mr_created:
                    return [], {}
                return [mr], {}
            if resource == "/merge_requests/38":
                return mr, {}
            if resource == "/merge_requests/38/commits":
                return [dict(id=self.sha, message="REQ-021 implement", author_name="Alice")], {}
            if resource == "/repository/branches":
                return [], {}
            if resource == "/merge_requests/38/diffs":
                return [dict(new_path="src/skill.py", old_path="src/skill.py", diff="@@ -1,1 +1,2 @@\n+def load(): pass")], {}
            if resource == "/repository/files/src%2Fskill.py/raw":
                return "def load():\n    pass\n", {}
            if resource == "/pipelines/9/test_report_summary":
                return dict(total=dict(count=2, success=2, failed=0, error=0)), {}
            raise AssertionError("Unexpected GitLab resource: " + resource)
        if client.source == "LLM":
            self.llm_calls += 1
            self.assertEqual(path, "/chat/completions")
            context = json.loads(body["messages"][1]["content"])
            if "project" in context:
                return dict(choices=[dict(message=dict(content=json.dumps(dict(summary="建议优先补齐回滚验收项。", priorities=["REQ-021"]))))]), {}
            self.assertLessEqual(len(context["files"]), 20)
            result = dict(requirement_id="REQ-021", implementation_score=78, status="PARTIAL",
                          acceptance_criteria=[dict(criterion=c, status="IMPLEMENTED" if i == 0 else "MISSING", evidence=["src/skill.py:1"] if i == 0 else []) for i, c in enumerate(self.criteria)],
                          tests=dict(status="PARTIAL", summary="Missing rollback test"),
                          risks=[dict(level="HIGH", description="Rollback missing")], summary="Partial")
            return dict(choices=[dict(message=dict(content="invalid" if self.broken_json else json.dumps(result)))]), {}
        raise AssertionError("Unexpected provider")

    def import_project(self):
        response = self.client.post("/api/connections/plane", json={}, headers=self.headers)
        self.assertEqual(response.status_code, 200, response.get_json())
        self.project = response.get_json()["id"]
        return self.project

    def request(self, path):
        return self.client.post("/api" + path + "?project=" + str(self.project), json={}, headers=self.headers)

    def test_plane_git_ai_complete_flow(self):
        project = self.import_project()
        self.assertNotEqual(project, 1)
        self.assertEqual(self.request("/connections/git").status_code, 200)
        response = self.request("/requirements/REQ-021/inspect")
        self.assertEqual(response.status_code, 200, response.get_json())
        item = response.get_json()
        self.assertEqual(item["module"], "Skills")
        self.assertEqual(item["owner"], "Alice")
        self.assertEqual(item["progress"], 70)
        self.assertEqual(item["inspection"]["implementation_score"], 78)
        self.assertFalse(item["inspection"]["stale"])
        demo = self.client.get("/api/bootstrap?project=1").get_json()
        self.assertEqual(len(demo["requirements"]), 30)
        self.broken_json = True
        self.assertEqual(self.request("/requirements/REQ-021/inspect").status_code, 400)
        item = self.client.get("/api/requirements/REQ-021?project=" + str(project)).get_json()
        self.assertEqual(item["inspection"]["implementation_score"], 78)
        self.sha = "new456"
        self.assertEqual(self.request("/connections/git").status_code, 200)
        item = self.client.get("/api/requirements/REQ-021?project=" + str(project)).get_json()
        self.assertTrue(item["inspection"]["stale"])
        self.assertEqual(item["progress"], 50)

    def test_partial_plane_pagination_does_not_replace_cache(self):
        self.import_project()
        before = self.client.get("/api/bootstrap?project=" + str(self.project)).get_json()
        self.fail_page = True
        self.assertEqual(self.request("/sync").status_code, 502)
        after = self.client.get("/api/bootstrap?project=" + str(self.project)).get_json()
        self.assertEqual(before["requirements"], after["requirements"])
        self.assertEqual(before["dashboard"]["project"]["lastSync"], after["dashboard"]["project"]["lastSync"])
        self.assertEqual(after["logs"][0]["status"], "FAILED")

    def test_webhook_push_never_invokes_llm_and_same_mr_sha_is_deduplicated(self):
        self.import_project()
        payload = dict(object_kind="push", project=dict(path_with_namespace="team/repo"))
        self.assertEqual(self.client.post("/api/webhooks/gitlab", json=payload).status_code, 401)
        headers = {"X-Gitlab-Token": "test-hook"}
        self.assertEqual(self.client.post("/api/webhooks/gitlab", json=payload, headers=headers).status_code, 200)
        self.assertEqual(self.llm_calls, 0)
        payload.update(object_kind="merge_request", object_attributes=dict(iid=38))
        self.assertEqual(self.client.post("/api/webhooks/gitlab", json=payload, headers=headers).status_code, 200)
        self.assertEqual(self.llm_calls, 1)
        self.assertEqual(self.client.post("/api/webhooks/gitlab", json=payload, headers=headers).status_code, 200)
        self.assertEqual(self.llm_calls, 1)

    def test_summary_is_persisted_and_becomes_stale(self):
        self.import_project()
        self.assertEqual(self.request("/summary").status_code, 200)
        data = self.client.get("/api/bootstrap?project=" + str(self.project)).get_json()
        self.assertEqual(data["aiSummary"]["priorities"], ["REQ-021"])
        self.assertFalse(data["aiSummary"]["stale"])
        self.request("/connections/git")
        data = self.client.get("/api/bootstrap?project=" + str(self.project)).get_json()
        self.assertTrue(data["aiSummary"]["stale"])

    def test_edit_writes_plane_and_reads_authoritative_result(self):
        self.import_project()
        response = self.client.patch("/api/requirements/REQ-021?project=" + str(self.project),
                                     json=dict(title="Updated", status="TESTING", priority="P1", owner="Alice",
                                               description="A < B", criteria=["one", "two"], due="2026-10-01"),
                                     headers=self.headers)
        self.assertEqual(response.status_code, 200, response.get_json())
        item = response.get_json()
        self.assertEqual(item["title"], "Updated")
        self.assertEqual(item["status"], "TESTING")
        self.assertEqual(item["priority"], "P1")
        self.assertEqual(item["description"], "A < B")
        self.assertEqual(item["criteria"], ["one", "two"])
        path, method, body = self.writes[0]
        self.assertEqual((path, method), ("work-items/i21/", "PATCH"))
        self.assertEqual(body["priority"], "high")
        self.assertEqual(body["state"], "testing")
        self.assertEqual(body["description_html"].count("Acceptance Criteria"), 1)

    def test_create_uses_separate_module_cycle_associations(self):
        self.import_project()
        response = self.client.post("/api/requirements?project=" + str(self.project), headers=self.headers,
                                    json=dict(title="New requirement", module="Skills", week=1, priority="P0", owner="Alice"))
        self.assertEqual(response.status_code, 201, response.get_json())
        self.assertEqual(response.get_json()["id"], "REQ-022")
        self.assertEqual([w[0] for w in self.writes],
                         ["work-items/", "modules/m/module-issues/", "cycles/c/cycle-issues/"])
        self.assertNotIn("module_ids", self.writes[0][2])
        self.assertEqual(self.writes[1][2], dict(issues=["i22"]))

    def test_failed_write_preserves_cache(self):
        self.import_project()
        self.fail_write = True
        response = self.client.patch("/api/requirements/REQ-021?project=" + str(self.project),
                                     json=dict(title="Not saved"), headers=self.headers)
        self.assertEqual(response.status_code, 502)
        item = self.client.get("/api/requirements/REQ-021?project=" + str(self.project)).get_json()
        self.assertEqual(item["title"], "Dynamic Skill")

    def test_partial_create_is_not_reported_as_atomic_failure(self):
        self.import_project()
        self.fail_relation = True
        response = self.client.post("/api/requirements?project=" + str(self.project), headers=self.headers,
                                    json=dict(title="Created remotely", module="Skills"))
        self.assertEqual(response.status_code, 502)
        self.assertTrue(response.get_json()["partial"])
        self.assertIn("不要再次创建", response.get_json()["error"])
        self.assertIsNotNone(self.created_item)

    def test_write_rejects_invalid_fields_and_cross_project_settings(self):
        self.import_project()
        for body in [dict(title=""), dict(criteria="bad"), dict(week=True), dict(priority="bad"),
                     dict(start="2026-10-02", due="2026-10-01"), dict(status="BLOCKED")]:
            response = self.client.patch("/api/requirements/REQ-021?project=" + str(self.project),
                                         json=body, headers=self.headers)
            self.assertIn(response.status_code, (400, 502), response.get_json())
        self.assertEqual(self.writes, [])
        self.client.patch("/api/settings", json=dict(planeProject="other-project"), headers=self.headers)
        response = self.client.patch("/api/requirements/REQ-021?project=" + str(self.project),
                                     json=dict(title="Wrong project"), headers=self.headers)
        self.assertEqual(response.status_code, 400)
        self.assertEqual(self.writes, [])

    def test_write_requires_admin_and_demo_is_readonly(self):
        response = self.client.patch("/api/requirements/REQ-012?project=1",
                                     json=dict(title="No demo mutation"), headers=self.headers)
        self.assertEqual(response.status_code, 400)
        self.client.post("/api/auth/login", json=dict(username="member", password="member"), headers=self.headers)
        for path, method in [("/api/requirements", "POST"), ("/api/requirements/REQ-012", "PATCH"),
                             ("/api/requirements/REQ-012/branch", "POST"), ("/api/requirements/REQ-012/merge-request", "POST")]:
            self.assertEqual(self.client.open(path, method=method, json={}, headers=self.headers).status_code, 403)

    def test_branch_and_mr_created_from_requirement_and_linked(self):
        self.import_project()
        response = self.request("/requirements/REQ-021/branch")
        self.assertEqual(response.status_code, 200, response.get_json())
        branch = response.get_json()["branch"]
        self.assertEqual(self.git_writes[0][1]["ref"], "main")
        item = self.client.get("/api/requirements/REQ-021?project=" + str(self.project)).get_json()
        self.assertEqual(item["git"]["branch"], branch)
        response = self.client.post("/api/requirements/REQ-021/merge-request?project=" + str(self.project),
                                    json=dict(branch=branch), headers=self.headers)
        self.assertEqual(response.status_code, 200, response.get_json())
        self.assertEqual(response.get_json()["git"]["mr"], 38)
        self.assertTrue(self.git_writes[1][1]["title"].startswith("REQ-021"))
        self.assertEqual(self.git_writes[1][1]["target_branch"], "main")
        duplicate = self.client.post("/api/requirements/REQ-021/merge-request?project=" + str(self.project),
                                     json=dict(branch=branch), headers=self.headers)
        self.assertEqual(duplicate.status_code, 400)
        self.assertEqual(len(self.git_writes), 2)

    def test_bound_repository_cannot_be_silently_changed(self):
        self.import_project()
        self.assertEqual(self.request("/connections/git").status_code, 200)
        self.client.patch("/api/settings", json=dict(repository="wrong/repo"), headers=self.headers)
        response = self.request("/requirements/REQ-021/branch")
        self.assertEqual(response.status_code, 400)
        self.assertEqual(self.git_writes, [])
