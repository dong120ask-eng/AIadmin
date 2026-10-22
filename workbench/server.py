"""Loopback-only internal dashboard. Not a public SaaS server."""
import json
import secrets
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

from .recipes import TYPES, platform_catalog
from .media import media_index
from .dispatch import DispatchQueue
from .runner import doctor, run_job
from .store import Problem, identifier

STATIC = Path(__file__).parent / "static"


def make_server(store, port=8765, allow_cli=False, runtime=None, capabilities=None, homepage="index.html"):
    from .ecommerce import Operations, template, FIELDS, KINDS, PLATFORMS, LIMITATION
    operations = Operations(store)
    csrf = secrets.token_urlsafe(32)
    caps = capabilities if capabilities is not None else doctor()
    caps = {**caps, "cli_enabled": allow_cli}

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_):
            pass  # Request bodies and user content never enter console logs.

        def send(self, data, status=200, mime="application/json; charset=utf-8", filename=None):
            if not isinstance(data, bytes):
                data = json.dumps(data, ensure_ascii=False).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", mime)
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("X-Frame-Options", "DENY")
            self.send_header("Content-Security-Policy", "default-src 'self'; script-src 'self'; style-src 'self'; connect-src 'self'; img-src 'self' data:; frame-ancestors 'none'; base-uri 'none'")
            if filename:
                self.send_header("Content-Disposition", f'attachment; filename="{filename}"')
            self.end_headers()
            self.wfile.write(data)

        def guard(self, mutation=False):
            hosts = {f"127.0.0.1:{self.server.server_port}", f"localhost:{self.server.server_port}"}
            if self.headers.get("Host") not in hosts:
                raise Problem("只接受本机访问", 403)
            origin = self.headers.get("Origin")
            if origin and origin not in {"http://" + host for host in hosts}:
                raise Problem("跨站请求已拒绝", 403)
            if mutation and self.headers.get("X-Workbench-Token") != csrf:
                raise Problem("请求校验失败，请刷新工作台", 403)

        def route(self, mutation=False):
            self.guard(mutation)
            parsed = urlsplit(self.path)
            query = parse_qs(parsed.query)
            tenant = query.get("tenant", ["internal"])[0]
            identifier(tenant)
            path = parsed.path
            if not mutation:
                files = {"/": (homepage, "text/html; charset=utf-8"),
                         "/ecommerce.html": ("ecommerce.html", "text/html; charset=utf-8"),
                         "/ecommerce.js": ("ecommerce.js", "text/javascript; charset=utf-8"),
                         "/ecommerce.css": ("ecommerce.css", "text/css; charset=utf-8"),
                         "/app.js": ("app.js", "text/javascript; charset=utf-8"),
                         "/media.html": ("media.html", "text/html; charset=utf-8"),
                         "/dispatch.html": ("dispatch.html", "text/html; charset=utf-8"),
                         "/dispatch.js": ("dispatch.js", "text/javascript; charset=utf-8"),
                         "/media.js": ("media.js", "text/javascript; charset=utf-8"),
                         "/style.css": ("style.css", "text/css; charset=utf-8")}
                if path in files:
                    filename, mime = files[path]
                    return self.send((STATIC / filename).read_bytes(), mime=mime)
                if path == "/api/ecommerce/config":
                    return self.send({"token": csrf, "fields": FIELDS, "kinds": KINDS, "platforms": PLATFORMS, "limitation": LIMITATION})
                if path == "/api/ecommerce/template":
                    return self.send(template(), mime="text/csv; charset=utf-8", filename="ecommerce-template.csv")
                if path == "/api/ecommerce/imports":
                    return self.send(operations.imports())
                eparts = path.strip("/").split("/")
                if len(eparts) in (4, 5) and eparts[:3] == ["api", "ecommerce", "imports"]:
                    key = identifier(eparts[3])
                    if len(eparts) == 4:
                        return self.send(operations.get(key))
                    if eparts[4] == "export":
                        return self.send(operations.export(key), mime="application/zip", filename="ecommerce-" + key + ".zip")
                if path == "/api/dispatch":
                    return self.send(DispatchQueue(store.path.parent/"dispatch.sqlite3").tasks(tenant))
                if path == "/api/media-index":
                    return self.send(media_index(query.get("category", [None])[0], query.get("keyword", [None])[0]))
                if path == "/api/bootstrap":
                    return self.send({"token": csrf, "capabilities": caps, "types": {k: v[0] for k, v in TYPES.items()}, "platforms": platform_catalog()})
                if path == "/api/projects":
                    return self.send(store.projects(tenant))
                if path == "/api/jobs":
                    return self.send(store.jobs(tenant, query.get("project", [""])[0]))
                if path == "/api/accounts":
                    return self.send(store.accounts(tenant, query.get("project", [""])[0]))
                parts = path.strip("/").split("/")
                if len(parts) in (3, 4) and parts[:2] == ["api", "jobs"]:
                    job_id = identifier(parts[2])
                    if len(parts) == 3:
                        return self.send({**store.job(tenant, job_id), "events": store.events(tenant, job_id)})
                    if parts[3] == "export":
                        return self.send(store.export(tenant, job_id), mime="application/zip", filename=f"job-{job_id}.zip")
                raise Problem("页面或接口不存在", 404)
            try:
                length = int(self.headers.get("Content-Length", "0"))
            except ValueError:
                raise Problem("请求长度无效")
            limit = 6 * 1024 * 1024 if path == "/api/ecommerce/imports" else 128 * 1024
            if not 0 < length <= limit:
                raise Problem("请求过大或为空", 413)
            if self.headers.get_content_type() != "application/json":
                raise Problem("请使用JSON请求", 415)
            try:
                data = json.loads(self.rfile.read(length))
            except (ValueError, UnicodeError):
                raise Problem("请求不是有效JSON")
            if not isinstance(data, dict):
                raise Problem("请求内容必须为对象")
            if path == "/api/ecommerce/demo":
                return self.send(operations.demo(), 201)
            if path == "/api/ecommerce/imports":
                return self.send(operations.ingest(data), 201)
            eparts = path.strip("/").split("/")
            if len(eparts) == 4 and eparts[:3] == ["api", "ecommerce", "issues"]:
                return self.send(operations.update_issue(eparts[3], data))
            if path == "/api/projects":
                return self.send(store.create_project(tenant, data), 201)
            if path == "/api/accounts":
                return self.send(store.create_account(tenant, data.get("project_id", ""), data), 201)
            if path == "/api/jobs":
                return self.send(store.create_job(tenant, data.get("project_id", ""), data), 201)
            parts = path.strip("/").split("/")
            if len(parts) == 4 and parts[:2] == ["api", "jobs"]:
                job_id, action = identifier(parts[2]), parts[3]
                if action == "prepare":
                    return self.send(store.prepare(tenant, job_id))
                if action == "check":
                    return self.send(store.check(tenant, job_id, data.get("checks")))
                if action == "publish":
                    return self.send(store.request_publish(tenant, job_id))
                if action == "run":
                    if not allow_cli:
                        raise Problem("CLI生成未启用。请在终端显式启用，调用费用可能未知。", 409)
                    job = store.job(tenant, job_id)
                    if job["state"] not in {"planned", "brief_ready", "failed", "blocked", "unknown"}:
                        raise Problem("当前任务不能启动生成", 409)
                    # Claim in request thread, so concurrent clicks never create two workers.
                    if job["state"] == "planned":
                        store.prepare(tenant, job_id)
                    store.claim(tenant, job_id)
                    # Worker runner expects brief_ready; use an already_claimed option below.
                    def worker():
                        try:
                            run_job(store, tenant, job_id, runtime, allow_unknown_cost=True, already_claimed=True)
                        except Problem:
                            pass
                    threading.Thread(target=worker, daemon=True).start()
                    return self.send(store.job(tenant, job_id), 202)
            raise Problem("接口不存在", 404)

        def do_GET(self):
            self.handle_route(False)

        def do_POST(self):
            self.handle_route(True)

        def handle_route(self, mutation):
            self.connection.settimeout(10)
            try:
                self.route(mutation)
            except Problem as error:
                self.send({"error": str(error)}, error.status)
            except Exception:
                self.send({"error": "内部操作失败，请检查本机任务记录"}, 500)

    return ThreadingHTTPServer(("127.0.0.1", port), Handler)
