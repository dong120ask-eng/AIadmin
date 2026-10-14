"""Read-only workspace progress and Chinese next-step dashboard. Never operates a device."""
import argparse
import html
import json
import shutil
import sqlite3
from collections import Counter
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path

BUNDLE = Path(__file__).resolve().parents[1]
STATES = {
    'prepared': ('待质检', '核对事实、素材权利和正文，再运行 content-quality-gate。'),
    'reviewed': ('待草稿', '选定真实账号和已校准页面，准备草稿。'),
    'draft': ('待预览确认', '检查真实草稿、账号和可见性，确认后再批准。'),
    'approved': ('已批准待提交', '重新核对当前账号与素材，使用单次提交流程。'),
    'publishing': ('提交中待核验', '先到平台核验作品；不要再次点击发布。'),
    'uncertain': ('结果不明需恢复', '使用 publishing-recovery 核验是否已发布；保留设备锁。'),
    'published': ('已发布待复盘', '导入平台真实数据，观察 2h/24h/72h 表现。'),
}

def read_json(path):
    return json.loads(path.read_text(encoding='utf-8-sig'))

def snapshot(root, bundle=BUNDLE):
    root = Path(root).resolve()
    bundle = Path(bundle).resolve()
    if not root.is_dir():
        raise ValueError('工作目录不存在，请选择已部署项目文件夹。')
    errors = []
    manifest = read_json(bundle / 'config/skill-manifest.json')
    tasks, locks, accounts = [], [], 0
    database = root / 'state/selfmedia.sqlite'
    if database.exists():
        try:
            # URI read-only: neither creates a database nor migrates its schema.
            with closing(sqlite3.connect(database.resolve().as_uri() + '?mode=ro', uri=True, timeout=3)) as db:
                accounts = db.execute('SELECT COUNT(*) FROM instances').fetchone()[0]
                for key, body in db.execute('SELECT id, body FROM tasks ORDER BY id'):
                    try:
                        item = json.loads(body)
                        state = item.get('state', 'unknown')
                        label, action = STATES.get(state, ('状态待检查', '检查任务台账和证据，不自动重试。'))
                        tasks.append({'id': key, 'state': state, 'label': label, 'next': action,
                                      'platform': item.get('instance', {}).get('platform', '未指定')})
                    except (ValueError, TypeError, AttributeError):
                        errors.append('任务记录无法解析：' + key)
                # Do not export physical device identifiers or account IDs.
                locks = [row[0] for row in db.execute('SELECT task FROM locks ORDER BY task')]
        except sqlite3.Error as exc:
            errors.append('台账暂不可读：' + type(exc).__name__ + '；保留原文件，检查是否被占用或需要恢复。')
    counts = dict(Counter(t['state'] for t in tasks))
    priorities = []
    if counts.get('uncertain') or counts.get('publishing'):
        priorities.append('优先核验提交结果不明的任务，再安排该设备的新任务。')
    if errors:
        priorities.append('先处理台账读取错误；当前统计可能不完整。')
    if not accounts:
        priorities.append('首次使用：登记一个真实账号、一个设备实例，从一条样稿开始。')
    if not tasks:
        priorities.append('提供产品资料、目标人群和一个平台，完成策划与电脑样稿；示例配置不能直接当真实账号。')
    if locks:
        priorities.append('有设备锁：按任务核对当前页面；不要直接删锁或重复提交。')
    if not priorities:
        priorities.append('按任务表的下一步继续；先完成一条内容的完整闭环，再扩大账号矩阵。')
    return {
        'schema': 'selfmedia-progress/v1', 'captured_at': datetime.now(timezone.utc).isoformat(),
        'workspace': str(root), 'version': manifest['version'],
        'development': {'skills': manifest['skill_count'], 'platform_flows': manifest['platform_count'],
                        'note': '技能存在与回归测试通过，不等于各平台真实发布已验收。'},
        'runtime_acceptance': '真实账号、页面、模拟器与发布验收需逐项留证；本进度台不推断通过。',
        'accounts_registered': accounts, 'task_counts': counts, 'tasks': tasks,
        'locked_task_ids': locks, 'warnings': errors, 'next_steps': priorities,
        'local_tools': {name: bool(shutil.which(name)) for name in ('adb', 'ffmpeg', 'scrcpy', 'memuc')},
        'tool_note': '仅检查 PATH 可发现性；未发现不代表未安装，发现不代表设备已连接或软件已验收。',
    }

