#!/usr/bin/env python
"""短视频自动生产流水线；在线配音需要网络，成品先保存电脑等待审核。

输入一份"生产单"(spec JSON)，输出一条平台可直接上传的竖版成片。

能力链路：
    口播稿 → 免费配音(edge-tts) → 字幕时间轴 → 竖版画面(Pillow) →
    ffmpeg 合成(动态缩放+烧字幕+背景音乐) → 封面图 → 成片质检报告

不需要任何 API Key，不需要联网付费服务。全程不覆盖原始素材，只写新文件。

用法:
    python make_video.py --spec 生产单.json
    python make_video.py --spec 生产单.json --outdir D:\\输出 --keep-temp

生产单结构见同目录 生产单模板.json。
"""

from __future__ import annotations

import argparse
import json
import math
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

# --------------------------------------------------------------------------
# 工具链：显式环境变量优先，其次系统 PATH
# --------------------------------------------------------------------------
FFMPEG = Path(os.environ.get('OPS_FFMPEG') or shutil.which('ffmpeg') or 'ffmpeg.exe')
FFPROBE = Path(os.environ.get('OPS_FFPROBE') or shutil.which('ffprobe') or 'ffprobe.exe')
PYTHON = Path(os.environ.get('OPS_PY') or sys.executable)

W, H = 1080, 1920
FPS = 30
SEGMENT_TAIL = 0.45  # 每段结尾留白，避免语音贴死下一段

THEMES = {
    "medical-teal":  {"bg": "#F1F7F6", "fg": "#10302C", "accent": "#0E8F7E", "muted": "#5B7A76", "card": "#FFFFFF"},
    "swiss-blue":    {"bg": "#0B1F3A", "fg": "#FFFFFF", "accent": "#2F7DF6", "muted": "#8FA6C4", "card": "#12294A"},
    "ink-green":     {"bg": "#0E2119", "fg": "#F2F7F2", "accent": "#3FBF7F", "muted": "#8FB3A2", "card": "#143024"},
    "warn-amber":    {"bg": "#1F1708", "fg": "#FFF6E5", "accent": "#F2A33C", "muted": "#B79A6E", "card": "#2C2110"},
    "night-purple":  {"bg": "#16102B", "fg": "#F4F0FF", "accent": "#9B6BFF", "muted": "#9C93B8", "card": "#211741"},
    "warm-kraft":    {"bg": "#E8DCC8", "fg": "#2B2118", "accent": "#B5561F", "muted": "#6E5B45", "card": "#F4EBDC"},
    "clean-white":   {"bg": "#FFFFFF", "fg": "#111111", "accent": "#D93F2B", "muted": "#7A7A7A", "card": "#F4F4F5"},
    "swiss-paper":   {"bg": "#F5F2EC", "fg": "#1A1A1A", "accent": "#C8452D", "muted": "#6B6B6B", "card": "#FFFFFF"},
}

FONT_BOLD = os.environ.get('OPS_FONT_BOLD') or str(Path(os.environ.get('WINDIR','C:/Windows'))/'Fonts/msyhbd.ttc')
FONT_REG = os.environ.get('OPS_FONT_REG') or str(Path(os.environ.get('WINDIR','C:/Windows'))/'Fonts/msyh.ttc')
_FONT_CACHE: dict[tuple[str, int], ImageFont.FreeTypeFont] = {}

NO_LINE_START = "，。、；：？！）】》」』%,.;:?!)]}…"
NO_LINE_END = "（【《「『([{"


def font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    path = FONT_BOLD if bold else FONT_REG
    key = (path, size)
    if key not in _FONT_CACHE:
        _FONT_CACHE[key] = ImageFont.truetype(path, size)
    return _FONT_CACHE[key]


def wrap(draw: ImageDraw.ImageDraw, text: str, fnt, max_w: int) -> list[str]:
    """中文友好折行：按字符测宽，避免行首标点、行尾开括号。"""
    lines: list[str] = []
    for para in str(text).split("\n"):
        if not para:
            lines.append("")
            continue
        cur = ""
        for ch in para:
            trial = cur + ch
            if draw.textlength(trial, font=fnt) <= max_w:
                cur = trial
                continue
            if ch in NO_LINE_START and cur:
                cur = trial
                continue
            while cur and cur[-1] in NO_LINE_END:
                ch = cur[-1] + ch
                cur = cur[:-1]
            lines.append(cur)
            cur = ch
        lines.append(cur)
    return lines


