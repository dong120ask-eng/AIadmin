"""Independent CLI/HTTP smoke. Only synthetic demo records in a temporary database."""
import argparse
import hashlib
import io
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import urllib.request
import zipfile
from datetime import datetime, timezone


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    with tempfile.TemporaryDirectory(prefix='电商 试用验收 ') as tmp:
        env = dict(os.environ, PYTHONUTF8='1')
        process = subprocess.Popen([sys.executable, '-m', 'workbench.ecommerce', 'serve', '--data-dir', tmp, '--port', '0'], cwd=root, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding='utf-8')
        try:
            line = process.stdout.readline()
            match = re.search(r'http://127\.0\.0\.1:\d+', line)
            if not match:
                raise RuntimeError('CLI did not report a loopback address: ' + process.stderr.read()[:1000])
            base = match[0]
            def call(path, data=None, token=None):
                headers = {'Content-Type': 'application/json'}
                if token:
                    headers['X-Workbench-Token'] = token
                req = urllib.request.Request(base + path, data=None if data is None else json.dumps(data).encode(), headers=headers)
                with urllib.request.urlopen(req, timeout=10) as response:
                    return response.status, response.read()
            assets = []
            for path, expected in [('/', b'<!doctype html>'), ('/ecommerce.js', b'textContent'), ('/ecommerce.css', b'@media')]:
                status, body = call(path)
                assert status == 200 and expected in body
                assets.append({'path': path, 'http': status})
            _, content = call('/api/ecommerce/config')
            token = json.loads(content)['token']
            _, content = call('/api/ecommerce/demo', {}, token)
            demo = json.loads(content)
            assert demo['metadata']['kind'] == 'demo'
            assert demo['analysis']['summary'] == {'sku_count': 3, 'alert_count': 6, 'profit_rows': 2, 'profit_missing_rows': 1, 'covered_net_revenue': '1100.00', 'covered_contribution_profit': '305.00'}
            issue = demo['issues'][0]
            _, content = call('/api/ecommerce/issues/' + issue['id'], {'state': '已关闭', 'owner': '合成验收人员', 'note': '仅验收本地状态留存，非实际补货', 'version': issue['version']}, token)
            assert json.loads(content)['state'] == '已关闭'
            status, raw = call('/api/ecommerce/imports/' + demo['id'] + '/export')
            with zipfile.ZipFile(io.BytesIO(raw)) as archive:
                assert archive.testzip() is None
                report = json.loads(archive.read('analysis.json'))
                assert report['issues'][0]['state'] == '已关闭'
                assert report['metadata']['kind'] == 'demo'
                assert '演示数据' in archive.read('report.md').decode()
                members = archive.namelist()
            _, template = call('/api/ecommerce/template')
            assert '记录ID' in template.decode('utf-8-sig')
            evidence = {'at_utc': datetime.now(timezone.utc).isoformat(), 'python': sys.version.split()[0], 'os': sys.platform, 'environment': 'separate CLI HTTP server process', 'data_dir_scenario': 'temporary Chinese and space path', 'binding': base, 'source_kind': 'demo', 'merchant_connected': False, 'assets_http_checks': assets, 'demo_summary': demo['analysis']['summary'], 'issue_update_and_export_readback': 'passed', 'report_zip_crc': 'passed', 'report_members': members, 'report_sha256': hashlib.sha256(raw).hexdigest(), 'template_download': 'passed', 'visual_browser_qa': 'not run by this script', 'windows_user_machine': 'not connected; not verified', 'real_business_file': 'not supplied; not verified'}
        finally:
            process.terminate()
            process.communicate(timeout=10)
    result = json.dumps(evidence, ensure_ascii=False, indent=2) + '\n'
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(result, encoding='utf-8')
    print(result)


if __name__ == '__main__':
    main()
