import concurrent.futures
import io
import json
import os
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch
import urllib.error
import urllib.request
import zipfile

from workbench.recipes import TYPES, generation_prompt
from workbench.runner import invoke, run_job, validate_result
from workbench.server import make_server
from workbench.store import Problem, Store


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.store = Store(self.root / "records.sqlite3")
        self.project = self.store.create_project("company_a", {"product_name": "内部内容服务", "facts": [{"text": "本轮制作文章与视频脚本", "source": "用户提供任务要求"}]})

    def tearDown(self):
        self.tmp.cleanup()

    def job(self, **kwargs):
        return self.store.create_job("company_a", self.project["id"], {"content_type": "article", "topic": "如何核对内容产物", **kwargs})

    def draft(self):
        j = self.job()
        self.store.prepare("company_a", j["id"])
        self.store.claim("company_a", j["id"])
        return self.store.finish("company_a", j["id"], {"content.md": "实际草稿"}, [])


class StoreTests(Base):
    def test_persistent_restart(self):
        j = self.job()
        self.store.prepare("company_a", j["id"])
        restarted = Store(self.root / "records.sqlite3")
        self.assertEqual(restarted.job("company_a", j["id"])["state"], "brief_ready")
        self.assertEqual(restarted.project("company_a", self.project["id"])["facts"][0]["source"], "用户提供任务要求")

    def test_tenant_read_isolation(self):
        j = self.job()
        self.assertEqual(self.store.projects("company_b"), [])
        for fn in [lambda: self.store.project("company_b", self.project["id"]), lambda: self.store.job("company_b", j["id"]), lambda: self.store.export("company_b", j["id"]), lambda: self.store.events("company_b", j["id"])]:
            with self.assertRaises(Problem): fn()

    def test_cross_project_account_denied(self):
        other = self.store.create_project("company_a", {"product_name": "另一个项目"})
        account = self.store.create_account("company_a", other["id"], {"platform": "wechat", "external_id": "id1", "display_name": "账号"})
        with self.assertRaises(Problem): self.job(account_id=account["id"])

    def test_account_platform_mismatch(self):
        account = self.store.create_account("company_a", self.project["id"], {"platform": "wechat", "external_id": "id1", "display_name": "账号"})
        with self.assertRaises(Problem): self.job(account_id=account["id"], platform="toutiao")

    def test_platform_type_mismatch(self):
        with self.assertRaises(Problem): self.job(content_type="music", platform="wechat")

    def test_idempotent_same_payload(self):
        a = self.job(idempotency_key="same")
        b = self.job(idempotency_key="same")
        self.assertEqual(a["id"], b["id"])

    def test_idempotency_conflict(self):
        self.job(idempotency_key="same")
        with self.assertRaises(Problem) as context: self.job(idempotency_key="same", topic="different")
        self.assertEqual(context.exception.status, 409)

    def test_concurrent_create_only_one(self):
        with concurrent.futures.ThreadPoolExecutor(max_workers=6) as pool:
            result = list(pool.map(lambda _: self.job(idempotency_key="concurrent")["id"], range(6)))
        self.assertEqual(len(set(result)), 1)

    def test_concurrent_claim_only_one(self):
        j = self.job(); self.store.prepare("company_a", j["id"])
        def claim(_):
            try: self.store.claim("company_a", j["id"]); return True
            except Problem: return False
        with concurrent.futures.ThreadPoolExecutor(max_workers=6) as pool:
            self.assertEqual(sum(pool.map(claim, range(6))), 1)

    def test_illegal_state_transition(self):
        j = self.job()
        with self.assertRaises(Problem): self.store.claim("company_a", j["id"])
        with self.assertRaises(Problem): self.store.check("company_a", j["id"], dict.fromkeys(["facts", "rights", "format", "ai_label"], True))

    def test_all_recipes_are_briefs(self):
        for kind in TYPES:
            j = self.job(content_type=kind)
            result = self.store.prepare("company_a", j["id"])
            self.assertIn("不是已经生成", result["artifacts"]["brief.md"])
            self.assertEqual(result["state"], "brief_ready")
            self.assertEqual(result["publish_status"], "not_connected")

    def test_review_requires_all_true_booleans(self):
        j = self.draft()
        for checks in [{}, {"facts": True}, dict.fromkeys(["facts", "rights", "format", "ai_label"], "true")]:
            with self.assertRaises(Problem): self.store.check("company_a", j["id"], checks)
        result = self.store.check("company_a", j["id"], dict.fromkeys(["facts", "rights", "format", "ai_label"], True))
        self.assertEqual(result["state"], "checked")
        self.assertEqual(result["checks"]["method"], "manual")

    def test_publish_never_fakes_success(self):
        j = self.draft()
        checked = self.store.check("company_a", j["id"], dict.fromkeys(["facts", "rights", "format", "ai_label"], True))
        blocked = self.store.request_publish("company_a", checked["id"])
        self.assertEqual(blocked["state"], "blocked")
        self.assertEqual(blocked["publish_status"], "not_connected")

    def test_publish_without_review_denied(self):
        j = self.job()
        with self.assertRaises(Problem): self.store.request_publish("company_a", j["id"])

    def test_interruption_marks_unknown_no_retry(self):
        j = self.job(); self.store.prepare("company_a", j["id"]); self.store.claim("company_a", j["id"])
        self.assertEqual(self.store.recover_interrupted(), 1)
        self.assertEqual(self.store.job("company_a", j["id"])["state"], "unknown")
        self.assertEqual(self.store.recover_interrupted(), 0)

    def test_export_scoped_no_database_or_accounts(self):
        j = self.job(); self.store.prepare("company_a", j["id"])
        self.store.create_project("company_b", {"product_name": "别的企业秘密产品"})
        with zipfile.ZipFile(io.BytesIO(self.store.export("company_a", j["id"]))) as z:
            self.assertEqual(set(z.namelist()), {"brief.md", "manifest.json", "delivery.json"})
            self.assertNotIn("别的企业秘密产品", "".join(z.read(n).decode() for n in z.namelist()))

    def test_identifier_traversal_and_sql(self):
        for value in ["../secret", "a' OR 1=1", "", "x"*81]:
            with self.assertRaises(Problem): self.store.projects(value)

    def test_invalid_budget(self):
        for value in [True, -1, float("nan"), float("inf"), "1"]:
            with self.assertRaises(Problem): self.job(budget_cny=value)

    def test_fact_requires_source(self):
        with self.assertRaises(Problem): self.store.create_project("company_a", {"product_name": "产品", "facts": [{"text": "事实"}]})


