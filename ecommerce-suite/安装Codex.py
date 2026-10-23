"""Project-only installer. Identical installations are a no-op; edits are conflicts."""
import argparse
import hashlib
from pathlib import Path
import shutil
import tempfile


def snapshot(root):
    if root.is_symlink() or not root.is_dir():
        raise ValueError('技能路径必须为普通目录')
    result = {}
    for p in sorted(root.rglob('*')):
        if p.is_symlink() or (hasattr(p, 'is_junction') and p.is_junction()):
            raise ValueError('禁止符号链接')
        if p.is_file():
            result[p.relative_to(root).as_posix()] = hashlib.sha256(p.read_bytes()).hexdigest()
    return result


def install(project, source=None):
    source = source or Path(__file__).resolve().parent / 'Codex'
    sources = sorted(source.iterdir())
    expected = {p.name: snapshot(p) for p in sources}
    project = Path(project).absolute()
    # Refuse redirected project/ancestor paths, including Windows junctions.
    agents = project / '.agents'
    target = agents / 'skills'
    for p in [target, *target.parents]:
        if p.is_symlink() or (hasattr(p, 'is_junction') and p.is_junction()):
            raise ValueError('禁止链接或目录联接目标')
    agents.mkdir(parents=True, exist_ok=True)
    lock = agents / 'ecommerce-install.lock'
    created_files, created_dirs = [], []
    with lock.open('x', encoding='utf-8') as handle:
        handle.write('Installation in progress; inspect partial installation after abrupt termination.\n')
    try:
        conflicts = [name for name, tree in expected.items()
                     if (target / name).exists() and snapshot(target / name) != tree]
        if conflicts:
            raise ValueError('存在用户修改，未复制技能：' + ', '.join(conflicts))
        with tempfile.TemporaryDirectory(prefix='ecommerce-stage-', dir=agents) as temp:
            stage = Path(temp)
            for p in sources:
                shutil.copytree(p, stage / p.name)
            if not target.exists():
                target.mkdir(); created_dirs.append(target)
            for name in expected:
                dest = target / name
                if dest.exists():
                    continue
                dest.mkdir(); created_dirs.append(dest)
                for p in sorted((stage / name).rglob('*')):
                    out = dest / p.relative_to(stage / name)
                    if p.is_dir():
                        out.mkdir(); created_dirs.append(out)
                    else:
                        with out.open('xb') as f:
                            created_files.append(out)
                            f.write(p.read_bytes())
        return len(sources)
    except BaseException:
        for p in reversed(created_files):
            p.unlink(missing_ok=True)
        for p in reversed(created_dirs):
            p.rmdir()
        raise
    finally:
        lock.unlink(missing_ok=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('project', type=Path)
    args = parser.parse_args()
    try:
        count = install(args.project)
    except (OSError, ValueError) as exc:
        parser.exit(2, str(exc) + '\n')
    print('已核验', count, '个技能；相同版本重复安装不写入，客户端识别仍需验证')


if __name__ == '__main__':
    main()
