"""Build a small source-only pilot package. Never include user databases or outputs."""
import argparse
import hashlib
import json
from pathlib import Path
import zipfile


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    files = list((root/'workbench').glob('*.py'))
    files += list((root/'workbench/static').glob('*'))
    files += [root/'workbench/data/media-index.json']
    files += [root/'ecommerce-suite/示例与验收'/name for name in ['ecom_tools.py','data_quality.py']]
    files += [root/name for name in ['scripts/start-ecommerce.ps1','scripts/verify-ecommerce.py','scripts/package-ecommerce.py','启动电商运营壳.cmd','tests/__init__.py','tests/test_ecommerce.py','docs/ECOMMERCE-PILOT.md','docs/ECOMMERCE-PILOT-HTTP-EVIDENCE.json','LICENSE','ecommerce-suite/LICENSE']]
    entries = {}
    for file in files:
        if file.is_symlink() or not file.is_file():
            raise ValueError('Only ordinary source files are allowed: '+str(file))
        entries[file.relative_to(root).as_posix()] = file.read_bytes()
    entries['开始试用.txt'] = ('AIadmin电商运营壳（Python源码试用包，非EXE安装器）\n安装Python3.12+后，双击“启动电商运营壳.cmd”。\n打开http://127.0.0.1:8766。先点击“载入演示数据（合成）”。\n完整字段和现场验收清单：docs/ECOMMERCE-PILOT.md。\n源码测试：python -m unittest tests.test_ecommerce -v\n独立HTTP验收：python scripts/verify-ecommerce.py\n不含真实数据或凭据，不执行任何店铺写入。\n').encode('utf-8-sig')
    manifest = {'package': 'ecommerce-operations-pilot', 'runtime': 'Python 3.12+ standard library', 'scope': 'local offline read-only', 'sha256': {name: hashlib.sha256(data).hexdigest() for name,data in sorted(entries.items())}}
    entries['SOURCE-MANIFEST.json'] = json.dumps(manifest,ensure_ascii=False,indent=2).encode()
    args.output.parent.mkdir(parents=True,exist_ok=True)
    with zipfile.ZipFile(args.output,'x',zipfile.ZIP_DEFLATED) as archive:
        for name,data in sorted(entries.items()):
            archive.writestr(name,data)
    with zipfile.ZipFile(args.output) as archive:
        assert archive.testzip() is None
        for name,sha in manifest['sha256'].items():
            assert hashlib.sha256(archive.read(name)).hexdigest()==sha
    print(json.dumps({'files':len(entries),'bytes':args.output.stat().st_size,'sha256':hashlib.sha256(args.output.read_bytes()).hexdigest()}))


if __name__=='__main__':
    main()
