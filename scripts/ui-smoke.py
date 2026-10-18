"""Start a real isolated HTTP app and exercise its JS in JSDOM."""
import subprocess
import tempfile
import threading
from pathlib import Path
from workbench.server import make_server
from workbench.store import Store

with tempfile.TemporaryDirectory() as directory:
    server = make_server(Store(Path(directory)/"test.sqlite3"), 0, capabilities={"codex_installed": False, "codex_authenticated": False, "cli_enabled": False})
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        result = subprocess.run(["node", "scripts/ui-smoke.cjs", f"http://127.0.0.1:{server.server_port}"], timeout=30)
    finally:
        server.shutdown(); server.server_close(); thread.join()
    raise SystemExit(result.returncode)
