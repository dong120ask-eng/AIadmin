"""Explicitly enabled Codex execution in an isolated per-job workspace."""
import json
import os
import shutil
import signal
import subprocess
import tempfile
import time
from pathlib import Path

from .recipes import generation_prompt
from .store import Problem, identifier

MAX_BYTES = 2 * 1024 * 1024


def codex_binary():
    explicit = os.environ.get("CODEX_BIN")
    if explicit:
        return explicit
    installed = shutil.which("codex")
    if installed:
        return installed
    # Discover the official project's local npm installation without depending
    # on a global PATH or invoking Windows .cmd scripts through a shell.
    modules = Path(__file__).resolve().parents[1] / ".tools" / "codex" / "node_modules" / "@openai"
    native = "codex.exe" if os.name == "nt" else "codex"
    if modules.is_dir():
        for binary in sorted(modules.glob("codex-*/vendor/*/bin/" + native)):
            if binary.is_file():
                return str(binary)
    return None


def invoke(args, prompt="", timeout=90, cwd=None):
    """Bound time and output; temporary raw streams never enter saved reports."""
    with tempfile.TemporaryFile() as out, tempfile.TemporaryFile() as err:
        kwargs = {"start_new_session": True} if os.name == "posix" else {"creationflags": subprocess.CREATE_NEW_PROCESS_GROUP}
        try:
            p = subprocess.Popen(args, stdin=subprocess.PIPE, stdout=out, stderr=err,
                                 cwd=cwd, shell=False, **kwargs)
        except (OSError, ValueError):
            raise Problem("Codex进程无法启动，请检查CODEX_BIN与执行权限", 503)
        reason = None
        try:
            p.stdin.write(prompt.encode("utf-8"))
            p.stdin.close()
            started = time.monotonic()
            while p.poll() is None:
                if time.monotonic() - started > timeout:
                    reason = "Codex执行超时；本次计费未知，请检查后再重试"
                    break
                if os.fstat(out.fileno()).st_size + os.fstat(err.fileno()).st_size > MAX_BYTES:
                    reason = "Codex输出超过限制，任务已停止"
                    break
                time.sleep(0.05)
        except BrokenPipeError:
            p.wait(timeout=5)
        finally:
            if p.poll() is None:
                if os.name == "posix":
                    os.killpg(p.pid, signal.SIGKILL)
                else:
                    subprocess.run(["taskkill", "/PID", str(p.pid), "/T", "/F"], capture_output=True, timeout=10)
                p.wait(timeout=5)
        out.seek(0)
        stdout = out.read(MAX_BYTES).decode("utf-8", "replace")
        # No raw stderr, arguments, tokens or model messages are persisted.
        if reason:
            raise Problem(reason, 503)
        return p.returncode, stdout


def doctor():
    binary = codex_binary()
    report = {"python": "available", "sqlite": "available", "codex_installed": False,
              "codex_version": None, "codex_authenticated": False, "codex_execution": "not_verified",
              "video_rendering": "not_connected", "browser_publishing": "not_connected",
              "payment": "not_connected", "deepseek": "not_connected", "volcano": "not_connected",
              "billing": "unknown", "deployment": "local_only"}
    if not binary:
        return report
    try:
        code, output = invoke([binary, "--version"], timeout=5)
        report["codex_installed"] = code == 0
        report["codex_version"] = output.strip()[:100] if code == 0 else None
        # login status may print its status on stderr. Capture only a boolean via return code.
        code, _ = invoke([binary, "login", "status"], timeout=5)
        report["codex_authenticated"] = code == 0
    except Problem:
        report["codex_execution"] = "blocked"
    return report


