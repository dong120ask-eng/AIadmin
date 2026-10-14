"""Real loopback HTTP + JSDOM; isolated QA records, no Android device calls."""
import subprocess,tempfile,threading
from pathlib import Path
from workbench.dispatch import DispatchQueue
from workbench.server import make_server
from workbench.store import Store
with tempfile.TemporaryDirectory() as directory:
    root=Path(directory)
    queue=DispatchQueue(root/'dispatch.sqlite3')
    binding={'tenant_id':'internal','project_id':'qa','account_id':'qa-account','account_unique_id':'QA-only',
             'channel_id':'taobao-guanghe','route':'android_emulator','device_udid':'emulator-5554','app_package':'com.example.qa'}
    request={'tenant_id':'internal','project_id':'qa','account_id':'qa-account','channel_id':'taobao-guanghe','content_type':'short_video','publish_mode':'draft_only'}
    queue.enqueue('internal',binding,request,'qa-inspect')
    queue.enqueue('internal',binding,request,'qa-draft','draft')
    server=make_server(Store(root/'test.sqlite3'),0,capabilities={'cli_enabled':False})
    thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
    try:result=subprocess.run(['node','scripts/dispatch-ui-smoke.cjs',f'http://127.0.0.1:{server.server_port}'],timeout=30)
    finally:server.shutdown();server.server_close();thread.join()
    raise SystemExit(result.returncode)