class RunnerTests(Base):
    def fake(self, body):
        path = self.root / "fake_codex"
        path.write_text("#!/usr/bin/env python3\n" + body, encoding="utf-8")
        path.chmod(0o700)
        return str(path)

    def fixture(self, kind="article"):
        j = self.job(content_type=kind)
        _, required = generation_prompt(self.project, j)
        payload = {k: "实际交付内容" for k in required}
        if kind == "article": payload["body"] = "这是实际用于验证的文本草稿，引用了用户提供的项目资料。" * 10
        if "shots" in payload: payload["shots"] = [{"duration": 4, "action": "展示任务列表"}]
        return j, {"content_type": kind, "deliverable_status": "text_draft", "payload": payload, "limitations": ["测试数据，不是商业作品"]}

    @unittest.skipUnless(os.name == "posix", "fake executable test requires POSIX")
    def test_fake_executor_real_file_validation(self):
        j, result = self.fixture()
        code = "import sys,json\nfrom pathlib import Path\nprompt=sys.stdin.read()\nassert 'outputs/result.json' in prompt\nPath('outputs/result.json').write_text(" + repr(json.dumps(result, ensure_ascii=False)) + ",encoding='utf-8')\nprint(json.dumps({'type':'turn.completed'}))\n"
        with patch.dict(os.environ, {"CODEX_BIN": self.fake(code)}):
            draft = run_job(self.store, "company_a", j["id"], self.root / "runtime", timeout=3, allow_unknown_cost=True)
        self.assertEqual(draft["state"], "draft_ready")
        data = json.loads(draft["artifacts"]["result.json"])
        self.assertFalse(data["media_rendered"])
        self.assertIsNone(draft["actual_cost_cny"])
        self.assertEqual(draft["cost_status"], "unknown")

    def test_unknown_cost_requires_explicit_opt_in(self):
        j = self.job()
        with self.assertRaises(Problem): run_job(self.store, "company_a", j["id"], self.root / "runtime")
        self.assertEqual(self.store.job("company_a", j["id"])["state"], "planned")

    @unittest.skipUnless(os.name == "posix", "fake executable test requires POSIX")
    def test_zero_exit_without_artifact_fails(self):
        j = self.job()
        with patch.dict(os.environ, {"CODEX_BIN": self.fake("import sys\nsys.stdin.read()\n")}):
            with self.assertRaises(Problem): run_job(self.store, "company_a", j["id"], self.root / "runtime", timeout=3, allow_unknown_cost=True)
        self.assertEqual(self.store.job("company_a", j["id"])["state"], "failed")

    @unittest.skipUnless(os.name == "posix", "fake executable test requires POSIX")
    def test_nonzero_exit_fails(self):
        j = self.job()
        with patch.dict(os.environ, {"CODEX_BIN": self.fake("import sys\nsys.stdin.read()\nraise SystemExit(2)\n")}):
            with self.assertRaises(Problem): run_job(self.store, "company_a", j["id"], self.root / "runtime", timeout=3, allow_unknown_cost=True)
        self.assertEqual(self.store.job("company_a", j["id"])["state"], "failed")

    @unittest.skipUnless(os.name == "posix", "fake executable test requires POSIX")
    def test_timeout_stops_child(self):
        binary = self.fake("import sys,time\nsys.stdin.read()\ntime.sleep(30)\n")
        with self.assertRaises(Problem) as c: invoke([binary], timeout=1)
        self.assertIn("超时", str(c.exception))

    @unittest.skipUnless(os.name == "posix", "symlink test requires POSIX")
    def test_symlink_result_denied(self):
        j, result = self.fixture()
        outside = self.root / "outside.json"; outside.write_text(json.dumps(result))
        code = "import sys\nfrom pathlib import Path\nsys.stdin.read()\nPath('outputs/result.json').symlink_to(" + repr(str(outside)) + ")\n"
        with patch.dict(os.environ, {"CODEX_BIN": self.fake(code)}):
            with self.assertRaises(Problem): run_job(self.store, "company_a", j["id"], self.root / "runtime", timeout=3, allow_unknown_cost=True)

    def test_result_schema_requires_fields(self):
        j, result = self.fixture(); del result["payload"]["body"]
        path = self.root / "result.json"; path.write_text(json.dumps(result))
        _, required = generation_prompt(self.project, j)
        with self.assertRaises(Problem): validate_result(path, "article", required)

    def test_media_claim_denied(self):
        j, result = self.fixture("short_video"); result["deliverable_status"] = "video_rendered"
        path = self.root / "result.json"; path.write_text(json.dumps(result))
        _, required = generation_prompt(self.project, j)
        with self.assertRaises(Problem): validate_result(path, "short_video", required)


