"""SQLite-backed internal workflow; tenant fields isolate records, not identities."""
import hashlib
import io
import json
import re
import sqlite3
import uuid
import zipfile
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

from .recipes import TYPES, PLATFORMS, production_package


class Problem(Exception):
    def __init__(self, message, status=400):
        super().__init__(message)
        self.status = status


def now():
    return datetime.now(timezone.utc).isoformat()


def identifier(value):
    if not isinstance(value, str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,80}", value):
        raise Problem("资料标识格式不正确")
    return value


def text(value, label, maximum=10000, required=True):
    if value is None and not required:
        return None
    if not isinstance(value, str) or len(value) > maximum or (required and not value.strip()):
        raise Problem(f"{label}不能为空或超过长度限制")
    return value.strip()


def digest(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True).encode()).hexdigest()


class Store:
    def __init__(self, path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.connection() as c:
            c.executescript("""
            PRAGMA journal_mode=WAL;
            CREATE TABLE IF NOT EXISTS projects(id TEXT PRIMARY KEY, tenant TEXT NOT NULL, body TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS accounts(id TEXT PRIMARY KEY, tenant TEXT NOT NULL, project TEXT NOT NULL, body TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS jobs(id TEXT PRIMARY KEY, tenant TEXT NOT NULL, project TEXT NOT NULL,
              idem TEXT NOT NULL, request_hash TEXT NOT NULL, state TEXT NOT NULL, body TEXT NOT NULL,
              UNIQUE(tenant,project,idem));
            CREATE TABLE IF NOT EXISTS events(id INTEGER PRIMARY KEY AUTOINCREMENT, tenant TEXT NOT NULL,
              project TEXT NOT NULL, job TEXT, at TEXT NOT NULL, kind TEXT NOT NULL, details TEXT NOT NULL);
            """)

    @contextmanager
    def connection(self):
        c = sqlite3.connect(self.path, timeout=10)
        c.row_factory = sqlite3.Row
        try:
            with c:
                yield c
        finally:
            c.close()

    def _event(self, c, tenant, project, job, kind, details):
        c.execute("INSERT INTO events(tenant,project,job,at,kind,details) VALUES(?,?,?,?,?,?)",
                  (tenant, project, job, now(), kind, json.dumps(details, ensure_ascii=False)))

    def create_project(self, tenant, data):
        tenant = identifier(tenant)
        facts = data.get("facts", [])
        if not isinstance(facts, list) or len(facts) > 100:
            raise Problem("事实最多100条，必须为列表")
        clean_facts = []
        for fact in facts:
            if not isinstance(fact, dict):
                raise Problem("每条事实需要内容和来源")
            clean_facts.append({"text": text(fact.get("text"), "事实", 2000),
                                "source": text(fact.get("source"), "来源", 2000)})
        claims = data.get("claims_to_verify", [])
        if not isinstance(claims, list) or len(claims) > 100:
            raise Problem("待验证主张格式错误")
        claims = [text(x, "待验证主张", 2000) for x in claims]
        assets = data.get("asset_refs", [])
        if not isinstance(assets, list) or len(assets) > 100:
            raise Problem("素材引用格式错误")
        assets = [text(x, "素材引用", 2000) for x in assets]
        result = {"id": uuid.uuid4().hex, "tenant_id": tenant,
                  "product_name": text(data.get("product_name"), "产品名称", 200),
                  "facts": clean_facts, "claims_to_verify": claims, "asset_refs": assets,
                  "audience": text(data.get("audience"), "人群假设", 2000, False),
                  "business_goal": text(data.get("business_goal"), "业务目标", 2000, False),
                  "brand_voice": text(data.get("brand_voice"), "品牌口吻", 1000, False),
                  "created_at": now()}
        with self.connection() as c:
            c.execute("INSERT INTO projects VALUES(?,?,?)", (result["id"], tenant, json.dumps(result, ensure_ascii=False)))
            self._event(c, tenant, result["id"], None, "project_created", {})
        return result

    def project(self, tenant, project):
        identifier(tenant); identifier(project)
        with self.connection() as c:
            row = c.execute("SELECT body FROM projects WHERE id=? AND tenant=?", (project, tenant)).fetchone()
        if not row:
            raise Problem("项目不存在或不属于当前资料分区", 404)
        return json.loads(row["body"])

    def projects(self, tenant):
        identifier(tenant)
        with self.connection() as c:
            return [json.loads(x[0]) for x in c.execute("SELECT body FROM projects WHERE tenant=? ORDER BY rowid DESC", (tenant,))]

    def create_account(self, tenant, project, data):
        self.project(tenant, project)
        platform = data.get("platform")
        if platform not in PLATFORMS:
            raise Problem("未知的平台候选")
        authorized = data.get("publish_authorized", False)
        if not isinstance(authorized, bool):
            raise Problem("发布授权必须是布尔值")
        result = {"id": uuid.uuid4().hex, "tenant_id": tenant, "project_id": project,
                  "platform": platform, "external_id": text(data.get("external_id"), "账号唯一ID", 200),
                  "display_name": text(data.get("display_name"), "账号名称", 200),
                  "positioning": text(data.get("positioning"), "定位", 1000, False),
                  "credential_ref": text(data.get("credential_ref"), "凭证引用", 200, False),
                  "publish_authorized": authorized, "identity_verified": False,
                  "publishing_status": "not_connected", "created_at": now()}
        with self.connection() as c:
            c.execute("INSERT INTO accounts VALUES(?,?,?,?)", (result["id"], tenant, project, json.dumps(result, ensure_ascii=False)))
            self._event(c, tenant, project, None, "account_added", {"account_id": result["id"]})
        return result

    def accounts(self, tenant, project):
        self.project(tenant, project)
        with self.connection() as c:
            return [json.loads(x[0]) for x in c.execute("SELECT body FROM accounts WHERE tenant=? AND project=?", (tenant, project))]

    def create_job(self, tenant, project, data):
        self.project(tenant, project)
        kind = data.get("content_type")
        if kind not in TYPES:
            raise Problem("请选择受支持的内容类别")
        platform = data.get("platform") or None
        if platform is not None and platform not in PLATFORMS:
            raise Problem("未知的平台候选")
        if platform and kind not in PLATFORMS[platform][1]:
            raise Problem("该形式不在此平台候选范围内；请先核实平台能力")
        account_id = data.get("account_id") or None
        if account_id:
            identifier(account_id)
            matches = [a for a in self.accounts(tenant, project) if a["id"] == account_id]
            if not matches or (platform and matches[0]["platform"] != platform):
                raise Problem("账号不属于当前项目或平台不匹配")
            platform = matches[0]["platform"]
            if kind not in PLATFORMS[platform][1]:
                raise Problem("账号平台与内容形式不匹配")
        budget = data.get("budget_cny", 0)
        if isinstance(budget, bool) or not isinstance(budget, (float, int)) or not 0 <= budget <= 100000:
            raise Problem("预算需为0至100000之间的有限数值")
        idem = identifier(data.get("idempotency_key") or uuid.uuid4().hex)
        request = {"content_type": kind, "topic": text(data.get("topic"), "选题", 1000),
                   "platform": platform, "account_id": account_id, "budget_cny": budget,
                   "version": 1}
        request_hash = digest(request)
        result = {**request, "id": uuid.uuid4().hex, "tenant_id": tenant, "project_id": project,
                  "idempotency_key": idem, "state": "planned", "publish_status": "not_connected",
                  "artifacts": {}, "artifact_digest": None, "checks": {}, "events_summary": [],
                  "actual_cost_cny": None, "cost_status": "no_model_call_yet",
                  "created_at": now(), "updated_at": now(), "error": None}
        with self.connection() as c:
            c.execute("BEGIN IMMEDIATE")
            old = c.execute("SELECT request_hash,body FROM jobs WHERE tenant=? AND project=? AND idem=?", (tenant, project, idem)).fetchone()
            if old:
                if old["request_hash"] != request_hash:
                    raise Problem("同一幂等键对应不同任务，请换用新键", 409)
                return json.loads(old["body"])
            c.execute("INSERT INTO jobs VALUES(?,?,?,?,?,?,?)", (result["id"], tenant, project, idem, request_hash, "planned", json.dumps(result, ensure_ascii=False)))
            self._event(c, tenant, project, result["id"], "job_created", {"content_type": kind})
        return result

    def job(self, tenant, job):
        identifier(tenant); identifier(job)
        with self.connection() as c:
            row = c.execute("SELECT body FROM jobs WHERE tenant=? AND id=?", (tenant, job)).fetchone()
        if not row:
            raise Problem("任务不存在或不属于当前资料分区", 404)
        return json.loads(row[0])

    def jobs(self, tenant, project):
        self.project(tenant, project)
        with self.connection() as c:
            return [json.loads(x[0]) for x in c.execute("SELECT body FROM jobs WHERE tenant=? AND project=? ORDER BY rowid DESC", (tenant, project))]

    def mutate(self, tenant, job_id, expected, transform, event):
        identifier(tenant); identifier(job_id)
        with self.connection() as c:
            c.execute("BEGIN IMMEDIATE")
            row = c.execute("SELECT body,state FROM jobs WHERE tenant=? AND id=?", (tenant, job_id)).fetchone()
            if not row:
                raise Problem("任务不存在", 404)
            if row["state"] not in expected:
                raise Problem("当前任务状态不允许此操作", 409)
            job = json.loads(row["body"])
            transform(job)
            job["updated_at"] = now()
            c.execute("UPDATE jobs SET state=?,body=? WHERE tenant=? AND id=?", (job["state"], json.dumps(job, ensure_ascii=False), tenant, job_id))
            self._event(c, tenant, job["project_id"], job_id, event, {"state": job["state"]})
        return job

    def prepare(self, tenant, job_id):
        job = self.job(tenant, job_id)
        project = self.project(tenant, job["project_id"])
        artifacts = production_package(project, job)
        def change(j):
            j.update(state="brief_ready", artifacts=artifacts, artifact_digest=digest(artifacts),
                     checks={}, error=None, publish_status="not_connected")
        return self.mutate(tenant, job_id, ["planned", "brief_ready", "failed", "blocked", "unknown"], change, "brief_prepared")

    def claim(self, tenant, job_id):
        def change(j):
            j.update(state="running", checks={}, error=None)
        return self.mutate(tenant, job_id, ["brief_ready", "failed", "blocked", "unknown"], change, "generation_started")

    def finish(self, tenant, job_id, artifacts, event_summary):
        def change(j):
            j.update(state="draft_ready", artifacts={**j["artifacts"], **artifacts},
                     checks={}, error=None, actual_cost_cny=None, cost_status="unknown",
                     events_summary=event_summary)
            j["artifact_digest"] = digest(j["artifacts"])
        return self.mutate(tenant, job_id, ["running"], change, "draft_generated")

    def fail(self, tenant, job_id, message, state="failed", model_started=False):
        def change(j):
            j.update(state=state, error=message, checks={})
            if model_started:
                j.update(cost_status="unknown", actual_cost_cny=None)
        return self.mutate(tenant, job_id, ["running", "brief_ready", "planned", "checked", "draft_ready", "awaiting_approval"], change, "operation_blocked" if state == "blocked" else "generation_failed")

    def check(self, tenant, job_id, checks):
        if not isinstance(checks, dict) or set(checks) != {"facts", "rights", "format", "ai_label"} or not all(v is True for v in checks.values()):
            raise Problem("事实、权利、规格与AI声明四项都需人工确认通过")
        def change(j):
            if j["artifact_digest"] != digest(j["artifacts"]):
                raise Problem("产物已变化，需要重新生成并审核", 409)
            j.update(state="checked", checks={"items": checks, "method": "manual", "at": now(), "artifact_digest": j["artifact_digest"]})
        return self.mutate(tenant, job_id, ["draft_ready"], change, "manual_review_passed")

    def request_publish(self, tenant, job_id):
        job = self.job(tenant, job_id)
        if job["state"] != "checked":
            raise Problem("先生成实际草稿并完成四项审核", 409)
        # No real publishing adapter exists; no configuration can claim success.
        return self.fail(tenant, job_id, "浏览器／官方发布适配器尚未接入。请导出发布包并人工发布。", "blocked")

    def recover_interrupted(self):
        with self.connection() as c:
            c.execute("BEGIN IMMEDIATE")
            rows = c.execute("SELECT id,tenant,body FROM jobs WHERE state='running'").fetchall()
            for row in rows:
                job = json.loads(row["body"])
                job.update(state="unknown", error="上次执行被中断；请核对产物后显式重试。", updated_at=now(), checks={}, cost_status="unknown", actual_cost_cny=None)
                c.execute("UPDATE jobs SET state='unknown',body=? WHERE id=?", (json.dumps(job, ensure_ascii=False), row["id"]))
                self._event(c, row["tenant"], job["project_id"], row["id"], "interrupted", {})
        return len(rows)

    def events(self, tenant, job_id):
        self.job(tenant, job_id)
        with self.connection() as c:
            return [dict(x) for x in c.execute("SELECT at,kind,details FROM events WHERE tenant=? AND job=? ORDER BY id", (tenant, job_id))]

    def export(self, tenant, job_id):
        job = self.job(tenant, job_id)
        if not job["artifacts"]:
            raise Problem("先生成制作任务包")
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as z:
            for name, body in job["artifacts"].items():
                if not re.fullmatch(r"[A-Za-z0-9_-]+\.(md|json|txt)", name):
                    raise Problem("非法产物文件名")
                z.writestr(name, body)
            summary = {k: job[k] for k in ["id", "content_type", "topic", "state", "publish_status", "actual_cost_cny", "cost_status", "artifact_digest", "checks"]}
            z.writestr("delivery.json", json.dumps(summary, ensure_ascii=False, indent=2))
        return buffer.getvalue()
