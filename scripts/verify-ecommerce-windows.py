"""Exercise the actual PS5.1/7 launcher on Windows, using temporary synthetic data.

Success paths run the real application. Fault fixtures are explicitly identified;
no merchant connection, model request, browser launch or store write is performed.
"""
import argparse
import ctypes
from ctypes import wintypes
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import io
import json
import os
from pathlib import Path
import re
import shutil
import socket
import subprocess
import sys
import tempfile
import threading
import time
import unittest
import urllib.request
import zipfile

ROOT = Path(__file__).resolve().parents[1]
OPTIONS = None
EVIDENCE = []


def wait_until(check, timeout=15):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        result = check()
        if result:
            return result
        time.sleep(.1)
    raise AssertionError('Timed out waiting for launcher / process cleanup')


def request(base, path='/', data=None, token=None):
    headers = {'Content-Type': 'application/json'}
    if token:
        headers['X-Workbench-Token'] = token
    with urllib.request.urlopen(urllib.request.Request(
        base + path, data=None if data is None else json.dumps(data).encode(), headers=headers,
    ), timeout=3) as response:
        return response.read()


class ProcessHandle:
    """Keep a handle to the owned process so PID reuse cannot affect cleanup."""
    def __init__(self, pid):
        self.api = ctypes.WinDLL('kernel32', use_last_error=True)
        self.api.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
        self.api.OpenProcess.restype = wintypes.HANDLE
        self.api.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
        self.api.WaitForSingleObject.restype = wintypes.DWORD
        self.api.TerminateProcess.argtypes = [wintypes.HANDLE, wintypes.UINT]
        self.api.CloseHandle.argtypes = [wintypes.HANDLE]
        self.handle = self.api.OpenProcess(0x100000 | 0x1000 | 1, False, pid)
        if not self.handle:
            raise ctypes.WinError(ctypes.get_last_error())

    def exited(self):
        return self.api.WaitForSingleObject(self.handle, 0) == 0

    def kill(self):
        if not self.exited() and not self.api.TerminateProcess(self.handle, 97):
            raise ctypes.WinError(ctypes.get_last_error())

    def close(self):
        self.api.CloseHandle(self.handle)


class LauncherTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory(prefix='电商 启动验收 ')
        cls.base = Path(cls.temp.name)
        package = cls.base / 'pilot.zip'
        subprocess.run([sys.executable, str(ROOT/'scripts/package-ecommerce.py'), '--output', str(package)],
                       cwd=ROOT, check=True, capture_output=True, timeout=30)
        cls.package = package

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def setUp(self):
        self.case = self.base / self._testMethodName
        self.source = self.case / '中文 源码 [隔离] & test'
        self.data = self.case / '中文 数据 [合成] & test'
        self.logs = self.case / '错误 日志'
        self.stop = self.case / '停止 信号.txt'
        self.case.mkdir()
        with zipfile.ZipFile(self.package) as archive:
            archive.extractall(self.source)
        with socket.socket() as sock:
            sock.bind(('127.0.0.1', 0))
            self.port = sock.getsockname()[1]
        self.base_url = f'http://127.0.0.1:{self.port}'
        self.launcher = None
        self.service = None
        self.console = open(self.case/'console.log', 'wb')
        self.details = {'test': self._testMethodName, 'shell': OPTIONS.shell,
                        'fixture': 'real application; synthetic records only'}

    def launch(self, *extra):
        env = dict(os.environ, PYTHONUTF8='1', PYTHONUNBUFFERED='1',
                   LOCALAPPDATA=str(self.case/'localappdata'), TEMP=str(self.case), TMP=str(self.case),
                   PATH=str(Path(sys.executable).parent) + os.pathsep + os.environ['PATH'])
        # Trailing separator verifies Windows argument quoting, in addition to
        # Chinese, spaces, square brackets and ampersands in source/data paths.
        self.launcher = subprocess.Popen([
            OPTIONS.shell, '-NoProfile', '-NonInteractive', '-ExecutionPolicy', 'Bypass',
            '-File', str(self.source/'scripts/start-ecommerce.ps1'),
            '-DataDir', str(self.data) + '\\', '-Port', str(self.port), '-NoBrowser',
            '-LogDir', str(self.logs), '-StopFile', str(self.stop), *extra,
        ], cwd=self.case, env=env, stdout=self.console, stderr=subprocess.STDOUT)

    def log_text(self):
        return '\n'.join(p.read_text(encoding='utf-8-sig') for p in self.case.rglob('*-launcher.log'))

    def wait_ready(self):
        def ready():
            text = self.log_text()
            if f'HTTP_READY={self.base_url}' in text:
                return text
            if self.launcher.poll() is not None:
                raise AssertionError('Launcher exited before readiness:\n' + text)
        text = wait_until(ready, 40)
        pid = int(re.search(r'SERVICE_PID=(\d+)', text)[1])
        self.service = ProcessHandle(pid)
        self.assertFalse(self.service.exited())
        self.assertIn('Python ' + sys.version.split()[0] + ' /', text)
        self.assertIn(b'<!doctype html>', request(self.base_url))
        self.details['http_ready'] = True
        return json.loads(request(self.base_url, '/api/ecommerce/config'))['token']

    def assert_stopped(self):
        if self.service:
            wait_until(self.service.exited)
        def available():
            try:
                with socket.socket() as client:
                    client.settimeout(.2)
                    if client.connect_ex(('127.0.0.1', self.port)) == 0:
                        return False
                with socket.socket() as sock:
                    # Match HTTPServer's reuse setting; TIME_WAIT is not a live
                    # listener. Handle exit + connect refusal guard false reuse.
                    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                    sock.bind(('127.0.0.1', self.port))
                return True
            except OSError:
                return False
        wait_until(available)
        self.details['owned_process_exited_and_port_reusable'] = True

    def assert_failed(self, message):
        code = self.launcher.wait(timeout=40)
        self.assertNotEqual(code, 0)
        self.assertIn(message, self.log_text())
        self.assertNotIn('HTTP_READY=', self.log_text())
        self.details['expected_failure_exit'] = code

    def fault_module(self, body):
        # Importable constants let the real launcher preflight pass. Only the
        # isolated service entry is replaced, never the actual repository file.
        (self.source/'workbench/ecommerce.py').write_text(
            'TOOLS = QUALITY = None\nif __name__ == "__main__":\n' +
            '\n'.join('    '+line for line in body.splitlines()) + '\n', encoding='utf-8')
        self.details['fixture'] = 'controlled service fault injection in temporary copy'

    def test_real_start_synthetic_http_stop_and_restart(self):
        for iteration in range(2):
            if iteration:
                self.stop.unlink()
                self.service.close()
                self.service = None
            self.launch()
            token = self.wait_ready()
            if not iteration:
                demo = json.loads(request(self.base_url, '/api/ecommerce/demo', {}, token))
                self.assertEqual(demo['metadata']['kind'], 'demo')
                self.assertEqual(demo['analysis']['summary']['covered_contribution_profit'], '305.00')
                raw = request(self.base_url, '/api/ecommerce/imports/'+demo['id']+'/export')
                with zipfile.ZipFile(io.BytesIO(raw)) as archive:
                    self.assertIsNone(archive.testzip())
                    self.assertEqual(json.loads(archive.read('analysis.json'))['metadata']['kind'], 'demo')
            else:
                self.assertIn(demo['id'], request(self.base_url, '/api/ecommerce/imports').decode())
            self.stop.touch()
            self.assertEqual(self.launcher.wait(timeout=15), 0)
            self.assert_stopped()
        self.assertTrue((self.data/'workbench.db').is_file())
        self.assertFalse((self.case/'localappdata/AIadmin/ecommerce-pilot/workbench.db').exists())
        self.details['synthetic_demo_export_and_restart_readback'] = 'passed'

    def test_check_only_never_starts_service(self):
        self.launch('-CheckOnly')
        self.assertEqual(self.launcher.wait(timeout=30), 0)
        self.assertIn('未启动服务器', self.log_text())
        self.assertNotIn('SERVICE_PID=', self.log_text())
        self.assertFalse((self.data/'workbench.db').exists())
        self.assert_stopped()

    def test_port_conflict_does_not_accept_or_kill_other_http_server(self):
        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                self.send_response(200)
                self.end_headers()
                self.wfile.write(b'{"token":"unrelated-service"}')
            def log_message(self, *_):
                pass
        other = ThreadingHTTPServer(('127.0.0.1', self.port), Handler)
        thread = threading.Thread(target=other.serve_forever, daemon=True)
        thread.start()
        try:
            self.launch()
            self.assert_failed('已被占用')
            self.assertNotIn('SERVICE_PID=', self.log_text())
            self.assertEqual(json.loads(request(self.base_url))['token'], 'unrelated-service')
            self.assertFalse((self.data/'workbench.db').exists())
        finally:
            other.shutdown()
            other.server_close()
            thread.join(timeout=5)
        self.assert_stopped()

    def test_unwritable_data_target_preserves_python_error_log(self):
        self.data.write_text('synthetic file prevents directory creation', encoding='utf-8')
        self.launch()
        self.assert_failed('服务异常退出')
        self.assertTrue(any('Error' in p.read_text(encoding='utf-8')
                            for p in self.logs.glob('*-service.stderr.log')))
        self.assert_stopped()

    def test_service_crash_before_ready_preserves_exact_stderr(self):
        self.fault_module('import sys\nprint("合成故障 exit23", file=sys.stderr, flush=True)\nsys.exit(23)')
        self.launch()
        self.assert_failed('退出码 23')
        self.assertIn('合成故障 exit23', next(self.logs.glob('*-service.stderr.log')).read_text(encoding='utf-8'))
        self.assert_stopped()

    def test_http_503_never_becomes_ready_and_timeout_cleans_process(self):
        probe = self.case/'http-probe.txt'
        self.fault_module(
            'import sys\nfrom http.server import BaseHTTPRequestHandler, HTTPServer\nfrom pathlib import Path\n'
            'class Handler(BaseHTTPRequestHandler):\n'
            '    def do_GET(self):\n'
            f'        Path({str(probe)!r}).write_text("HTTP probed")\n'
            '        self.send_response(503)\n        self.end_headers()\n'
            '    def log_message(self, *_): pass\n'
            'port = int(sys.argv[sys.argv.index("--port")+1])\n'
            'server = HTTPServer(("127.0.0.1", port), Handler)\n'
            'print(f"http://127.0.0.1:{port}", flush=True)\nserver.serve_forever()')
        self.launch('-StartupTimeoutSeconds', '3')
        self.assert_failed('HTTP 就绪检查超时')
        self.assertTrue(probe.is_file(), 'The launcher must perform real HTTP probes')
        self.assert_stopped()

    def test_service_killed_after_ready_fails_launcher(self):
        self.launch()
        self.wait_ready()
        self.service.kill()
        self.assertNotEqual(self.launcher.wait(timeout=15), 0)
        self.assertIn('服务异常退出', self.log_text())
        self.assert_stopped()

    def test_launcher_force_killed_leaves_no_service(self):
        self.launch()
        self.wait_ready()
        self.launcher.kill()  # no PowerShell finally: exercises kill-on-job-close
        self.launcher.wait(timeout=10)
        self.assert_stopped()

    def test_force_kill_also_cleans_owned_descendant(self):
        pid_file = self.case/'synthetic-helper.pid'
        module = self.source/'workbench/ecommerce.py'
        code = module.read_text(encoding='utf-8')
        code = code.replace('    main()\n',
            '    import subprocess, sys\n'
            '    helper = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(120)"])\n'
            f'    Path({str(pid_file)!r}).write_text(str(helper.pid))\n'
            '    main()\n')
        module.write_text(code, encoding='utf-8')
        self.details['fixture'] = 'real app plus injected synthetic sleeping descendant'
        self.launch()
        self.wait_ready()
        descendant = ProcessHandle(int(pid_file.read_text()))
        try:
            self.launcher.kill()
            self.launcher.wait(timeout=10)
            self.assert_stopped()
            wait_until(descendant.exited)
            self.details['owned_descendant_cleanup'] = 'passed'
        finally:
            descendant.kill()
            descendant.close()

    def test_existing_stop_signal_is_rejected_before_start(self):
        self.stop.touch()
        self.launch()
        self.assert_failed('停止信号文件已存在')
        self.assertNotIn('SERVICE_PID=', self.log_text())
        self.assert_stopped()

    def test_bad_log_directory_leaves_fallback_diagnostic(self):
        self.logs.write_text('synthetic non-directory', encoding='utf-8')
        self.launch()
        self.assert_failed('启动或运行失败')
        self.assertTrue(list((self.case/'AIadmin-ecommerce-logs').glob('*-launcher.log')))
        self.assert_stopped()

    def tearDown(self):
        try:
            # Only handles/PIDs created by this case may be cleaned up.
            if self.launcher and self.launcher.poll() is None:
                self.launcher.kill()
                self.launcher.wait(timeout=10)
            if self.service:
                if not self.service.exited():
                    self.service.kill()
                    wait_until(self.service.exited)
                self.service.close()
            self.console.close()
            # Preserve diagnostics even when an assertion fails. Fixtures contain
            # only synthetic records; never upload the DB, imports, or auth token.
            target = OPTIONS.output.parent / (OPTIONS.output.stem+'-logs') / self._testMethodName
            target.mkdir(parents=True, exist_ok=True)
            for log in self.case.rglob('*.log'):
                shutil.copyfile(log, target/log.name)
        finally:
            EVIDENCE.append(self.details)