class HTTPTests(Base):
    def setUp(self):
        super().setUp()
        self.server = make_server(self.store, 0, capabilities={"codex_installed": False})
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True); self.thread.start()
        self.base = f"http://127.0.0.1:{self.server.server_port}"
        self.token = self.request("/api/bootstrap")[1]["token"]

    def tearDown(self):
        self.server.shutdown(); self.server.server_close(); self.thread.join(); super().tearDown()

    def request(self, path, data=None, headers=None):
        h = {"Content-Type": "application/json"}
        if headers: h.update(headers)
        request = urllib.request.Request(self.base+path, data=json.dumps(data).encode() if data is not None else None, headers=h)
        try:
            with urllib.request.urlopen(request, timeout=5) as r:
                payload = r.read()
                return r.status, json.loads(payload) if r.headers.get_content_type() == "application/json" else payload
        except urllib.error.HTTPError as e:
            return e.code, json.loads(e.read())

    def test_get_and_create_over_http(self):
        status, projects = self.request("/api/projects?tenant=company_a")
        self.assertEqual(status, 200); self.assertEqual(len(projects), 1)
        status, created = self.request("/api/projects?tenant=company_b", {"product_name": "HTTP产品"}, {"X-Workbench-Token": self.token})
        self.assertEqual(status, 201); self.assertEqual(created["tenant_id"], "company_b")

    def test_missing_csrf_denied(self):
        self.assertEqual(self.request("/api/projects", {"product_name": "unauthorized"})[0], 403)

    def test_cross_origin_denied(self):
        self.assertEqual(self.request("/api/bootstrap", headers={"Origin": "https://evil.example"})[0], 403)

    def test_dns_rebinding_host_denied(self):
        self.assertEqual(self.request("/api/bootstrap", headers={"Host": "evil.example"})[0], 403)

    def test_traversal_not_served(self):
        self.assertEqual(self.request("/../SPEC.md")[0], 404)

    def test_cli_disabled_does_not_run(self):
        j = self.job()
        status, _ = self.request("/api/jobs/"+j["id"]+"/run?tenant=company_a", {}, {"X-Workbench-Token": self.token})
        self.assertEqual(status, 409); self.assertEqual(self.store.job("company_a", j["id"])["state"], "planned")

    def test_static_uses_safe_text_rendering(self):
        status, html = self.request("/"); self.assertEqual(status, 200)
        self.assertIn("企业内容工作台".encode(), html)
        _, js = self.request("/app.js")
        self.assertNotIn(b"innerHTML", js)
        self.assertIn(b"textContent", js)


if __name__ == "__main__": unittest.main()