def render(data):
    def esc(value):
        return html.escape(str(value), quote=True)
    rows = ''.join('<tr><td>' + esc(t['id']) + '</td><td>' + esc(t['platform']) +
                   '</td><td>' + esc(t['label']) + '</td><td>' + esc(t['next']) + '</td></tr>'
                   for t in data['tasks']) or '<tr><td colspan="4">还没有内容任务，从一条样稿开始。</td></tr>'
    next_steps = ''.join('<li>' + esc(x) + '</li>' for x in data['next_steps'])
    warnings = ''.join('<p class="warning">' + esc(x) + '</p>' for x in data['warnings'])
    return ('''<!doctype html><html lang="zh-CN"><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>自媒体工作进度台</title><style>
body{font-family:system-ui,"Microsoft YaHei",sans-serif;max-width:1100px;margin:32px auto;padding:0 20px;color:#203047;background:#f4f7fb}
section{background:white;border-radius:12px;padding:20px;margin:18px 0}h1{font-size:28px}h2{font-size:20px}
.cards{display:flex;gap:16px;flex-wrap:wrap}.card{background:#e9f1ff;padding:18px;border-radius:8px;flex:1;min-width:150px}.card strong{font-size:30px;display:block}
table{border-collapse:collapse;width:100%}td,th{padding:12px;text-align:left;border-bottom:1px solid #dde4ee;vertical-align:top}.scroll{overflow:auto}
small{color:#53657d}.warning{color:#a33b19}li{margin:10px 0}button,input{font:inherit;padding:8px;border:1px solid #abbdd4;border-radius:6px}button{cursor:pointer}
</style><h1>自媒体工作进度台</h1><small>快照时间：''' + esc(data['captured_at']) + ' · ' + esc(data['version']) + '''</small>
<section class="cards"><div class="card"><strong>''' + esc(data['development']['skills']) + '''</strong>已开发技能</div>
<div class="card"><strong>''' + esc(data['development']['platform_flows']) + '''</strong>平台流程</div>
<div class="card"><strong>''' + esc(len(data['tasks'])) + '''</strong>真实台账任务</div>
<div class="card"><strong>''' + esc(len(data['locked_task_ids'])) + '''</strong>设备占用任务</div></section>
<section><h2>现在该做什么</h2><ol>''' + next_steps + '</ol>' + warnings + '''
<p>建议顺序：产品策划 → 样本拆解 → 一条样稿 → 电脑素材 → 质检 → 真实账号草稿 → 预览确认 → 单次提交与核验 → 数据复盘。</p></section>
<section><h2>任务进度</h2><label>筛选任务或平台 <input id="filter" placeholder="输入任务 ID 或平台"></label>
<button onclick="document.getElementById('filter').value='';filterRows()">清空筛选</button>
<div class="scroll"><table><thead><tr><th>任务</th><th>平台</th><th>当前环节</th><th>下一步</th></tr></thead><tbody id="tasks">''' + rows + '''</tbody></table></div></section>
<section><h2>验收边界与刷新</h2><p>''' + esc(data['runtime_acceptance']) + '''</p>
<p>这是离线快照，不会自动刷新、调用模型、连接手机或发布内容。重新运行进度入口会更新快照。统计不导出账号 ID、设备序列号、正文或凭据。</p>
<p>工作目录：''' + esc(data['workspace']) + '''</p><p>软件检查：''' +
esc('；'.join(k + (' PATH 可发现' if v else ' PATH 未发现') for k, v in data['local_tools'].items())) +
'''</p><small>''' + esc(data['tool_note']) + '''</small></section>
<script>function filterRows(){let q=document.getElementById('filter').value.toLowerCase();document.querySelectorAll('#tasks tr').forEach(r=>r.hidden=!r.textContent.toLowerCase().includes(q))}document.getElementById('filter').addEventListener('input',filterRows);</script></html>''')

def export(root, output=None, bundle=BUNDLE):
    root = Path(root).resolve()
    target = Path(output) if output else Path('work/progress-console')
    target = (target if target.is_absolute() else root / target).resolve()
    if not target.is_relative_to(root) or target == root:
        raise ValueError('进度输出必须是工作目录内的专用子目录。')
    # Fixed overwrite names are allowed only in a dedicated console directory.
    if target.exists() and any(p.name not in ('index.html', 'progress.json') for p in target.iterdir()):
        raise ValueError('输出目录有其他文件，请选择专用空目录，避免覆盖工作成果。')
    for name in ('index.html', 'progress.json'):
        if (target / name).is_symlink():
            raise ValueError('输出文件不能是符号链接。')
    data = snapshot(root, bundle)
    target.mkdir(parents=True, exist_ok=True)
    (target / 'progress.json').write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
    (target / 'index.html').write_text(render(data), encoding='utf-8')
    return target / 'index.html'

def main():
    parser = argparse.ArgumentParser(description='查看进度与下一步；不连接设备、不发布。')
    parser.add_argument('--root', required=True)
    parser.add_argument('--output')
    parser.add_argument('--json', action='store_true', help='仅输出状态，不写快照文件')
    args = parser.parse_args()
    try:
        if args.json:
            print(json.dumps(snapshot(args.root), ensure_ascii=False, indent=2))
        else:
            print('进度页面已更新：' + str(export(args.root, args.output)))
    except (ValueError, OSError, KeyError) as exc:
        print('无法生成进度页面：' + str(exc))
        return 2
    return 0

if __name__ == '__main__':
    raise SystemExit(main())
