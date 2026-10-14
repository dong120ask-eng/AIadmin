"""Run the existing Chinese card renderer with workspace-contained outputs."""
import argparse
import json
import subprocess
import sys
import tempfile
from pathlib import Path

def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--root", required=True)
    p.add_argument("--spec", required=True)
    p.add_argument("--python", required=True)
    p.add_argument("--renderer", required=True)
    a = p.parse_args()
    root = Path(a.root).resolve()
    spec = (root / a.spec).resolve()
    if not spec.is_relative_to(root) or not spec.is_file():
        raise ValueError("规格文件必须位于工作目录")
    body = json.loads(spec.read_text(encoding="utf-8-sig"))
    out = (root / body["output_dir"]).resolve()
    if not out.is_relative_to(root) or out.exists():
        raise ValueError("output_dir 必须是工作区内的新目录，避免覆盖")
    prefix = body.get("filename_prefix", "card")
    if not isinstance(prefix, str) or any(c in prefix for c in "/\\:") or prefix in (".", ".."):
        raise ValueError("filename_prefix 无效")
    if not isinstance(body.get("cards"), list) or not body["cards"]:
        raise ValueError("cards 必须为非空数组")
    body["output_dir"] = str(out)
    tempdir = root / "work"
    tempdir.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", dir=tempdir, delete=False, encoding="utf-8") as stream:
        json.dump(body, stream, ensure_ascii=False)
        temporary = Path(stream.name)
    try:
        r = subprocess.run([a.python, a.renderer, "--spec", str(temporary)], timeout=180, cwd=root)
        if r.returncode:
            raise ValueError("渲染失败，请检查依赖与错误输出")
        if not list(out.glob("*.png")):
            raise ValueError("没有生成 PNG")
        print(json.dumps({"output_dir": str(out), "files": [str(f) for f in out.glob("*.png")]}, ensure_ascii=False))
    finally:
        temporary.unlink(missing_ok=True)

if __name__ == "__main__":
    try:
        main()
    except (ValueError, OSError, KeyError, subprocess.TimeoutExpired) as e:
        print(json.dumps({"error": str(e)}, ensure_ascii=False)); sys.exit(2)
