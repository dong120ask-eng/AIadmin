"""中文图文卡片渲染器 —— 离线可用，像素精确，不需要任何 API Key。

用法:
    python render_cards.py --spec spec.json

spec.json 结构见 SKILL.md。输出为精确尺寸 PNG，适合小红书图文、公众号封面、
视频号封面、朋友圈九宫格。
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from PIL import Image, ImageDraw, ImageFont

SIZES = {
    "3:4": (1080, 1440),
    "1:1": (1080, 1080),
    "4:3": (1440, 1080),
    "9:16": (1080, 1920),
    "16:9": (1920, 1080),
    "21:9": (2100, 900),
}

THEMES = {
    "swiss-blue":    {"bg": "#0B1F3A", "fg": "#FFFFFF", "accent": "#2F7DF6", "muted": "#8FA6C4", "card": "#12294A"},
    "swiss-paper":   {"bg": "#F5F2EC", "fg": "#1A1A1A", "accent": "#C8452D", "muted": "#6B6B6B", "card": "#FFFFFF"},
    "ink-green":     {"bg": "#0E2119", "fg": "#F2F7F2", "accent": "#3FBF7F", "muted": "#8FB3A2", "card": "#143024"},
    "warm-kraft":    {"bg": "#E8DCC8", "fg": "#2B2118", "accent": "#B5561F", "muted": "#6E5B45", "card": "#F4EBDC"},
    "night-purple":  {"bg": "#16102B", "fg": "#F4F0FF", "accent": "#9B6BFF", "muted": "#9C93B8", "card": "#211741"},
    "clean-white":   {"bg": "#FFFFFF", "fg": "#111111", "accent": "#D93F2B", "muted": "#7A7A7A", "card": "#F4F4F5"},
    "medical-teal":  {"bg": "#F1F7F6", "fg": "#10302C", "accent": "#0E8F7E", "muted": "#5B7A76", "card": "#FFFFFF"},
    "warn-amber":    {"bg": "#1F1708", "fg": "#FFF6E5", "accent": "#F2A33C", "muted": "#B79A6E", "card": "#2C2110"},
}

FONT_CANDIDATES = [
    (r"C:\Windows\Fonts\msyhbd.ttc", r"C:\Windows\Fonts\msyh.ttc"),
    (r"C:\Windows\Fonts\Dengb.ttf", r"C:\Windows\Fonts\Deng.ttf"),
    (r"C:\Windows\Fonts\simhei.ttf", r"C:\Windows\Fonts\simhei.ttf"),
    (r"C:\Windows\Fonts\simsunb.ttf", r"C:\Windows\Fonts\simsun.ttc"),
]

_FONT_CACHE: dict[tuple[str, int], ImageFont.FreeTypeFont] = {}


def _font_paths() -> tuple[str, str]:
    for bold, regular in FONT_CANDIDATES:
        if os.path.exists(bold) and os.path.exists(regular):
            return bold, regular
    raise SystemExit("找不到可用的中文字体，请检查 C:\\Windows\\Fonts")


BOLD_PATH, REGULAR_PATH = _font_paths()


def font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    key = (BOLD_PATH if bold else REGULAR_PATH, size)
    if key not in _FONT_CACHE:
        _FONT_CACHE[key] = ImageFont.truetype(key[0], size)
    return _FONT_CACHE[key]


NO_LINE_START = "，。、；：？！）】》」』%,.;:?!)]}"
NO_LINE_END = "（【《「『([{"


def wrap(draw: ImageDraw.ImageDraw, text: str, fnt, max_w: int) -> list[str]:
    """中文友好的折行：按字符测宽，避免行首标点、行尾开括号。"""
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
                cur = trial  # 标点跟着上一行走
                continue
            while cur and cur[-1] in NO_LINE_END:
                ch = cur[-1] + ch
                cur = cur[:-1]
            lines.append(cur)
            cur = ch
        lines.append(cur)
    return lines


def draw_block(draw, xy, text, fnt, fill, max_w, line_h, align="left"):
    x, y = xy
    for line in wrap(draw, text, fnt, max_w):
        w = draw.textlength(line, font=fnt)
        dx = x if align == "left" else (x + (max_w - w) / 2 if align == "center" else x + max_w - w)
        draw.text((dx, y), line, font=fnt, fill=fill)
        y += line_h
    return y


def new_canvas(theme: dict, size: tuple[int, int]) -> tuple[Image.Image, ImageDraw.ImageDraw]:
    img = Image.new("RGB", size, theme["bg"])
    return img, ImageDraw.Draw(img)


def header(draw, theme, W, tag, brand, idx, total):
    m = int(W * 0.06)
    if tag:
        f = font(int(W * 0.028), bold=True)
        w = draw.textlength(tag, font=f)
        draw.rounded_rectangle([m, m * 0.6, m + w + m * 0.7, m * 0.6 + int(W * 0.062)],
                               radius=int(W * 0.031), fill=theme["accent"])
        draw.text((m + m * 0.35, m * 0.6 + int(W * 0.017)), tag, font=f, fill=theme["bg"])
    if brand:
        f = font(int(W * 0.026))
        w = draw.textlength(brand, font=f)
        draw.text((W - m - w, m * 0.6 + int(W * 0.02)), brand, font=f, fill=theme["muted"])
    if total > 1 and idx:
        f = font(int(W * 0.026), bold=True)
        label = f"{idx}/{total}"
        w = draw.textlength(label, font=f)
        draw.text((W - m - w, m * 0.6 + int(W * 0.062) + int(W * 0.03)), label, font=f, fill=theme["muted"])


def footer(draw, theme, W, H, page_label):
    if not page_label:
        return
    m = int(W * 0.06)
    f = font(int(W * 0.024))
    draw.text((m, H - m * 1.4), page_label, font=f, fill=theme["muted"])


def card_cover(img, draw, theme, spec):
    W, H = img.size
    m = int(W * 0.075)
    y = int(H * 0.30)
    if spec.get("kicker"):
        f = font(int(W * 0.032), bold=True)
        y = draw_block(draw, (m, y), spec["kicker"], f, theme["accent"], W - m * 2, int(W * 0.048))
        y += int(H * 0.035)
    f = font(int(W * 0.082), bold=True)
    y = draw_block(draw, (m, y), spec.get("title", ""), f, theme["fg"], W - m * 2, int(W * 0.108))
    y += int(H * 0.03)
    draw.line([m, y, m + int(W * 0.12), y], fill=theme["accent"], width=max(3, int(W * 0.006)))
    y += int(H * 0.035)
    if spec.get("subtitle"):
        f = font(int(W * 0.040))
        draw_block(draw, (m, y), spec["subtitle"], f, theme["muted"], W - m * 2, int(W * 0.060))


def card_bullets(img, draw, theme, spec):
    W, H = img.size
    m = int(W * 0.075)
    y = int(H * 0.20)
    if spec.get("title"):
        f = font(int(W * 0.062), bold=True)
        y = draw_block(draw, (m, y), spec["title"], f, theme["fg"], W - m * 2, int(W * 0.082))
        y += int(H * 0.028)
    items = spec.get("bullets") or spec.get("items") or []
    f = font(int(W * 0.038))
    fb = font(int(W * 0.038), bold=True)
    gap = int(H * 0.022)
    for i, item in enumerate(items, 1):
        num = f"{i:02d}"
        draw.text((m, y + int(W * 0.006)), num, font=fb, fill=theme["accent"])
        text_x = m + int(W * 0.085)
        y_end = draw_block(draw, (text_x, y), item, f, theme["fg"], W - text_x - m, int(W * 0.058))
        y = y_end + gap


def card_quote(img, draw, theme, spec):
    W, H = img.size
    m = int(W * 0.09)
    f = font(int(W * 0.070), bold=True)
    y = int(H * 0.34)
    draw.text((m, y - int(W * 0.085)), "“", font=font(int(W * 0.16), bold=True), fill=theme["accent"])
    y = draw_block(draw, (m, y), spec.get("text", ""), f, theme["fg"], W - m * 2, int(W * 0.094))
    if spec.get("source"):
        y += int(H * 0.03)
        sf = font(int(W * 0.032))
        draw.text((m, y), "—— " + spec["source"], font=sf, fill=theme["muted"])


def card_steps(img, draw, theme, spec):
    W, H = img.size
    m = int(W * 0.075)
    y = int(H * 0.18)
    if spec.get("title"):
        f = font(int(W * 0.060), bold=True)
        y = draw_block(draw, (m, y), spec["title"], f, theme["fg"], W - m * 2, int(W * 0.080))
        y += int(H * 0.022)
    steps = spec.get("steps") or []
    tf = font(int(W * 0.038))
    nf = font(int(W * 0.034), bold=True)
    line_h = int(W * 0.055)
    for i, st in enumerate(steps, 1):
        r = int(W * 0.032)
        cx, cy = m + r, y + int(W * 0.030)
        draw.ellipse([cx - r, cy - r, cx + r, cy + r], fill=theme["accent"])
        nw = draw.textlength(str(i), font=nf)
        draw.text((cx - nw / 2, cy - int(W * 0.021)), str(i), font=nf, fill=theme["bg"])
        text_x = m + r * 2 + int(W * 0.035)
        y = draw_block(draw, (text_x, y), st, tf, theme["fg"], W - text_x - m, line_h) + int(H * 0.018)


def card_compare(img, draw, theme, spec):
    W, H = img.size
    m = int(W * 0.075)
    y = int(H * 0.17)
    if spec.get("title"):
        f = font(int(W * 0.058), bold=True)
        y = draw_block(draw, (m, y), spec["title"], f, theme["fg"], W - m * 2, int(W * 0.076))
        y += int(H * 0.025)
    col_w = (W - m * 2 - int(W * 0.04)) // 2
    top = y
    box_h = H - top - int(H * 0.14)
    for i, side in enumerate(("left", "right")):
        x = m + i * (col_w + int(W * 0.04))
        draw.rounded_rectangle([x, top, x + col_w, top + box_h], radius=int(W * 0.030), fill=theme["card"])
        tf = font(int(W * 0.038), bold=True)
        draw.text((x + int(W * 0.035), top + int(H * 0.030)), spec.get(f"{side}_title", side), font=tf, fill=theme["accent"])
        bf = font(int(W * 0.032))
        ty = top + int(H * 0.030) + int(W * 0.062)
        for item in spec.get(f"{side}", []):
            ty = draw_block(draw, (x + int(W * 0.035), ty), "· " + item, bf, theme["fg"],
                            col_w - int(W * 0.070), int(W * 0.050)) + int(H * 0.010)


LAYOUTS = {
    "cover": card_cover,
    "bullets": card_bullets,
    "list": card_bullets,
    "quote": card_quote,
    "steps": card_steps,
    "compare": card_compare,
}


def render(spec_path: str) -> list[str]:
    with open(spec_path, encoding="utf-8") as fh:
        spec = json.load(fh)
    theme = THEMES[spec.get("theme", "swiss-blue")]
    size = SIZES[spec.get("size", "3:4")]
    out_dir = spec.get("output_dir") or os.path.join(os.path.dirname(spec_path), "output")
    os.makedirs(out_dir, exist_ok=True)
    prefix = spec.get("filename_prefix", "card")
    brand = spec.get("brand", "")
    page_label = spec.get("page_label", "")
    cards = spec["cards"]

    written = []
    for i, card in enumerate(cards, 1):
        img, draw = new_canvas(theme, size)
        layout = card.get("layout", "bullets")
        if layout == "end":
            layout = "cover"
        if layout not in LAYOUTS:
            raise SystemExit(f"未知版式: {layout}")
        header(draw, theme, size[0], card.get("tag"), brand, i if spec.get("show_pages", True) else 0, len(cards))
        LAYOUTS[layout](img, draw, theme, card)
        footer(draw, theme, size[0], size[1], page_label)
        path = os.path.join(out_dir, f"{prefix}_{i:02d}.png")
        img.save(path, "PNG")
        written.append(path)
    return written


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--spec", required=True)
    args = ap.parse_args()
    for p in render(args.spec):
        w, h = Image.open(p).size
        print(f"OK {p}  {w}x{h}")


if __name__ == "__main__":
    main()
