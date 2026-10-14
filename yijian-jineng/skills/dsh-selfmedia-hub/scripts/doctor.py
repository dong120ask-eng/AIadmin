"""Read-only environment audit; never installs dependencies or reads credentials."""
import argparse
import importlib.util
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--output")
    p.add_argument('--workspace',default=str(Path.cwd()))
    a = p.parse_args()
    user = Path(os.environ.get("USERPROFILE", Path.home()))
    center = user / "Documents/Codex/自媒体运营中心"
    codex = user / ".codex/skills"
    dsh = user / ".dsh/skills"
    selected = ["cn-card-render", "cn-video-auto", "cn-video-pipeline", "douyin-publish",
                "xiaohongshu-ops", "xiaohongshu-automation", "wechat-publisher",
                "wechat-article-suite", "toutiao-health-content", "social-push"]
    known = {
        "cards_renderer": codex / "cn-card-render/scripts/render_cards.py",
        "video_maker": center / "自动化/make_video.py",
        "video_verify": center / "自动化/verify_output.py",
        "codex_python": user / ".cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe",
        "dsh_python": user / ".dsh/dsh-runtimes/dsh-primary-runtime/dependencies/python/python.exe",
        "historical_ffmpeg": center / "tools/ffmpeg/bin/ffmpeg.exe",
        "historical_node": center / "tools/node/node.exe",
    }
    tools = {n: {"path": shutil.which(n), "found": shutil.which(n) is not None} for n in ("adb", "scrcpy", "ffmpeg", "ffprobe", "node")}
    result = {"python_used": sys.executable, "tools": tools,
              "known_paths": {k: {"path": str(v), "exists": v.is_file()} for k,v in known.items()},
              "local_skills": {n: (codex / n / "SKILL.md").is_file() for n in selected},
              "existing_dsh_skill_names": sorted(f.name for f in dsh.iterdir() if f.is_dir() and (f / "SKILL.md").is_file()) if dsh.exists() else [],
              "current_python_modules": {n: importlib.util.find_spec(n) is not None for n in ("PIL","edge_tts","numpy","uiautomator2","yaml")},
              "note": "文件存在不代表实跑通过；不读取配置、密码、Cookie、令牌。"}
    if tools["adb"]["found"]:
        r = subprocess.run([tools["adb"]["path"], "devices", "-l"], capture_output=True, timeout=30)
        result["adb_devices"] = r.stdout.decode("utf-8", errors="replace")
        result["adb_exit_code"] = r.returncode
    raw = json.dumps(result, ensure_ascii=False, indent=2)
    skill_root=Path(__file__).resolve().parents[2]
    result['bundled_resources']={name:str(skill_root/'desktop-media-production/scripts'/name) for name in ('render_cards.py','make_video.py','verify_output.py')}
    result['project_skills']={host:sorted(f.parent.name for f in (Path(a.workspace)/host/'skills').glob('*/SKILL.md')) for host in ('.dsh','.codebuddy','.agents')}
    raw = json.dumps(result, ensure_ascii=False, indent=2)
    if a.output:
        out = Path(a.output)
        out.parent.mkdir(parents=True, exist_ok=True)
        with out.open("x", encoding="utf-8") as f:
            f.write(raw + "\n")
    print(raw)

if __name__ == "__main__":
    main()
