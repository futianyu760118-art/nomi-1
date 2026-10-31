import copy
import json
import os
import secrets
import tempfile
import unittest
from datetime import date
from unittest.mock import patch
from sqlalchemy import select

from pmo import create_app
from pmo.domain import progress, weighted_progress, reference_ids, risk_rules, is_delayed
from pmo.inspector import parse_inspection, allowed_file
from pmo.integrations import map_plane, map_gitlab, IntegrationError, PlaneAdapter
from pmo.models import Requirement, Project, SystemSetting, Risk

# Per-run random test secret: never a real credential, never persisted in source.
TEST_SECRET = os.environ.get("PMO_TEST_SECRET") or secrets.token_hex(32)


class DomainTests(unittest.TestCase):
    def item(self, **kwargs):
        return dict(id="REQ-021", status="IN_PROGRESS", priority="P0", week=3, due="2026-09-19", **kwargs)

    def test_progress_evidence_ladder(self):
        item = self.item()
        self.assertEqual(progress(item), 30)
        item["git"] = dict(mr=38, pipeline="PASSED")
        self.assertEqual(progress(item), 50)
        item["inspection"] = dict(status="PARTIAL", implementation_score=78, tests=dict(status="PARTIAL"), stale=False)
        self.assertEqual(progress(item), 70)
        item["inspection"]["tests"]["status"] = "PASSED"
        self.assertEqual(progress(item), 90)
        item["status"] = "DONE"
        self.assertEqual(progress(item), 100)

    def test_pipeline_alone_is_not_a_test_pass(self):
        self.assertEqual(progress(self.item(git=dict(pipeline="PASSED"))), 30)

    def test_stale_inspection_excluded(self):
        item = self.item(git=dict(mr=38), inspection=dict(stale=True, implementation_score=100))
        self.assertEqual(progress(item), 50)

    def test_blocked_retains_progress(self):
        item = self.item(blockedProgress=70)
        item["status"] = "BLOCKED"
        self.assertEqual(progress(item), 70)

    def test_weighted_and_empty_progress(self):
        a, b = self.item(), self.item()
        a.update(status="DONE", priority="P0")
        b.update(status="TODO", priority="P2")
        self.assertEqual(weighted_progress([a, b]), 83)
        self.assertEqual(weighted_progress([]), 0)

    def test_exact_requirement_association(self):
        self.assertEqual(reference_ids("feat/REQ-021-loader, REQ-021: fix; REQ-0211"), {"REQ-021", "REQ-0211"})
        self.assertNotIn("REQ-021", reference_ids("REQ-0211"))
        self.assertEqual(reference_ids("feat/req-021"), {"REQ-021"})

    def test_delay_uses_real_date(self):
        item = self.item()
        self.assertFalse(is_delayed(item, date(2026, 9, 18)))
        self.assertTrue(is_delayed(item, date(2026, 9, 20)))
        item["status"] = "DONE"
        self.assertFalse(is_delayed(item, date(2026, 9, 20)))

    def test_risks(self):
        item = self.item(git=dict(pipeline="FAILED", mrState="opened", updatedAt="2026-09-01"))
        item["status"] = "BLOCKED"
        rules = {r["rule"] for r in risk_rules(item, date(2026, 9, 20), 3)}
        self.assertTrue({"BLOCKED", "DEADLINE", "PIPELINE", "MR_STALE"} <= rules)

    def test_plane_mapper(self):
        item = dict(id="external-21", sequence_id=21, name="Skill", state="s", assignees=["u"], priority="urgent",
                    description_html="<p>描述</p><h2>Acceptance Criteria</h2><ul><li>动态加载</li><li>失败回滚</li></ul>")
        result = map_plane(item, {"s": {"name": "Testing", "group": "started"}}, {"u": {"display_name": "Wu"}},
                           "Skills", 3, dict(planeUrl="https://plane.test", workspace="team", planeProject="p1"))
        self.assertEqual(result["key"], "REQ-021")
        self.assertEqual(result["status"], "TESTING")
        self.assertEqual(result["criteria"], ["动态加载", "失败回滚"])
        self.assertEqual(result["priority"], "P0")
        self.assertEqual(result["owner"], "Wu")

    def test_gitlab_mapper(self):
        result = map_gitlab(dict(iid=38, state="opened", source_branch="feat/REQ-021", head_pipeline=dict(status="failed")),
                            [dict(id="abc", message="REQ-021 fix", author_name="Wu")], "team/repo")
        self.assertEqual(result["pipeline"], "FAILED")
        self.assertEqual(result["commits"][0]["sha"], "abc")

    def test_ai_parser(self):
        result = dict(requirement_id="REQ-021", implementation_score=78, status="PARTIAL",
                      acceptance_criteria=[dict(criterion="load", status="IMPLEMENTED", evidence=["app.py:1"])],
                      risks=[], tests=dict(status="PARTIAL", summary="No report"), summary="Partial")
        self.assertEqual(parse_inspection(json.dumps(result), "REQ-021", ["load"]), result)
        with self.assertRaises(ValueError):
            parse_inspection(json.dumps(result), "REQ-022", ["load"])
        with self.assertRaises(ValueError):
            parse_inspection(json.dumps(result), "REQ-021", ["load", "rollback"])
        result["implementation_score"] = True
        with self.assertRaises(ValueError):
            parse_inspection(json.dumps(result), "REQ-021", ["load"])
        with self.assertRaises(ValueError):
            parse_inspection("not json", "REQ-021", [])

    def test_sensitive_files_excluded(self):
        for path in [".env", ".env.production", "config/private_key.pem", "secrets.json"]:
            self.assertFalse(allowed_file(path))
        self.assertTrue(allowed_file("src/main.py"))


class ApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        cls.env = patch.dict(os.environ, {"DEMO_MODE": "true", "ADMIN_USERNAME": "demo", "ADMIN_PASSWORD": "demo", "MEMBER_PASSWORD": "member"})
        cls.env.start()
        cls.url = "sqlite:///" + cls.temp.name.replace("\\", "/") + "/test.db"
        cls.app = create_app(dict(TESTING=True, DATABASE_URL=cls.url, SECRET_KEY=TEST_SECRET))

    @classmethod
    def tearDownClass(cls):
        cls.app.extensions["engine"].dispose()
        cls.env.stop()
        cls.temp.cleanup()

    def setUp(self):
        self.client = self.app.test_client()
        self.headers = {"X-PMO-Request": "1"}
        self.login()

    def login(self, username="demo", password="demo"):
        return self.client.post("/api/auth/login", json=dict(username=username, password=password), headers=self.headers)

    def test_auth_and_csrf(self):
        anon = self.app.test_client()
        self.assertEqual(anon.get("/api/bootstrap").status_code, 401)
        self.assertEqual(anon.post("/api/auth/login", json=dict(username="demo", password="demo")).status_code, 403)
        self.assertEqual(self.login(password="wrong").status_code, 401)

    def test_30_requirements_and_consistent_counts(self):
        data = self.client.get("/api/bootstrap?project=1").get_json()
        self.assertEqual(len(data["requirements"]), 30)
        self.assertEqual(data["dashboard"]["requirements"]["total"], 30)
        self.assertEqual(sum(w["total"] for w in data["dashboard"]["weeks"]), 30)
        self.assertEqual(sum(m["total"] for m in data["dashboard"]["modules"]), 30)
        self.assertEqual(data["dashboard"]["requirements"]["done"], sum(r["status"] == "DONE" for r in data["requirements"]))

    def test_detail_is_requirement_specific(self):
        a = self.client.get("/api/requirements/REQ-001?project=1").get_json()
        b = self.client.get("/api/requirements/REQ-012?project=1").get_json()
        self.assertNotEqual(a["criteria"], b["criteria"])
        self.assertNotEqual(a["inspection"]["acceptance_criteria"], b["inspection"]["acceptance_criteria"])
        self.assertEqual(self.client.get("/api/requirements/REQ-999?project=1").status_code, 404)

    def test_member_readonly(self):
        self.login("member", "member")
        self.assertEqual(self.client.get("/api/bootstrap").status_code, 200)
        self.assertEqual(self.client.get("/api/settings").status_code, 403)
        for path in ["/api/sync", "/api/risks/scan", "/api/connections/plane", "/api/requirements/REQ-012/inspect"]:
            self.assertEqual(self.client.post(path, json={}, headers=self.headers).status_code, 403)

    def test_settings_encrypt_and_redact_secrets(self):
        result = self.client.patch("/api/settings", json=dict(planeToken="secret-example"), headers=self.headers)
        self.assertEqual(result.status_code, 200)
        self.assertNotIn("secret-example", result.get_data(as_text=True))
        with self.app.extensions["sessions"]() as db:
            row = db.get(SystemSetting, "integrations")
            self.assertNotIn("secret-example", json.dumps(row.data))
        self.assertTrue(result.get_json()["planeTokenConfigured"])
        self.assertEqual(self.client.patch("/api/settings", json=dict(syncInterval=0), headers=self.headers).status_code, 400)

    def test_demo_refresh_and_risk_idempotence(self):
        first = self.client.get("/api/bootstrap").get_json()
        result = self.client.post("/api/sync", json={}, headers=self.headers)
        self.assertEqual(result.status_code, 200)
        self.assertEqual(first["dashboard"]["project"]["progress"], result.get_json()["dashboard"]["project"]["progress"])
        self.assertEqual(len(first["risks"]), len(result.get_json()["risks"]))

    def test_demo_cannot_send_code_to_llm(self):
        result = self.client.post("/api/requirements/REQ-012/inspect", json={}, headers=self.headers)
        self.assertEqual(result.status_code, 400)

    def test_offline_plane_preserves_demo(self):
        before = self.client.get("/api/bootstrap").get_json()
        with patch("pmo.services.PlaneAdapter.fetch", side_effect=IntegrationError("Plane", "offline")):
            with patch("pmo.services.PlaneAdapter.__init__", return_value=None):
                result = self.client.post("/api/connections/plane", json={}, headers=self.headers)
        self.assertEqual(result.status_code, 502)
        after = self.client.get("/api/bootstrap").get_json()
        self.assertEqual(before["requirements"], after["requirements"])

    def test_risk_acknowledge(self):
        risks = self.client.get("/api/risks").get_json()["items"]
        self.assertTrue(risks)
        result = self.client.patch("/api/risks/{}".format(risks[0]["id"]), json=dict(status="ACKNOWLEDGED"), headers=self.headers)
        self.assertEqual(result.status_code, 200)
        self.client.post("/api/risks/scan", json={}, headers=self.headers)
        updated = self.client.get("/api/risks").get_json()["items"]
        self.assertEqual(next(r for r in updated if r["id"] == risks[0]["id"])["status"], "ACKNOWLEDGED")

    def test_manual_risk_survives_scan_and_can_be_closed(self):
        response = self.client.post("/api/risks?project=1", json=dict(requirementId="REQ-012", level="LOW", title="人工依赖风险", action="确认外部交付日期"), headers=self.headers)
        self.assertEqual(response.status_code, 201)
        rid = response.get_json()["id"]
        self.client.post("/api/risks/scan", json={}, headers=self.headers)
        risks = self.client.get("/api/risks").get_json()["items"]
        self.assertEqual(next(r for r in risks if r["id"] == rid)["status"], "OPEN")
        self.client.patch("/api/risks/{}".format(rid), json=dict(status="RESOLVED"), headers=self.headers)
        risks = self.client.get("/api/risks").get_json()["items"]
        self.assertEqual(next(r for r in risks if r["id"] == rid)["status"], "RESOLVED")

    def test_local_project_lifecycle(self):
        self.login("member", "member")
        self.assertEqual(self.client.post("/api/projects", json=dict(name="X", start="2026-09-21", weeks=4), headers=self.headers).status_code, 403)
        self.login()
        result = self.client.post("/api/projects", json=dict(name="本地看板项目", start="2026-09-21", weeks=4), headers=self.headers)
        self.assertEqual(result.status_code, 201)
        created = result.get_json()
        pid = created["id"]
        self.assertEqual(created["mode"], "local")
        self.assertEqual(created["weeks"], 4)
        self.assertEqual(created["requirements"]["total"], 0)

        items = self.client.get("/api/projects").get_json()["items"]
        overview = next(i for i in items if i["id"] == pid)
        self.assertIn("progress", overview)
        self.assertIn("riskSummary", overview)

        row = self.client.post("/api/requirements?project={}".format(pid), json=dict(
            title="看板卡片", criteria=["可拖拽改状态"], owner="张三", module="看板", status="IN_PROGRESS", week=2), headers=self.headers)
        self.assertEqual(row.status_code, 201)
        self.assertEqual(row.get_json()["id"], "REQ-001")
        self.assertEqual(row.get_json()["status"], "IN_PROGRESS")

        moved = self.client.patch("/api/requirements/REQ-001?project={}".format(pid), json=dict(status="DONE"), headers=self.headers)
        self.assertEqual(moved.status_code, 200)
        self.assertEqual(moved.get_json()["status"], "DONE")

        options = self.client.get("/api/management/options?project={}".format(pid), headers=self.headers).get_json()
        self.assertIn("张三", options["owners"])
        self.assertIn("看板", options["modules"])
        self.assertEqual(len(options["weeks"]), 4)

        self.assertEqual(self.client.post("/api/sync?project={}".format(pid), json={}, headers=self.headers).status_code, 200)
        self.assertEqual(self.client.post("/api/requirements/REQ-001/branch?project={}".format(pid), json=dict(name="feat/req-001-dev"), headers=self.headers).status_code, 400)
        self.assertEqual(self.client.post("/api/requirements/REQ-001/inspect?project={}".format(pid), json={}, headers=self.headers).status_code, 400)

        data = self.client.get("/api/bootstrap?project={}".format(pid)).get_json()
        self.assertEqual(data["requirements"][0]["status"], "DONE")
        self.assertEqual(data["dashboard"]["requirements"]["done"], 1)

    def test_local_project_validation_and_rename(self):
        for body in (dict(name="", start="2026-09-21", weeks=4), dict(name="X", start="2026-09-21", weeks=0),
                     dict(name="X", weeks=4), dict(name="X", start="21-09-2026", weeks=4)):
            self.assertEqual(self.client.post("/api/projects", json=body, headers=self.headers).status_code, 400)
        result = self.client.post("/api/projects", json=dict(name="校验项目", start="2026-09-21", weeks=2), headers=self.headers)
        pid = result.get_json()["id"]
        renamed = self.client.patch("/api/projects/{}".format(pid), json=dict(name="校验项目改名"), headers=self.headers)
        self.assertEqual(renamed.status_code, 200)
        self.assertEqual(renamed.get_json()["name"], "校验项目改名")
        self.assertEqual(self.client.patch("/api/projects/1", json=dict(name="演示不可改"), headers=self.headers).status_code, 400)

    def test_migration_and_seed_are_idempotent(self):
        second = create_app(dict(TESTING=True, DATABASE_URL=self.url, SECRET_KEY=TEST_SECRET))
        try:
            with second.extensions["sessions"]() as db:
                demo = db.scalar(select(Project).where(Project.mode == "demo"))
                self.assertEqual(len(db.scalars(select(Requirement).where(Requirement.project_id == demo.id)).all()), 30)
        finally:
            second.extensions["engine"].dispose()


if __name__ == "__main__":
    unittest.main()
