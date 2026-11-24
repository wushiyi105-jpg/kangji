"""生成 assets/demo.gif：960×600 的终端风演示动图。

只用 Pillow（开发期依赖，不进 requirements）。跑法：
    python scripts/make_demo_gif.py

画面里的数字都是真跑出来的：10 条样例、2 对不宜同用、模型 0 处提到箱外药。
"""

from __future__ import annotations

import os

from PIL import Image, ImageDraw, ImageFont

W, H = 960, 600
BG = "#0b0f14"
BAR = "#161b22"
LINE = "#21262d"
GREEN = "#7ee787"
TEXT = "#c9d1d9"
DIM = "#8b949e"
BLUE = "#79c0ff"
YELLOW = "#e3b341"
RED = "#ff7b72"

FONT_PATH = r"C:\Windows\Fonts\msyh.ttc"

LINE_H = 25
MAX_W = W - 56

COLORS = {"cmd": GREEN, "out": TEXT, "dim": DIM, "cite": BLUE, "warn": YELLOW, "bad": RED}


def font(size: int):
    return ImageFont.truetype(FONT_PATH, size)


_MEASURE = ImageDraw.Draw(Image.new("RGB", (1, 1)))


def clip(text: str, size: int = 16) -> str:
    f = font(size)
    if _MEASURE.textlength(text, font=f) <= MAX_W:
        return text
    while text and _MEASURE.textlength(text + "…", font=f) > MAX_W:
        text = text[:-1]
    return text + "…"


def render(rows, cursor_row=None):
    img = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(img)
    d.rectangle([0, 0, W, 36], fill=BAR)
    for i, color in enumerate(["#ff5f56", "#ffbd2e", "#27c93f"]):
        d.ellipse([16 + i * 22, 12, 28 + i * 22, 24], fill=color)
    d.text((92, 9), "kangji — 家里那箱药，过期、重复、能不能一起吃", font=font(15), fill=DIM)
    d.line([0, 36, W, 36], fill=LINE)

    y = 54
    for idx, (style, text) in enumerate(rows):
        shown = clip(text)
        d.text((26, y), shown, font=font(16), fill=COLORS[style])
        if cursor_row == idx:
            w = _MEASURE.textlength(shown, font=font(16))
            d.rectangle([26 + w + 4, y + 2, 26 + w + 12, y + 19], fill=GREEN)
        y += LINE_H
        if y > H - 16:
            break
    return img


SCRIPT = [
    ("cmd", "> python -m kangji import samples/药箱.csv"),
    ("out", "· 导入 10 条"),
    ("cmd", "> python -m kangji check"),
    ("out", "检查于 2026-11-25 · 10 条 · 有硬问题，先处理"),
    ("dim", "过期 1、60 天内到期 1、重复成分 1 项、不宜同用 2 对、用完 1、认不出 1"),
    ("out", "过期了，别吃："),
    ("bad", "  · 氯雷他定 — 过期 15 天，2026-11-10"),
    ("out", "60 天内到期："),
    ("warn", "  · 999感冒灵 — 还剩 25 天，2026-12-20"),
    ("out", "同一成分出现在好几盒里（一起吃等于加量）："),
    ("cite", "  · 对乙酰氨基酚：999感冒灵、泰诺林"),
    ("out", "不宜同用："),
    ("bad", "  · [high] 头孢克肟 + 藿香正气水 —— 双硫仑样反应"),
    ("bad", "  · [high] 999感冒灵 + 泰诺林 —— 同一成分加倍"),
    ("cmd", "> python -m kangji advice"),
    ("out", "1. 清理过期的氯雷他定，并排查那个 60 天内到期的药品。"),
    ("out", "2. 将 999感冒灵与泰诺林分开存放并标记，提醒不宜同用。"),
    ("out", "3. 标记头孢克肟与藿香正气水，提醒不宜同用。"),
    ("out", "4. 外用的创可贴与内服药分开收纳，保留原包装、避光避潮。"),
    ("dim", "提到的箱外药名：0 处"),
]
TAIL = [
    ("warn", "第一版把「剩 1 片」也报成快用完 —— 十条警告里九条是噪音。"),
    ("dim", "阈值改成只报「真的没了」，顺手把模型的编号重排、药名逐个核。"),
]


def build():
    frames, shown = [], []
    for style, text in SCRIPT:
        if style == "cmd":
            for i in range(6, len(text) + 1, 6):
                frames.append(render(shown + [("cmd", text[:i])], cursor_row=len(shown)))
        shown = shown + [(style, text)]
        frames.append(render(shown))
    for _ in range(12):
        frames.append(render(shown + TAIL))

    frames = [f.quantize(colors=20, method=Image.MEDIANCUT) for f in frames]
    os.makedirs("assets", exist_ok=True)
    out = os.path.join("assets", "demo.gif")
    frames[0].save(out, save_all=True, append_images=frames[1:], duration=140, loop=0, optimize=True)
    print(f"ok -> {out}  {len(frames)} 帧  {os.path.getsize(out) / 1024:.1f} KB")


if __name__ == "__main__":
    build()
