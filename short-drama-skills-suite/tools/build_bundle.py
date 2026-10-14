import hashlib
import json
from pathlib import Path
import shutil
import sys
import zipfile

SKILLS = ['short-drama-hub', 'cn-drama-director', 'global-short-drama', 'drama-assets', 'drama-postproduction', 'drama-release', 'drama-growth', 'drama-market-research']


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    root = Path(__file__).resolve().parent.parent
    source = root/'skills' if (root/'skills').is_dir() else root
    out = root / '短剧生产技能套装'
    out.mkdir(exist_ok=True)
    for name in SKILLS:
        shutil.copytree(source/name, out/'skills'/name, dirs_exist_ok=True, ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
    (out/'tools').mkdir(exist_ok=True)
    shutil.copyfile(root/'tools/deploy.py', out/'tools/deploy.py')
    shutil.copyfile(root/'短剧技能套装_功能部署操作与优化说明.md', out/'短剧技能套装_功能部署操作与优化说明.md')
    shutil.copyfile(root/'市场适配审查与升级记录.md', out/'市场适配审查与升级记录.md')
    (out/'verification').mkdir(exist_ok=True)
    for name in ['test_bundle.py','run_checks.py','verify_bundle.py','验收记录.json','verification-summary.json']:
        if (root/'verification'/name).exists():
            shutil.copyfile(root/'verification'/name, out/'verification'/name)
    (out/'examples').mkdir(exist_ok=True)
    shutil.copyfile(source/'global-short-drama/assets/project.example.json', out/'examples/project.example.json')
    shutil.copyfile(source/'drama-growth/assets/metrics.example.csv', out/'examples/metrics.example.csv')
    (out/'packages').mkdir(exist_ok=True)
    for name in SKILLS:
        with zipfile.ZipFile(out/'packages'/f'{name}.zip','w',zipfile.ZIP_DEFLATED) as z:
            for path in sorted((out/'skills'/name).rglob('*')):
                if path.is_file():
                    z.write(path,str(Path(name)/path.relative_to(out/'skills'/name)))
    files = []
    for path in sorted(out.rglob('*')):
        if path.is_file() and path.name != 'bundle-manifest.json':
            files.append({'path': path.relative_to(out).as_posix(), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest(), 'bytes': path.stat().st_size})
    (out/'bundle-manifest.json').write_text(json.dumps({'schema_version':1,'skills':SKILLS,'files':files,'real_api_acceptance':False,'installed':False},ensure_ascii=False,indent=2),encoding='utf-8')
    archive = root/'短剧生产技能套装.zip'
    with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED) as z:
        for path in sorted(out.rglob('*')):
            if path.is_file():
                z.write(path, str(Path(out.name)/path.relative_to(out)))
    print(json.dumps({'folder':str(out),'archive':str(archive),'skills':len(SKILLS),'files':len(files)},ensure_ascii=False))


if __name__ == '__main__':
    main()
