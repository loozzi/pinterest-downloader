"""
Tạo hàng loạt ảnh "quote card" kiểu TikTok/Pinterest từ file text.

Mỗi dòng trong file text = 1 ảnh. Dùng "\\n" trong dòng để tự xuống dòng.

Cách dùng:
    python image.py texts.txt
    python image.py texts.txt -o output_cards --size 1080x1920 --template random
    python image.py texts.txt --template kraft --seed 42
"""

import argparse
import math
import os
import random
import re
import unicodedata
import urllib.request
from functools import lru_cache

from PIL import Image, ImageDraw, ImageFilter, ImageFont

# ---------------------------------------------------------------------------
# Fonts
# ---------------------------------------------------------------------------

WIN_FONTS = "/mnt/c/Windows/Fonts"
FONT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fonts")
DOWNLOAD_FONTS = {
    "Pangolin-Regular.ttf": "https://github.com/google/fonts/raw/main/ofl/pangolin/Pangolin-Regular.ttf",
}
VIET_SAMPLE = "ỔẦẬƯỜỊỆỐẰđư"

FONT_CANDIDATES = {
    "bold": [
        f"{WIN_FONTS}/arialbd.ttf",
        "C:/Windows/Fonts/arialbd.ttf",
        f"{WIN_FONTS}/segoeuib.ttf",
        "/usr/share/fonts/truetype/noto/NotoSans-Bold.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/Library/Fonts/Arial Bold.ttf",
    ],
    "heavy": [
        f"{WIN_FONTS}/verdanab.ttf",
        "C:/Windows/Fonts/verdanab.ttf",
        f"{WIN_FONTS}/tahomabd.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    ],
    # Font viết tay hỗ trợ tiếng Việt, tự tải về fonts/ ở lần chạy đầu
    "hand": [
        os.path.join(FONT_DIR, "Pangolin-Regular.ttf"),
        f"{WIN_FONTS}/arialbd.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    ],
    "regular": [
        f"{WIN_FONTS}/arial.ttf",
        "C:/Windows/Fonts/arial.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    ],
    "emoji": [
        f"{WIN_FONTS}/seguiemj.ttf",
        "C:/Windows/Fonts/seguiemj.ttf",
        "/usr/share/fonts/truetype/noto/NotoColorEmoji.ttf",
        "/System/Library/Fonts/Apple Color Emoji.ttc",
    ],
}


def download_fonts():
    for name, url in DOWNLOAD_FONTS.items():
        path = os.path.join(FONT_DIR, name)
        if os.path.exists(path):
            continue
        try:
            os.makedirs(FONT_DIR, exist_ok=True)
            urllib.request.urlretrieve(url, path)
            print(f"Đã tải font {name}")
        except Exception as e:
            print(f"Không tải được font {name} ({e}), dùng font dự phòng")


def supports_vietnamese(path):
    try:
        font = ImageFont.truetype(path, 40)
    except OSError:
        return False
    tofu = bytes(font.getmask("\uffff"))
    return all(bytes(font.getmask(c)) != tofu for c in VIET_SAMPLE)


@lru_cache(maxsize=None)
def find_font(kind):
    for path in FONT_CANDIDATES[kind]:
        if os.path.exists(path) and (kind == "emoji" or supports_vietnamese(path)):
            return path
    if kind == "emoji":
        return None
    raise FileNotFoundError(f"Không tìm thấy font cho '{kind}', hãy sửa FONT_CANDIDATES")


@lru_cache(maxsize=256)
def load_font(path, size):
    return ImageFont.truetype(path, size)


# ---------------------------------------------------------------------------
# Emoji
# ---------------------------------------------------------------------------

EMOJI_RE = re.compile(
    "(?:[\U0001F000-\U0001FAFF\u2600-\u27BF\u2B00-\u2BFF\u2300-\u23FF]"
    "[\uFE0F\u200D\U0001F3FB-\U0001F3FF]*)+"
)


@lru_cache(maxsize=256)
def render_emoji(emoji, height):
    """Render emoji thành ảnh RGBA có chiều cao ~height (None nếu không có font emoji)."""
    path = find_font("emoji")
    if not path:
        return None
    try:
        font = ImageFont.truetype(path, height)
    except OSError:
        # Font bitmap (NotoColorEmoji) chỉ load được ở size 109
        font = ImageFont.truetype(path, 109)
    size = int(font.size * 1.6) * max(1, len(emoji))
    layer = Image.new("RGBA", (size, int(font.size * 1.6)), (0, 0, 0, 0))
    ImageDraw.Draw(layer).text((0, 0), emoji, font=font, embedded_color=True)
    bbox = layer.getbbox()
    if not bbox:
        return None
    layer = layer.crop(bbox)
    scale = height / layer.height
    return layer.resize((max(1, int(layer.width * scale)), height), Image.LANCZOS)


def split_segments(word):
    """Tách 1 từ thành các đoạn [(text, is_emoji)]."""
    segs, pos = [], 0
    for m in EMOJI_RE.finditer(word):
        if m.start() > pos:
            segs.append((word[pos:m.start()], False))
        segs.append((m.group(), True))
        pos = m.end()
    if pos < len(word):
        segs.append((word[pos:], False))
    return segs


# ---------------------------------------------------------------------------
# Text layout
# ---------------------------------------------------------------------------


def word_width(word, font):
    w = 0
    for seg, is_emoji in split_segments(word):
        if is_emoji:
            img = render_emoji(seg, int(font.size * 0.95))
            w += (img.width if img else 0) + int(font.size * 0.08)
        else:
            w += font.getlength(seg)
    return w


def wrap_text(text, font, max_width):
    lines = []
    space = font.getlength(" ")
    for para in text.split("\n"):
        words = para.split()
        if not words:
            lines.append("")
            continue
        cur, cur_w = [], 0
        for word in words:
            ww = word_width(word, font)
            add = ww if not cur else cur_w + space + ww
            if cur and add > max_width:
                lines.append(" ".join(cur))
                cur, cur_w = [word], ww
            else:
                cur.append(word)
                cur_w = add
        lines.append(" ".join(cur))
    return lines


def fit_text(text, box, font_path, max_size, min_size=28, spacing=1.18):
    x0, y0, x1, y1 = box
    bw, bh = x1 - x0, y1 - y0
    for size in range(max_size, min_size - 1, -2):
        font = load_font(font_path, size)
        lines = wrap_text(text, font, bw)
        line_h = int(size * spacing)
        if line_h * len(lines) <= bh and all(word_width(l, font) <= bw for l in lines):
            return font, lines, line_h
    font = load_font(font_path, min_size)
    return font, wrap_text(text, font, bw), int(min_size * spacing)


def draw_text_block(img, text, box, font_path, color, align="left", valign="center",
                    max_size=120, spacing=1.18, upper=False, stroke=0, stroke_color=None):
    if upper:
        text = text.upper()
    draw = ImageDraw.Draw(img)
    font, lines, line_h = fit_text(text, box, font_path, max_size, spacing=spacing)
    x0, y0, x1, y1 = box
    total_h = line_h * len(lines)
    if valign == "center":
        y = y0 + (y1 - y0 - total_h) // 2
    elif valign == "bottom":
        y = y1 - total_h
    else:
        y = y0
    ascent, _ = font.getmetrics()
    space = font.getlength(" ")
    for line in lines:
        lw = word_width(line, font)
        if align == "center":
            x = x0 + (x1 - x0 - lw) / 2
        elif align == "right":
            x = x1 - lw
        else:
            x = x0
        baseline = y + int(line_h * 0.5 + font.size * 0.36)
        for i, word in enumerate(line.split(" ")):
            if i:
                x += space
            for seg, is_emoji in split_segments(word):
                if is_emoji:
                    em = render_emoji(seg, int(font.size * 0.95))
                    if em:
                        img.alpha_composite(em, (int(x), baseline - int(font.size * 0.82)))
                        x += em.width + int(font.size * 0.08)
                else:
                    draw.text((x, baseline), seg, font=font, fill=color, anchor="ls",
                              stroke_width=stroke, stroke_fill=stroke_color)
                    x += font.getlength(seg)
        y += line_h
    return font


# ---------------------------------------------------------------------------
# Drawing helpers
# ---------------------------------------------------------------------------

STICKERS = ["🐶", "🐱", "🐬", "🤖", "🐨", "⛵", "🐰", "🐻", "🦊", "🐼", "🍀", "🌸", "🧧", "🎁"]

# 12 con giáp (theo Việt Nam: Mão là mèo)
ZODIAC = {
    "tý": "🐭", "tí": "🐭", "sửu": "🐃", "dần": "🐯", "mão": "🐱", "mẹo": "🐱", "thìn": "🐉",
    "tỵ": "🐍", "tị": "🐍", "ngọ": "🐴", "mùi": "🐐", "thân": "🐒", "dậu": "🐓", "tuất": "🐶", "hợi": "🐷",
}
ZODIAC_RE = re.compile(r"tuổi\s+(" + "|".join(ZODIAC) + r")(?!\w)")


def pick_sticker(text, rnd):
    """Lấy con giáp được nhắc trong text (vd "tuổi Sửu" -> 🐃), không có thì chọn ngẫu nhiên."""
    m = ZODIAC_RE.search(unicodedata.normalize("NFC", text).lower())
    return ZODIAC[m.group(1)] if m else rnd.choice(STICKERS)


def shadow(img, box, radius, offset=(0, 14), blur=22, alpha=70):
    layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
    x0, y0, x1, y1 = box
    ImageDraw.Draw(layer).rounded_rectangle(
        (x0 + offset[0], y0 + offset[1], x1 + offset[0], y1 + offset[1]),
        radius, fill=(0, 0, 0, alpha))
    img.alpha_composite(layer.filter(ImageFilter.GaussianBlur(blur)))


def paste_sticker(img, emoji, center, height):
    em = render_emoji(emoji, height)
    if em:
        img.alpha_composite(em, (int(center[0] - em.width / 2), int(center[1] - em.height / 2)))


def h_lines(draw, box, gap, color, width=2):
    x0, y0, x1, y1 = box
    y = y0 + gap
    while y < y1:
        draw.line((x0, y, x1, y), fill=color, width=width)
        y += gap


def grid(draw, box, gap, color, width=2):
    h_lines(draw, box, gap, color, width)
    x0, y0, x1, y1 = box
    x = x0 + gap
    while x < x1:
        draw.line((x, y0, x, y1), fill=color, width=width)
        x += gap


def noise_texture(size, base, amount=18, seed=0):
    rnd = random.Random(seed)
    img = Image.new("RGB", size, base)
    noise = Image.effect_noise(size, amount * 3).convert("L")
    tint = Image.new("RGB", size, tuple(max(0, c - 40) for c in base))
    img = Image.composite(tint, img, noise.point(lambda p: int(p * 0.35)))
    # vài vệt sợi giấy
    d = ImageDraw.Draw(img)
    for _ in range(size[0] * size[1] // 6000):
        x, y = rnd.randrange(size[0]), rnd.randrange(size[1])
        d.line((x, y, x + rnd.randint(4, 14), y + rnd.randint(-3, 3)),
               fill=tuple(max(0, c - rnd.randint(15, 45)) for c in base), width=1)
    return img.convert("RGBA")


def torn_rect(box, rnd, jag=10, step=18):
    x0, y0, x1, y1 = box
    pts = []
    for x in range(int(x0), int(x1), step):
        pts.append((x, y0 + rnd.uniform(-jag, jag)))
    for y in range(int(y0), int(y1), step):
        pts.append((x1 + rnd.uniform(-jag, jag), y))
    for x in range(int(x1), int(x0), -step):
        pts.append((x, y1 + rnd.uniform(-jag, jag)))
    for y in range(int(y1), int(y0), -step):
        pts.append((x0 + rnd.uniform(-jag, jag), y))
    return pts


def rotate_layer(layer, angle):
    return layer.rotate(angle, resample=Image.BICUBIC, center=(layer.width / 2, layer.height / 2))


# ---------------------------------------------------------------------------
# Templates — mỗi hàm nhận (text, W, H, rnd) và trả về ảnh RGBA
# ---------------------------------------------------------------------------


def tpl_note_card(text, W, H, rnd):
    """Nền pastel + tờ giấy kẻ dòng trắng, chữ in hoa màu đậm."""
    bg, fg = rnd.choice([
        ("#bfe9df", "#2f8a86"), ("#ffd9e3", "#c2456b"), ("#d8e7ff", "#2e5ea8"),
        ("#fff1b8", "#b06a00"), ("#e2d9ff", "#5a3fa8"),
    ])
    img = Image.new("RGBA", (W, H), bg)
    d = ImageDraw.Draw(img)
    m = int(W * 0.06)
    card = (m, int(H * 0.08), W - m, H - int(H * 0.06))
    shadow(img, card, 18)
    d.rounded_rectangle(card, 18, fill="#ffffff")
    # dải màu bên trái giống mẫu
    d.rectangle((card[0], card[1], card[0] + int(W * 0.04), card[3]), fill=bg)
    h_lines(d, (card[0] + int(W * 0.04), card[1] + 60, card[2], card[3] - 20), int(H * 0.035), "#e6eef5")
    d.text((card[2] - 40, card[1] + 40), "Say Something", font=load_font(find_font("bold"), int(W * 0.028)),
           fill=fg, anchor="rt")
    box = (card[0] + int(W * 0.1), card[1] + int(H * 0.08), card[2] - int(W * 0.08), card[3] - int(H * 0.15))
    draw_text_block(img, text, box, find_font("bold"), fg, align="left", upper=True, max_size=int(W * 0.12))
    paste_sticker(img, pick_sticker(text, rnd), (card[2] - int(W * 0.17), card[3] - int(H * 0.07)), int(W * 0.13))
    return img


def tpl_dark(text, W, H, rnd):
    """Nền đen, chữ trắng căn trái kiểu cảnh báo."""
    img = Image.new("RGBA", (W, H), rnd.choice(["#1f1f1f", "#141414", "#232323"]))
    box = (int(W * 0.12), int(H * 0.12), W - int(W * 0.12), H - int(H * 0.18))
    draw_text_block(img, text, box, find_font("bold"), "#ffffff", align="left", max_size=int(W * 0.09),
                    spacing=1.25)
    return img


def tpl_kraft(text, W, H, rnd):
    """Nền giấy kraft + mẩu giấy xé, chữ viết tay nâu."""
    img = noise_texture((W, H), (196, 160, 118), seed=rnd.random())
    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    m = int(W * 0.1)
    paper = (m, int(H * 0.1), W - m, H - int(H * 0.1))
    pts = torn_rect(paper, rnd)
    shadow_layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ImageDraw.Draw(shadow_layer).polygon([(x + 8, y + 14) for x, y in pts], fill=(60, 35, 10, 90))
    layer.alpha_composite(shadow_layer.filter(ImageFilter.GaussianBlur(14)))
    d.polygon(pts, fill="#efe2c8")
    # băng dính
    tw, th = int(W * 0.28), int(H * 0.035)
    cx = W // 2
    d.rectangle((cx - tw // 2, paper[1] - th // 2, cx + tw // 2, paper[1] + th // 2), fill=(255, 255, 240, 150))
    small = load_font(find_font("hand"), int(W * 0.03))
    d.text((paper[0] + 50, paper[1] + 60), "/ Today /", font=small, fill="#8a6b47")
    box = (paper[0] + 50, paper[1] + int(H * 0.08), paper[2] - 50, paper[3] - int(H * 0.08))
    draw_text_block(layer, text, box, find_font("hand"), "#4a3420", align="left", max_size=int(W * 0.085),
                    spacing=1.3)
    d.text((paper[2] - 40, paper[3] - 50), "TikTok Text", font=small, fill="#4a3420", anchor="rb")
    img.alpha_composite(rotate_layer(layer, rnd.uniform(-2.5, 2.5)))
    return img


def tpl_grid_blue(text, W, H, rnd):
    """Nền xanh dương + tờ giấy ô li, chữ in hoa xanh đậm."""
    bg = rnd.choice(["#2f6fd6", "#2b5fc4", "#3d7be0"])
    img = Image.new("RGBA", (W, H), bg)
    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    m = int(W * 0.07)
    card = (m, int(H * 0.06), W - m, H - int(H * 0.06))
    shadow(layer, card, 6, offset=(8, 12), alpha=90)
    d.rectangle(card, fill="#f7f9ff")
    grid(d, card, int(W * 0.045), "#dfe6f3")
    box = (card[0] + int(W * 0.08), card[1] + int(H * 0.07), card[2] - int(W * 0.08), card[3] - int(H * 0.16))
    draw_text_block(layer, text, box, find_font("bold"), "#1d3557", align="left", upper=True,
                    max_size=int(W * 0.11))
    paste_sticker(layer, pick_sticker(text, rnd), (card[2] - int(W * 0.17), card[3] - int(H * 0.08)), int(W * 0.14))
    img.alpha_composite(rotate_layer(layer, rnd.uniform(-1.5, 1.5)))
    return img


def tpl_quote_yellow(text, W, H, rnd):
    """Nền vàng + dấu ngoặc kép lớn, chữ in hoa."""
    bg = rnd.choice(["#fbf26c", "#ffe96b", "#fff176"])
    img = Image.new("RGBA", (W, H), bg)
    d = ImageDraw.Draw(img)
    qfont = load_font(find_font("heavy"), int(W * 0.42))
    d.text((W - int(W * 0.1), int(H * 0.02)), "\u201d", font=qfont, fill="#2457d6", anchor="rt")
    box = (int(W * 0.1), int(H * 0.2), W - int(W * 0.12), H - int(H * 0.12))
    draw_text_block(img, text, box, find_font("bold"), "#2b2111", align="left", upper=True,
                    max_size=int(W * 0.105))
    d.text((int(W * 0.1), H - int(H * 0.06)), "Daily memo \u25b2", font=load_font(find_font("bold"), int(W * 0.03)),
           fill="#4a7a2a")
    return img


def tpl_pink_center(text, W, H, rnd):
    """Nền hồng với hoạ tiết mờ, chữ căn giữa màu mận."""
    bg, fg = rnd.choice([("#fde4ef", "#7a1846"), ("#e8f6ff", "#18457a"), ("#eafbe7", "#1d6a2a")])
    img = Image.new("RGBA", (W, H), bg)
    deco = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    dd = ImageDraw.Draw(deco)
    qf = load_font(find_font("heavy"), int(W * 0.35))
    for _ in range(4):
        dd.text((rnd.randint(-100, W), rnd.randint(-100, H)), rnd.choice("?!♥"), font=qf, fill=(255, 255, 255, 120))
    for _ in range(3):
        r = rnd.randint(int(W * 0.12), int(W * 0.25))
        x, y = rnd.randint(0, W), rnd.randint(0, H)
        dd.ellipse((x - r, y - r, x + r, y + r), outline=(255, 255, 255, 140), width=10)
    img.alpha_composite(deco)
    paste_sticker(img, pick_sticker(text, rnd), (W // 2, int(H * 0.17)), int(W * 0.14))
    box = (int(W * 0.1), int(H * 0.27), W - int(W * 0.1), H - int(H * 0.12))
    draw_text_block(img, text, box, find_font("bold"), fg, align="center", upper=True, max_size=int(W * 0.105))
    return img


def tpl_notebook(text, W, H, rnd):
    """Trang sổ trắng có lỗ lò xo, dòng kẻ ngang."""
    img = Image.new("RGBA", (W, H), "#fbfbfb")
    d = ImageDraw.Draw(img)
    h_lines(d, (int(W * 0.12), int(H * 0.05), W - int(W * 0.06), H - int(H * 0.04)), int(H * 0.05), "#e3e3e3", 3)
    for i in range(7):
        y = int(H * 0.08 + i * H * 0.14)
        r = int(W * 0.018)
        d.ellipse((int(W * 0.04) - r, y - r, int(W * 0.04) + r, y + r), fill="#ffffff", outline="#9a9a9a", width=3)
    box = (int(W * 0.15), int(H * 0.1), W - int(W * 0.1), H - int(H * 0.2))
    draw_text_block(img, text, box, find_font("bold"), "#262626", align="left", upper=True, max_size=int(W * 0.11))
    paste_sticker(img, pick_sticker(text, rnd), (W - int(W * 0.18), H - int(H * 0.1)), int(W * 0.14))
    return img


def tpl_purple_frame(text, W, H, rnd):
    """Khung viền tím + giấy ô mờ, chữ căn giữa."""
    frame, fg = rnd.choice([("#c49be6", "#7b2fb8"), ("#f2a7c3", "#b0306a"), ("#9fd8c9", "#1f7a63")])
    img = Image.new("RGBA", (W, H), frame)
    d = ImageDraw.Draw(img)
    m = int(W * 0.06)
    paper = (m, int(H * 0.05), W - m, H - int(H * 0.04))
    d.rounded_rectangle(paper, 30, fill="#fdfbff", outline=fg, width=6)
    grid(d, (paper[0] + 10, paper[1] + 60, paper[2] - 10, paper[3] - 10), int(W * 0.05), "#efe7f7")
    # thanh cuộn phía trên
    d.rounded_rectangle((paper[0] - 20, paper[1] - 10, paper[2] + 20, paper[1] + 40), 25, fill=frame, outline=fg,
                        width=5)
    d.text((W // 2, paper[1] + 80), "TikTok Text", font=load_font(find_font("regular"), int(W * 0.025)),
           fill="#c7b8d6", anchor="mt")
    box = (paper[0] + int(W * 0.08), paper[1] + int(H * 0.1), paper[2] - int(W * 0.08), paper[3] - int(H * 0.08))
    draw_text_block(img, text, box, find_font("bold"), fg, align="center", max_size=int(W * 0.08), spacing=1.3)
    return img


def tpl_cream_center(text, W, H, rnd):
    """Nền kem với nét vẽ nguệch ngoạc mờ, chữ in hoa căn giữa."""
    bg, fg = rnd.choice([("#fff6d9", "#5a3a12"), ("#f3ecff", "#3d2a6b"), ("#e9f7f2", "#1d4d3c")])
    img = Image.new("RGBA", (W, H), bg)
    d = ImageDraw.Draw(img)
    doodle = tuple(max(0, int(int(bg[i:i + 2], 16) * 0.93)) for i in (1, 3, 5))
    for _ in range(6):
        cx, cy, r = rnd.randint(0, W), rnd.randint(0, H), rnd.randint(80, 220)
        pts = [(cx + r * math.cos(a / 10) + rnd.randint(-20, 20), cy + r * math.sin(a / 10) + rnd.randint(-20, 20))
               for a in range(0, 50)]
        d.line(pts, fill=doodle, width=8, joint="curve")
    paste_sticker(img, pick_sticker(text, rnd), (W // 2, int(H * 0.17)), int(W * 0.14))
    box = (int(W * 0.12), int(H * 0.27), W - int(W * 0.12), H - int(H * 0.2))
    draw_text_block(img, text, box, find_font("heavy"), fg, align="center", upper=True, max_size=int(W * 0.1))
    paste_sticker(img, rnd.choice(["⛵", "🍀", "🧧", "✨"]), (W // 2, H - int(H * 0.13)), int(W * 0.08))
    return img


TEMPLATES = {
    "note_card": tpl_note_card,
    "dark": tpl_dark,
    "kraft": tpl_kraft,
    "grid_blue": tpl_grid_blue,
    "quote_yellow": tpl_quote_yellow,
    "pink_center": tpl_pink_center,
    "notebook": tpl_notebook,
    "purple_frame": tpl_purple_frame,
    "cream_center": tpl_cream_center,
}


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def slugify(text, max_len=40):
    text = unicodedata.normalize("NFD", text.replace("đ", "d").replace("Đ", "D"))
    text = "".join(c for c in text if unicodedata.category(c) != "Mn")
    text = re.sub(r"[^A-Za-z0-9]+", "_", text).strip("_").lower()
    return text[:max_len] or "card"


def read_lines(path):
    with open(path, encoding="utf-8") as f:
        lines = [unicodedata.normalize("NFC", l.strip()) for l in f]
    return [l.replace("\\n", "\n") for l in lines if l]


def main():
    parser = argparse.ArgumentParser(description="Tạo ảnh quote card từ file text (mỗi dòng 1 ảnh)")
    parser.add_argument("input", nargs="?", default="texts.txt", help="File text, mỗi dòng 1 ảnh")
    parser.add_argument("-o", "--output", default="output_cards", help="Thư mục lưu ảnh")
    parser.add_argument("--size", default="1080x1920", help="Kích thước WxH (mặc định 1080x1920 = 9:16 dọc; "
                                                            "1920x1080 cho 16:9 ngang)")
    parser.add_argument("--template", default="cycle",
                        help=f"cycle | random | {' | '.join(TEMPLATES)}")
    parser.add_argument("--seed", type=int, default=None, help="Seed để kết quả lặp lại được")
    args = parser.parse_args()

    download_fonts()
    W, H = map(int, args.size.lower().split("x"))
    rnd = random.Random(args.seed)
    names = list(TEMPLATES)
    lines = read_lines(args.input)
    os.makedirs(args.output, exist_ok=True)

    for i, text in enumerate(lines, 1):
        if args.template == "cycle":
            name = names[(i - 1) % len(names)]
        elif args.template == "random":
            name = rnd.choice(names)
        else:
            name = args.template
        img = TEMPLATES[name](text, W, H, random.Random(rnd.random()))
        out = os.path.join(args.output, f"{i:03d}_{name}_{slugify(text)}.png")
        img.convert("RGB").save(out, quality=95)
        print(f"[{i}/{len(lines)}] {out}")


if __name__ == "__main__":
    main()