def validate_result(path, kind, required):
    if path.is_symlink() or not path.is_file() or path.stat().st_size > MAX_BYTES:
        raise Problem("未找到安全且有效的outputs/result.json", 422)
    raw = path.read_text(encoding="utf-8")
    try:
        result = json.loads(raw)
    except (ValueError, UnicodeError):
        raise Problem("生成结果不是有效JSON", 422)
    if not isinstance(result, dict) or result.get("content_type") != kind or result.get("deliverable_status") != "text_draft":
        raise Problem("生成结果类别或交付状态不正确", 422)
    payload = result.get("payload")
    if not isinstance(payload, dict) or not all(k in payload and payload[k] not in (None, "", [], {}) for k in required):
        raise Problem("生成结果缺少必要的实质内容", 422)
    if "填写实际内容" in json.dumps(payload, ensure_ascii=False):
        raise Problem("生成结果仍包含模板占位符", 422)
    if not isinstance(result.get("limitations"), list):
        raise Problem("生成结果缺少限制说明", 422)
    if kind == "article" and (not isinstance(payload["body"], str) or len(payload["body"].strip()) < 100):
        raise Problem("文章正文过短或格式错误", 422)
    if kind in ("short_video", "long_video", "short_drama") and (not isinstance(payload["shots"], list) or not payload["shots"]):
        raise Problem("视频脚本需要逐镜分镜列表", 422)
    result["media_rendered"] = False
    result["publish_status"] = "not_connected"
    return result


def run_job(store, tenant, job_id, runtime, timeout=90, allow_unknown_cost=False, already_claimed=False):
    if not allow_unknown_cost:
        raise Problem("模型调用费用未知，请显式允许使用现有权益后运行", 409)
    if not isinstance(timeout, int) or not 1 <= timeout <= 1800:
        raise Problem("超时须为1至1800秒")
    binary = codex_binary()
    if not binary:
        if already_claimed:
            store.fail(tenant, job_id, "Codex CLI尚未安装或未配置CODEX_BIN", "blocked")
        raise Problem("Codex CLI尚未安装或未配置CODEX_BIN", 503)
    job = store.job(tenant, job_id)
    if job["state"] == "planned":
        store.prepare(tenant, job_id)
    if already_claimed:
        if job["state"] != "running":
            raise Problem("任务未被原子占用", 409)
    else:
        job = store.claim(tenant, job_id)
    started = False
    try:
        root = Path(runtime).resolve()
        root.mkdir(parents=True, exist_ok=True)
        identifier(job_id)
        # Fresh attempt directory: stale outputs never satisfy a later retry.
        folder = Path(tempfile.mkdtemp(prefix=job_id + "-", dir=root))
        (folder / "outputs").mkdir()
        for name in ("brief.md", "manifest.json"):
            (folder / name).write_text(job["artifacts"][name], encoding="utf-8")
        subprocess.run(["git", "init", "-q", str(folder)], check=True, capture_output=True, timeout=10)
        prompt, required = generation_prompt(store.project(tenant, job["project_id"]), job)
        started = True
        code, stdout = invoke([binary, "exec", "--json", "--sandbox", "workspace-write", "-C", str(folder), "-"],
                              prompt=prompt, timeout=timeout, cwd=folder)
        events = []
        for line in stdout.splitlines():
            try:
                event = json.loads(line)
            except ValueError:
                continue
            name = event.get("type")
            if name in {"thread.started", "turn.started", "turn.completed", "turn.failed", "error"}:
                events.append({"type": name})
        if code != 0:
            raise Problem(f"Codex退出码为{code}；检查本机执行环境后重试", 503)
        path = folder / "outputs" / "result.json"
        if (folder / "outputs").is_symlink() or not path.resolve().is_relative_to(folder.resolve()):
            raise Problem("生成结果路径越出任务目录", 422)
        result = validate_result(path, job["content_type"], required)
        artifacts = {"result.json": json.dumps(result, ensure_ascii=False, indent=2)}
        # Render the validated JSON ourselves; do not ingest arbitrary model-created files.
        blocks = [f"# {result['payload'].get('title', job['topic'])}", "> 文本草稿／脚本；未生成媒体成品、未发布。"]
        for key, value in result["payload"].items():
            blocks.extend([f"## {key}", value if isinstance(value, str) else json.dumps(value, ensure_ascii=False, indent=2)])
        blocks.extend(["## 局限", json.dumps(result["limitations"], ensure_ascii=False, indent=2)])
        artifacts["content.md"] = "\n\n".join(blocks)
        return store.finish(tenant, job_id, artifacts, events[-20:])
    except (Problem, OSError, subprocess.SubprocessError, ValueError, KeyError):
        # Store a safe operational description, never an arbitrary model/error string.
        import sys
        error = sys.exc_info()[1]
        message = str(error) if isinstance(error, Problem) else "制作执行失败，请检查本机工具、任务目录与结果格式"
        store.fail(tenant, job_id, message, model_started=started)
        raise Problem(message, 503)
