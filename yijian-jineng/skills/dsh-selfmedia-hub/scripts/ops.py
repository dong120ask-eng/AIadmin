"""Local task ledger. Does not log in or submit to any platform."""
import argparse
import hashlib
import json
import re
import shutil
import sqlite3
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

def stamp():
    return datetime.now(timezone.utc).isoformat()

def emit(value):
    print(json.dumps(value, ensure_ascii=False, indent=2))

class Ledger:
    def __init__(self, root):
        self.root = Path(root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        data = self.root / "state"
        data.mkdir(exist_ok=True)
        self.db = sqlite3.connect(data / "selfmedia.sqlite", timeout=10)
        self.db.row_factory = sqlite3.Row
        self.db.executescript("""
        CREATE TABLE IF NOT EXISTS instances(id TEXT PRIMARY KEY, body TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS tasks(id TEXT PRIMARY KEY, body TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS locks(device TEXT PRIMARY KEY, task TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS events(id INTEGER PRIMARY KEY, task TEXT, at TEXT, kind TEXT, detail TEXT);
        """)

    def path(self, value):
        p = Path(value)
        p = (p if p.is_absolute() else self.root / p).resolve()
        if not p.is_relative_to(self.root) or not p.is_file():
            raise ValueError("文件必须存在且位于工作目录内")
        return p

    def file(self, value):
        p = self.path(value)
        return {"path": str(p.relative_to(self.root)), "sha256": hashlib.sha256(p.read_bytes()).hexdigest()}

    def evidence(self, value):
        record = self.file(value)
        if self.path(value).stat().st_size == 0:
            raise ValueError("证据文件不能为空")
        return record

    def instance(self, key):
        r = self.db.execute("SELECT body FROM instances WHERE id=?", (key,)).fetchone()
        if not r:
            raise ValueError("实例未登记")
        return json.loads(r[0])

    def register(self, value):
        fields = ("id", "device_id", "platform", "package_name", "account_id", "account_alias", "launch_mode")
        if any(not isinstance(value.get(k), str) or not value[k].strip() for k in fields):
            raise ValueError("实例缺少必要字符串字段")
        if not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", value["id"]):
            raise ValueError("实例 id 应使用英文小写和连字符")
        if not re.fullmatch(r"[A-Za-z0-9_.]+", value["package_name"]):
            raise ValueError("包名无效")
        if value["launch_mode"] not in ("primary", "android-user", "manual-clone"):
            raise ValueError("launch_mode 无效")
        if value["launch_mode"] == "android-user" and not isinstance(value.get("android_user_id"), int):
            raise ValueError("系统用户实例需要整数 android_user_id")
        if value["launch_mode"] == "manual-clone" and not value.get("clone_entry"):
            raise ValueError("分身实例需要 clone_entry")
        if any(k.lower() in ("password", "cookie", "token", "secret", "otp") for k in value):
            raise ValueError("不允许将凭据写入实例登记")
        with self.db:
            self.db.execute("INSERT INTO instances VALUES(?,?)", (value["id"], json.dumps(value, ensure_ascii=False)))
        return value

    def create(self, instance, title, text, media, visibility):
        identity = self.instance(instance)
        if not title.strip() or not visibility.strip():
            raise ValueError("标题和可见性不能为空")
        body = {
            "id": uuid.uuid4().hex[:12], "instance": identity,
            "title": title, "visibility": visibility, "text": self.file(text),
            "media": [self.file(p) for p in media], "state": "prepared", "created_at": stamp(),
        }
        if self.path(text).stat().st_size == 0:
            raise ValueError("正文不能为空")
        body["fingerprint"] = self.fingerprint(body)
        with self.db:
            self.db.execute("INSERT INTO tasks VALUES(?,?)", (body["id"], json.dumps(body, ensure_ascii=False)))
            self.log(body["id"], "created", {"fingerprint": body["fingerprint"]})
        return body

    @staticmethod
    def fingerprint(body):
        fields = {k: body[k] for k in ("instance", "title", "visibility", "text", "media")}
        return hashlib.sha256(json.dumps(fields, sort_keys=True, ensure_ascii=False).encode()).hexdigest()

    def load(self, key):
        r = self.db.execute("SELECT body FROM tasks WHERE id=?", (key,)).fetchone()
        if not r:
            raise ValueError("任务不存在")
        return json.loads(r[0])

    def check(self, body):
        for record in [body["text"], *body["media"]]:
            if self.file(record["path"]) != record:
                raise ValueError("素材已改变，须新建任务并重新预览确认")
        if self.fingerprint(body) != body["fingerprint"]:
            raise ValueError("任务指纹不一致")
        if body.get('qa'):
            if self.file(body['qa']['path'])!=body['qa']: raise ValueError('质检证据已改变')
            report=json.loads(self.path(body['qa']['path']).read_text(encoding='utf-8-sig'))
            if not isinstance(report,dict) or report.get('schema')!='content-qa/v1' or report.get('passed') is not True or report.get('task_id')!=body['id'] or report.get('fingerprint')!=body['fingerprint'] or report.get('issues') or not report.get('reviewer'): raise ValueError('质检无效或来自旧版本，请重新建任务质检')

    def log(self, task, kind, detail):
        self.db.execute("INSERT INTO events(task,at,kind,detail) VALUES(?,?,?,?)",
                        (task, stamp(), kind, json.dumps(detail, ensure_ascii=False)))

    def save(self, body, kind):
        body["updated_at"] = stamp()
        self.db.execute("UPDATE tasks SET body=? WHERE id=?", (json.dumps(body, ensure_ascii=False), body["id"]))
        self.log(body["id"], kind, {"state": body["state"]})

    def owns(self, body):
        device = body["instance"]["device_id"]
        r = self.db.execute("SELECT task FROM locks WHERE device=?", (device,)).fetchone()
        if not r or r[0] != body["id"]:
            raise ValueError("先为该任务 claim 设备；同一手机只能有一个活动任务")

    def change(self, key, kind, observed=None, evidence=None, approval=None, result=None):
        self.db.execute("BEGIN IMMEDIATE")
        try:
            b = self.load(key)
            if kind in ("claim", "qa", "draft", "approve", "begin", "attempt"):
                self.check(b)
            device = b["instance"]["device_id"]
            if kind == "claim":
                if b["state"] in ("published", "publishing", "uncertain"):
                    raise ValueError("发布中或结果未知的任务不可重新操作")
                r = self.db.execute("SELECT task FROM locks WHERE device=?", (device,)).fetchone()
                if r and r[0] != key:
                    raise ValueError("设备已有另一活动任务")
                self.db.execute("INSERT OR IGNORE INTO locks VALUES(?,?)", (device, key))
            elif kind == "release":
                self.owns(b)
                if b["state"] in ("publishing", "uncertain"):
                    raise ValueError("发布中/结果未知时不能释放锁；先 reconcile")
                self.db.execute("DELETE FROM locks WHERE device=? AND task=?", (device, key))
            elif kind == "qa":
                if b["state"] != "prepared":
                    raise ValueError("仅 prepared 可进入 reviewed")
                report=json.loads(self.path(evidence).read_text(encoding='utf-8-sig'))
                if report.get('schema')!='content-qa/v1' or report.get('passed') is not True or report.get('task_id')!=key or report.get('fingerprint')!=b['fingerprint'] or report.get('issues') or not report.get('reviewer'):
                    raise ValueError('需当前任务通过的结构化质检报告；普通文件不能代替质检')
                b["qa"] = self.evidence(evidence)
                b["state"] = "reviewed"
            elif kind == "draft":
                self.owns(b)
                if b["state"] != "reviewed":
                    raise ValueError("草稿前必须完成 QA")
                self.account(b, observed)
                b["draft"] = self.evidence(evidence)
                b["state"] = "draft"
            elif kind == "approve":
                if b["state"] != "draft":
                    raise ValueError("必须先有真实草稿")
                a = json.loads(self.path(approval).read_text(encoding="utf-8-sig"))
                if a.get("consent") is not True or a.get("task_id") != key or a.get("fingerprint") != b["fingerprint"] or a.get("draft_sha256") != b["draft"]["sha256"] or not a.get("approved_by"):
                    raise ValueError("确认记录必须绑定该任务和精确素材指纹")
                b["approval"] = self.evidence(approval)
                b["state"] = "approved"
            elif kind == "begin":
                self.owns(b)
                self.account(b, observed)
                if b["state"] != "approved":
                    raise ValueError("必须经用户确认，且不可重复 begin")
                if self.file(b["approval"]["path"]) != b["approval"]:
                    raise ValueError("确认记录已修改")
                if self.file(b["draft"]["path"]) != b["draft"]:
                    raise ValueError("草稿证据已修改，需重新预览")
                if self.file(b["qa"]["path"]) != b["qa"]:
                    raise ValueError("质检证据已修改")
                b["pre_submit"] = self.evidence(evidence)
                b["state"] = "publishing"
            elif kind == "attempt":
                self.owns(b)
                self.account(b, observed)
                if b["state"] != "publishing" or b.get("submit_attempt"):
                    raise ValueError("提交尚未确认或已经尝试，先核验结果，禁止重复点击")
                for evidence_key in ("approval", "draft", "qa"):
                    if self.file(b[evidence_key]["path"]) != b[evidence_key]:
                        raise ValueError("确认或证据已变化")
                b["submit_attempt"] = stamp()
            elif kind == "uncertain":
                self.owns(b)
                if b["state"] != "publishing":
                    raise ValueError("仅 publishing 可记为结果未知")
                b["uncertain_evidence"] = self.evidence(evidence)
                b["state"] = "uncertain"
            elif kind in ("complete", "reconcile"):
                self.owns(b)
                self.account(b, observed)
                allowed = ("publishing",) if kind == "complete" else ("publishing", "uncertain")
                if b["state"] not in allowed or not result:
                    raise ValueError("缺少可核验作品链接/ID或任务状态不允许")
                b["result"] = result
                b["result_evidence"] = self.evidence(evidence)
                b["state"] = "published"
                self.db.execute("DELETE FROM locks WHERE device=? AND task=?", (device, key))
            elif kind == "not-published":
                self.owns(b)
                self.account(b, observed)
                if b["state"] not in ("publishing", "uncertain"):
                    raise ValueError("仅发布中或结果未知可核验未发布")
                b["not_published_evidence"] = self.evidence(evidence)
                b.pop("approval", None)
                b.pop("submit_attempt", None)
                b["state"] = "draft"
                self.db.execute("DELETE FROM locks WHERE device=? AND task=?", (device, key))
            else:
                raise ValueError("未知操作")
            self.save(b, kind)
            self.db.commit()
            return b
        except Exception:
            self.db.rollback()
            raise

    @staticmethod
    def account(body, observed):
        if observed != body["instance"]["account_id"]:
            raise ValueError("当前账号与目标账号不一致")

    def listing(self):
        return [json.loads(r[0]) for r in self.db.execute("SELECT body FROM tasks ORDER BY rowid")]

def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--root", required=True)
    s = p.add_subparsers(dest="cmd", required=True)
    reg = s.add_parser("register"); reg.add_argument("--file", required=True)
    create = s.add_parser("create")
    for field in ("instance", "title", "text", "visibility"):
        create.add_argument("--" + field, required=True)
    create.add_argument("--media", action="append", default=[])
    show = s.add_parser("show"); show.add_argument("--task", required=True)
    s.add_parser("list")
    for cmd in ("claim", "release", "qa", "draft", "approve", "begin", "attempt", "uncertain", "complete", "reconcile", "not-published"):
        q = s.add_parser(cmd); q.add_argument("--task", required=True)
        if cmd in ("draft", "begin", "attempt", "complete", "reconcile", "not-published"):
            q.add_argument("--observed-account", required=True)
        if cmd in ("qa", "draft", "begin", "uncertain", "complete", "reconcile", "not-published"):
            q.add_argument("--evidence", required=True)
        if cmd == "approve":
            q.add_argument("--approval", required=True)
        if cmd in ("complete", "reconcile"):
            q.add_argument("--result", required=True)
    args = p.parse_args()
    l = Ledger(args.root)
    try:
        execute(args, l)
    finally:
        l.db.close()

def execute(args, l):
    if args.cmd == "register":
        value = l.register(json.loads(l.path(args.file).read_text(encoding="utf-8-sig")))
    elif args.cmd == "create":
        value = l.create(args.instance, args.title, args.text, args.media, args.visibility)
    elif args.cmd == "show":
        value = l.load(args.task)
    elif args.cmd == "list":
        value = l.listing()
    else:
        value = l.change(args.task, args.cmd, getattr(args, "observed_account", None),
                         getattr(args, "evidence", None), getattr(args, "approval", None), getattr(args, "result", None))
    emit(value)

if __name__ == "__main__":
    try:
        main()
    except (ValueError, sqlite3.Error, OSError, json.JSONDecodeError) as e:
        emit({"error": str(e)}); sys.exit(2)
