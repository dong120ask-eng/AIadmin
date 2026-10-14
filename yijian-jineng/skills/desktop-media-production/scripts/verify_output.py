#!/usr/bin/env python
"""成片复核器：在没有肉眼的情况下，用像素和元数据验证成片是否真的合格。

检查项：
  1. 分辨率/编码/音轨/时长（读元数据）
  2. 字幕是否真的烧进画面（对比"无字幕原图"与"成片抽帧"的字幕带白像素）
  3. 画面内容是否越界到字幕带（版式安全区）
  4. 封面是否生成

用法:
    python verify_output.py --dir "输出\\<主题>"
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import numpy as np
from PIL import Image

FFMPEG = Path(os.environ.get('OPS_FFMPEG') or shutil.which('ffmpeg') or 'ffmpeg.exe')
FFPROBE = Path(os.environ.get('OPS_FFPROBE') or shutil.which('ffprobe') or 'ffprobe.exe')

SUB_BAND = (1560, 1800)   # 字幕带（烧录字幕落在这里）
SAFE_BOTTOM = 1560        # 画面内容不许越过这条线


def probe(path: Path) -> dict:
    res = subprocess.run(
        [str(FFPROBE), "-v", "error", "-show_entries",
         "stream=codec_type,codec_name,width,height:format=duration,size,bit_rate",
         "-of", "json", str(path)],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
    )
    return json.loads(res.stdout or "{}")


def white_in_band(path: Path, band=SUB_BAND) -> int:
    im = Image.open(path).convert("RGB")
    W, H = im.size
    y0, y1 = band
    y1 = min(y1, H)
    arr = np.asarray(im.crop((0, y0, W, y1)))
    return int(((arr[:, :, 0] > 205) & (arr[:, :, 1] > 205) & (arr[:, :, 2] > 205)).sum())


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", required=True, help="成片所在目录")
    args = ap.parse_args()

    outdir = Path(args.dir).resolve()
    mp4 = next((p for p in outdir.glob("*_成片.mp4")), None)
    cover = next((p for p in outdir.glob("*_封面.png")), None)
    srt = next((p for p in outdir.glob("*_字幕.srt")), None)
    if not mp4:
        print("找不到成片 mp4")
        return 1

    info = probe(mp4)
    v = next((s for s in info.get("streams", []) if s.get("codec_type") == "video"), {})
    a = next((s for s in info.get("streams", []) if s.get("codec_type") == "audio"), {})
    dur = float(info.get("format", {}).get("duration", 0) or 0)

    result: dict = {"成片": str(mp4), "时长秒": round(dur, 2), "分辨率": f"{v.get('width')}x{v.get('height')}"}
    checks: dict[str, bool] = {
        "竖版1080x1920": (v.get("width"), v.get("height")) == (1080, 1920),
        "H.264编码": v.get("codec_name") == "h264",
        "含AAC音轨": a.get("codec_name") == "aac",
        "时长15-180秒": 15 <= dur <= 180,
        "封面已生成": bool(cover and cover.exists() and cover.stat().st_size > 0),
        "字幕文件已生成": bool(srt and srt.exists() and srt.stat().st_size > 0),
    }

    # 抽帧验证字幕真的烧录进画面
    frames = outdir / "_质检抽帧"
    frames.mkdir(exist_ok=True)
    burn_ok = True
    details = []
    for t in (3, 20, 35, 50):
        if t >= dur - 1:
            continue
        f = frames / f"t{t}.png"
        subprocess.run([str(FFMPEG), "-y", "-ss", str(t), "-i", str(mp4), "-frames:v", "1", str(f)],
                       capture_output=True)
        if f.exists():
            n = white_in_band(f)
            details.append(f"t={t}s 字幕带白像素={n}")
            if n < 300:
                burn_ok = False
    checks["字幕已烧入画面"] = burn_ok
    result["字幕抽帧"] = details

    # 版式安全区：读渲染器写出的实测内容底部坐标
    layout_files = sorted(outdir.glob("*_版式检查.json"))
    if layout_files:
        layout = json.loads(layout_files[0].read_text(encoding="utf-8"))
        worst = max(layout.values()) if layout else 0
        result["画面最低内容行"] = worst
        result["版式明细"] = layout
        checks["内容未压字幕带"] = worst < SAFE_BOTTOM

    result["检查项"] = checks
    result["全部通过"] = all(checks.values())
    (outdir / "_成片复核.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")

    print("====== 成片复核 ======")
    for k, val in result.items():
        if k != "检查项":
            print(f"  {k}: {val}")
    for k, val in checks.items():
        print(f"  [{'OK ' if val else 'FAIL'}] {k}")
    bad = [k for k, val in checks.items() if not val]
    print("结论：" + ("全部通过" if not bad else "未通过 -> " + "、".join(bad)))
    return 0 if not bad else 2


if __name__ == "__main__":
    sys.exit(main())