# --------------------------------------------------------------------------
# 基础执行封装
# --------------------------------------------------------------------------
def run(cmd: list[str], cwd: Path | None = None, quiet: bool = True) -> subprocess.CompletedProcess:
    res = subprocess.run(
        [str(c) for c in cmd],
        cwd=str(cwd) if cwd else None,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if res.returncode != 0:
        tail = (res.stderr or res.stdout or "")[-1500:]
        raise RuntimeError(f"命令失败({res.returncode}): {' '.join(str(c) for c in cmd[:3])}...\n{tail}")
    return res


def probe_duration(path: Path) -> float:
    res = run([
        FFPROBE, "-v", "error", "-show_entries", "format=duration",
        "-of", "default=nw=1:nk=1", path,
    ])
    for line in res.stdout.splitlines():
        line = line.strip()
        if line and line.replace(".", "", 1).isdigit():
            return float(line)
    return 0.0


def probe_streams(path: Path) -> dict:
    res = run([
        FFPROBE, "-v", "error", "-show_entries",
        "stream=codec_type,codec_name,width,height,r_frame_rate:format=duration,size,bit_rate",
        "-of", "json", path,
    ])
    return json.loads(res.stdout)


# --------------------------------------------------------------------------
# 配音 + 字幕
# --------------------------------------------------------------------------
def tts(text: str, voice: str, rate: str, volume: str, mp3: Path, srt: Path, workdir: Path) -> None:
    """edge-tts：微软免费在线语音，中文自然度高，同时产出字幕时间轴。"""
    run(
        [
            PYTHON, "-m", "edge_tts",
            "--voice", voice,
            "--rate", rate,
            "--volume", volume,
            "--text", text,
            "--write-media", mp3.name,
            "--write-subtitles", srt.name,
        ],
        cwd=workdir,
    )


TIME_RE = re.compile(r"(\d{2}):(\d{2}):(\d{2})[,.](\d{3})")


def parse_srt(path: Path) -> list[tuple[float, float, str]]:
    if not path.exists():
        return []
    raw = path.read_text(encoding="utf-8", errors="replace").replace("\ufeff", "")
    cues: list[tuple[float, float, str]] = []
    for block in re.split(r"\n\s*\n", raw.strip()):
        lines = [ln.strip() for ln in block.splitlines() if ln.strip()]
        if len(lines) < 2:
            continue
        idx = 0
        if lines[0].isdigit():
            idx = 1
        if idx >= len(lines) or "-->" not in lines[idx]:
            continue
        start_s, end_s = [p.strip() for p in lines[idx].split("-->")]
        body = " ".join(lines[idx + 1:]).strip()
        sm, em = TIME_RE.search(start_s), TIME_RE.search(end_s)
        if not sm or not em or not body:
            continue

        def to_sec(m: re.Match) -> float:
            return int(m.group(1)) * 3600 + int(m.group(2)) * 60 + int(m.group(3)) + int(m.group(4)) / 1000

        cues.append((to_sec(sm), to_sec(em), body))
    return cues


def fmt_time(sec: float) -> str:
    sec = max(0.0, sec)
    h = int(sec // 3600)
    m = int((sec % 3600) // 60)
    s = int(sec % 60)
    ms = int(round((sec - int(sec)) * 1000))
    if ms == 1000:
        ms = 0
        s += 1
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def split_cue_text(text: str, max_len: int = 15) -> str:
    """字幕一行别太长：超过阈值就在标点或中点折断为两行。"""
    text = text.strip()
    if len(text) <= max_len:
        return text
    mid = len(text) // 2
    best = -1
    for i in range(max(1, mid - 6), min(len(text) - 1, mid + 6)):
        if text[i] in "，。、；：？！,.;:?!":
            best = i + 1
            break
    if best <= 0:
        best = mid
    return text[:best].rstrip() + "\n" + text[best:].lstrip()


def build_global_srt(segments: list[dict], srt_dir: Path, out_srt: Path) -> list[dict]:
    """把每段局部时间轴拼成全局字幕。"""
    blocks: list[str] = []
    timeline: list[dict] = []
    offset = 0.0
    idx = 1
    for seg in segments:
        for start, end, body in parse_srt(srt_dir / f"{seg['_id']}.srt"):
            gs = offset + start
            ge = offset + min(end, seg["_dur"] + 0.25)
            if ge <= gs:
                ge = gs + 0.6
            blocks.append(f"{idx}\n{fmt_time(gs)} --> {fmt_time(ge)}\n{split_cue_text(body)}\n")
            idx += 1
        timeline.append({"id": seg["_id"], "start": round(offset, 3), "duration": round(seg["_dur"], 3)})
        offset += seg["_dur"] + SEGMENT_TAIL
    out_srt.write_text("\n".join(blocks), encoding="utf-8")
    return timeline


# --------------------------------------------------------------------------
# 竖版画面（1080×1920）
# --------------------------------------------------------------------------
def draw_header(d: ImageDraw.ImageDraw, theme: dict, tag: str, brand: str, size: tuple[int, int]) -> int:
    Wp, _ = size
    m = int(Wp * 0.068)
    y = int(Wp * 0.052)
    if tag:
        f = font(int(Wp * 0.03), bold=True)
        tw = d.textlength(tag, font=f)
        ph = int(Wp * 0.072)
        d.rounded_rectangle([m, y, m + tw + int(Wp * 0.052), y + ph], radius=ph // 2, fill=theme["accent"])
        d.text((m + int(Wp * 0.026), y + (ph - int(Wp * 0.03) * 1.28) / 2), tag, font=f, fill=theme["bg"])
    if brand:
        f = font(int(Wp * 0.028))
        bw = d.textlength(brand, font=f)
        d.text((Wp - m - bw, y + int(Wp * 0.012)), brand, font=f, fill=theme["muted"])
    return y + int(Wp * 0.072)


def draw_bottom_scrim(img: Image.Image, theme: dict, height_ratio: float = 0.26) -> Image.Image:
    """底部压暗/压亮，保证烧录字幕清晰可读。"""
    Wp, Hp = img.size
    h = int(Hp * height_ratio)
    overlay = Image.new("RGBA", (Wp, h), (0, 0, 0, 0))
    dd = ImageDraw.Draw(overlay)
    dark = theme["bg"].lstrip("#")
    r, g, b = int(dark[0:2], 16), int(dark[2:4], 16), int(dark[4:6], 16)
    lum = 0.299 * r + 0.587 * g + 0.114 * b
    tone = (0, 0, 0) if lum > 140 else (255, 255, 255)
    for i in range(h):
        alpha = int(150 * (i / h) ** 1.4)
        dd.line([(0, i), (Wp, i)], fill=tone + (alpha,))
    base = img.convert("RGBA")
    base.alpha_composite(overlay, (0, Hp - h))
    return base.convert("RGB")


def draw_footer(d: ImageDraw.ImageDraw, theme: dict, text: str, size: tuple[int, int], resume_y: int) -> int:
    Wp, Hp = size
    m = int(Wp * 0.068)
    if not text:
        return resume_y
    f = font(int(Wp * 0.026))
    lines = wrap(d, text, f, Wp - 2 * m)
    lh = int(Wp * 0.042)
    y = Hp - int(Hp * 0.30) - lh * len(lines)
    for ln in lines:
        d.text((m, y), ln, font=f, fill=theme["muted"])
        y += lh
    return y


def render_frame(seg: dict, idx: int, total: int, theme: dict, brand: str,
                 out_png: Path, disclaimer: str = "", cover: bool = False) -> int:
    """渲染一帧竖版画面，返回内容底部 y 坐标（用于版式安全区检查）。"""
    size = (W, H)
    img = Image.new("RGB", size, theme["bg"])
    d = ImageDraw.Draw(img)
    m = int(W * 0.068)
    content_w = W - 2 * m
    content_bottom = 0

    draw_header(d, theme, seg.get("tag") or f"{idx:02d}/{total:02d}", brand, size)

    y = int(H * 0.20)
    title_f = font(int(W * (0.094 if cover else 0.084)), bold=True)
    title = seg.get("title") or seg.get("screen") or ""
    if title:
        d.rounded_rectangle([m, y, m + int(W * 0.014), y + int(W * 0.10)], radius=int(W * 0.007), fill=theme["accent"])
        lines = wrap(d, title, title_f, content_w - int(W * 0.05))
        lh = int(title_f.size * 1.32)
        ty = y
        for ln in lines:
            d.text((m + int(W * 0.042), ty), ln, font=title_f, fill=theme["fg"])
            ty += lh
        y = ty + int(H * 0.022)

    sub = seg.get("sub") or ""
    if sub:
        sub_f = font(int(W * 0.044))
        for ln in wrap(d, sub, sub_f, content_w):
            d.text((m, y), ln, font=sub_f, fill=theme["muted"])
            y += int(sub_f.size * 1.45)
        y += int(H * 0.012)
    content_bottom = max(content_bottom, y)

    bullets = seg.get("bullets") or []
    if bullets:
        bf = font(int(W * 0.046))
        lh = int(bf.size * 1.5)
        panel_h = lh * len(bullets) + int(H * 0.036)
        d.rounded_rectangle([m, y, W - m, y + panel_h], radius=int(W * 0.028), fill=theme["card"])
        by = y + int(H * 0.018)
        for i, item in enumerate(bullets, 1):
            dot_x = m + int(W * 0.036)
            d.ellipse([dot_x, by + int(bf.size * 0.34), dot_x + int(W * 0.018), by + int(bf.size * 0.34) + int(W * 0.018)],
                      fill=theme["accent"])
            for j, ln in enumerate(wrap(d, str(item), bf, content_w - int(W * 0.12))):
                d.text((dot_x + int(W * 0.036), by), ln, font=bf, fill=theme["fg"])
                by += lh
        y += panel_h + int(H * 0.02)
        content_bottom = max(content_bottom, y)

    if seg.get("footer"):
        content_bottom = max(content_bottom, draw_footer(d, theme, seg["footer"], size, y))
    if disclaimer and idx == total:
        content_bottom = max(content_bottom, draw_footer(d, theme, disclaimer, size, y))

    img = draw_bottom_scrim(img, theme)
    img.save(out_png, "PNG")
    return content_bottom


# --------------------------------------------------------------------------
# 视频合成
# --------------------------------------------------------------------------
def build_segment_video(png: Path, mp3: Path, dur: float, out_mp4: Path, workdir: Path,
                        zoom: bool = True) -> None:
    frames = max(1, int(math.ceil(dur * FPS)))
    if zoom:
        vf = (
            f"[0:v]scale={int(W * 1.25)}:{int(H * 1.25)}:force_original_aspect_ratio=increase,"
            f"crop={int(W * 1.25)}:{int(H * 1.25)},"
            f"zoompan=z='min(1.0+0.00045*on,1.10)':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)'"
            f":d=1:s={W}x{H}:fps={FPS}[v]"
        )
    else:
        vf = f"[0:v]scale={W}:{H},setsar=1[v]"
    run([
        FFMPEG, "-y", "-loop", "1", "-framerate", str(FPS), "-i", png,
        "-i", mp3,
        "-filter_complex", vf,
        "-map", "[v]", "-map", "1:a",
        "-t", f"{dur:.3f}",
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "19", "-pix_fmt", "yuv420p",
        "-r", str(FPS), "-g", str(FPS * 2), "-keyint_min", str(FPS),
        "-c:a", "aac", "-b:a", "160k", "-ar", "44100", "-ac", "2",
        "-movflags", "+faststart",
        out_mp4.name,
    ], cwd=workdir)


def concat_videos(parts: list[Path], out_mp4: Path, workdir: Path) -> None:
    listing = workdir / "concat.txt"
    listing.write_text("".join(f"file '{p.name}'\n" for p in parts), encoding="utf-8")
    run([FFMPEG, "-y", "-f", "concat", "-safe", "0", "-i", listing.name, "-c", "copy", out_mp4.name], cwd=workdir)


def finalize(video: Path, srt: Path, bgm: Path | None, out_mp4: Path, workdir: Path) -> None:
    """烧字幕 + 混背景音乐。subtitles 滤镜用相对路径，规避 Windows 盘符冒号问题。"""
    style = "FontName=Microsoft YaHei,FontSize=17,PrimaryColour=&H00FFFFFF,BorderStyle=1,Outline=2,Shadow=0,MarginV=70,Alignment=2"
    if bgm and Path(bgm).exists():
        fc = (
            f"[0:v]subtitles={srt.name}:force_style='{style}'[v];"
            f"[1:a]volume=0.14,afade=t=in:st=0:d=1.2[b];"
            f"[0:a][b]amix=inputs=2:duration=first:dropout_transition=0[a]"
        )
        run([
            FFMPEG, "-y", "-i", Path(video).resolve(), "-i", Path(bgm).resolve(),
            "-filter_complex", fc,
            "-map", "[v]", "-map", "[a]",
            "-c:v", "libx264", "-preset", "medium", "-crf", "20", "-pix_fmt", "yuv420p",
            "-c:a", "aac", "-b:a", "160k", "-movflags", "+faststart",
            str(Path(out_mp4).resolve()),
        ], cwd=workdir)
    else:
        run([
            FFMPEG, "-y", "-i", Path(video).resolve(),
            "-vf", f"subtitles={srt.name}:force_style='{style}'",
            "-c:v", "libx264", "-preset", "medium", "-crf", "20", "-pix_fmt", "yuv420p",
            "-c:a", "copy", "-movflags", "+faststart",
            str(Path(out_mp4).resolve()),
        ], cwd=workdir)


# --------------------------------------------------------------------------
# 质检
# --------------------------------------------------------------------------
def quality_check(out_mp4: Path, cover: Path, report_path: Path, spec: dict) -> dict:
    info = probe_streams(out_mp4)
    video = next((s for s in info.get("streams", []) if s.get("codec_type") == "video"), {})
    audio = next((s for s in info.get("streams", []) if s.get("codec_type") == "audio"), {})
    dur = float(info.get("format", {}).get("duration", 0) or 0)
    w, h = video.get("width"), video.get("height")
    checks = {
        "分辨率竖版1080x1920": (w, h) == (W, H),
        "有音轨": bool(audio),
        "音轨编码AAC": audio.get("codec_name") == "aac",
        "视频编码H264": video.get("codec_name") == "h264",
        "时长在15-180秒": 15 <= dur <= 180,
        "封面存在": cover.exists() and cover.stat().st_size > 0,
    }
    texts = " ".join(seg.get("text", "") for seg in spec.get("segments", [])) + " " + spec.get("disclaimer", "")
    if spec.get("regulated_health", False):
        checks["含就医提示"] = ("就医" in texts) or ("医院" in texts) or ("就诊" in texts)
        checks["含免责声明"] = bool(spec.get("disclaimer", "").strip())
    report = {
        "成片": str(out_mp4),
        "封面": str(cover),
        "时长秒": round(dur, 2),
        "体积MB": round(out_mp4.stat().st_size / 1024 / 1024, 2),
        "分辨率": f"{w}x{h}",
        "码率kbps": round(int(info.get("format", {}).get("bit_rate", 0) or 0) / 1000),
        "检查项": checks,
        "全部通过": all(checks.values()),
        "生成时间": time.strftime("%Y-%m-%d %H:%M:%S"),
    }
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return report


# --------------------------------------------------------------------------
# 主流程
# --------------------------------------------------------------------------
def main() -> int:
    ap = argparse.ArgumentParser(description="短视频自动生产流水线")
    ap.add_argument("--spec", required=True, help="生产单 JSON 路径")
    ap.add_argument("--outdir", default=None, help="输出目录，默认 输出\\<标题>")
    ap.add_argument("--keep-temp", action="store_true", help="保留中间产物")
    ap.add_argument("--no-zoom", action="store_true", help="关闭动态缩放")
    args = ap.parse_args()

    spec_path = Path(args.spec).resolve()
    spec = json.loads(spec_path.read_text(encoding="utf-8"))

    title = spec.get("title") or "未命名"
    safe_title = re.sub(r'[\\/:*?"<>|\s]+', "_", title)[:40]
    outdir = Path(args.outdir) if args.outdir else (OPS / "输出" / safe_title)
    outdir = outdir.resolve()
    outdir.mkdir(parents=True, exist_ok=True)

    theme = THEMES.get(spec.get("theme", "medical-teal"))
    if theme is None:
        raise SystemExit(f"未知主题 {spec.get('theme')}，可选：{', '.join(THEMES)}")
    brand = spec.get("brand", "")
    voice = spec.get("voice", "zh-CN-XiaoxiaoNeural")
    rate = spec.get("rate", "+8%")
    volume = spec.get("volume", "+0%")
    disclaimer = spec.get("disclaimer", "")
    segments = spec.get("segments") or []
    if not segments:
        raise SystemExit("生产单里 segments 为空，没有内容可生产。")
    if len(segments) > 12:
        raise SystemExit(f"分段过多({len(segments)})，短视频建议 6-10 段。")

    print(f"[1/6] 生产单：{title}  共 {len(segments)} 段")
    tmp = Path(tempfile.mkdtemp(prefix="vid_", dir=str(outdir)))
    try:
        # ---- 配音 + 分段字幕
        print("[2/6] 生成配音与字幕时间轴 (edge-tts 免费)...")
        for i, seg in enumerate(segments, 1):
            sid = f"seg{i:02d}"
            seg["_id"] = sid
            text = (seg.get("text") or "").strip()
            if not text:
                raise SystemExit(f"第 {i} 段缺少 text 口播稿")
            tts(text, voice, rate, volume, tmp / f"{sid}.mp3", tmp / f"{sid}.srt", tmp)
            seg["_dur"] = probe_duration(tmp / f"{sid}.mp3")
            print(f"      {sid}  {seg['_dur']:.2f}s  {text[:18]}...")

        # ---- 画面
        print("[3/6] 渲染竖版画面...")
        layout: dict[str, int] = {}
        for i, seg in enumerate(segments, 1):
            layout[seg["_id"]] = render_frame(
                seg, i, len(segments), theme, brand, tmp / f"{seg['_id']}.png", disclaimer)
        cover_png = outdir / f"{safe_title}_封面.png"
        render_frame(
            {"tag": spec.get("tag", "封面"), "title": title, "sub": spec.get("cover_sub", "")},
            1, len(segments), theme, brand, cover_png, disclaimer, cover=True,
        )
        (outdir / f"{safe_title}_版式检查.json").write_text(
            json.dumps(layout, ensure_ascii=False, indent=2), encoding="utf-8")

        # ---- 分段视频
        print("[4/6] 合成分段视频...")
        parts: list[Path] = []
        for seg in segments:
            part = tmp / f"{seg['_id']}.mp4"
            build_segment_video(
                tmp / f"{seg['_id']}.png", tmp / f"{seg['_id']}.mp3",
                seg["_dur"] + SEGMENT_TAIL, part, tmp, zoom=not args.no_zoom,
            )
            parts.append(part)
        concat_videos(parts, tmp / "concat.mp4", tmp)

        # ---- 字幕 + 音乐
        print("[5/6] 烧字幕 / 混音...")
        build_global_srt(segments, tmp, tmp / "sub.srt")
        out_mp4 = outdir / f"{time.strftime('%Y%m%d')}_{safe_title}_成片.mp4"
        finalize(tmp / "concat.mp4", tmp / "sub.srt", spec.get("bgm"), out_mp4, tmp)
        shutil.copy2(tmp / "sub.srt", outdir / f"{safe_title}_字幕.srt")

        # ---- 质检
        print("[6/6] 质检...")
        report = quality_check(out_mp4, cover_png, outdir / f"{safe_title}_质检报告.json", spec)
        report["字幕"] = str(outdir / f"{safe_title}_字幕.srt")
        record = {
            "标题": title, "平台": spec.get("platform", ""), "主题": spec.get("theme", "medical-teal"),
            "段数": len(segments), "时长秒": report["时长秒"], "成片": str(out_mp4), "封面": str(cover_png),
            "质检通过": report["全部通过"],
        }
        (outdir / f"{safe_title}_交付单.json").write_text(
            json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")

        print("\n====== 交付 ======")
        for k, v in report.items():
            if k != "检查项":
                print(f"  {k}: {v}")
        bad = [k for k, v in report["检查项"].items() if not v]
        print(f"  质检: {'全部通过' if not bad else '未通过 -> ' + '、'.join(bad)}")
        print(f"  输出目录: {outdir}")
        return 0 if not bad else 2
    finally:
        if not args.keep_temp:
            shutil.rmtree(tmp, ignore_errors=True)
        else:
            print(f"  中间产物保留在: {tmp}")


if __name__ == "__main__":
    sys.exit(main())