class Results(unittest.TextTestResult):
    def addSuccess(self, test):
        test.details['result'] = 'passed'
        super().addSuccess(test)

    def addFailure(self, test, err):
        test.details['result'] = 'failed'
        super().addFailure(test, err)

    def addError(self, test, err):
        if hasattr(test, 'details'):
            test.details['result'] = 'error'
        super().addError(test, err)


def main():
    global OPTIONS
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--shell', choices=['powershell', 'pwsh'], required=True)
    parser.add_argument('--output', type=Path, required=True)
    OPTIONS = parser.parse_args()
    if sys.platform != 'win32':
        parser.error('Requires Windows; Linux results must not claim PowerShell acceptance')
    OPTIONS.output = OPTIONS.output.resolve()
    OPTIONS.output.parent.mkdir(parents=True, exist_ok=True)
    version = subprocess.run([OPTIONS.shell, '-NoProfile', '-Command', '$PSVersionTable.PSVersion.ToString()'],
                             capture_output=True, text=True, check=True, timeout=15).stdout.strip()
    expected = '5.1.' if OPTIONS.shell == 'powershell' else '7.'
    if not version.startswith(expected):
        raise RuntimeError('Wrong PowerShell version: '+version)
    result = unittest.TextTestRunner(verbosity=2, resultclass=Results).run(
        unittest.defaultTestLoader.loadTestsFromTestCase(LauncherTests))
    evidence = {'at_utc': datetime.now(timezone.utc).isoformat(), 'shell': OPTIONS.shell,
                'powershell_version': version, 'python': sys.version.split()[0], 'os': sys.platform,
                'tests_run': result.testsRun, 'failures': len(result.failures), 'errors': len(result.errors),
                'skipped': len(result.skipped), 'passed': result.wasSuccessful(), 'cases': EVIDENCE,
                'scope': 'actual Windows PowerShell launcher; isolated source package and synthetic data',
                'browser_opened': False, 'merchant_connected': False, 'model_called': False,
                'windows_11_user_machine': 'not connected; not verified',
                'ctrl_c_and_cmd_double_click': 'manual operator acceptance still required'}
    OPTIONS.output.write_text(json.dumps(evidence, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    return 0 if result.wasSuccessful() else 1


if __name__ == '__main__':
    sys.exit(main())
