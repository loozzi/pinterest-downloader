"""
Tạo hàng loạt ảnh "quote card" kiểu TikTok/Pinterest từ file text.

Mỗi dòng trong file text = 1 ảnh. Dùng "\\n" trong dòng để tự xuống dòng.

Cách dùng:
    python image.py texts.txt
    python image.py texts.txt -o output_cards --size 1080x1920 --template random
    python image.py texts.txt --template kraft --seed 42
"""

import argparse
import datetime
import math
import os
import random
import re
import unicodedata
import urllib.request
from functools import lru_cache

from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageFont

# ---------------------------------------------------------------------------
# Fonts
# ---------------------------------------------------------------------------

WIN_FONTS = "/mnt/c/Windows/Fonts"
FONT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fonts")
GF = "https://github.com/google/fonts/raw/main/ofl"
DOWNLOAD_FONTS = {
    "Pangolin-Regular.ttf": f"{GF}/pangolin/Pangolin-Regular.ttf",
    "PatrickHand-Regular.ttf": f"{GF}/patrickhand/PatrickHand-Regular.ttf",
    "Sriracha-Regular.ttf": f"{GF}/sriracha/Sriracha-Regular.ttf",
    "DancingScript.ttf": f"{GF}/dancingscript/DancingScript%5Bwght%5D.ttf",
    "Pacifico-Regular.ttf": f"{GF}/pacifico/Pacifico-Regular.ttf",
    "Lobster-Regular.ttf": f"{GF}/lobster/Lobster-Regular.ttf",
    "PlayfairDisplay.ttf": f"{GF}/playfairdisplay/PlayfairDisplay%5Bwght%5D.ttf",
    "Lora.ttf": f"{GF}/lora/Lora%5Bwght%5D.ttf",
    "JetBrainsMono.ttf": f"{GF}/jetbrainsmono/JetBrainsMono%5Bwght%5D.ttf",
    "VT323-Regular.ttf": f"{GF}/vt323/VT323-Regular.ttf",
    "Bangers-Regular.ttf": f"{GF}/bangers/Bangers-Regular.ttf",
    "BeVietnamPro-Black.ttf": f"{GF}/bevietnampro/BeVietnamPro-Black.ttf",
    "Baloo2.ttf": f"{GF}/baloo2/Baloo2%5Bwght%5D.ttf",
}
# Font variable: độ đậm (trục wght) muốn dùng
FONT_WEIGHTS = {"DancingScript.ttf": 700, "PlayfairDisplay.ttf": 700, "Lora.ttf": 500,
                "JetBrainsMono.ttf": 600, "Baloo2.ttf": 800}
DEJAVU = "/usr/share/fonts/truetype/dejavu"
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
    "hand2": [os.path.join(FONT_DIR, "PatrickHand-Regular.ttf"), f"{DEJAVU}/DejaVuSans.ttf"],
    "marker": [os.path.join(FONT_DIR, "Sriracha-Regular.ttf"), f"{DEJAVU}/DejaVuSans-Bold.ttf"],
    "script": [os.path.join(FONT_DIR, "DancingScript.ttf"), f"{DEJAVU}/DejaVuSerif-Italic.ttf"],
    "brush": [os.path.join(FONT_DIR, "Pacifico-Regular.ttf"), f"{DEJAVU}/DejaVuSerif-BoldItalic.ttf"],
    "retro": [os.path.join(FONT_DIR, "Lobster-Regular.ttf"), f"{DEJAVU}/DejaVuSerif-BoldItalic.ttf"],
    "serif": [os.path.join(FONT_DIR, "PlayfairDisplay.ttf"), f"{WIN_FONTS}/georgiab.ttf",
              f"{DEJAVU}/DejaVuSerif-Bold.ttf"],
    "book": [os.path.join(FONT_DIR, "Lora.ttf"), f"{WIN_FONTS}/georgia.ttf", f"{DEJAVU}/DejaVuSerif.ttf"],
    "mono": [os.path.join(FONT_DIR, "JetBrainsMono.ttf"), f"{WIN_FONTS}/consola.ttf",
             f"{DEJAVU}/DejaVuSansMono-Bold.ttf"],
    "pixel": [os.path.join(FONT_DIR, "VT323-Regular.ttf"), f"{DEJAVU}/DejaVuSansMono-Bold.ttf"],
    "comic": [os.path.join(FONT_DIR, "Bangers-Regular.ttf"), f"{WIN_FONTS}/impact.ttf",
              f"{DEJAVU}/DejaVuSansCondensed-Bold.ttf"],
    "black": [os.path.join(FONT_DIR, "BeVietnamPro-Black.ttf"), f"{WIN_FONTS}/ariblk.ttf",
              f"{DEJAVU}/DejaVuSans-Bold.ttf"],
    "round": [os.path.join(FONT_DIR, "Baloo2.ttf"), f"{DEJAVU}/DejaVuSans-Bold.ttf"],
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
    font = ImageFont.truetype(path, size)
    weight = FONT_WEIGHTS.get(os.path.basename(path))
    if weight:
        try:
            font.set_variation_by_axes([weight])
        except Exception:
            pass
    return font


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


def draw_word(img, draw, x, baseline, word, font, color, stroke=0, stroke_color=None):
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
    return x


def draw_text_block(img, text, box, font_path, color, align="left", valign="center",
                    max_size=120, spacing=1.18, upper=False, stroke=0, stroke_color=None,
                    line_bg=None, word_bg=None):
    """Vẽ text tự co chữ cho vừa box.

    line_bg(img, x, y, w, line_h, font): vẽ nền cho từng dòng (vd highlight).
    word_bg(img, x, baseline, w, font): vẽ nền cho từng từ, trả về màu chữ (hoặc None = color).
    """
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
    space = font.getlength(" ")
    for line in lines:
        lw = word_width(line, font)
        if align == "center":
            x = x0 + (x1 - x0 - lw) / 2
        elif align == "right":
            x = x1 - lw
        else:
            x = x0
        if line_bg and line.strip():
            line_bg(img, x, y, lw, line_h, font)
        baseline = y + int(line_h * 0.5 + font.size * 0.36)
        for i, word in enumerate(line.split(" ")):
            if i:
                x += space
            c = color
            if word_bg and word:
                c = word_bg(img, x, baseline, word_width(word, font), font) or color
            x = draw_word(img, draw, x, baseline, word, font, c, stroke, stroke_color)
        y += line_h
    return font


def measure_text(text, box, font_path, max_size, spacing=1.18, upper=False):
    """Trả về (font, rộng, cao, line_h) của text sau khi co chữ vừa box."""
    if upper:
        text = text.upper()
    font, lines, line_h = fit_text(text, box, font_path, max_size, spacing=spacing)
    return font, int(max(word_width(l, font) for l in lines)) + 4, line_h * len(lines), line_h


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


# Lưu ý: ImageDraw trên ảnh RGBA GHI ĐÈ pixel chứ không trộn alpha. Muốn hình bán trong suốt
# thì vẽ lên layer riêng rồi img.alpha_composite(layer).

VN_WEEKDAYS = ["Thứ Hai", "Thứ Ba", "Thứ Tư", "Thứ Năm", "Thứ Sáu", "Thứ Bảy", "Chủ Nhật"]


def rgb(c):
    if isinstance(c, str):
        c = c.lstrip("#")
        if len(c) in (3, 4):
            c = "".join(ch * 2 for ch in c)
        return tuple(int(c[i:i + 2], 16) for i in (0, 2, 4))
    return tuple(c[:3])


def rgba(c, a):
    return rgb(c) + (int(a),)


def mix(c1, c2, t):
    return tuple(int(a + (b - a) * t) for a, b in zip(rgb(c1), rgb(c2)))


def luminance(c):
    r, g, b = rgb(c)
    return 0.299 * r + 0.587 * g + 0.114 * b


def label(d, xy, text, kind, size, fill, anchor="la"):
    d.text(xy, text, font=load_font(find_font(kind), max(8, int(size))), fill=fill, anchor=anchor)


def gradient(size, colors, angle=0):
    """Ảnh gradient nhiều màu (>= 2 màu); angle=0 là dọc từ trên xuống, 90 là trái -> phải."""
    W, H = size
    cols = [rgb(c) for c in colors]
    n = int(math.hypot(W, H)) + 2 if angle else H

    def at(t):
        t *= len(cols) - 1
        k = min(int(t), len(cols) - 2)
        return mix(cols[k], cols[k + 1], t - k)

    strip = Image.new("RGB", (1, n))
    strip.putdata([at(i / max(1, n - 1)) for i in range(n)])
    if not angle:
        return strip.resize((W, H)).convert("RGBA")
    sq = strip.resize((n, n)).rotate(angle, resample=Image.BICUBIC)
    x, y = (n - W) // 2, (n - H) // 2
    return sq.crop((x, y, x + W, y + H)).convert("RGBA")


def gradient_fill(img, colors, shape, angle=0):
    """Tô gradient cho một hình: shape(draw) vẽ mask (fill=255) lên ImageDraw."""
    mask = Image.new("L", img.size, 0)
    shape(ImageDraw.Draw(mask))
    img.paste(gradient(img.size, colors, angle), (0, 0), mask)


def soft_blobs(img, rnd, colors, n=6, alpha=255, blur=0.12, rmin=0.2, rmax=0.45, box=None):
    """Các đốm màu loang mờ lên img (mesh gradient, aurora...)."""
    W, H = img.size
    k = 4
    w, h = W // k, H // k
    u = min(w, h)
    x0, y0, x1, y1 = [int(v) // k for v in box] if box else (0, 0, w, h)
    small = img.convert("RGB").resize((w, h))
    mask = Image.new("L", (w, h), 0)
    dc, dm = ImageDraw.Draw(small), ImageDraw.Draw(mask)
    for i in range(n):
        r = int(u * rnd.uniform(rmin, rmax))
        x, y = rnd.randint(x0, x1), rnd.randint(y0, y1)
        dc.ellipse((x - r, y - r, x + r, y + r), fill=rgb(colors[i % len(colors)]))
        dm.ellipse((x - r, y - r, x + r, y + r), fill=alpha)
    f = ImageFilter.GaussianBlur(u * blur)
    img.paste(small.filter(f).resize((W, H), Image.BICUBIC), (0, 0), mask.filter(f).resize((W, H), Image.BICUBIC))


def add_grain(img, amount=14):
    W, H = img.size
    n = Image.effect_noise((W, H), 64).convert("L")
    img.alpha_composite(Image.merge("RGBA", (n, n, n, Image.new("L", (W, H), amount))))


def vignette(img, strength=140):
    W, H = img.size
    w, h = W // 4, H // 4
    mask = Image.new("L", (w, h), 0)
    ImageDraw.Draw(mask).ellipse((-w // 4, -h // 4, w + w // 4, h + h // 4), fill=255)
    mask = mask.filter(ImageFilter.GaussianBlur(min(w, h) // 5)).resize((W, H))
    dark = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    dark.putalpha(mask.point(lambda p: int((255 - p) * strength / 255)))
    img.alpha_composite(dark)


def frosted(img, box, radius, tint=(255, 255, 255, 60), blur=30, outline=(255, 255, 255, 110)):
    """Thẻ kính mờ (glassmorphism) tại box."""
    box = tuple(int(v) for v in box)
    region = img.crop(box).filter(ImageFilter.GaussianBlur(blur))
    mask = Image.new("L", region.size, 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, region.width - 1, region.height - 1), radius, fill=255)
    img.paste(region, box[:2], mask)
    layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
    ImageDraw.Draw(layer).rounded_rectangle(box, radius, fill=tint, outline=outline, width=3)
    img.alpha_composite(layer)


def glow(img, layer, radii=(0.035, 0.012)):
    """Hiệu ứng phát sáng: layer nên tạo bằng Image.new("RGBA", size, rgba(color, 0))."""
    u = min(img.size)
    for r in radii:
        img.alpha_composite(layer.filter(ImageFilter.GaussianBlur(u * r)))
    img.alpha_composite(layer)


def glow_text(img, text, box, font_path, color, core=None, radii=(0.035, 0.012), **kw):
    """Chữ neon: quầng sáng màu color + lõi sáng hơn."""
    layer = Image.new("RGBA", img.size, rgba(color, 0))
    draw_text_block(layer, text, box, font_path, rgba(color, 255), **kw)
    glow(img, layer, radii)
    return draw_text_block(img, text, box, font_path, core or mix(color, "#ffffff", 0.6), **kw)


def rough_text(img, text, box, font_path, color, k=2.0, **kw):
    """Chữ có vân lỗ chỗ (phấn, mực máy đánh chữ); k càng lớn càng rỗ."""
    layer = Image.new("RGBA", img.size, rgba(color, 0))
    font = draw_text_block(layer, text, box, font_path, rgba(color, 255), **kw)
    noise = Image.effect_noise(img.size, 90).convert("L").point(
        lambda p: min(255, max(0, int((p - 128) * k + 210))))
    layer.putalpha(ImageChops.multiply(layer.getchannel("A"), noise))
    img.alpha_composite(layer)
    return font


def paste_rotated(img, layer, center, angle=0):
    """Dán layer (RGBA) xoay angle độ, tâm tại center (cho phép tràn mép)."""
    r = layer.rotate(angle, resample=Image.BICUBIC, expand=True) if angle else layer
    tmp = Image.new("RGBA", img.size, (0, 0, 0, 0))
    tmp.paste(r, (int(center[0] - r.width / 2), int(center[1] - r.height / 2)))
    img.alpha_composite(tmp)


def text_bubble(img, text, xy, max_wh, font_path, max_size, fill, fg, pad, radius, right=False,
                spacing=1.18, upper=False, outline=None, width=0, align="left"):
    """Bong bóng co theo text; xy là góc trên-trái (right=True: góc trên-phải). Trả về box."""
    font, tw, th, _ = measure_text(text, (0, 0, int(max_wh[0]), int(max_wh[1])), font_path, max_size,
                                   spacing, upper)
    x, y = xy
    bw, bh = tw + 2 * pad, th + 2 * pad
    if right:
        x -= bw
    box = (int(x), int(y), int(x + bw), int(y + bh))
    ImageDraw.Draw(img).rounded_rectangle(box, radius, fill=fill, outline=outline, width=width)
    draw_text_block(img, text, (box[0] + pad, box[1] + pad, box[0] + pad + tw, box[1] + pad + th), font_path,
                    fg, align=align, max_size=font.size, spacing=spacing, upper=upper)
    return box


def ruled_text(img, text, box, font_path, color, rule_color, max_size, spacing=1.5, rule_box=None, width=2, **kw):
    """Text căn trên + dòng kẻ ngang khớp đúng chân chữ (giấy kẻ dòng)."""
    font, _, _, lh = measure_text(text, box, font_path, max_size, spacing)
    x0, y0, x1, y1 = rule_box or box
    d = ImageDraw.Draw(img)
    y = box[1] + lh * 0.5 + font.size * 0.48
    while y - lh > y0:
        y -= lh
    while y < y1:
        d.line((x0, y, x1, y), fill=rule_color, width=width)
        y += lh
    return draw_text_block(img, text, box, font_path, color, valign="top", max_size=font.size, spacing=spacing, **kw)


def star_points(cx, cy, ro, ri, n=5, rot=-90):
    pts = []
    for i in range(n * 2):
        r = ro if i % 2 == 0 else ri
        a = math.radians(rot + i * 180 / n)
        pts.append((cx + r * math.cos(a), cy + r * math.sin(a)))
    return pts


def heart_points(cx, cy, s, steps=90):
    """Hình tim rộng ~s, tâm (cx, cy); trên ~ cy-0.34s, đáy ~ cy+0.5s."""
    k = s / 34
    return [(cx + 16 * math.sin(t) ** 3 * k,
             cy - (13 * math.cos(t) - 5 * math.cos(2 * t) - 2 * math.cos(3 * t) - math.cos(4 * t)) * k)
            for t in (i * 2 * math.pi / steps for i in range(steps))]


def rot_rect_points(cx, cy, w, h, angle):
    a = math.radians(angle)
    ca, sa = math.cos(a), math.sin(a)
    return [(cx + x * ca - y * sa, cy + x * sa + y * ca)
            for x, y in ((-w / 2, -h / 2), (w / 2, -h / 2), (w / 2, h / 2), (-w / 2, h / 2))]


def sparkle(d, cx, cy, r, fill):
    d.polygon(star_points(cx, cy, r, r * 0.22, 4), fill=fill)


def star_field(d, rnd, box, n, color, rmax=4):
    x0, y0, x1, y1 = box
    for _ in range(n):
        x, y, r = rnd.uniform(x0, x1), rnd.uniform(y0, y1), rnd.uniform(1, rmax)
        d.ellipse((x - r, y - r, x + r, y + r), fill=color)


def dots(d, box, gap, r, color, stagger=True):
    x0, y0, x1, y1 = (int(v) for v in box)
    for row, y in enumerate(range(y0, y1 + gap, gap)):
        off = gap // 2 if stagger and row % 2 else 0
        for x in range(x0 - off, x1 + gap, gap):
            d.ellipse((x - r, y - r, x + r, y + r), fill=color)


def diag_stripes(d, W, H, gap, width, color):
    for x in range(-H, W + H, gap):
        d.line((x, 0, x + H, H), fill=color, width=width)


def checker(d, W, H, s, color):
    for j, y in enumerate(range(0, H, s)):
        for i, x in enumerate(range(0, W, s)):
            if (i + j) % 2:
                d.rectangle((x, y, x + s, y + s), fill=color)


def crescent(layer, cx, cy, r, color, cut=0.35):
    """Trăng khuyết; layer phải là RGBA (phần khoét thành trong suốt)."""
    d = ImageDraw.Draw(layer)
    d.ellipse((cx - r, cy - r, cx + r, cy + r), fill=color)
    o = r * cut
    d.ellipse((cx - r + o * 1.4, cy - r - o * 0.6, cx + r + o * 1.4, cy + r - o * 0.6), fill=(0, 0, 0, 0))


def cloud(d, cx, cy, s, fill):
    for dx, dy, r in ((-0.3, 0.05, 0.2), (-0.1, -0.1, 0.27), (0.17, -0.04, 0.24), (0.36, 0.08, 0.17)):
        d.ellipse((cx + (dx - r) * s, cy + (dy - r) * s, cx + (dx + r) * s, cy + (dy + r) * s), fill=fill)
    d.rounded_rectangle((cx - 0.45 * s, cy + 0.02 * s, cx + 0.5 * s, cy + 0.25 * s), int(0.11 * s), fill=fill)


def barcode(d, box, rnd, color):
    x0, y0, x1, y1 = (int(v) for v in box)
    k = max(1, (x1 - x0) // 300)
    x = x0
    while True:
        w = rnd.choice([1, 1, 2, 3]) * k
        if x + w > x1:
            break
        d.rectangle((x, y0, x + w - 1, y1), fill=color)
        x += w + rnd.choice([1, 2, 3]) * k


def dashed(d, p0, p1, dash, gap, color, width=2):
    (x0, y0), (x1, y1) = p0, p1
    L = math.hypot(x1 - x0, y1 - y0) or 1
    dx, dy = (x1 - x0) / L, (y1 - y0) / L
    t = 0
    while t < L:
        e = min(t + dash, L)
        d.line((x0 + dx * t, y0 + dy * t, x0 + dx * e, y0 + dy * e), fill=color, width=width)
        t += dash + gap


def dashed_rect(d, box, dash, gap, color, width=2):
    x0, y0, x1, y1 = box
    for a, b in (((x0, y0), (x1, y0)), ((x1, y0), (x1, y1)), ((x1, y1), (x0, y1)), ((x0, y1), (x0, y0))):
        dashed(d, a, b, dash, gap, color, width)


def bevel(d, box, fill="#c0c0c0", pressed=False, w=3):
    """Nút/khung nổi kiểu Windows 95."""
    x0, y0, x1, y1 = box
    d.rectangle(box, fill=fill)
    hi, lo = ("#808080", "#ffffff") if pressed else ("#ffffff", "#808080")
    for i in range(w):
        d.line((x0 + i, y1 - i, x0 + i, y0 + i, x1 - i, y0 + i), fill=hi)
        d.line((x0 + i, y1 - i, x1 - i, y1 - i, x1 - i, y0 + i), fill=lo)


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


# --- batch 1 ---

def _b1_t(text):
    """Chuẩn hoá xuống dòng (chấp nhận cả chuỗi "\\n" thô)."""
    return text.replace("\\n", "\n").strip()


def _b1_f(kind, size):
    return load_font(find_font(kind), max(8, int(size)))


def _b1_box(W, H, pw, ph, lw, lh, cy=0.5):
    """Khung căn giữa: tỉ lệ (pw, ph) khi ảnh dọc, (lw, lh) khi ảnh ngang."""
    w, h = (W * lw, H * lh) if W > H else (W * pw, H * ph)
    x0, y0 = (W - w) / 2, H * cy - h / 2
    return tuple(int(v) for v in (x0, y0, x0 + w, y0 + h))


def _b1_split(text, n=4):
    """Chia text thành tối đa n đoạn (theo dòng, nếu chỉ 1 dòng thì theo câu)."""
    parts = [p.strip() for p in text.split("\n") if p.strip()]
    if len(parts) == 1:
        parts = [p for p in re.split(r"(?<=[.!?…])\s+", parts[0]) if p.strip()]
    while len(parts) > n:
        parts[-2:] = [parts[-2] + " " + parts[-1]]
    return parts or [text]


def _b1_clock(rnd):
    return f"{rnd.randint(6, 23)}:{rnd.randint(0, 59):02d}"


def _b1_today():
    return datetime.date.today()


def _b1_vn_date(dt):
    return f"{VN_WEEKDAYS[dt.weekday()]}, {dt.day} tháng {dt.month}"


def _b1_status_bar(d, box, time, color, light=None):
    """Thanh trạng thái điện thoại: giờ bên trái, sóng + pin bên phải."""
    x0, y0, x1, y1 = box
    h = y1 - y0
    cy = (y0 + y1) / 2
    label(d, (x0, cy), time, "bold", h * 0.62, color, "lm")
    bw, bh = h * 0.95, h * 0.48
    bx = x1 - bw - h * 0.08
    d.rounded_rectangle((bx, cy - bh / 2, bx + bw, cy + bh / 2), int(bh * 0.28), outline=color, width=max(2, int(h * 0.05)))
    d.rounded_rectangle((bx + h * 0.08, cy - bh / 2 + h * 0.08, bx + bw * 0.72, cy + bh / 2 - h * 0.08), int(bh * 0.15),
                        fill=color)
    d.rectangle((bx + bw + 1, cy - bh * 0.18, bx + bw + h * 0.07, cy + bh * 0.18), fill=color)
    sx = bx - h * 0.25
    for i in range(4):
        bh2 = h * (0.18 + 0.12 * i)
        xx = sx - (3 - i) * h * 0.17
        d.rounded_rectangle((xx - h * 0.11, cy + h * 0.26 - bh2, xx, cy + h * 0.26), 2,
                            fill=color if i < 3 or light is None else light)


def _b1_chev(d, x, y, s, color, w, direction="left"):
    """Mũi tên chữ V (left/right/down)."""
    if direction == "left":
        pts = [(x + s * 0.6, y - s), (x, y), (x + s * 0.6, y + s)]
    elif direction == "right":
        pts = [(x, y - s), (x + s * 0.6, y), (x, y + s)]
    else:
        pts = [(x - s, y - s * 0.4), (x, y + s * 0.3), (x + s, y - s * 0.4)]
    d.line(pts, fill=color, width=int(w), joint="curve")


def _b1_dots3(d, cx, cy, r, gap, color, vertical=False):
    for k in (-1, 0, 1):
        x, y = (cx, cy + k * gap) if vertical else (cx + k * gap, cy)
        d.ellipse((x - r, y - r, x + r, y + r), fill=color)


def _b1_avatar(img, cx, cy, r, cols, star="#ffffff"):
    """Avatar tròn gradient có ngôi sao lấp lánh."""
    gradient_fill(img, cols, lambda m: m.ellipse((cx - r, cy - r, cx + r, cy + r), fill=255), angle=45)
    d = ImageDraw.Draw(img)
    sparkle(d, cx, cy, r * 0.6, star)
    sparkle(d, cx + r * 0.45, cy - r * 0.45, r * 0.2, star)


def _b1_traffic(d, x, cy, r, gap):
    for i, c in enumerate(("#ff5f57", "#febc2e", "#28c840")):
        xx = x + i * gap
        d.ellipse((xx - r, cy - r, xx + r, cy + r), fill=c)


def _b1_segments(d, x, y, segs, font):
    """Vẽ một dòng code gồm nhiều đoạn màu (text, color), y là baseline."""
    for s, c in segs:
        d.text((x, y), s, font=font, fill=c, anchor="ls")
        x += font.getlength(s)
    return x


def _b1_pastel_bg(W, H, rnd, cols=None, blobs=None):
    cols = cols or rnd.choice([["#fde2f3", "#e5d9ff"], ["#d9f2ff", "#fbe3ff"], ["#fff1d6", "#ffd9e8"],
                               ["#e0f7ea", "#dbe8ff"]])
    img = gradient((W, H), cols, angle=rnd.choice([0, 35, 135]))
    soft_blobs(img, rnd, blobs or ["#ffffff", "#ffc8e4", "#c9d8ff", "#ffe6b3"], n=6, alpha=170)
    return img


def tpl_phone_notes(text, W, H, rnd):
    """Ảnh chụp màn hình app ghi chú trên điện thoại, nền pastel loang."""
    text, u = _b1_t(text), min(W, H)
    accent = rnd.choice(["#e0a100", "#f29d0a", "#d98c00"])
    paper = rnd.choice(["#fffdf7", "#ffffff", "#fbf8ef"])
    img = _b1_pastel_bg(W, H, rnd)
    card = _b1_box(W, H, 0.88, 0.9, 0.6, 0.9)
    x0, y0, x1, y1 = card
    r, p = int(u * 0.06), int(u * 0.065)
    shadow(img, card, r, offset=(0, int(u * 0.02)), blur=int(u * 0.04), alpha=70)
    d = ImageDraw.Draw(img)
    d.rounded_rectangle(card, r, fill=paper)
    time = _b1_clock(rnd)
    _b1_status_bar(d, (x0 + p, y0 + int(u * 0.03), x1 - p, y0 + int(u * 0.07)), time, "#1c1c1e")
    ty = y0 + int(u * 0.14)
    s = u * 0.022
    _b1_chev(d, x0 + p, ty, s, accent, u * 0.008)
    label(d, (x0 + p + s * 1.4, ty), "Ghi chú", "bold", u * 0.042, accent, "lm")
    # icon chia sẻ + menu
    ix = x1 - p - u * 0.03
    d.ellipse((ix - u * 0.03, ty - u * 0.03, ix + u * 0.03, ty + u * 0.03), outline=accent, width=int(u * 0.005))
    _b1_dots3(d, ix, ty, u * 0.0055, u * 0.014, accent)
    sx = ix - u * 0.1
    d.rounded_rectangle((sx - u * 0.022, ty - u * 0.008, sx + u * 0.022, ty + u * 0.032), int(u * 0.006), outline=accent,
                        width=int(u * 0.005))
    d.rectangle((sx - u * 0.01, ty - u * 0.012, sx + u * 0.01, ty), fill=paper)
    d.line((sx, ty - u * 0.04, sx, ty + u * 0.012), fill=accent, width=int(u * 0.005))
    d.line((sx - u * 0.013, ty - u * 0.027, sx, ty - u * 0.04, sx + u * 0.013, ty - u * 0.027), fill=accent,
           width=int(u * 0.005))
    dt = _b1_today()
    label(d, ((x0 + x1) / 2, ty + u * 0.085), f"{dt.day} tháng {dt.month}, {dt.year} lúc {time}", "regular",
          u * 0.027, "#a1a1a6", "mm")
    box = (x0 + p, ty + int(u * 0.15), x1 - p, y1 - int(u * 0.17))
    draw_text_block(img, text, box, find_font("bold"), "#1c1c1e", valign="top", max_size=int(u * 0.075), spacing=1.32)
    # thanh công cụ dưới
    by = y1 - int(u * 0.085)
    d.line((x0, by - u * 0.05, x1, by - u * 0.05), fill="#ececec", width=2)
    n, lw = 4, int(u * 0.005)
    for i in range(n):
        cx = x0 + p + (x1 - x0 - 2 * p) * i / (n - 1)
        q = u * 0.022
        if i == 0:  # checklist
            d.ellipse((cx - q, by - q, cx + q, by + q), outline=accent, width=lw)
            d.line((cx - q * 0.45, by, cx - q * 0.1, by + q * 0.4, cx + q * 0.5, by - q * 0.35), fill=accent, width=lw)
        elif i == 1:  # máy ảnh
            d.rounded_rectangle((cx - q * 1.2, by - q * 0.75, cx + q * 1.2, by + q * 0.9), int(q * 0.3), outline=accent,
                                width=lw)
            d.ellipse((cx - q * 0.45, by - q * 0.3, cx + q * 0.45, by + q * 0.6), outline=accent, width=lw)
        elif i == 2:  # bút
            d.polygon(rot_rect_points(cx, by, q * 0.5, q * 2.2, 40), outline=accent, width=lw)
        else:  # soạn mới
            d.rounded_rectangle((cx - q, by - q, cx + q, by + q), int(q * 0.3), outline=accent, width=lw)
            d.line((cx - q * 0.2, by + q * 0.2, cx + q * 1.1, by - q * 1.1), fill=accent, width=lw)
    d.rounded_rectangle(((x0 + x1) / 2 - u * 0.13, y1 - u * 0.03, (x0 + x1) / 2 + u * 0.13, y1 - u * 0.02), 5,
                        fill="#1c1c1e")
    add_grain(img, 8)
    return img


def tpl_chat_bubble(text, W, H, rnd):
    """Đoạn chat với "Vũ Trụ": câu hỏi của bạn và các bong bóng trả lời."""
    text, u = _b1_t(text), min(W, H)
    c1, c2 = rnd.choice([("#7b5cff", "#c06bff"), ("#ff4f8b", "#ff9a6b"), ("#2f80ed", "#56ccf2"),
                         ("#11998e", "#38ef7d")])
    img = _b1_pastel_bg(W, H, rnd)
    card = _b1_box(W, H, 0.9, 0.92, 0.56, 0.92)
    x0, y0, x1, y1 = card
    r, p = int(u * 0.05), int(u * 0.05)
    shadow(img, card, r, offset=(0, int(u * 0.02)), blur=int(u * 0.04), alpha=70)
    d = ImageDraw.Draw(img)
    d.rounded_rectangle(card, r, fill="#ffffff")
    time = _b1_clock(rnd)
    _b1_status_bar(d, (x0 + p, y0 + int(u * 0.028), x1 - p, y0 + int(u * 0.066)), time, "#111111")
    # header
    hy = y0 + int(u * 0.15)
    _b1_chev(d, x0 + p, hy, u * 0.022, c1, u * 0.008)
    ar = u * 0.045
    ax = x0 + p + u * 0.085
    _b1_avatar(img, ax, hy, ar, [c1, c2])
    d.ellipse((ax + ar * 0.55, hy + ar * 0.55, ax + ar * 1.05, hy + ar * 1.05), fill="#31c95a", outline="#ffffff",
              width=int(u * 0.005))
    label(d, (ax + ar + u * 0.025, hy - u * 0.004), "Vũ Trụ", "bold", u * 0.042, "#111111", "ls")
    label(d, (ax + ar + u * 0.025, hy + u * 0.01), "Đang hoạt động", "regular", u * 0.027, "#8e8e93", "lt")
    # icon gọi điện / video
    q = u * 0.02
    vx = x1 - p - q
    d.rounded_rectangle((vx - q * 2.2, hy - q * 0.8, vx - q * 0.5, hy + q * 0.8), int(q * 0.3), fill=c1)
    d.polygon([(vx - q * 0.5, hy), (vx + q * 0.6, hy - q * 0.7), (vx + q * 0.6, hy + q * 0.7)], fill=c1)
    hb = hy + int(u * 0.075)
    d.line((x0, hb, x1, hb), fill="#ededed", width=2)
    # ô nhập
    iy0, iy1 = y1 - int(u * 0.13), y1 - int(u * 0.05)
    d.ellipse((x0 + p, iy0 + u * 0.01, x0 + p + (iy1 - iy0) - u * 0.02, iy1 - u * 0.01), fill=c1)
    pc = (x0 + p + ((iy1 - iy0) - u * 0.02) / 2, (iy0 + iy1) / 2)
    d.line((pc[0] - q * 0.7, pc[1], pc[0] + q * 0.7, pc[1]), fill="#ffffff", width=int(u * 0.006))
    d.line((pc[0], pc[1] - q * 0.7, pc[0], pc[1] + q * 0.7), fill="#ffffff", width=int(u * 0.006))
    ix0 = x0 + p + (iy1 - iy0)
    d.rounded_rectangle((ix0, iy0, x1 - p - u * 0.08, iy1), (iy1 - iy0) // 2, fill="#f2f2f5")
    label(d, (ix0 + u * 0.03, (iy0 + iy1) / 2), "Nhắn tin...", "regular", u * 0.03, "#9a9aa0", "lm")
    hx, hyy = x1 - p - u * 0.035, (iy0 + iy1) / 2
    d.polygon(heart_points(hx, hyy + u * 0.004, u * 0.055), fill=c2)
    # tin nhắn
    top, bot = hb + int(u * 0.05), iy0 - int(u * 0.04)
    label(d, ((x0 + x1) / 2, top), f"Hôm nay {time}", "bold", u * 0.024, "#b0b0b5", "mt")
    top += int(u * 0.06)
    ask = rnd.choice(["Vũ Trụ ơi, hôm nay có gì cho con không ạ?", "Cho con xin một dấu hiệu đi ạ",
                      "Vũ Trụ ơi, con nên làm gì bây giờ?"])
    parts = _b1_split(text, 4)
    bold = find_font("bold")

    def fit(cw, ch, uu):
        maxw, gap, ex = cw * 0.79, int(uu * 0.016), int(uu * 0.06)
        for size in range(int(uu * 0.058), 27, -2):
            pad = int(size * 0.55)
            tot = ex + gap * (len(parts) + 1)
            for s in [ask] + parts:
                tot += measure_text(s, (0, 0, int(maxw - 2 * pad), 10 ** 5), bold, size)[2] + 2 * pad
            if tot <= ch:
                return size, tot
        return 28, tot

    cw, ch = x1 - x0 - 2 * p, bot - top
    size, tot = fit(cw, ch, u)
    k = 1.0
    while tot > ch and k < 4:  # chữ quá dài: vẽ lên layer lớn hơn rồi thu nhỏ
        k += 0.25
        size, tot = fit(cw * k, ch * k, u * k)
    lay = Image.new("RGBA", (int(cw * k), int(ch * k)), (255, 255, 255, 0))
    ld, uu = ImageDraw.Draw(lay), u * k
    maxw, gap = cw * k * 0.79, int(uu * 0.016)
    pad, rad = int(size * 0.55), int(min(size * 1.1, uu * 0.05))
    b = text_bubble(lay, ask, (lay.width, 0), (maxw - 2 * pad, 10 ** 5), bold, size, c1, "#ffffff", pad, rad, right=True)
    y = b[3] + int(uu * 0.008)
    label(ld, (lay.width, y), "Đã xem", "regular", uu * 0.022, "#a1a1a6", "rt")
    y += int(uu * 0.045)
    sm = uu * 0.03
    bx = sm * 2 + uu * 0.012
    for i, s in enumerate(parts):
        b = text_bubble(lay, s, (bx, y), (maxw - 2 * pad, 10 ** 5), bold, size, "#efeff4", "#111111", pad, rad)
        if i == len(parts) - 1:
            _b1_avatar(lay, sm, b[3] - sm, sm, [c1, c2])
            ld.ellipse((b[2] - uu * 0.03, b[3] - uu * 0.022, b[2] + uu * 0.02, b[3] + uu * 0.028), fill="#ffffff",
                       outline="#efeff4", width=3)
            ld.polygon(heart_points(b[2] - uu * 0.005, b[3] + uu * 0.004, uu * 0.03), fill="#ff3b5c")
        y = b[3] + gap
    if k > 1:
        lay = lay.resize((int(cw), int(ch)), Image.LANCZOS)
    img.alpha_composite(lay, (int(x0 + p), int(top)))
    return img


def tpl_lock_screen(text, W, H, rnd):
    """Màn hình khoá điện thoại: giờ lớn, ngày tiếng Việt và thông báo kính mờ."""
    text, u = _b1_t(text), min(W, H)
    cols, blobs, dark = rnd.choice([
        (["#0f0c29", "#302b63", "#24243e"], ["#6a3cff", "#ff5fa2", "#2b5cff"], True),
        (["#1a2a6c", "#b21f1f", "#fdbb2d"], ["#ff7a59", "#ffd36b", "#7a3cff"], True),
        (["#ffafbd", "#ffc3a0", "#c9a7ff"], ["#ffffff", "#ff8fb1", "#9fb8ff"], False),
        (["#0b3d4f", "#11766f", "#8de2c4"], ["#2fe0b0", "#4a7bff", "#a0ffe0"], True),
    ])
    img = gradient((W, H), cols, angle=rnd.choice([0, 20, 160]))
    soft_blobs(img, rnd, blobs, n=7, alpha=200, blur=0.14)
    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ld = ImageDraw.Draw(layer)
    star_field(ld, rnd, (0, 0, W, H * 0.6), int(W * H / 9000), (255, 255, 255, 150 if dark else 90), u * 0.003)
    for _ in range(6):
        sparkle(ld, rnd.uniform(0, W), rnd.uniform(0, H * 0.7), u * rnd.uniform(0.008, 0.02), (255, 255, 255, 200))
    crescent(layer, W * rnd.uniform(0.7, 0.85), H * 0.5, u * 0.09, (255, 245, 220, 110))
    img.alpha_composite(layer)
    add_grain(img, 10)
    d = ImageDraw.Draw(img)
    land = W > H
    # khoá
    lx, ly = W / 2, H * (0.07 if not land else 0.06)
    q = u * 0.018
    d.arc((lx - q * 0.75, ly - q * 1.7, lx + q * 0.75, ly - q * 0.1), 180, 360, fill="#ffffff", width=int(u * 0.005))
    d.line((lx - q * 0.75, ly - q * 0.9, lx - q * 0.75, ly - q * 0.1), fill="#ffffff", width=int(u * 0.005))
    d.line((lx + q * 0.75, ly - q * 0.9, lx + q * 0.75, ly - q * 0.1), fill="#ffffff", width=int(u * 0.005))
    d.rounded_rectangle((lx - q * 1.1, ly - q * 0.3, lx + q * 1.1, ly + q * 1.2), int(q * 0.3), fill="#ffffff")
    dy = ly + u * 0.075
    label(d, (W / 2, dy), _b1_vn_date(_b1_today()), "bold", u * 0.042, (255, 255, 255), "mm")
    time = _b1_clock(rnd)
    tf = _b1_f("round", u * (0.26 if not land else 0.2))
    tl = Image.new("RGBA", (W, H), (255, 255, 255, 0))
    ib = tf.getbbox(time, anchor="mt")
    ImageDraw.Draw(tl).text((W / 2, dy + u * 0.05 - ib[1]), time, font=tf, fill=(255, 255, 255, 255), anchor="mt")
    tb = tl.getbbox()
    glow(img, tl, (0.02,))
    # thông báo
    nw = min(W * 0.9, u * 1.0) if not land else W * 0.5
    nx0, nx1 = (W - nw) / 2, (W + nw) / 2
    ny0 = tb[3] + u * 0.07
    pad = int(u * 0.04)
    head = int(u * 0.085)
    maxh = H - u * 0.2 - ny0 - head - 2 * pad - u * 0.04
    bold = find_font("bold")
    f, tw, th, _ = measure_text(text, (0, 0, int(nw - 2 * pad), int(maxh)), bold, int(u * 0.055), spacing=1.25)
    ny1 = ny0 + head + th + 2 * pad
    peek = (nx0 + u * 0.035, ny0 + u * 0.03, nx1 - u * 0.035, ny1 + u * 0.03)
    frosted(img, peek, int(u * 0.045), tint=(255, 255, 255, 90), outline=None)
    frosted(img, (nx0, ny0, nx1, ny1), int(u * 0.045), tint=(250, 250, 255, 200), outline=(255, 255, 255, 160))
    d = ImageDraw.Draw(img)
    ic = u * 0.055
    icx, icy = nx0 + pad, ny0 + pad
    gradient_fill(img, [blobs[0], blobs[1]],
                  lambda m: m.rounded_rectangle((icx, icy, icx + ic, icy + ic), int(ic * 0.25), fill=255), angle=45)
    sparkle(d, icx + ic / 2, icy + ic / 2, ic * 0.32, "#ffffff")
    label(d, (icx + ic + u * 0.02, icy + ic / 2), "VŨ TRỤ", "bold", u * 0.028, "#55555c", "lm")
    label(d, (nx1 - pad, icy + ic / 2), "bây giờ", "regular", u * 0.026, "#7a7a80", "rm")
    tb2 = (nx0 + pad, ny0 + pad + head, nx1 - pad, ny0 + pad + head + th)
    draw_text_block(img, text, tb2, bold, "#141418", valign="top", max_size=f.size, spacing=1.25)
    if peek[3] < H - u * 0.2:
        label(d, (W / 2, peek[3] + u * 0.04), "2 thông báo khác", "bold", u * 0.026, (255, 255, 255), "mt")
    # nút đèn pin / máy ảnh + thanh home
    br = u * 0.055
    for k, cx in enumerate((W * 0.15 if not land else W * 0.08, W * 0.85 if not land else W * 0.92)):
        cy = H - u * 0.12
        frosted(img, (cx - br, cy - br, cx + br, cy + br), int(br), tint=(0, 0, 0, 60), outline=None)
        d = ImageDraw.Draw(img)
        if k == 0:
            d.polygon([(cx - br * 0.3, cy - br * 0.45), (cx + br * 0.3, cy - br * 0.45), (cx + br * 0.15, cy - br * 0.1),
                       (cx - br * 0.15, cy - br * 0.1)], fill="#ffffff")
            d.rounded_rectangle((cx - br * 0.15, cy - br * 0.1, cx + br * 0.15, cy + br * 0.5), 3, fill="#ffffff")
        else:
            d.rounded_rectangle((cx - br * 0.45, cy - br * 0.28, cx + br * 0.45, cy + br * 0.35), int(br * 0.1),
                                fill="#ffffff")
            d.ellipse((cx - br * 0.17, cy - br * 0.12, cx + br * 0.17, cy + br * 0.22), fill="#333333")
    d.rounded_rectangle((W / 2 - u * 0.14, H - u * 0.03, W / 2 + u * 0.14, H - u * 0.019), 6, fill="#ffffff")
    return img


def tpl_social_post(text, W, H, rnd):
    """Bài đăng mạng xã hội: avatar, ảnh vuông chứa chữ, lượt thích và chú thích."""
    text, u = _b1_t(text), min(W, H)
    img = _b1_pastel_bg(W, H, rnd, ["#f4f4f7", "#ece8f5"], ["#ffffff", "#f2e6ff", "#e6f0ff"])
    c1, c2, c3 = rnd.choice([("#ff6a88", "#ff99ac", "#7a3cff"), ("#4facfe", "#00f2fe", "#3a1c71"),
                             ("#f7971e", "#ffd200", "#e9446a"), ("#8e2de2", "#4a00e0", "#ff6fd8")])
    land = W > H
    card = _b1_box(W, H, 0.9, 0.84, 0.84, 0.86)
    x0, y0, x1, y1 = card
    if not land:  # chiều cao card vừa đủ: header + ảnh vuông + phần chân
        side = min(x1 - x0, (y1 - y0) - u * 0.46)
        ch = u * 0.46 + side
        x0, x1, y0 = (W - side) / 2, (W + side) / 2, (H - ch) / 2
        card = (int(x0), int(y0), int(x1), int(y0 + ch))
        x0, y0, x1, y1 = card
    rad = int(u * 0.035)
    shadow(img, card, rad, offset=(0, int(u * 0.015)), blur=int(u * 0.035), alpha=60)
    d = ImageDraw.Draw(img)
    d.rounded_rectangle(card, rad, fill="#ffffff")
    p = int(u * 0.035)
    if land:
        sq = (x0, y0, x0 + (y1 - y0), y1)
        cx0, cx1 = sq[2], x1
    else:
        hh = int(u * 0.14)
        side = x1 - x0
        sq = (x0, y0 + hh, x1, y0 + hh + side)
        cx0, cx1 = x0, x1
    # ảnh vuông
    art = gradient((sq[2] - sq[0], sq[3] - sq[1]), [c3, c1, c2], angle=rnd.choice([30, 135]))
    soft_blobs(art, rnd, [c1, c2, "#ffffff"], n=4, alpha=110)
    ad = ImageDraw.Draw(art)
    aw, ah = art.size
    for _ in range(9):
        sparkle(ad, rnd.uniform(0, aw), rnd.uniform(0, ah), aw * rnd.uniform(0.012, 0.03), (255, 255, 255, 220))
    m = int(aw * 0.1)
    draw_text_block(art, text, (m, m, aw - m, ah - m), find_font("black"), "#ffffff", align="center",
                    max_size=int(aw * 0.095), spacing=1.22, stroke=max(1, int(aw * 0.003)),
                    stroke_color=mix(c3, "#000000", 0.3))
    mask = Image.new("L", art.size, 0)
    md = ImageDraw.Draw(mask)
    if land:
        md.rounded_rectangle((0, 0, aw + rad * 2, ah - 1), rad, fill=255)
    else:
        md.rectangle((0, 0, aw, ah), fill=255)
    img.paste(art, sq[:2], mask)
    d = ImageDraw.Draw(img)
    # header
    hy = (y0 + p + u * 0.045) if land else (y0 + (sq[1] - y0) / 2)
    ar = u * 0.042
    ax = cx0 + p + ar
    gradient_fill(img, ["#feda75", "#fa7e1e", "#d62976", "#962fbf"],
                  lambda mm: mm.ellipse((ax - ar - 6, hy - ar - 6, ax + ar + 6, hy + ar + 6), fill=255), angle=45)
    d.ellipse((ax - ar - 2, hy - ar - 2, ax + ar + 2, hy + ar + 2), fill="#ffffff")
    _b1_avatar(img, ax, hy, ar - 3, [c1, c3])
    name = "vutru.thongthai"
    nf = _b1_f("bold", u * 0.032)
    nxx = ax + ar + u * 0.025
    d.text((nxx, hy - u * 0.004), name, font=nf, fill="#111111", anchor="ls")
    bx = nxx + nf.getlength(name) + u * 0.02
    br = u * 0.013
    d.polygon(star_points(bx, hy - u * 0.016, br * 1.25, br * 1.05, 10), fill="#3897f0")
    d.line((bx - br * 0.45, hy - u * 0.016, bx - br * 0.1, hy - u * 0.016 + br * 0.4, bx + br * 0.5, hy - u * 0.016 - br * 0.35),
           fill="#ffffff", width=max(2, int(u * 0.004)))
    label(d, (nxx, hy + u * 0.01), "Tử vi · Thông điệp", "regular", u * 0.024, "#8e8e8e", "lt")
    _b1_dots3(d, cx1 - p - u * 0.02, hy, u * 0.005, u * 0.014, "#262626")
    # hàng hành động
    ay = (sq[3] + u * 0.06) if not land else (y1 - p - u * 0.2)
    if land:
        d.line((cx0, hy + ar + p * 0.8, cx1, hy + ar + p * 0.8), fill="#efefef", width=2)
    q = u * 0.03
    lw = max(2, int(u * 0.005))
    hx = cx0 + p + q
    d.polygon(heart_points(hx, ay, q * 2.1), fill="#ff3040")
    cx = hx + q * 2.8
    d.ellipse((cx - q, ay - q, cx + q, ay + q), outline="#262626", width=lw)
    d.polygon([(cx - q * 0.9, ay + q * 0.5), (cx - q * 1.1, ay + q * 1.1), (cx - q * 0.4, ay + q * 0.9)], fill="#262626")
    sx = cx + q * 2.8
    d.polygon([(sx - q, ay - q * 0.9), (sx + q, ay - q * 0.9), (sx, ay + q)], outline="#262626", width=lw)
    d.line((sx - q * 0.7, ay - q * 0.7, sx + q * 0.1, ay - q * 0.15), fill="#262626", width=lw)
    kx = cx1 - p - q * 0.8
    d.polygon([(kx - q * 0.75, ay - q), (kx + q * 0.75, ay - q), (kx + q * 0.75, ay + q), (kx, ay + q * 0.45),
               (kx - q * 0.75, ay + q)], outline="#262626", width=lw)
    if not land:
        for k in (-1, 0, 1):
            mx = (cx0 + cx1) / 2 + k * u * 0.022
            d.ellipse((mx - u * 0.006, ay - u * 0.006, mx + u * 0.006, ay + u * 0.006),
                      fill="#3897f0" if k == -1 else "#c8c8c8")
    likes = f"{rnd.randint(2, 98)}.{rnd.randint(100, 999)} lượt thích"
    ly = ay + q * 1.9
    label(d, (cx0 + p, ly), likes, "bold", u * 0.03, "#111111", "lt")
    cap = rnd.choice(["Nhận lấy năng lượng tốt hôm nay nhé", "Ai thấy được là có duyên đó", "Lưu lại để nhận may mắn"])
    capf = _b1_f("bold", u * 0.027)
    d.text((cx0 + p, ly + u * 0.05), name, font=capf, fill="#111111", anchor="lt")
    cw = capf.getlength(name + " ")
    cap_box = (int(cx0 + p), int(ly + u * 0.05), int(cx1 - p), int(ly + u * 0.12))
    rf = _b1_f("regular", u * 0.027)
    cap_line = cap
    while rf.getlength(cap_line) > cap_box[2] - cap_box[0] - cw and len(cap_line) > 4:
        cap_line = cap_line[:-2]
    if cap_line != cap:
        cap_line = cap_line.rstrip() + "..."
    d.text((cx0 + p + cw, ly + u * 0.05), cap_line, font=rf, fill="#262626", anchor="lt")
    label(d, (cx0 + p, ly + u * 0.095), f"Xem tất cả {rnd.randint(120, 999)} bình luận", "regular", u * 0.026, "#8e8e8e",
          "lt")
    label(d, (cx0 + p, ly + u * 0.14), f"{rnd.randint(1, 11)} giờ trước", "regular", u * 0.022, "#a8a8a8", "lt")
    if land:
        # vài bình luận mẫu ở cột phải
        cy = hy + ar + p * 1.8
        for who, msg in [("ngoc.an_", "Con xin nhận ạ"), ("minh.tuan", "Đúng quá trời luôn"),
                         ("thu.ha.99", "Lưu lại liền"), ("bao.chau", "Mong là vậy")][:3]:
            if cy > ay - u * 0.12:
                break
            _b1_avatar(img, cx0 + p + u * 0.025, cy + u * 0.02, u * 0.025, [c2, c1])
            d = ImageDraw.Draw(img)
            ff = _b1_f("bold", u * 0.026)
            d.text((cx0 + p + u * 0.07, cy + u * 0.02), who, font=ff, fill="#111111", anchor="lm")
            d.text((cx0 + p + u * 0.07 + ff.getlength(who + "  "), cy + u * 0.02), msg, font=_b1_f("regular", u * 0.026),
                   fill="#262626", anchor="lm")
            cy += u * 0.085
    return img


def tpl_win95(text, W, H, rnd):
    """Cửa sổ sổ tay hệ điều hành cổ điển kiểu bevel xám trên desktop xanh két."""
    text, u = _b1_t(text), min(W, H)
    desk = rnd.choice(["#008080", "#2a7f86", "#3a6ea5", "#7a6aa8"])
    img = Image.new("RGBA", (W, H), desk)
    d = ImageDraw.Draw(img)
    land = W > H
    bw = max(2, int(u * 0.004))
    tbh = int(u * 0.065)
    # icon desktop
    names = ["Máy tính", "Vũ Trụ", "Thùng rác"]
    for i, nm in enumerate(names):
        if land:
            cx, cy = W * 0.065, H * 0.1 + i * u * 0.2
        else:
            cx, cy = W * 0.13 + i * W * 0.2, H * 0.06
        s = u * 0.045
        if i == 0:
            d.rectangle((cx - s, cy - s * 0.85, cx + s, cy + s * 0.55), fill="#c0c0c0", outline="#000000", width=2)
            d.rectangle((cx - s * 0.8, cy - s * 0.65, cx + s * 0.8, cy + s * 0.35), fill="#0000a8")
            d.rectangle((cx - s * 0.5, cy + s * 0.6, cx + s * 0.5, cy + s * 0.85), fill="#c0c0c0", outline="#000000", width=2)
        elif i == 1:
            d.polygon([(cx - s, cy - s * 0.7), (cx - s * 0.2, cy - s * 0.7), (cx, cy - s * 0.45), (cx + s, cy - s * 0.45),
                       (cx + s, cy + s * 0.8), (cx - s, cy + s * 0.8)], fill="#f7d65a", outline="#000000")
            sparkle(d, cx, cy + s * 0.15, s * 0.45, "#ffffff")
        else:
            d.polygon([(cx - s * 0.7, cy - s * 0.6), (cx + s * 0.7, cy - s * 0.6), (cx + s * 0.55, cy + s * 0.85),
                       (cx - s * 0.55, cy + s * 0.85)], fill="#dcdcdc", outline="#000000")
            d.rectangle((cx - s * 0.85, cy - s * 0.8, cx + s * 0.85, cy - s * 0.6), fill="#9a9a9a", outline="#000000")
        label(d, (cx, cy + s * 1.2), nm, "regular", u * 0.024, "#ffffff", "mt")
    # cửa sổ
    if land:
        win = (int(W * 0.17), int(H * 0.08), int(W * 0.85), H - tbh - int(H * 0.08))
    else:
        win = (int(W * 0.05), int(H * 0.15), int(W * 0.95), H - tbh - int(H * 0.06))
    x0, y0, x1, y1 = win
    d.rectangle((x0 + u * 0.012, y0 + u * 0.012, x1 + u * 0.012, y1 + u * 0.012), fill=mix(desk, "#000000", 0.45))
    bevel(d, win, w=bw)
    th = int(u * 0.055)
    tb = (x0 + bw + 2, y0 + bw + 2, x1 - bw - 2, y0 + bw + 2 + th)
    gradient_fill(img, ["#000080", "#1084d0"], lambda m: m.rectangle(tb, fill=255), angle=90)
    d = ImageDraw.Draw(img)
    ic = th * 0.6
    d.rectangle((tb[0] + th * 0.2, tb[1] + th * 0.2, tb[0] + th * 0.2 + ic, tb[1] + th * 0.2 + ic), fill="#ffffff",
                outline="#000000")
    h_lines(d, (tb[0] + th * 0.28, tb[1] + th * 0.25, tb[0] + th * 0.12 + ic, tb[1] + th * 0.15 + ic), max(3, int(ic / 4)),
            "#000080", 1)
    label(d, (tb[0] + th * 0.35 + ic, (tb[1] + tb[3]) / 2), "thong_diep.txt - Sổ tay", "bold", th * 0.5, "#ffffff", "lm")
    bs = th * 0.78
    for k in range(3):
        bx1 = tb[2] - th * 0.12 - k * (bs + th * 0.08) - (th * 0.08 if k == 0 else 0)
        bb = (bx1 - bs, tb[1] + (th - bs * 0.88) / 2, bx1, tb[1] + (th + bs * 0.88) / 2)
        bevel(d, bb, w=max(2, bw - 1))
        cx, cy, q = (bb[0] + bb[2]) / 2, (bb[1] + bb[3]) / 2, bs * 0.22
        lw = max(2, int(u * 0.004))
        if k == 0:
            d.line((cx - q, cy - q, cx + q, cy + q), fill="#000000", width=lw)
            d.line((cx - q, cy + q, cx + q, cy - q), fill="#000000", width=lw)
        elif k == 1:
            d.rectangle((cx - q, cy - q, cx + q, cy + q), outline="#000000", width=max(2, lw - 1))
            d.line((cx - q, cy - q + 1, cx + q, cy - q + 1), fill="#000000", width=lw)
        else:
            d.line((cx - q, cy + q, cx + q * 0.6, cy + q), fill="#000000", width=lw)
    # menu
    my = tb[3] + th * 0.5
    mf = _b1_f("regular", th * 0.46)
    mx = x0 + th * 0.4
    for it in ["Tệp", "Sửa", "Định dạng", "Xem", "Trợ giúp"]:
        if mx + mf.getlength(it) > x1 - th * 0.4:
            break
        d.text((mx, my), it, font=mf, fill="#000000", anchor="lm")
        d.line((mx, my + th * 0.26, mx + mf.getlength(it[0]), my + th * 0.26), fill="#000000", width=1)
        mx += mf.getlength(it) + th * 0.6
    # vùng soạn thảo
    sbh = int(th * 0.75)
    ed = (x0 + bw + 6, int(my + th * 0.45), x1 - bw - 6, y1 - bw - 8 - sbh)
    bevel(d, ed, fill="#ffffff", pressed=True, w=bw)
    sw = int(th * 0.75)
    sc = (ed[2] - bw - sw, ed[1] + bw, ed[2] - bw, ed[3] - bw)
    d.rectangle(sc, fill="#dfdfdf")
    dither = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    checker(ImageDraw.Draw(dither), W, H, 2, (255, 255, 255, 120))
    for k, (a, b) in enumerate(((sc[1], sc[1] + sw), (sc[3] - sw, sc[3]))):
        bevel(d, (sc[0], a, sc[2], b), w=max(2, bw - 1))
        cx, cy, q = (sc[0] + sc[2]) / 2, (a + b) / 2, sw * 0.2
        pts = [(cx - q, cy + q * 0.5), (cx + q, cy + q * 0.5), (cx, cy - q * 0.5)] if k == 0 else \
            [(cx - q, cy - q * 0.5), (cx + q, cy - q * 0.5), (cx, cy + q * 0.5)]
        d.polygon(pts, fill="#000000")
    bevel(d, (sc[0], sc[1] + sw + 2, sc[2], sc[1] + sw * 2.6), w=max(2, bw - 1))
    pad = int(u * 0.035)
    tbx = (ed[0] + pad, ed[1] + pad, sc[0] - pad, ed[3] - pad)
    f = draw_text_block(img, text, tbx, find_font("mono"), "#000000", valign="top", max_size=int(u * 0.068),
                        spacing=1.3)
    # thanh trạng thái
    st = (ed[0], y1 - bw - 4 - sbh, ed[2], y1 - bw - 4)
    mid = st[0] + (st[2] - st[0]) * 0.55
    bevel(d, (st[0], st[1], mid - 4, st[3]), pressed=True, w=2)
    bevel(d, (mid, st[1], st[2], st[3]), pressed=True, w=2)
    label(d, (mid + th * 0.25, (st[1] + st[3]) / 2), f"Dòng 1, Cột {rnd.randint(2, 40)}", "regular", sbh * 0.5, "#000000",
          "lm")
    label(d, (st[0] + th * 0.25, (st[1] + st[3]) / 2), "100%  UTF-8", "regular", sbh * 0.5, "#000000", "lm")
    # taskbar
    tbar = (0, H - tbh, W, H)
    bevel(d, (-bw, H - tbh, W + bw, H + bw), w=bw)
    sbw = u * 0.2
    sb = (u * 0.012, H - tbh + u * 0.01, u * 0.012 + sbw, H - u * 0.01)
    bevel(d, sb, w=bw)
    sq = (sb[3] - sb[1]) * 0.55
    scx, scy = sb[0] + sq * 0.9, (sb[1] + sb[3]) / 2
    for k, c in enumerate(["#ff3b30", "#34c759", "#007aff", "#ffcc00"]):
        ox, oy = (k % 2) * sq / 2, (k // 2) * sq / 2
        d.rectangle((scx - sq / 2 + ox, scy - sq / 2 + oy, scx + ox - 2, scy + oy - 2), fill=c)
    label(d, (scx + sq * 0.8, scy), "Bắt đầu", "bold", tbh * 0.42, "#000000", "lm")
    task = (sb[2] + u * 0.015, sb[1], min(sb[2] + u * 0.015 + u * 0.38, W * 0.7), sb[3])
    bevel(d, task, pressed=True, w=bw)
    label(d, (task[0] + u * 0.02, scy), "thong_diep.txt", "bold", tbh * 0.38, "#000000", "lm")
    clk = (W - u * 0.17, sb[1], W - u * 0.012, sb[3])
    bevel(d, clk, pressed=True, w=2)
    label(d, ((clk[0] + clk[2]) / 2, scy), _b1_clock(rnd), "regular", tbh * 0.4, "#000000", "mm")
    return img


def tpl_terminal(text, W, H, rnd):
    """Cửa sổ dòng lệnh nền tối, chữ mono xanh lá phát sáng."""
    text, u = _b1_t(text), min(W, H)
    green = rnd.choice(["#39ff14", "#4dff88", "#7CFC00"])
    img = gradient((W, H), rnd.choice([["#0f2027", "#203a43", "#2c5364"], ["#1a0b2e", "#2d1b4e", "#0b1a3a"],
                                       ["#0b0f19", "#16222a", "#3a6073"]]), angle=rnd.choice([0, 135]))
    soft_blobs(img, rnd, ["#1e6f5c", "#2c3e8f", "#5b2c83"], n=5, alpha=150)
    add_grain(img, 10)
    win = _b1_box(W, H, 0.9, 0.72, 0.72, 0.82)
    x0, y0, x1, y1 = win
    rad = int(u * 0.025)
    shadow(img, win, rad, offset=(0, int(u * 0.02)), blur=int(u * 0.04), alpha=140)
    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ld = ImageDraw.Draw(layer)
    ld.rounded_rectangle(win, rad, fill=(10, 13, 18, 240), outline=(80, 90, 110, 255), width=2)
    th = int(u * 0.065)
    ld.rounded_rectangle((x0, y0, x1, y0 + th), rad, fill=(36, 40, 52, 255))
    ld.rectangle((x0, y0 + th - rad, x1, y0 + th), fill=(36, 40, 52, 255))
    img.alpha_composite(layer)
    d = ImageDraw.Draw(img)
    _b1_traffic(d, x0 + th * 0.55, y0 + th / 2, th * 0.15, th * 0.45)
    label(d, ((x0 + x1) / 2, y0 + th / 2), "vutru@thienha: ~", "mono", th * 0.38, "#9aa3b5", "mm")
    p = int(u * 0.045)
    sf = _b1_f("mono", u * 0.03)
    lh = int(u * 0.05)
    y = y0 + th + p + lh * 0.7
    xl = x0 + p
    _b1_segments(d, xl, y, [("vutru@thienha", "#5fd7ff"), (":~$ ", "#c0c0c0"), ("./boi --hom-nay", "#ffffff")], sf)
    y += lh
    _b1_segments(d, xl, y, [("Đang kết nối với vũ trụ...", mix(green, "#000000", 0.35))], sf)
    y += lh
    # thanh tiến trình
    pw = min((x1 - x0) - 2 * p - sf.getlength(" 100%") - u * 0.02, u * 0.6)
    bh = sf.size * 0.75
    d.rectangle((xl, y - bh, xl + pw, y), outline=green, width=2)
    n = 20
    for k in range(n):
        bx = xl + 4 + k * (pw - 8) / n
        d.rectangle((bx, y - bh + 4, bx + (pw - 8) / n - 3, y - 4), fill=green)
    d.text((xl + pw + u * 0.02, y), "100%", font=sf, fill=green, anchor="ls")
    y += lh
    _b1_segments(d, xl, y, [("> THÔNG ĐIỆP:", "#ffd866")], sf)
    y += lh * 0.5
    box = (int(xl), int(y), int(x1 - p), int(y1 - p - lh * 1.6))
    mono = find_font("mono")
    f, tw, tht, tlh = measure_text(text, box, mono, int(u * 0.065), spacing=1.32)
    glow_text(img, text, (box[0], box[1], box[2], box[1] + tht), mono, green, valign="top", max_size=f.size,
              spacing=1.32, radii=(0.02, 0.006))
    d = ImageDraw.Draw(img)
    y = box[1] + tht + lh * 0.9
    x = _b1_segments(d, xl, y, [("vutru@thienha", "#5fd7ff"), (":~$ ", "#c0c0c0")], sf)
    d.rectangle((x + 2, y - sf.size * 0.85, x + sf.size * 0.55, y + sf.size * 0.12), fill=green)
    # scanline
    sl = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    h_lines(ImageDraw.Draw(sl), (x0, y0 + th, x1, y1 - rad), max(3, int(u * 0.004)), (0, 0, 0, 55), 1)
    img.alpha_composite(sl)
    return img


def tpl_code_editor(text, W, H, rnd):
    """Trình soạn code theme tối: thông điệp nằm trong chuỗi của một hàm."""
    text, u = _b1_t(text), min(W, H)
    C = dict(bg="#1e1e2e", side="#181825", fg="#cdd6f4", kw="#cba6f7", fn="#89b4fa", st="#a6e3a1", cm="#7f849c",
             num="#585b70", acc=rnd.choice(["#cba6f7", "#f5c2e7", "#89dceb", "#fab387"]))
    img = _b1_pastel_bg(W, H, rnd, rnd.choice([["#c9b6ff", "#ffc6e0"], ["#a8e6ff", "#d5c6ff"], ["#ffd6a5", "#ffb3c6"]]),
                     ["#ffffff", "#e4d4ff", "#ffd1e8"])
    land = W > H
    win = _b1_box(W, H, 0.92, 0.84, 0.82, 0.86)
    x0, y0, x1, y1 = win
    rad = int(u * 0.022)
    shadow(img, win, rad, offset=(0, int(u * 0.02)), blur=int(u * 0.04), alpha=110)
    d = ImageDraw.Draw(img)
    d.rounded_rectangle(win, rad, fill=C["bg"])
    th = int(u * 0.06)
    d.rounded_rectangle((x0, y0, x1, y0 + th), rad, fill=C["side"])
    d.rectangle((x0, y0 + th - rad, x1, y0 + th), fill=C["side"])
    _b1_traffic(d, x0 + th * 0.5, y0 + th / 2, th * 0.14, th * 0.42)
    label(d, ((x0 + x1) / 2, y0 + th / 2), "thong_diep.py — vu-tru", "mono", th * 0.36, "#a6adc8", "mm")
    sbh = int(u * 0.045)
    # thanh hoạt động bên trái
    ab = int(u * 0.075)
    d.rectangle((x0, y0 + th, x0 + ab, y1 - sbh), fill=C["side"])
    for k in range(4):
        cy = y0 + th + ab * (0.6 + k * 0.95)
        q = ab * 0.2
        col = C["fg"] if k == 0 else C["num"]
        if k == 0:
            d.rectangle((x0, cy - q * 1.4, x0 + 4, cy + q * 1.4), fill=C["acc"])
        d.rounded_rectangle((x0 + ab / 2 - q, cy - q * 1.2, x0 + ab / 2 + q, cy + q * 1.2), 3, outline=col, width=3)
    ex = x0 + ab
    if land:  # cây thư mục
        sw = int((x1 - x0) * 0.2)
        d.rectangle((ex, y0 + th, ex + sw, y1 - sbh), fill="#1b1b29")
        ff = _b1_f("mono", u * 0.026)
        d.text((ex + u * 0.025, y0 + th + u * 0.04), "VU-TRU", font=ff, fill="#a6adc8", anchor="lm")
        for k, (nm, ind, col) in enumerate([("v tu_vi", 0, C["fg"]), ("con_giap.py", 1, C["fn"]),
                                            ("thong_diep.py", 1, C["acc"]), ("may_man.json", 1, "#f9e2af"),
                                            ("> loc", 0, C["fg"]), ("README.md", 0, C["cm"])]):
            yy = y0 + th + u * (0.1 + k * 0.055)
            if k == 2:
                d.rectangle((ex, yy - u * 0.024, ex + sw, yy + u * 0.024), fill="#313244")
            d.text((ex + u * 0.03 + ind * u * 0.03, yy), nm, font=ff, fill=col, anchor="lm")
        ex += sw
    # tab
    tab_h = int(u * 0.06)
    d.rectangle((ex, y0 + th, x1, y0 + th + tab_h), fill=C["side"])
    tf = _b1_f("mono", u * 0.027)
    tname = "thong_diep.py"
    tw_ = tf.getlength(tname) + u * 0.1
    d.rectangle((ex, y0 + th, ex + tw_, y0 + th + tab_h), fill=C["bg"])
    d.line((ex, y0 + th + 1, ex + tw_, y0 + th + 1), fill=C["acc"], width=3)
    d.ellipse((ex + u * 0.022, y0 + th + tab_h / 2 - u * 0.009, ex + u * 0.04, y0 + th + tab_h / 2 + u * 0.009),
              fill="#f9e2af")
    d.text((ex + u * 0.052, y0 + th + tab_h / 2), tname, font=tf, fill=C["fg"], anchor="lm")
    if ex + tw_ * 2 < x1:
        d.text((ex + tw_ + u * 0.03, y0 + th + tab_h / 2), "may_man.json", font=tf, fill=C["num"], anchor="lm")
    # vùng code
    top = y0 + th + tab_h + int(u * 0.03)
    bot = y1 - sbh - int(u * 0.03)
    mono = find_font("mono")
    gut = int(u * 0.075)
    cx0 = ex + gut + int(u * 0.02)
    mm = int(u * 0.06) if land else 0
    cx1 = x1 - int(u * 0.03) - mm
    sp = 1.45
    for size in range(int(u * 0.05), 25, -2):
        lh = int(size * sp)
        f = load_font(mono, size)
        ind = f.getlength("        ")
        boxh = bot - top - 9 * lh
        if boxh < lh or f.getlength("# >> may_man += 1000") > cx1 - cx0 or f.getlength("# Thông điệp vũ trụ gửi bạn") > cx1 - cx0:
            continue
        ft, tw, tht, tlh = measure_text(text, (0, 0, int(cx1 - cx0 - ind), boxh), mono, size, spacing=sp)
        if ft.size == size and tht <= boxh:
            break
    n_txt = max(1, round(tht / tlh))
    f = load_font(mono, ft.size)
    lh = tlh
    ind = f.getlength("        ")
    ind4 = f.getlength("    ")
    code_top = [
        [("# Thông điệp vũ trụ gửi bạn", C["cm"])],
        [("from ", C["kw"]), ("vu_tru ", C["fg"]), ("import ", C["kw"]), ("may_man", C["fg"])],
        [],
        [("def ", C["kw"]), ("thong_diep", C["fn"]), ("():", C["fg"])],
        [("    return ", C["kw"]), ('"""', C["st"])],
    ]
    code_bot = [[("    " + '"""', C["st"])], [],
                [("print", C["fn"]), ("(", C["fg"]), ("thong_diep", C["fn"]), ("())", C["fg"])],
                [("# >> may_man += ", C["cm"]), ("100", "#fab387")]]
    total = len(code_top) + n_txt + len(code_bot)
    y = top + (bot - top - total * lh) / 2
    gf = _b1_f("mono", f.size * 0.8)
    cur = len(code_top) + n_txt - 1
    for i in range(total):
        base = y + i * lh + int(lh * 0.5 + f.size * 0.36)
        if i == cur:
            d.rectangle((ex, y + i * lh, x1 - mm, y + (i + 1) * lh), fill="#262637")
        d.text((ex + gut, base), str(i + 1), font=gf, fill=C["fg"] if i == cur else C["num"], anchor="rs")
        if i < len(code_top):
            _b1_segments(d, cx0, base, code_top[i], f)
        elif i >= len(code_top) + n_txt:
            _b1_segments(d, cx0, base, code_bot[i - len(code_top) - n_txt], f)
    d.line((cx0 + ind4 * 0.25, y + len(code_top) * lh, cx0 + ind4 * 0.25, y + (len(code_top) + n_txt + 1) * lh),
           fill="#313244", width=2)
    ty0 = int(y + len(code_top) * lh)
    draw_text_block(img, text, (int(cx0 + ind), ty0, int(cx1), ty0 + n_txt * lh), mono, C["st"], valign="top",
                    max_size=f.size, spacing=sp)
    if land:  # minimap
        for k in range(int((bot - top) / (u * 0.012))):
            yy = top + k * u * 0.012
            wl = rnd.uniform(0.2, 0.9) * mm * 0.8
            d.rectangle((x1 - mm, yy, x1 - mm + wl, yy + u * 0.005),
                        fill=rnd.choice([C["num"], "#45475a", C["st"] if k % 3 else C["kw"]]))
    # thanh trạng thái
    d.rounded_rectangle((x0, y1 - sbh, x1, y1), rad, fill=C["acc"])
    d.rectangle((x0, y1 - sbh, x1, y1 - rad), fill=C["acc"])
    sf = _b1_f("mono", sbh * 0.48)
    d.text((x0 + u * 0.03, y1 - sbh / 2), "main  0 lỗi", font=sf, fill=C["bg"], anchor="lm")
    d.text((x1 - u * 0.03, y1 - sbh / 2), f"Dòng {cur + 1}  UTF-8  Python", font=sf, fill=C["bg"], anchor="rm")
    return img


def tpl_browser(text, W, H, rnd):
    """Cửa sổ trình duyệt mở trang "Thông điệp vũ trụ" với hero gradient."""
    text, u = _b1_t(text), min(W, H)
    c1, c2, ink = rnd.choice([("#ffd3e8", "#d7c8ff", "#3b1f5e"), ("#c9f2ff", "#e3d7ff", "#16325c"),
                              ("#ffe8c7", "#ffc9d9", "#5a2333"), ("#d6ffe8", "#c9e0ff", "#123f3a")])
    btn = mix(ink, "#ff5fa2", 0.35)
    img = _b1_pastel_bg(W, H, rnd, [mix(c1, "#ffffff", 0.3), mix(c2, "#ffffff", 0.3)], [c1, c2, "#ffffff"])
    win = _b1_box(W, H, 0.9, 0.86, 0.8, 0.86)
    x0, y0, x1, y1 = win
    rad = int(u * 0.03)
    shadow(img, win, rad, offset=(0, int(u * 0.02)), blur=int(u * 0.045), alpha=80)
    d = ImageDraw.Draw(img)
    d.rounded_rectangle(win, rad, fill="#ffffff")
    tbh = int(u * 0.07)
    d.rounded_rectangle((x0, y0, x1, y0 + tbh), rad, fill="#e9e7f0")
    d.rectangle((x0, y0 + tbh - rad, x1, y0 + tbh), fill="#e9e7f0")
    _b1_traffic(d, x0 + tbh * 0.5, y0 + tbh / 2, tbh * 0.13, tbh * 0.38)
    tx0 = x0 + tbh * 1.6
    tw_ = min(u * 0.5, (x1 - tx0) * 0.75)
    d.rounded_rectangle((tx0, y0 + tbh * 0.18, tx0 + tw_, y0 + tbh + rad), int(tbh * 0.25), fill="#ffffff")
    gradient_fill(img, ["#ff7eb3", "#7a5cff"], lambda m: m.ellipse(
        (tx0 + tbh * 0.25, y0 + tbh * 0.4, tx0 + tbh * 0.55, y0 + tbh * 0.7), fill=255))
    d = ImageDraw.Draw(img)
    label(d, (tx0 + tbh * 0.7, y0 + tbh * 0.56), "Thông điệp vũ trụ", "bold", tbh * 0.3, "#333333", "lm")
    qx, qy, q = tx0 + tw_ - tbh * 0.35, y0 + tbh * 0.56, tbh * 0.1
    d.line((qx - q, qy - q, qx + q, qy + q), fill="#777777", width=3)
    d.line((qx - q, qy + q, qx + q, qy - q), fill="#777777", width=3)
    px = tx0 + tw_ + tbh * 0.4
    d.line((px - q * 1.2, qy, px + q * 1.2, qy), fill="#777777", width=3)
    d.line((px, qy - q * 1.2, px, qy + q * 1.2), fill="#777777", width=3)
    # thanh địa chỉ
    ay = y0 + tbh + tbh * 0.55
    s, lw = tbh * 0.13, max(2, int(u * 0.005))
    _b1_chev(d, x0 + tbh * 0.4, ay, s, "#555555", lw)
    _b1_chev(d, x0 + tbh * 0.95, ay, s, "#bbbbbb", lw, "right")
    rx, rr = x0 + tbh * 1.6, tbh * 0.15
    d.arc((rx - rr, ay - rr, rx + rr, ay + rr), 40, 320, fill="#555555", width=lw)
    d.polygon([(rx + rr * 0.5, ay - rr * 1.2), (rx + rr * 1.3, ay - rr * 0.9), (rx + rr * 0.7, ay - rr * 0.2)],
              fill="#555555")
    ab = (x0 + tbh * 2.1, ay - tbh * 0.32, x1 - tbh * 0.8, ay + tbh * 0.32)
    d.rounded_rectangle(ab, int(tbh * 0.32), fill="#f1f0f5")
    lx = ab[0] + tbh * 0.4
    d.rounded_rectangle((lx - tbh * 0.1, ay - tbh * 0.02, lx + tbh * 0.1, ay + tbh * 0.14), 2, fill="#555555")
    d.arc((lx - tbh * 0.07, ay - tbh * 0.15, lx + tbh * 0.07, ay + tbh * 0.02), 180, 360, fill="#555555", width=2)
    url = "vutru.vn/thong-diep-hom-nay"
    uf = _b1_f("regular", tbh * 0.3)
    while uf.getlength(url) > ab[2] - lx - tbh * 0.5 and len(url) > 10:
        url = url[:-4]
    d.text((lx + tbh * 0.3, ay), url, font=uf, fill="#333333", anchor="lm")
    _b1_dots3(d, x1 - tbh * 0.4, ay, u * 0.005, u * 0.013, "#555555", vertical=True)
    # trang
    pg = (x0, int(ay + tbh * 0.55), x1, y1)
    pw, ph = pg[2] - pg[0], pg[3] - pg[1]
    page = gradient((pw, ph), [c1, "#ffffff", c2], angle=135)
    pd = ImageDraw.Draw(page)
    pr = pw * 0.22
    pcx, pcy = pw * 0.9, ph * 0.2
    gl = Image.new("RGBA", page.size, (0, 0, 0, 0))
    gd = ImageDraw.Draw(gl)
    gd.ellipse((pcx - pr, pcy - pr, pcx + pr, pcy + pr), fill=rgba(mix(c2, ink, 0.25), 200))
    gd.ellipse((pcx - pr * 1.7, pcy - pr * 0.3, pcx + pr * 1.7, pcy + pr * 0.3), outline=rgba(mix(c1, ink, 0.3), 200),
               width=max(3, int(u * 0.008)))
    for _ in range(10):
        sparkle(gd, rnd.uniform(0, pw), rnd.uniform(0, ph), u * rnd.uniform(0.008, 0.02), rgba(ink, 120))
    page.alpha_composite(gl)
    m = int(pw * 0.08)
    label(pd, (m, u * 0.06), "Vũ Trụ", "retro", u * 0.05, ink, "lm")
    nf = _b1_f("bold", u * 0.026)
    nx = pw - m
    for it in reversed(["Tử vi", "Con giáp", "Liên hệ"]):
        wv = nf.getlength(it)
        if nx - wv < m + u * 0.25:
            break
        pd.text((nx, u * 0.06), it, font=nf, fill=mix(ink, "#ffffff", 0.25), anchor="rm")
        nx -= wv + u * 0.04
    by = u * 0.16
    bf = _b1_f("bold", u * 0.024)
    tag = "THÔNG ĐIỆP HÔM NAY"
    pd.rounded_rectangle((m, by, m + bf.getlength(tag) + u * 0.05, by + u * 0.05), int(u * 0.025),
                         fill=rgba(ink, 255))
    pd.text((m + u * 0.025, by + u * 0.025), tag, font=bf, fill="#ffffff", anchor="lm")
    btn_h = int(u * 0.085)
    box = (m, int(by + u * 0.09), pw - m, int(ph - btn_h - u * 0.12))
    draw_text_block(page, text, box, find_font("black"), ink, valign="center", max_size=int(u * 0.085), spacing=1.2)
    bb = (m, ph - btn_h - u * 0.07, m + u * 0.34, ph - u * 0.07)
    pd.rounded_rectangle((bb[0], bb[1] + u * 0.01, bb[2], bb[3] + u * 0.01), btn_h // 2, fill=mix(btn, "#000000", 0.3))
    pd.rounded_rectangle(bb, btn_h // 2, fill=btn)
    label(pd, ((bb[0] + bb[2]) / 2, (bb[1] + bb[3]) / 2), "Nhận lộc ngay", "bold", u * 0.03, "#ffffff", "mm")
    b2 = (bb[2] + u * 0.03, bb[1], bb[2] + u * 0.03 + u * 0.22, bb[3])
    if b2[2] < pw - m:
        pd.rounded_rectangle(b2, btn_h // 2, outline=ink, width=max(2, int(u * 0.004)))
        label(pd, ((b2[0] + b2[2]) / 2, (b2[1] + b2[3]) / 2), "Chia sẻ", "bold", u * 0.03, ink, "mm")
    mask = Image.new("L", page.size, 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, -rad * 2, pw - 1, ph - 1), rad, fill=255)
    img.paste(page, pg[:2], mask)
    return img


def tpl_music_player(text, W, H, rnd):
    """Trình phát nhạc: bìa album vũ trụ, lời bài hát là text, thanh tiến trình."""
    text, u = _b1_t(text), min(W, H)
    c1, c2, c3 = rnd.choice([("#ff7eb3", "#7a5cff", "#2a1150"), ("#43cea2", "#185a9d", "#0b2440"),
                             ("#f7971e", "#ff4e7a", "#3a0f2e"), ("#a18cd1", "#fbc2eb", "#30204f")])
    img = gradient((W, H), [c1, c2, c3], angle=rnd.choice([0, 25]))
    soft_blobs(img, rnd, [c1, c2, "#ffffff"], n=6, alpha=140, blur=0.16)
    dark = Image.new("RGBA", (W, H), (0, 0, 0, 70))
    img.alpha_composite(dark)
    add_grain(img, 8)
    land = W > H
    d = ImageDraw.Draw(img)
    # thanh trên
    ty = H * 0.05 if not land else H * 0.07
    _b1_chev(d, W * 0.08 if not land else W * 0.05, ty, u * 0.022, "#ffffff", u * 0.007, "down")
    label(d, (W / 2, ty - u * 0.004), "ĐANG PHÁT TỪ DANH SÁCH", "bold", u * 0.022, (255, 255, 255, 200), "ms")
    label(d, (W / 2, ty + u * 0.008), "Năng lượng Vũ Trụ", "bold", u * 0.03, "#ffffff", "mt")
    _b1_dots3(d, W * 0.92 if not land else W * 0.95, ty, u * 0.006, u * 0.016, "#ffffff")
    # bìa album
    if land:
        cs = int(H * 0.68)
        cv = (int(W * 0.08), int(H * 0.18), int(W * 0.08) + cs, int(H * 0.18) + cs)
        col = (cv[2] + int(W * 0.06), int(W * 0.94))
        ry0 = cv[1]
    else:
        cs = int(min(W * 0.8, H * 0.4))
        cv = (int((W - cs) / 2), int(H * 0.11), int((W + cs) / 2), int(H * 0.11) + cs)
        col = (int(W * 0.08), int(W * 0.92))
        ry0 = cv[3] + int(u * 0.07)
    shadow(img, cv, int(cs * 0.04), offset=(0, int(u * 0.025)), blur=int(u * 0.04), alpha=120)
    art = gradient((cs, cs), [c3, c2, c1], angle=135)
    al = Image.new("RGBA", (cs, cs), (0, 0, 0, 0))
    ad = ImageDraw.Draw(al)
    star_field(ad, rnd, (0, 0, cs, cs), 70, (255, 255, 255, 200), cs * 0.004)
    crescent(al, cs * 0.6, cs * 0.42, cs * 0.22, (255, 244, 214, 255))
    for k in range(3):
        rr = cs * (0.36 + k * 0.1)
        ad.ellipse((cs * 0.5 - rr, cs * 0.85 - rr * 0.25, cs * 0.5 + rr, cs * 0.85 + rr * 0.25),
                   outline=(255, 255, 255, 90 - k * 25), width=max(2, int(cs * 0.006)))
    for _ in range(5):
        sparkle(ad, rnd.uniform(0, cs), rnd.uniform(0, cs * 0.7), cs * rnd.uniform(0.012, 0.03), (255, 255, 255, 230))
    art.alpha_composite(al)
    label(ImageDraw.Draw(art), (cs * 0.07, cs * 0.07), "VŨ TRỤ", "black", cs * 0.06, "#ffffff", "lt")
    label(ImageDraw.Draw(art), (cs * 0.07, cs * 0.14), "Thông Điệp", "script", cs * 0.065, "#ffffff", "lt")
    mask = Image.new("L", (cs, cs), 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, cs - 1, cs - 1), int(cs * 0.04), fill=255)
    img.paste(art, cv[:2], mask)
    d = ImageDraw.Draw(img)
    # tên bài
    cx0, cx1 = col
    label(d, (cx0, ry0), "Thông Điệp Hôm Nay", "bold", u * 0.045, "#ffffff", "lt")
    label(d, (cx0, ry0 + u * 0.06), "Vũ Trụ", "regular", u * 0.032, (255, 255, 255, 190), "lt")
    hx, hy = cx1 - u * 0.03, ry0 + u * 0.045
    d.polygon(heart_points(hx, hy, u * 0.06), fill="#ffffff")
    # vùng điều khiển (từ dưới lên)
    cy_ctrl = (H * 0.9) if not land else (cv[3] - u * 0.06)
    py = cy_ctrl - u * 0.15
    lyr = (cx0, int(ry0 + u * 0.14), cx1, int(py - u * 0.06))
    lay = Image.new("RGBA", (W, H), (255, 255, 255, 0))
    ImageDraw.Draw(lay).rounded_rectangle((lyr[0] - u * 0.03, lyr[1] - u * 0.03, lyr[2] + u * 0.03, lyr[3] + u * 0.03),
                                          int(u * 0.035), fill=(0, 0, 0, 55))
    img.alpha_composite(lay)
    draw_text_block(img, text, lyr, find_font("black"), "#ffffff", valign="center", max_size=int(u * 0.07), spacing=1.25)
    d = ImageDraw.Draw(img)
    t = rnd.uniform(0.3, 0.65)
    tl = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    td = ImageDraw.Draw(tl)
    td.rounded_rectangle((cx0, py - u * 0.005, cx1, py + u * 0.005), int(u * 0.005), fill=(255, 255, 255, 90))
    img.alpha_composite(tl)
    kx = cx0 + (cx1 - cx0) * t
    d.rounded_rectangle((cx0, py - u * 0.005, kx, py + u * 0.005), int(u * 0.005), fill="#ffffff")
    d.ellipse((kx - u * 0.014, py - u * 0.014, kx + u * 0.014, py + u * 0.014), fill="#ffffff")
    total = rnd.randint(170, 260)
    cur = int(total * t)
    label(d, (cx0, py + u * 0.03), f"{cur // 60}:{cur % 60:02d}", "regular", u * 0.025, (255, 255, 255, 200), "lt")
    left = total - cur
    label(d, (cx1, py + u * 0.03), f"-{left // 60}:{left % 60:02d}", "regular", u * 0.025, (255, 255, 255, 200), "rt")
    # nút
    mid = (cx0 + cx1) / 2
    span = (cx1 - cx0) / 2
    q = u * 0.035
    pr = u * 0.065
    d.ellipse((mid - pr, cy_ctrl - pr, mid + pr, cy_ctrl + pr), fill="#ffffff")
    d.rounded_rectangle((mid - pr * 0.32, cy_ctrl - pr * 0.4, mid - pr * 0.1, cy_ctrl + pr * 0.4), 3, fill=c3)
    d.rounded_rectangle((mid + pr * 0.1, cy_ctrl - pr * 0.4, mid + pr * 0.32, cy_ctrl + pr * 0.4), 3, fill=c3)
    for sgn in (-1, 1):
        nx = mid + sgn * span * 0.45
        tri = [(nx - sgn * q * 0.5, cy_ctrl - q * 0.6), (nx - sgn * q * 0.5, cy_ctrl + q * 0.6), (nx + sgn * q * 0.3, cy_ctrl)]
        d.polygon(tri, fill="#ffffff")
        d.rectangle((nx + sgn * q * 0.3 - 3, cy_ctrl - q * 0.6, nx + sgn * q * 0.3 + 3, cy_ctrl + q * 0.6), fill="#ffffff")
    lw = max(2, int(u * 0.005))
    sx = mid - span * 0.92
    d.line((sx - q * 0.5, cy_ctrl - q * 0.35, sx + q * 0.5, cy_ctrl + q * 0.35), fill=(255, 255, 255), width=lw)
    d.line((sx - q * 0.5, cy_ctrl + q * 0.35, sx + q * 0.5, cy_ctrl - q * 0.35), fill=(255, 255, 255), width=lw)
    rx = mid + span * 0.92
    d.rounded_rectangle((rx - q * 0.5, cy_ctrl - q * 0.35, rx + q * 0.5, cy_ctrl + q * 0.35), int(q * 0.2),
                        outline=(255, 255, 255), width=lw)
    d.polygon([(rx + q * 0.1, cy_ctrl - q * 0.6), (rx + q * 0.1, cy_ctrl - q * 0.1), (rx + q * 0.4, cy_ctrl - q * 0.35)],
              fill="#ffffff")
    return img


def _b1_y2k_window(img, box, title, cols, u, hard="#5b3f8c"):
    """Một cửa sổ Y2K bo góc, bóng cứng, thanh tiêu đề gradient. Trả về box nội dung."""
    x0, y0, x1, y1 = box
    o = int(u * 0.014)
    rad = int(u * 0.018)
    d = ImageDraw.Draw(img)
    d.rounded_rectangle((x0 + o, y0 + o, x1 + o, y1 + o), rad, fill=hard)
    d.rounded_rectangle(box, rad, fill="#fdf7ff", outline=hard, width=max(3, int(u * 0.005)))
    th = int(u * 0.06)
    bw = max(3, int(u * 0.005))
    gradient_fill(img, cols, lambda m: m.rounded_rectangle((x0 + bw, y0 + bw, x1 - bw, y0 + th), max(1, rad - bw),
                                                           fill=255), angle=90)
    d = ImageDraw.Draw(img)
    d.line((x0, y0 + th, x1, y0 + th), fill=hard, width=bw)
    tf = _b1_f("bold", th * 0.44)
    t = title
    while tf.getlength(t) > (x1 - x0) - th * 2.8 and len(t) > 3:
        t = t[:-2]
    d.text((x0 + th * 0.3, y0 + th * 0.55), t, font=tf, fill="#ffffff", anchor="lm", stroke_width=2, stroke_fill=hard)
    bs = th * 0.55
    for k in range(2):
        bx1 = x1 - th * 0.22 - k * (bs + th * 0.12)
        bb = (bx1 - bs, y0 + th * 0.55 - bs / 2, bx1, y0 + th * 0.55 + bs / 2)
        d.rounded_rectangle(bb, int(bs * 0.25), fill="#ffffff", outline=hard, width=2)
        cx, cy, q = (bb[0] + bb[2]) / 2, (bb[1] + bb[3]) / 2, bs * 0.22
        if k == 0:
            d.line((cx - q, cy - q, cx + q, cy + q), fill=hard, width=3)
            d.line((cx - q, cy + q, cx + q, cy - q), fill=hard, width=3)
        else:
            d.line((cx - q, cy + q * 0.6, cx + q, cy + q * 0.6), fill=hard, width=3)
    return (x0 + bw, y0 + th + bw, x1 - bw, y1 - bw)


def _b1_warn_icon(d, cx, cy, s, hard):
    d.polygon([(cx, cy - s * 0.55), (cx + s * 0.6, cy + s * 0.48), (cx - s * 0.6, cy + s * 0.48)], fill="#ffe066",
              outline=hard, width=max(3, int(s * 0.06)))
    d.rounded_rectangle((cx - s * 0.06, cy - s * 0.25, cx + s * 0.06, cy + s * 0.15), int(s * 0.05), fill=hard)
    d.ellipse((cx - s * 0.07, cy + s * 0.22, cx + s * 0.07, cy + s * 0.36), fill=hard)


def tpl_y2k_error(text, W, H, rnd):
    """Nhiều hộp thoại lỗi kiểu Y2K pastel chồng lên nhau, hộp trước chứa thông điệp."""
    text, u = _b1_t(text), min(W, H)
    hard = rnd.choice(["#5b3f8c", "#3b4a9c", "#8c3f6e"])
    bars = [["#ff8ad8", "#b388ff"], ["#7fd4ff", "#b39dff"], ["#ffb3d9", "#ffd36e"], ["#a0f0d0", "#7fb8ff"]]
    img = gradient((W, H), rnd.choice([["#ffd6f5", "#d6e8ff"], ["#e6d6ff", "#ffe0f0"], ["#d6fff2", "#f0d6ff"]]),
                   angle=135)
    lay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ld = ImageDraw.Draw(lay)
    grid(ld, (0, 0, W, H), int(u * 0.07), (255, 255, 255, 150), 2)
    for _ in range(14):
        sparkle(ld, rnd.uniform(0, W), rnd.uniform(0, H), u * rnd.uniform(0.012, 0.035), (255, 255, 255, 230))
    for _ in range(5):
        x, y = rnd.uniform(0, W), rnd.uniform(0, H)
        ld.polygon(heart_points(x, y, u * rnd.uniform(0.04, 0.07)), fill=rgba(rnd.choice(["#ff8ad8", "#b388ff"]), 150))
    img.alpha_composite(lay)
    msgs = ["nỗi_buồn.exe đã ngừng hoạt động", "Bộ nhớ đầy: quá nhiều lo âu", "Không tìm thấy: người yêu cũ",
            "Cảnh báo: sắp có lộc lớn!", "Năng lượng tiêu cực: 0%", "Xui xẻo đã bị chặn"]
    rnd.shuffle(msgs)
    titles = ["Lỗi!", "cảnh_báo.exe", "Hệ thống", "Thông báo"]
    bold = find_font("bold")
    for k in range(4):
        ww, hh = u * rnd.uniform(0.55, 0.7), u * rnd.uniform(0.3, 0.36)
        x = rnd.uniform(-ww * 0.25, W - ww * 0.75)
        y = rnd.uniform(H * 0.02, H * 0.72) if k % 2 else (H * 0.03 + k * H * 0.25) % (H * 0.8)
        cb = _b1_y2k_window(img, (int(x), int(y), int(x + ww), int(y + hh)), titles[k], bars[k % 4], u, hard)
        dd = ImageDraw.Draw(img)
        s = u * 0.08
        _b1_warn_icon(dd, cb[0] + s * 0.9, cb[1] + (cb[3] - cb[1]) * 0.4, s, hard)
        draw_text_block(img, msgs[k], (int(cb[0] + s * 1.7), cb[1] + int(u * 0.02), cb[2] - int(u * 0.03),
                                       int(cb[3] - u * 0.1)), bold, hard, max_size=int(u * 0.035))
        ob = (cb[2] - u * 0.18, cb[3] - u * 0.08, cb[2] - u * 0.03, cb[3] - u * 0.025)
        dd.rounded_rectangle(ob, int(u * 0.015), fill="#ffffff", outline=hard, width=2)
        label(dd, ((ob[0] + ob[2]) / 2, (ob[1] + ob[3]) / 2), "OK", "bold", u * 0.026, hard, "mm")
    # cửa sổ chính
    main = _b1_box(W, H, 0.86, 0.5, 0.6, 0.66, cy=0.52)
    cb = _b1_y2k_window(img, main, "thong_diep_vu_tru.exe", rnd.choice(bars), u, hard)
    d = ImageDraw.Draw(img)
    p = int(u * 0.04)
    s = u * 0.13
    _b1_warn_icon(d, cb[0] + p + s * 0.6, cb[1] + p + s * 0.55, s, hard)
    bh = int(u * 0.085)
    tb = (int(cb[0] + p * 1.5 + s * 1.2), cb[1] + p, cb[2] - p, cb[3] - p * 2 - bh)
    draw_text_block(img, text, tb, bold, mix(hard, "#000000", 0.35), max_size=int(u * 0.068), spacing=1.22)
    bw_ = u * 0.22
    bx1 = cb[2] - p
    for k, nm in enumerate(["Huỷ", "OK"][::-1]):
        bb = (bx1 - bw_, cb[3] - p - bh, bx1, cb[3] - p)
        d.rounded_rectangle((bb[0] + 6, bb[1] + 6, bb[2] + 6, bb[3] + 6), int(bh * 0.3), fill=hard)
        d.rounded_rectangle(bb, int(bh * 0.3), fill="#ffd6f0" if k == 0 else "#ffffff", outline=hard, width=3)
        label(d, ((bb[0] + bb[2]) / 2, (bb[1] + bb[3]) / 2), nm, "bold", bh * 0.4, hard, "mm")
        if k == 0:
            cur = (bb[0] + bw_ * 0.6, bb[1] + bh * 0.55)
        bx1 -= bw_ + u * 0.03
    cx, cy, cs = cur[0], cur[1], u * 0.07
    arrow = [(cx, cy), (cx, cy + cs), (cx + cs * 0.27, cy + cs * 0.75), (cx + cs * 0.45, cy + cs * 1.1),
             (cx + cs * 0.58, cy + cs * 1.03), (cx + cs * 0.4, cy + cs * 0.7), (cx + cs * 0.72, cy + cs * 0.7)]
    d.polygon(arrow, fill="#ffffff", outline="#000000", width=max(2, int(u * 0.004)))
    return img


_b1_SPRITE = [
    "....yy....",
    "...yyyy...",
    "..pppppp..",
    ".pppppppp.",
    "...ssss...",
    "..s.ss.s..",
    "..ssssss..",
    ".bbbbbbbb.",
    "bbbbyybbbb",
    "bbbbbbbbbb",
    ".bb....bb.",
]


def tpl_rpg_dialog(text, W, H, rnd):
    """Cảnh game RPG pixel và hộp thoại nhân vật "VŨ TRỤ" nói thông điệp."""
    text, u = _b1_t(text), min(W, H)
    px = max(4, u // 135)
    w, h = W // px, H // px
    sky = rnd.choice([["#1b1442", "#3d2a7a", "#8a4fb5", "#ff8fab", "#ffc89a"],
                      ["#0d1b3e", "#1e3a75", "#3f6fb5", "#7fb2e5", "#c4e4ff"],
                      ["#2a0f3a", "#6b1f5c", "#c2416b", "#ff8c5a", "#ffd27a"]])
    sm = Image.new("RGB", (w, h), sky[0])
    d = ImageDraw.Draw(sm)
    ground = int(h * (0.62 if H > W else 0.55))
    for k in range(ground):  # dải màu trời bậc thang
        t = k / ground
        d.line((0, k, w, k), fill=sky[min(len(sky) - 1, int(t * len(sky)))])
    for _ in range(w * h // 40):
        x, y = rnd.randrange(w), rnd.randrange(int(ground * 0.6))
        d.point((x, y), fill="#ffffff" if rnd.random() < 0.6 else "#ffe9a8")
    mx, my, mr = int(w * 0.75), int(h * 0.12), max(4, int(min(w, h) * 0.07))
    d.ellipse((mx - mr, my - mr, mx + mr, my + mr), fill="#fff4c9")
    d.ellipse((mx - mr // 2, my - mr // 3, mx - mr // 4, my), fill="#f0dc9a")
    for layer_k, col in enumerate(["#4a3a7a", "#2f2659"]):
        pts = [(0, ground)]
        x = 0
        while x <= w:
            pts.append((x, ground - rnd.randint(int(h * 0.04), int(h * (0.16 - layer_k * 0.05)))))
            x += rnd.randint(int(w * 0.08), int(w * 0.18))
        pts.append((w, ground))
        d.polygon(pts, fill=col)
    d.rectangle((0, ground, w, h), fill="#3f8f4a")
    d.rectangle((0, ground, w, ground + 1), fill="#6bc06a")
    for _ in range(w // 6):
        x, y = rnd.randrange(w), rnd.randint(ground + 3, h)
        d.point((x, y), fill="#2f6f3a")
        d.point((x + 1, y), fill="#5aa85a")
    for _ in range(max(3, w // 30)):  # cây thông
        tx, tb = rnd.randrange(w), ground + rnd.randint(1, 4)
        for r in range(4):
            d.rectangle((tx - r - 1, tb - 12 + r * 3, tx + r + 1, tb - 10 + r * 3), fill="#1f5a35")
        d.rectangle((tx, tb, tx + 1, tb + 2), fill="#5a3a22")
    # nhân vật
    pal = {"y": "#ffd23f", "p": "#6a3cbc", "s": "#ffd6b0", "b": "#3f5fd0", ".": None}
    ox, oy = int(w * 0.5) - 5, ground - 6
    for j, row in enumerate(_b1_SPRITE):
        for i, ch in enumerate(row):
            if pal[ch]:
                d.point((ox + i, oy + j), fill=pal[ch])
    d.point((ox + 3, oy + 5), fill="#222222")
    d.point((ox + 6, oy + 5), fill="#222222")
    img = sm.resize((W, H), Image.NEAREST).convert("RGBA")
    dd = ImageDraw.Draw(img)
    # HUD
    hf = find_font("pixel")
    hx, hy = u * 0.04, u * 0.05
    heart = [".xx.xx.", "xxxxxxx", "xxxxxxx", ".xxxxx.", "..xxx..", "...x..."]
    for k in range(3):
        for j, row in enumerate(heart):
            for i, ch in enumerate(row):
                if ch == "x":
                    x = hx + k * 9 * px + i * px
                    dd.rectangle((x, hy + j * px, x + px - 1, hy + (j + 1) * px - 1), fill="#ff4d6d")
    label(dd, (W - u * 0.04, hy - px), "LV 99  VÀNG 999", "pixel", u * 0.065, "#ffe066", "rt")
    # hộp thoại
    m = int(u * 0.04)
    bh = int(H * 0.36) if H > W else int(H * 0.42)
    box = (m, H - m - bh, W - m, H - m)
    x0, y0, x1, y1 = box
    dd.rectangle((x0 + px, y0 + px, x1 + px, y1 + px), fill="#000000")
    dd.rectangle(box, fill="#000000")
    dd.rectangle((x0 + px, y0 + px, x1 - px, y1 - px), fill="#ffffff")
    dd.rectangle((x0 + 2 * px, y0 + 2 * px, x1 - 2 * px, y1 - 2 * px), fill="#000000")
    gradient_fill(img, ["#1d2a6b", "#121845"], lambda mm: mm.rectangle((x0 + 3 * px, y0 + 3 * px, x1 - 3 * px,
                                                                       y1 - 3 * px), fill=255))
    dd = ImageDraw.Draw(img)
    for cx, cy in ((x0, y0), (x1 - px, y0), (x0, y1 - px), (x1 - px, y1 - px)):
        dd.rectangle((cx, cy, cx + px - 1, cy + px - 1), fill=img.getpixel((min(W - 1, int(cx)), int(y0 - px * 3))))
    nf = _b1_f("pixel", u * 0.065)
    name = "VŨ TRỤ"
    nw = nf.getlength(name) + u * 0.06
    nb = (x0 + u * 0.04, y0 - u * 0.05, x0 + u * 0.04 + nw, y0 + u * 0.035)
    dd.rectangle(nb, fill="#000000")
    dd.rectangle((nb[0] + px, nb[1] + px, nb[2] - px, nb[3] - px), fill="#ffffff")
    dd.rectangle((nb[0] + 2 * px, nb[1] + 2 * px, nb[2] - 2 * px, nb[3] - 2 * px), fill="#5a2ca0")
    dd.text(((nb[0] + nb[2]) / 2, (nb[1] + nb[3]) / 2), name, font=nf, fill="#ffe066", anchor="mm")
    p = int(u * 0.06)
    tb = (x0 + p, y0 + int(p * 1.1), x1 - p, y1 - int(p * 1.2))
    draw_text_block(img, text, tb, hf, "#ffffff", valign="top", max_size=int(u * 0.1), spacing=1.12)
    ax, ay = x1 - p, y1 - p * 0.7
    dd.polygon([(ax - 3 * px, ay - 2 * px), (ax + 3 * px, ay - 2 * px), (ax, ay + px)], fill="#ffe066")
    return img


def tpl_breaking_news(text, W, H, rnd):
    """Bản tin nóng truyền hình: logo kênh, nhãn TIN NÓNG và thanh chữ chạy."""
    text, u = _b1_t(text), min(W, H)
    red = rnd.choice(["#e10600", "#d7263d", "#c4001a"])
    navy = rnd.choice(["#0a1a4a", "#0b1d3a", "#111a40"])
    img = gradient((W, H), [mix(navy, "#000000", 0.3), "#1546a0", navy], angle=rnd.choice([20, 160]))
    lay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ld = ImageDraw.Draw(lay)
    diag_stripes(ld, W, H, int(u * 0.12), int(u * 0.035), (120, 180, 255, 40))
    img.alpha_composite(lay.filter(ImageFilter.GaussianBlur(u * 0.01)))
    # quả địa cầu mờ
    gl = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    gd = ImageDraw.Draw(gl)
    gr = u * 0.42
    gx, gy = (W * 0.72, H * 0.3) if H > W else (W * 0.78, H * 0.42)
    lw = max(2, int(u * 0.004))
    col = (140, 200, 255, 110)
    gd.ellipse((gx - gr, gy - gr, gx + gr, gy + gr), outline=col, width=lw)
    for k in range(1, 4):
        rx = gr * k / 4
        gd.ellipse((gx - rx, gy - gr, gx + rx, gy + gr), outline=col, width=lw)
        ry = gr * math.sin(math.pi * k / 8)
        yy = gy - gr * math.cos(math.pi * k / 4)
        hw = math.sqrt(max(0, gr ** 2 - (yy - gy) ** 2))
        gd.line((gx - hw, yy, gx + hw, yy), fill=col, width=lw)
        yy2 = gy + (gy - yy)
        gd.line((gx - hw, yy2, gx + hw, yy2), fill=col, width=lw)
    gd.line((gx - gr, gy, gx + gr, gy), fill=col, width=lw)
    glow(img, gl, (0.01,))
    sl = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    star_field(ImageDraw.Draw(sl), rnd, (0, 0, W, H), 60, (200, 230, 255, 120), u * 0.004)
    img.alpha_composite(sl)
    vignette(img, 120)
    d = ImageDraw.Draw(img)
    m = int(u * 0.05)
    # logo
    lf = _b1_f("black", u * 0.042)
    k1, k2 = "KÊNH", "VŨ TRỤ"
    w1, w2 = lf.getlength(k1) + u * 0.04, lf.getlength(k2) + u * 0.04
    lh = u * 0.075
    d.rectangle((m, m, m + w1, m + lh), fill=red)
    d.rectangle((m + w1, m, m + w1 + w2, m + lh), fill="#ffffff")
    d.text((m + w1 / 2, m + lh / 2), k1, font=lf, fill="#ffffff", anchor="mm")
    d.text((m + w1 + w2 / 2, m + lh / 2), k2, font=lf, fill=navy, anchor="mm")
    label(d, (m, m + lh + u * 0.015), "24/7  ·  HD", "bold", u * 0.025, (255, 255, 255, 200), "lt")
    lv = "TRỰC TIẾP"
    vf = _b1_f("black", u * 0.03)
    vw = vf.getlength(lv) + u * 0.08
    vb = (W - m - vw, m, W - m, m + u * 0.06)
    d.rounded_rectangle(vb, int(u * 0.01), fill=red)
    d.ellipse((vb[0] + u * 0.02, (vb[1] + vb[3]) / 2 - u * 0.01, vb[0] + u * 0.04, (vb[1] + vb[3]) / 2 + u * 0.01),
              fill="#ffffff")
    d.text((vb[0] + u * 0.055, (vb[1] + vb[3]) / 2), lv, font=vf, fill="#ffffff", anchor="lm")
    label(d, (W - m, vb[3] + u * 0.015), _b1_clock(rnd), "bold", u * 0.032, "#ffffff", "rt")
    # thanh chữ chạy
    tk = int(u * 0.075)
    ty0 = H - tk - int(u * 0.04)
    d.rectangle((0, ty0, W, ty0 + tk), fill="#0a0f24")
    tlab = "MỚI"
    tf = _b1_f("black", tk * 0.45)
    tlw = tf.getlength(tlab) + u * 0.06
    items = ["Tuổi Tý đón tin vui", "Tuổi Mão gặp quý nhân", "Tuổi Ngọ tiền vào như nước",
             "Tuổi Dậu tình duyên khởi sắc", "Tuổi Hợi có lộc bất ngờ", "Vũ Trụ xác nhận vận may"]
    rnd.shuffle(items)
    x = tlw + u * 0.03 - rnd.uniform(0, u * 0.3)
    rf = _b1_f("bold", tk * 0.42)
    for it in items * 2:
        if x > W:
            break
        d.text((x, ty0 + tk / 2), it.upper(), font=rf, fill="#ffffff", anchor="lm")
        x += rf.getlength(it.upper()) + u * 0.035
        d.ellipse((x - u * 0.008, ty0 + tk / 2 - u * 0.008, x + u * 0.008, ty0 + tk / 2 + u * 0.008), fill=red)
        x += u * 0.035
    d.rectangle((0, ty0, tlw, ty0 + tk), fill="#ffd400")
    d.text((tlw / 2, ty0 + tk / 2), tlab, font=tf, fill="#0a0f24", anchor="mm")
    # dải phụ dưới khung tin
    sub = int(u * 0.06)
    sy1 = ty0 - int(u * 0.03)
    sy0 = sy1 - sub
    # khung tin chính
    pw = W - 2 * m
    pad = int(u * 0.04)
    maxh = (sy0 - H * (0.42 if H > W else 0.3)) - 2 * pad
    blk = find_font("black")
    f, tw, th, _ = measure_text(text, (0, 0, int(pw - 2 * pad), int(maxh)), blk, int(u * 0.075), spacing=1.18,
                                upper=True)
    py1 = sy0
    py0 = int(py1 - th - 2 * pad)
    shadow(img, (m, py0, m + pw, sy1), 0, offset=(0, int(u * 0.01)), blur=int(u * 0.02), alpha=120)
    d = ImageDraw.Draw(img)
    d.rectangle((m, py0, m + pw, py1), fill="#ffffff")
    d.rectangle((m, py0, m + int(u * 0.015), py1), fill=red)
    draw_text_block(img, text, (m + pad + int(u * 0.01), py0 + pad, m + pw - pad, py1 - pad), blk, navy, valign="center",
                    max_size=f.size, spacing=1.18, upper=True)
    d.rectangle((m, sy0, m + pw, sy1), fill="#1546a0")
    dt = _b1_today()
    label(d, (m + pad, (sy0 + sy1) / 2), f"VŨ TRỤ VỪA XÁC NHẬN  ·  {_b1_vn_date(dt).upper()}", "bold", sub * 0.42,
          "#ffffff", "lm")
    # nhãn TIN NÓNG
    hf = _b1_f("black", u * 0.06)
    hl = "TIN NÓNG"
    hw = hf.getlength(hl) + u * 0.1
    hh = u * 0.095
    hy1 = py0
    sk = hh * 0.35
    d.polygon([(m, hy1 - hh), (m + hw + sk, hy1 - hh), (m + hw, hy1), (m, hy1)], fill=red)
    d.text((m + u * 0.04, hy1 - hh / 2), hl, font=hf, fill="#ffffff", anchor="lm")
    d.polygon([(m + hw + sk * 1.3, hy1 - hh), (m + hw + sk * 1.3 + u * 0.03, hy1 - hh), (m + hw + u * 0.03, hy1),
               (m + hw, hy1)], fill="#ffd400")
    return img


# --- batch 2 ---

FILLER = ("ngày mới bình an niềm vui đến từ những điều nhỏ bé người ta thường nói rằng vũ trụ luôn "
          "lắng nghe mỗi lời ước nguyện chân thành khi lòng an yên thì mọi việc sẽ hanh thông hơn "
          "buổi sáng trời trong gió nhẹ mang theo hương hoa sữa trên con phố quen thuộc ai cũng mong "
          "một chút may mắn cho gia đình sức khỏe dồi dào công việc thuận lợi tình cảm vẹn tròn và "
          "những giấc mơ đẹp sẽ thành sự thật nếu ta đủ kiên nhẫn chờ đợi thời điểm thích hợp").split()


def _b2_filler(rnd, n):
    """Chuỗi chữ ngẫu nhiên làm nền (cột báo, trang sách)."""
    words = [rnd.choice(FILLER) for _ in range(n)]
    out, cap = [], True
    for i, w in enumerate(words):
        out.append(w.capitalize() if cap else w)
        cap = False
        if i % rnd.randint(9, 16) == 8:
            out[-1] += "."
            cap = True
    return " ".join(out) + "."


def _b2_rot(dx, dy, angle):
    """Toạ độ (dx, dy) sau khi xoay angle độ theo chiều của PIL (ngược kim đồng hồ)."""
    a = math.radians(angle)
    return dx * math.cos(a) + dy * math.sin(a), -dx * math.sin(a) + dy * math.cos(a)


def _b2_drop(img, layer, center, angle=0, off=(0.006, 0.014), blur=0.012, alpha=110):
    """Dán layer xoay kèm bóng đổ mềm lấy theo alpha của layer."""
    u = min(img.size)
    sh = Image.new("RGBA", layer.size, (25, 15, 5, 0))
    sh.putalpha(layer.getchannel("A").point(lambda p: p * alpha // 255))
    tmp = Image.new("RGBA", img.size, (0, 0, 0, 0))
    paste_rotated(tmp, sh, (center[0] + off[0] * u, center[1] + off[1] * u), angle)
    img.alpha_composite(tmp.filter(ImageFilter.GaussianBlur(max(1, u * blur))))
    paste_rotated(img, layer, center, angle)


def _b2_shadow_text(img, text, box, path, color, shade=(0, 0, 0, 150), blur=6, off=(0, 3), **kw):
    """Chữ kèm bóng mờ phía sau cho dễ đọc trên nền ảnh."""
    layer = Image.new("RGBA", img.size, shade[:3] + (0,))
    sbox = (box[0] + off[0], box[1] + off[1], box[2] + off[0], box[3] + off[1])
    draw_text_block(layer, text, sbox, path, shade, **kw)
    img.alpha_composite(layer.filter(ImageFilter.GaussianBlur(blur)))
    return draw_text_block(img, text, box, path, color, **kw)


def _b2_pin(img, cx, cy, r, color):
    """Đinh ghim đầu tròn nhìn từ trên xuống."""
    sh = Image.new("RGBA", img.size, (0, 0, 0, 0))
    ImageDraw.Draw(sh).ellipse((cx - r + r * 0.4, cy - r + r * 0.7, cx + r + r * 0.4, cy + r + r * 0.7),
                               fill=(0, 0, 0, 120))
    img.alpha_composite(sh.filter(ImageFilter.GaussianBlur(r * 0.35)))
    d = ImageDraw.Draw(img)
    d.ellipse((cx - r, cy - r, cx + r, cy + r), fill=mix(color, "#000000", 0.25))
    r2 = r * 0.82
    d.ellipse((cx - r2 - r * 0.08, cy - r2 - r * 0.08, cx + r2 - r * 0.08, cy + r2 - r * 0.08), fill=rgb(color))
    r3 = r * 0.28
    d.ellipse((cx - r * 0.42 - r3, cy - r * 0.42 - r3, cx - r * 0.42 + r3, cy - r * 0.42 + r3),
              fill=mix(color, "#ffffff", 0.7))


def _b2_washi(img, center, w, h, angle, color, rnd, alpha=190):
    """Băng dính washi bán trong suốt có hoạ tiết, hai đầu răng cưa."""
    w, h = int(w), int(h)
    tape = Image.new("RGBA", (w, h), rgba(color, alpha))
    d = ImageDraw.Draw(tape)
    kind = rnd.choice(["stripe", "dot", "plain", "grid"])
    pc = rgba(mix(color, "#ffffff", 0.55), alpha)
    if kind == "stripe":
        for x in range(-h, w + h, max(6, h // 2)):
            d.line((x, 0, x + h, h), fill=pc, width=max(3, h // 7))
    elif kind == "dot":
        dots(d, (0, 0, w, h), max(8, h // 3), max(2, h // 12), pc)
    elif kind == "grid":
        grid(d, (0, 0, w, h), max(8, h // 3), pc, max(2, h // 18))
    mask = Image.new("L", (w, h), 0)
    t = max(3, h // 10)
    pts = [(0, 0)] + [(w - (t if i % 2 else 0), i * h / 8) for i in range(9)] + \
          [(t if i % 2 else 0, h - i * h / 8) for i in range(9)]
    ImageDraw.Draw(mask).polygon(pts, fill=255)
    tape.putalpha(Image.composite(tape.getchannel("A"), mask, mask))
    paste_rotated(img, tape, center, angle)


def _b2_wood(W, H, rnd, base=(150, 102, 64)):
    """Mặt bàn gỗ: nền nhiễu + vân gỗ ngang."""
    img = noise_texture((W, H), base, amount=12, seed=rnd.random())
    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    u = min(W, H)
    y = 0
    while y < H:
        amp, f, ph = rnd.uniform(2, u * 0.012), rnd.uniform(0.002, 0.006), rnd.uniform(0, 6)
        dark = rnd.random() < 0.5
        pts = [(x, y + amp * math.sin(x * f + ph)) for x in range(0, W + 20, 20)]
        d.line(pts, fill=(40, 20, 5, rnd.randint(25, 60)) if dark else (255, 230, 200, rnd.randint(15, 35)),
               width=rnd.randint(1, 4))
        y += rnd.uniform(u * 0.006, u * 0.025)
    img.alpha_composite(layer.filter(ImageFilter.GaussianBlur(1)))
    return img


def _b2_cork(W, H, rnd):
    """Bảng bần với các hạt lấm tấm và khung gỗ."""
    img = noise_texture((W, H), (184, 136, 88), amount=22, seed=rnd.random())
    d = ImageDraw.Draw(img)
    u = min(W, H)
    for _ in range(W * H // 900):
        x, y, r = rnd.randrange(W), rnd.randrange(H), rnd.uniform(1, u * 0.004)
        c = rnd.choice([(120, 78, 40), (140, 92, 50), (214, 170, 118), (98, 62, 30)])
        d.ellipse((x - r, y - r, x + r, y + r), fill=c)
    fw = int(u * 0.035)
    d.rectangle((0, 0, W, H), outline=(110, 70, 38), width=fw)
    d.rectangle((fw, fw, W - fw, H - fw), outline=(80, 48, 22), width=max(2, fw // 6))
    vignette(img, 90)
    return img


def _b2_pencil(L, t):
    """Bút chì nằm ngang dài L, dày t (đầu tẩy bên trái)."""
    L, t = int(L), int(t)
    p = Image.new("RGBA", (L, t), (0, 0, 0, 0))
    d = ImageDraw.Draw(p)
    er, fe, cone = int(L * 0.08), int(L * 0.06), int(L * 0.13)
    d.rounded_rectangle((0, 0, er + t // 3, t - 1), t // 3, fill="#f28b9b")
    d.rectangle((er, 0, er + fe, t - 1), fill="#c9c9c9")
    for k in range(3):
        x = er + fe * (k + 1) // 4
        d.line((x, 0, x, t), fill="#8f8f8f", width=max(1, t // 12))
    x0 = er + fe
    d.rectangle((x0, 0, L - cone, t - 1), fill="#f4b400")
    d.rectangle((x0, 0, L - cone, t // 3), fill="#ffcf40")
    d.rectangle((x0, 2 * t // 3, L - cone, t - 1), fill="#d99a00")
    d.polygon([(L - cone, 0), (L - cone, t - 1), (L - 1, t // 2)], fill="#e9c69c")
    d.polygon([(L - cone * 0.35, t / 2 - t * 0.18), (L - cone * 0.35, t / 2 + t * 0.18), (L - 1, t // 2)],
              fill="#333333")
    return p


def _b2_halftone(d, box, rnd, color):
    """Ô 'ảnh' in kiểu chấm halftone (núi + mặt trời)."""
    x0, y0, x1, y1 = (int(v) for v in box)
    w, h = x1 - x0, y1 - y0
    g = max(5, w // 34)
    sx, sy, sr = x0 + w * rnd.uniform(0.25, 0.75), y0 + h * 0.35, h * 0.18
    for y in range(y0 + g // 2, y1, g):
        for x in range(x0 + g // 2, x1, g):
            ridge = y0 + h * (0.62 + 0.12 * math.sin((x - x0) / w * 5 + 1))
            v = 0.85 if y > ridge else 0.2 + 0.5 * (y - y0) / h
            if math.hypot(x - sx, y - sy) < sr:
                v = 0.05
            r = g * 0.55 * v
            if r > 0.6:
                d.ellipse((x - r, y - r, x + r, y + r), fill=color)
    d.rectangle(box, outline=color, width=2)


def _b2_heart_doodle(d, cx, cy, s, color, width=3):
    pts = heart_points(cx, cy, s)
    d.line(pts + pts[:1], fill=color, width=width, joint="curve")


def tpl_sticky_cork(text, W, H, rnd):
    """Giấy note dán trên bảng bần có đinh ghim, chữ bút dạ."""
    u = min(W, H)
    img = _b2_cork(W, H, rnd)
    notes = [("#fff27a", "#2b2a1f"), ("#ffb3c7", "#4a1830"), ("#b8f2c8", "#173d26"),
             ("#a8dcff", "#122f4d"), ("#ffcf8a", "#4a2a08")]
    rnd.shuffle(notes)
    pins = ["#e63946", "#2a9d8f", "#f4a261", "#457b9d", "#8e44ad"]
    # note phụ trang trí ở góc
    for (cx, cy), (col, _) in zip([(W * 0.1, H * 0.09), (W * 0.92, H * 0.93), (W * 0.9, H * 0.08)], notes[1:]):
        s = int(u * rnd.uniform(0.28, 0.36))
        n = Image.new("RGBA", (s, s), col)
        ImageDraw.Draw(n).rectangle((0, 0, s, s * 0.14), fill=mix(col, "#000000", 0.06))
        ang = rnd.uniform(-18, 18)
        _b2_drop(img, n, (cx, cy), ang)
        _b2_pin(img, cx, cy - s * 0.38, u * 0.022, rnd.choice(pins))
    col, fg = notes[0]
    nw = int(min(W * 0.8, H * 0.82))
    nh = int(min(H * 0.76, nw * 1.18))
    note = Image.new("RGBA", (nw, nh), col)
    d = ImageDraw.Draw(note)
    # vệt keo phía trên + bóng cong ở đáy
    d.rectangle((0, 0, nw, nh * 0.1), fill=mix(col, "#000000", 0.05))
    shade = Image.new("RGBA", (nw, nh), (0, 0, 0, 0))
    ImageDraw.Draw(shade).polygon([(nw * 0.55, nh), (nw, nh * 0.82), (nw, nh)], fill=(0, 0, 0, 40))
    note.alpha_composite(shade.filter(ImageFilter.GaussianBlur(u * 0.03)))
    label(d, (nw * 0.08, nh * 0.13), rnd.choice(["Ghi chú", "Nhớ nhé!", "Lời nhắn"]), "marker", u * 0.04,
          mix(col, fg, 0.55))
    d.line((nw * 0.08, nh * 0.13 + u * 0.06, nw * 0.4, nh * 0.13 + u * 0.06), fill=mix(col, fg, 0.4),
           width=max(2, int(u * 0.005)))
    box = (nw * 0.09, nh * 0.24, nw * 0.91, nh * 0.86)
    draw_text_block(note, text, tuple(int(v) for v in box), find_font("marker"), fg, align="center",
                    max_size=int(u * 0.095), spacing=1.25)
    _b2_heart_doodle(d, nw * 0.86, nh * 0.91, u * 0.05, mix(col, "#e63946", 0.6), max(2, int(u * 0.004)))
    ang = rnd.uniform(-3, 3)
    c = (W / 2, H / 2 + u * 0.02)
    _b2_drop(img, note, c, ang, off=(0.01, 0.02), blur=0.018, alpha=120)
    dx, dy = _b2_rot(0, -nh / 2 + u * 0.035, ang)
    _b2_pin(img, c[0] + dx, c[1] + dy, u * 0.03, rnd.choice(pins))
    return img


def tpl_polaroid(text, W, H, rnd):
    """Ảnh polaroid trên nền giấy, chữ trắng trong ảnh + chú thích viết tay ở viền dưới."""
    u = min(W, H)
    img = noise_texture((W, H), rgb(rnd.choice(["#efe6da", "#e9ecef", "#f3e3e6", "#e6efe6"])), amount=10,
                        seed=rnd.random())
    d = ImageDraw.Draw(img)
    dots(d, (0, 0, W, H), int(u * 0.05), max(2, int(u * 0.003)), mix(img.getpixel((5, 5)), "#000000", 0.08))
    skies = [["#ffb88c", "#de6262"], ["#a1c4fd", "#c2e9fb"], ["#fbc2eb", "#a6c1ee"], ["#f6d365", "#fda085"],
             ["#84fab0", "#8fd3f4"], ["#2b5876", "#4e4376"]]
    rnd.shuffle(skies)
    land = W > H
    if land:
        fw = int(min(W * 0.6, H * 0.88 * 108 / 86)); fh = int(fw * 86 / 108)
        m, ph = int(fw * 0.045), int(fh * 0.73)
    else:
        fw = int(min(W * 0.8, H * 0.8 * 54 / 86)); fh = int(fw * 86 / 54)
        m, ph = int(fw * 0.075), int(fh * 0.74)

    def photo(sky, w, h):
        p = gradient((w, h), sky + [mix(sky[-1], "#3a2a4a", 0.35)])
        soft_blobs(p, rnd, [mix(sky[0], "#ffffff", 0.4), sky[1]], n=4, alpha=120, rmin=0.3, rmax=0.6)
        pd = ImageDraw.Draw(p)
        sr = min(w, h) * 0.12
        sx, sy = w * rnd.uniform(0.25, 0.75), h * 0.38
        sun = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        ImageDraw.Draw(sun).ellipse((sx - sr, sy - sr, sx + sr, sy + sr), fill=(255, 250, 230, 200))
        glow(p, sun, (0.08, 0.03))
        for k, tone in enumerate([0.45, 0.65]):
            base = h * (0.72 + 0.1 * k)
            ph_ = rnd.uniform(0, 6)
            pts = [(x, base + h * 0.06 * math.sin(x / w * (3 + k) + ph_)) for x in range(0, w + 10, 10)]
            pd.polygon(pts + [(w, h), (0, h)], fill=mix(sky[-1], "#1b1630", tone))
        add_grain(p, 18)
        return p

    def frame(sky, cap):
        f = noise_texture((fw, fh), (250, 248, 242), amount=6, seed=rnd.random())
        f.paste(photo(sky, fw - 2 * m, ph), (m, m))
        if cap:
            box = (m, m, fw - m, m + ph)
            ib = (box[0] + int(fw * 0.08), box[1] + int(ph * 0.1), box[2] - int(fw * 0.08), box[3] - int(ph * 0.12))
            _b2_shadow_text(f, text, ib, find_font("black"), "#ffffff", shade=(20, 10, 30, 170), blur=max(3, u * 0.008),
                         align="center", max_size=int(u * 0.085), spacing=1.2)
            today = datetime.date.today()
            capt = f"{rnd.choice(['kỷ niệm', 'ngày đẹp trời', 'vũ trụ gửi', 'mùa thu ấy'])} · {today:%d.%m.%Y}"
            cb = (m, m + ph + int((fh - m - ph) * 0.15), fw - m, fh - int((fh - m - ph) * 0.15))
            draw_text_block(f, capt, cb, find_font("hand"), "#3b3b46", align="center", max_size=int(u * 0.06))
        return f

    _b2_drop(img, frame(skies[1], False), (W * 0.5 + u * 0.12, H * 0.5 - u * 0.06), rnd.uniform(6, 11))
    ang = rnd.uniform(-4, 1)
    _b2_drop(img, frame(skies[0], True), (W / 2, H / 2 + u * 0.02), ang, blur=0.016, alpha=130)
    dx, dy = _b2_rot(0, -fh / 2, ang)
    _b2_washi(img, (W / 2 + dx, H / 2 + u * 0.02 + dy), fw * 0.34, u * 0.07, ang + rnd.uniform(-6, 6),
           rnd.choice(["#f7c6d0", "#cde7f0", "#fbe3a1", "#d6c8f0"]), rnd, alpha=200)
    return img


def tpl_receipt(text, W, H, rnd):
    """Hoá đơn in nhiệt răng cưa, chữ mono mờ mực + mã vạch."""
    u = min(W, H)
    bg = rnd.choice([["#2b2d42", "#14151f"], ["#f7c8c0", "#f1a7a0"], ["#c9e4de", "#9cc9c0"], ["#3d405b", "#222433"]])
    img = gradient((W, H), bg, angle=30)
    add_grain(img, 10)
    rw = int(min(W * 0.74, H * 0.6))
    rh = int(H * 0.9)
    paper = noise_texture((rw, rh), (248, 246, 240), amount=6, seed=rnd.random())
    mask = Image.new("L", (rw, rh), 0)
    t = rw * 0.025
    n = 26
    top = [(i * rw / n, t if i % 2 else 0) for i in range(n + 1)]
    bot = [(rw - i * rw / n, rh - (t if i % 2 else 0)) for i in range(n + 1)]
    ImageDraw.Draw(mask).polygon(top + bot, fill=255)
    paper.putalpha(mask)
    d = ImageDraw.Draw(paper)
    ink, faint = "#232323", "#6a6a6a"
    mono = "mono"
    mx = rw * 0.08
    fs = min(rw * 0.036, rh * 0.021)
    dw = max(2, int(rw * 0.004))
    # phần đầu: chảy từ trên xuống
    y = t + fs * 2.2
    sparkle(d, rw / 2, y, fs * 1.6, ink)
    y += fs * 2.2
    label(d, (rw / 2, y), "KÊNH VŨ TRỤ", mono, fs * 2.1, ink, "mt")
    y += fs * 2.8
    label(d, (rw / 2, y), "Cửa hàng may mắn số 7", mono, fs, faint, "mt")
    y += fs * 2.2
    now = datetime.datetime.now()
    label(d, (mx, y), f"Ngày: {now:%d/%m/%Y}", mono, fs, ink)
    label(d, (rw - mx, y), f"Giờ: {now:%H:%M}", mono, fs, ink, "ra")
    y += fs * 1.5
    label(d, (mx, y), f"HĐ: #{rnd.randint(10000, 99999)}", mono, fs, ink)
    label(d, (rw - mx, y), f"Quầy: {rnd.randint(1, 9):02d}", mono, fs, ink, "ra")
    y += fs * 2
    dashed(d, (mx, y), (rw - mx, y), rw * 0.02, rw * 0.012, ink, dw)
    top_y = y + fs
    # phần cuối: chảy từ dưới lên
    y = rh - t - fs * 2
    label(d, (rw / 2, y), "CẢM ƠN & HẸN GẶP LẠI", mono, fs, ink, "mt")
    y -= fs * 1.4
    label(d, (rw / 2, y), " ".join(str(rnd.randint(0, 9)) for _ in range(12)), mono, fs * 0.8, faint, "mt")
    y -= fs * 0.4 + fs * 3
    barcode(d, (rw * 0.14, y, rw * 0.86, y + fs * 3), rnd, ink)
    y -= fs * 2.6
    label(d, (mx, y), "TỔNG CỘNG", mono, fs * 1.4, ink)
    label(d, (rw - mx, y), "VÔ GIÁ", mono, fs * 1.4, ink, "ra")
    y -= fs * 0.6
    d.line((mx, y, rw - mx, y), fill=ink, width=dw)
    for name, val in rnd.sample([("May mắn", "x1"), ("Bình an", "x1"), ("Tài lộc", "x3"), ("Sức khỏe", "x2"),
                                 ("Niềm vui", "x5"), ("Quý nhân", "x1")], 3):
        y -= fs * 1.8
        label(d, (mx, y), name, mono, fs * 1.1, ink)
        label(d, (rw - mx, y), val, mono, fs * 1.1, ink, "ra")
    y -= fs * 1.2
    dashed(d, (mx, y), (rw - mx, y), rw * 0.02, rw * 0.012, ink, dw)
    rough_text(paper, text, (int(mx), int(top_y), int(rw - mx), int(y - fs)), find_font(mono), ink, k=1.2,
               align="center", upper=True, max_size=int(rw * 0.1), spacing=1.3)
    _b2_drop(img, paper, (W / 2, H / 2), rnd.uniform(-3, 3), off=(0.012, 0.02), blur=0.02, alpha=140)
    return img


def tpl_typewriter(text, W, H, rnd):
    """Tờ giấy kẹp trong máy đánh chữ cổ, chữ mono mực rỗ."""
    u = min(W, H)
    body, key = rnd.choice([("#8fc1b5", "#2f3e46"), ("#e8dcc4", "#3b3027"), ("#c0392b", "#1f1f1f"),
                            ("#2f3e46", "#e8e2d0")])
    img = gradient((W, H), ["#3a2f2a", "#1d1714"])
    add_grain(img, 12)
    ry = H * (0.8 if W > H else 0.83)        # tâm trục lăn
    rr = u * 0.055                            # bán kính trục
    pw = min(W * 0.78, H * 0.95)
    px0, px1 = W / 2 - pw / 2, W / 2 + pw / 2
    paper = noise_texture((int(pw), int(ry - H * 0.04)), (246, 240, 226), amount=8, seed=rnd.random())
    shadow(img, (px0, H * 0.04, px1, ry), 4, offset=(0, int(u * 0.01)), blur=int(u * 0.02), alpha=120)
    img.alpha_composite(paper, (int(px0), int(H * 0.04)))
    d = ImageDraw.Draw(img)
    today = datetime.date.today()
    label(d, (px1 - pw * 0.08, H * 0.04 + u * 0.07), f"Ngày {today.day} tháng {today.month} năm {today.year}",
          "mono", u * 0.03, "#4a4038", "ra")
    box = (int(px0 + pw * 0.1), int(H * 0.04 + u * 0.15), int(px1 - pw * 0.1), int(ry - rr - u * 0.07))
    rough_text(img, text, box, find_font("mono"), "#1e1b18", k=1.6, align="left", valign="top",
               max_size=int(u * 0.09), spacing=1.4)
    # thân máy
    d.rounded_rectangle((W * 0.02, ry - rr * 0.2, W * 0.98, H + u * 0.1), int(u * 0.05), fill=body)
    d.line((W * 0.05, ry + rr * 1.5, W * 0.95, ry + rr * 1.5), fill=mix(body, "#ffffff", 0.3),
           width=max(2, int(u * 0.006)))
    # trục lăn hình trụ
    for i in range(12):
        t = i / 11
        c = mix("#0d0d0d", "#5a5a5a", 1 - abs(t - 0.35) * 1.4)
        y = ry - rr + 2 * rr * t
        d.rectangle((W * 0.06, y, W * 0.94, y + 2 * rr / 11 + 1), fill=c)
    for x in (W * 0.03, W * 0.93):
        d.rounded_rectangle((x, ry - rr * 1.2, x + W * 0.04, ry + rr * 1.2), int(rr * 0.4), fill="#1a1a1a",
                            outline="#555555", width=2)
    # thanh kẹp giấy mạ crôm
    by = ry - rr - u * 0.012
    d.rounded_rectangle((px0 - pw * 0.04, by - u * 0.008, px1 + pw * 0.04, by + u * 0.008), int(u * 0.008),
                        fill="#d9d9d9", outline="#8a8a8a", width=1)
    for x in (px0 + pw * 0.25, px1 - pw * 0.25):
        d.rounded_rectangle((x - u * 0.02, by - u * 0.014, x + u * 0.02, by + u * 0.014), int(u * 0.01),
                            fill="#2b2b2b")
    # hàng phím tròn phía dưới
    kr = u * 0.045
    ky = ry + rr * 2.6 + kr
    n = max(5, int(W / (kr * 2.7)))
    keys = "QWERTYUIOPASDFGHJKL"
    for i in range(n):
        kx = W / 2 + (i - (n - 1) / 2) * kr * 2.6
        d.ellipse((kx - kr, ky - kr + kr * 0.25, kx + kr, ky + kr + kr * 0.25), fill="#111111")
        d.ellipse((kx - kr, ky - kr, kx + kr, ky + kr), fill=key, outline="#cfcfcf", width=max(2, int(kr * 0.12)))
        label(d, (kx, ky), keys[i % len(keys)], "mono", kr * 0.8, ("#ffffff" if luminance(key) < 128 else "#111111"), "mm")
    vignette(img, 110)
    return img


def tpl_legal_pad(text, W, H, rnd):
    """Tập giấy vàng kẻ xanh, lề đỏ đôi, gáy đỏ sẫm trên bàn gỗ + bút chì."""
    u = min(W, H)
    img = _b2_wood(W, H, rnd)
    land = W > H
    pw = W * (0.66 if land else 0.86)
    ph = H * (0.9 if land else 0.82)
    pad = int(u * 0.03)
    lay = Image.new("RGBA", (int(pw) + 2 * pad, int(ph) + 2 * pad), (0, 0, 0, 0))
    x0, y0, x1, y1 = pad, pad, pad + int(pw), pad + int(ph)
    d = ImageDraw.Draw(lay)
    for k in (3, 2, 1):  # độ dày tập giấy
        d.rectangle((x0 + k * 2, y0 + k * 4, x1 + k * 2, y1 + k * 4), fill=mix("#f3e27a", "#8a7a30", k * 0.12))
    lay.paste(noise_texture((x1 - x0, y1 - y0), (253, 240, 150), amount=8, seed=rnd.random()), (x0, y0))
    bh = int(u * 0.09)
    d.rectangle((x0, y0, x1, y0 + bh), fill="#7a2430")
    for i in range(0, x1 - x0, max(4, int(u * 0.008))):
        d.line((x0 + i, y0, x0 + i, y0 + bh), fill="#6a1e29", width=1)
    d.rectangle((x0, y0 + bh, x1, y0 + bh + int(u * 0.008)), fill="#5a1520")
    for i in range(int(pw / (u * 0.02))):  # mép giấy xé còn sót dưới gáy
        xx = x0 + i * u * 0.02
        d.polygon([(xx, y0 + bh), (xx + u * 0.01, y0 + bh + rnd.uniform(u * 0.008, u * 0.02)), (xx + u * 0.02, y0 + bh)],
                  fill="#f6e690")
    mxl = x0 + pw * 0.14
    for dx in (0, u * 0.01):
        d.line((mxl + dx, y0 + bh, mxl + dx, y1), fill="#e8838a", width=max(2, int(u * 0.003)))
    box = (int(mxl + pw * 0.04), int(y0 + bh + u * 0.07), int(x1 - pw * 0.06), int(y1 - u * 0.05))
    ruled_text(lay, text, box, find_font("hand"), "#1f3b8a", "#9cc4e4", int(u * 0.09), spacing=1.55,
               rule_box=(x0, y0 + bh + u * 0.02, x1, y1 - u * 0.01), width=max(2, int(u * 0.0025)))
    label(d, (x1 - pw * 0.05, y0 + bh / 2), "GHI CHÉP", "black", u * 0.03, "#e8c7a0", "rm")
    ang = rnd.uniform(-2, 2)
    cx, cy = (W * 0.45, H / 2) if land else (W / 2, H * 0.45)
    _b2_drop(img, lay, (cx, cy), ang, blur=0.016, alpha=140)
    pen = _b2_pencil(u * 0.75, u * 0.045)
    if land:
        _b2_drop(img, pen, (W * 0.88, H * 0.52), 90 + rnd.uniform(-8, 8), alpha=120)
    else:
        _b2_drop(img, pen, (W * 0.52, H * 0.93), rnd.uniform(-6, 6), alpha=120)
    return img


def tpl_index_card(text, W, H, rnd):
    """Thẻ index kẻ dòng có dòng đỏ đầu thẻ, xếp chồng và kẹp giấy."""
    u = min(W, H)
    bg = rnd.choice(["#c9d6c3", "#cfd8e6", "#ead7cf", "#d9d2e9"])
    img = Image.new("RGBA", (W, H), bg)
    dots(ImageDraw.Draw(img), (0, 0, W, H), int(u * 0.045), max(2, int(u * 0.003)), mix(bg, "#000000", 0.12))
    if W > H:
        cw = int(min(W * 0.62, H * 0.82 * 5 / 3)); ch = int(cw * 3 / 5)
    else:
        cw = int(W * 0.84); ch = int(min(H * 0.6, cw * 1.3))
    c = (W / 2, H / 2)
    for col in rnd.sample(["#f9c6d3", "#bfe3f5", "#fbe7a1", "#cdeccd"], 2):
        _b2_drop(img, Image.new("RGBA", (cw, ch), col), (c[0] + rnd.uniform(-1, 1) * u * 0.03,
                                                       c[1] + rnd.uniform(-1, 1) * u * 0.03), rnd.uniform(-8, 8))
    pad = int(u * 0.09)
    lay = Image.new("RGBA", (cw + 2 * pad, ch + 2 * pad), (0, 0, 0, 0))
    lay.paste(noise_texture((cw, ch), (255, 253, 247), amount=5, seed=rnd.random()), (pad, pad))
    d = ImageDraw.Draw(lay)
    x0, y0, x1, y1 = pad, pad, pad + cw, pad + ch
    hh = int(min(ch * 0.17, u * 0.12))
    lw = max(2, int(u * 0.0035))
    d.line((x0, y0 + hh, x1, y0 + hh), fill="#e05a5a", width=lw)
    label(d, (x0 + cw * 0.18, y0 + hh * 0.55), rnd.choice(["Ghi nhớ", "Hôm nay", "Lời nhắn"]), "marker", hh * 0.5,
          "#c0392b", "lm")
    label(d, (x1 - cw * 0.06, y0 + hh * 0.55), f"No. {rnd.randint(1, 99):02d}", "mono", hh * 0.3, "#9a9a9a", "rm")
    box = (int(x0 + cw * 0.08), int(y0 + hh + u * 0.03), int(x1 - cw * 0.08), int(y1 - u * 0.04))
    ruled_text(lay, text, box, find_font("hand2"), "#22304a", "#a9cbe8", int(u * 0.08), spacing=1.45,
               rule_box=(x0, y0 + hh + 2, x1, y1 - u * 0.01), width=lw)
    # kẹp giấy
    cx, cy = x0 + cw * 0.08, y0
    sw = max(3, int(u * 0.008))
    clip = Image.new("RGBA", (int(u * 0.09), int(u * 0.26)), (0, 0, 0, 0))
    cd = ImageDraw.Draw(clip)
    cwid, chgt = clip.size
    cd.rounded_rectangle((sw, sw, cwid - sw, chgt - sw), cwid // 2, outline="#8d99a6", width=sw)
    cd.rounded_rectangle((cwid * 0.25, sw * 2, cwid * 0.75, chgt * 0.72), cwid // 4, outline="#b8c2cc", width=sw)
    paste_rotated(lay, clip, (cx, cy + chgt * 0.12), -12)
    _b2_drop(img, lay, c, rnd.uniform(-3, 3), blur=0.014, alpha=120)
    return img


def tpl_newspaper(text, W, H, rnd):
    """Trang báo cũ ngả vàng: tên báo, tít lớn là nội dung, cột chữ và ảnh chấm."""
    u = min(W, H)
    img = noise_texture((W, H), (228, 219, 196), amount=14, seed=rnd.random())
    d = ImageDraw.Draw(img)
    ink, grey = "#1c1a17", "#4a453d"
    m = int(u * 0.06)
    today = datetime.date.today()
    label(d, (W / 2, m), "Phát hành mỗi ngày · Tin vui cho mọi tuổi", "book", u * 0.022, grey, "mt")
    draw_text_block(img, "Báo Vũ Trụ", (m, int(m + u * 0.035), W - m, int(m + u * 0.2)), find_font("serif"), ink,
                    align="center", max_size=int(u * 0.16), upper=True)
    y = m + u * 0.215
    lw = max(2, int(u * 0.003))
    d.line((m, y, W - m, y), fill=ink, width=lw * 2)
    d.line((m, y + lw * 3, W - m, y + lw * 3), fill=ink, width=lw)
    fs = u * 0.022
    yy = y + lw * 3 + u * 0.012
    label(d, (m, yy), f"SỐ {rnd.randint(100, 9999)}", "bold", fs, ink)
    label(d, (W / 2, yy), f"{VN_WEEKDAYS[today.weekday()].upper()}, {today:%d/%m/%Y}", "bold", fs, ink, "ma")
    label(d, (W - m, yy), "GIÁ: 1 NỤ CƯỜI", "bold", fs, ink, "ra")
    y = yy + fs * 1.6
    d.line((m, y, W - m, y), fill=ink, width=lw)
    d.line((m, y + lw * 3, W - m, y + lw * 3), fill=ink, width=lw * 2)
    y += u * 0.04
    hbox = (m, int(y), W - m, int(y + (H - y - m) * (0.42 if H > W else 0.48)))
    font, tw, th, _ = measure_text(text, hbox, find_font("serif"), int(u * 0.11), spacing=1.12)
    draw_text_block(img, text, (m, int(y), W - m, int(y + th)), find_font("serif"), ink, align="center",
                    valign="top", max_size=font.size, spacing=1.12)
    y += th + u * 0.02
    label(d, (W / 2, y), "— Theo nguồn tin từ các vì sao, điều tốt lành đang đến rất gần —", "book", u * 0.024,
          grey, "mt")
    y += u * 0.05
    d.line((m, y, W - m, y), fill=ink, width=lw)
    y += u * 0.025
    ncol = 3 if H > W else 4
    gap = u * 0.03
    cw = (W - 2 * m - gap * (ncol - 1)) / ncol
    small = load_font(find_font("book"), max(10, int(u * 0.02)))
    lh = small.size * 1.35
    photo_col = rnd.randrange(ncol)
    heads = rnd.sample(["TIN NÓNG", "VẬN MAY", "TÌNH DUYÊN", "SỨC KHỎE", "TÀI LỘC"], 5)
    for i in range(ncol):
        cx0 = m + i * (cw + gap)
        cy = y
        if i:
            d.line((cx0 - gap / 2, y, cx0 - gap / 2, H - m), fill=grey, width=1)
        if i == photo_col:
            ph = min(cw * 0.8, (H - m - y) * 0.6)
            _b2_halftone(d, (cx0, cy, cx0 + cw, cy + ph), rnd, ink)
            cy += ph + u * 0.01
            label(d, (cx0, cy), "Ảnh: Bầu trời sáng nay", "book", small.size * 0.9, grey)
            cy += lh * 1.4
        else:
            label(d, (cx0, cy), heads.pop(), "black",
                  small.size * 1.3, ink)
            cy += lh * 1.5
        for line in wrap_text(_b2_filler(rnd, 160), small, cw):
            if cy + lh > H - m:
                break
            d.text((cx0, cy), line, font=small, fill=grey)
            cy += lh
    # nếp gấp giữa trang
    fold = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    fd = ImageDraw.Draw(fold)
    fd.rectangle((0, H * 0.5 - u * 0.004, W, H * 0.5), fill=(60, 40, 10, 50))
    fd.rectangle((0, H * 0.5, W, H * 0.5 + u * 0.004), fill=(255, 255, 255, 60))
    img.alpha_composite(fold.filter(ImageFilter.GaussianBlur(u * 0.004)))
    stain = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    soft_blobs(stain, rnd, ["#a07a3a"], n=3, alpha=40, rmin=0.15, rmax=0.3)
    img.alpha_composite(stain)
    vignette(img, 120)
    add_grain(img, 14)
    return img


def tpl_ransom(text, W, H, rnd):
    """Chữ cắt dán từ tạp chí: mỗi từ một mảnh giấy khác màu, khác font, xoay nhẹ."""
    u = min(W, H)
    dark = rnd.random() < 0.4
    img = noise_texture((W, H), (24, 24, 26) if dark else (238, 233, 222), amount=10, seed=rnd.random())
    if not dark:
        h_lines(ImageDraw.Draw(img), (0, 0, W, H), int(u * 0.05), (220, 214, 200), 2)
    swatches = [("#ffffff", "#111111"), ("#111111", "#ffffff"), ("#e63946", "#ffffff"), ("#ffd60a", "#111111"),
                ("#4361ee", "#ffffff"), ("#f1e3c8", "#3a2b1a"), ("#ff8fab", "#2b0a18"), ("#2a9d8f", "#ffffff"),
                ("#f4f1de", "#c1121f"), ("#d9d4c7", "#222222"), ("#8338ec", "#fff3b0"), ("#fb8500", "#111111")]
    kinds = ["black", "serif", "comic", "retro", "mono", "round", "marker", "book", "heavy", "brush"]
    rows_src = [p.split() for p in text.split("\n")]
    words = []
    for r, row in enumerate(rows_src):
        for w in row:
            if word_width(w, load_font(find_font("bold"), 100)) < 30:  # emoji không render được
                continue
            sw = rnd.choice(swatches)
            if dark and sw[0] == "#111111":
                sw = ("#ffffff", "#111111")
            words.append(dict(w=w.upper() if rnd.random() < 0.45 else w, row=r, kind=rnd.choice(kinds),
                              sc=rnd.uniform(0.85, 1.2), sw=sw, ang=rnd.uniform(-7, 7)))
    bx0, by0, bx1, by1 = W * 0.07, H * 0.1, W * 0.93, H * 0.9
    bw, bh = bx1 - bx0, by1 - by0

    def layout(s):
        rows, cur, cw, last = [], [], 0, None
        for wd in words:
            f = load_font(find_font(wd["kind"]), max(8, int(s * wd["sc"])))
            pw = word_width(wd["w"], f) + f.size * 0.5
            wd["f"], wd["pw"], wd["ph"] = f, pw, f.size * 1.45
            if cur and (cw + pw > bw or wd["row"] != last):
                rows.append(cur); cur, cw = [], 0
            cur.append(wd); cw += pw + s * 0.15; last = wd["row"]
        rows.append(cur)
        th = sum(max(w_["ph"] for w_ in r) + s * 0.25 for r in rows)
        ok = th <= bh and all(w_["pw"] <= bw for w_ in words)
        return rows, th, ok

    s = int(u * 0.12)
    while True:
        rows, th, ok = layout(s)
        if ok or s <= 20:
            break
        s -= 3
    pieces = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    y = by0 + (bh - th) / 2
    for r in rows:
        rh = max(w_["ph"] for w_ in r)
        rw = sum(w_["pw"] for w_ in r) + s * 0.15 * (len(r) - 1)
        x = bx0 + (bw - rw) / 2
        for wd in r:
            e = int(s * 0.1)
            pw, ph, f = int(wd["pw"]), int(wd["ph"]), wd["f"]
            lay = Image.new("RGBA", (pw + 2 * e, ph + 2 * e), (0, 0, 0, 0))
            ld = ImageDraw.Draw(lay)
            j = lambda: rnd.uniform(-e * 0.8, e * 0.8)
            ld.polygon([(e + j(), e + j()), (e + pw + j(), e + j()), (e + pw + j(), e + ph + j()),
                        (e + j(), e + ph + j())], fill=wd["sw"][0])
            draw_word(lay, ld, e + f.size * 0.25, int(e + ph / 2 + f.size * 0.36), wd["w"], f, wd["sw"][1])
            paste_rotated(pieces, lay, (x + pw / 2, y + rh / 2 + rnd.uniform(-1, 1) * s * 0.06), wd["ang"])
            x += pw + s * 0.15
        y += rh + s * 0.25
    _b2_drop(img, pieces, (W / 2, H / 2), 0, off=(0.004, 0.008), blur=0.006, alpha=150)
    # băng dính trong ở hai góc
    for cx, cy, a in ((W * 0.12, H * 0.07, 25), (W * 0.88, H * 0.93, 30)):
        tape = Image.new("RGBA", (int(u * 0.3), int(u * 0.07)), (255, 255, 240, 110))
        paste_rotated(img, tape, (cx, cy), a)
    return img


def tpl_scrapbook(text, W, H, rnd):
    """Trang scrapbook: giấy hoạ tiết xếp lớp, thẻ ghi chú, băng washi, nhãn và hoa."""
    u = min(W, H)
    bg = rnd.choice(["#efd9c3", "#f4dfe4", "#dfe8dc", "#e3dcef"])
    img = noise_texture((W, H), rgb(bg), amount=10, seed=rnd.random())
    grid(ImageDraw.Draw(img), (0, 0, W, H), int(u * 0.06), mix(bg, "#ffffff", 0.35), 2)
    pal = ["#e8a0a8", "#9cc5b5", "#f2c879", "#a9b8e0", "#d7a6d9"]
    rnd.shuffle(pal)
    # giấy hoạ tiết lót
    for k, col in enumerate(pal[:2]):
        pw, ph = int(W * 0.78), int(H * 0.72)
        p = Image.new("RGBA", (pw, ph), col)
        pd = ImageDraw.Draw(p)
        if k == 0:
            dots(pd, (0, 0, pw, ph), int(u * 0.04), int(u * 0.006), mix(col, "#ffffff", 0.45))
        else:
            for x in range(0, pw, int(u * 0.05)):
                pd.rectangle((x, 0, x + u * 0.02, ph), fill=mix(col, "#ffffff", 0.3))
        _b2_drop(img, p, (W / 2 + (-1) ** k * u * 0.05, H / 2 + (-1) ** k * u * 0.03),
              (-1) ** k * rnd.uniform(4, 8), alpha=90)
    cw, chh = int(W * 0.76), int(H * 0.66)
    pad = int(u * 0.03)
    lay = Image.new("RGBA", (cw + 2 * pad, chh + 2 * pad), (0, 0, 0, 0))
    ld = ImageDraw.Draw(lay)
    ld.polygon(torn_rect((pad, pad, pad + cw, pad + chh), rnd, jag=u * 0.006, step=max(6, int(u * 0.015))),
               fill="#fffaf0")
    dots(ld, (pad + u * 0.04, pad + u * 0.04, pad + cw - u * 0.04, pad + chh - u * 0.04), int(u * 0.04),
         max(1, int(u * 0.0025)), "#e6dccb", stagger=False)
    label(ld, (pad + cw * 0.08, pad + u * 0.05), rnd.choice(["nhật ký nhỏ", "gửi chính mình", "hôm nay"]), "hand", u * 0.04, "#b07a5a")
    box = (int(pad + cw * 0.09), int(pad + u * 0.13), int(pad + cw * 0.91), int(pad + chh - u * 0.07))
    draw_text_block(lay, text, box, find_font("hand"), "#4a3426", align="center", max_size=int(u * 0.1),
                    spacing=1.3)
    ang = rnd.uniform(-2.5, 2.5)
    c = (W / 2, H / 2)
    _b2_drop(img, lay, c, ang, alpha=110)
    for sx, sy, a in ((-1, -1, 35), (1, 1, 35)):
        dx, dy = _b2_rot(sx * cw / 2, sy * chh / 2, ang)
        _b2_washi(img, (c[0] + dx, c[1] + dy), u * 0.3, u * 0.075, sx * sy * a + rnd.uniform(-8, 8),
               rnd.choice(pal[2:]), rnd)
    _b2_washi(img, (c[0] + cw * 0.15, c[1] - chh / 2 - u * 0.005), u * 0.24, u * 0.06, rnd.uniform(-5, 5), pal[0], rnd)
    # nhãn treo
    tw, th = int(u * 0.28), int(u * 0.12)
    tag = Image.new("RGBA", (tw, th), (0, 0, 0, 0))
    td = ImageDraw.Draw(tag)
    td.polygon([(th * 0.4, 0), (tw, 0), (tw, th), (th * 0.4, th), (0, th / 2)], fill="#c89f74")
    td.ellipse((th * 0.3, th * 0.4, th * 0.5, th * 0.6), fill=(0, 0, 0, 0))
    label(td, (tw * 0.6, th / 2), "kỷ niệm", "marker", th * 0.38, "#4a2f1a", "mm")
    _b2_drop(img, tag, (W - u * 0.2, c[1] + chh / 2 + u * 0.02), rnd.uniform(-20, -8), alpha=100)
    # hoa và sao trang trí
    d = ImageDraw.Draw(img)
    for fx, fy in ((u * 0.1, H - u * 0.1), (W - u * 0.1, u * 0.1)):
        r = u * 0.04
        col = rnd.choice(pal)
        for k in range(6):
            a = math.radians(k * 60)
            px, py = fx + r * math.cos(a), fy + r * math.sin(a)
            d.ellipse((px - r * 0.7, py - r * 0.7, px + r * 0.7, py + r * 0.7), fill=col)
        d.ellipse((fx - r * 0.5, fy - r * 0.5, fx + r * 0.5, fy + r * 0.5), fill="#f7d774")
    for _ in range(5):
        x, y = rnd.uniform(0, W), rnd.choice([rnd.uniform(0, H * 0.12), rnd.uniform(H * 0.88, H)])
        sparkle(d, x, y, u * rnd.uniform(0.015, 0.03), "#ffffff")
    return img


def tpl_book_page(text, W, H, rnd):
    """Trang sách mở trên nền vải, câu chính được tô dạ quang giữa đoạn văn."""
    u = min(W, H)
    img = gradient((W, H), rnd.choice([["#5b4636", "#2e2219"], ["#3c4a5c", "#1e2530"], ["#5a3b3b", "#2a1b1b"]]))
    add_grain(img, 16)
    land = W > H
    cover = rnd.choice(["#6b1f2a", "#1f3b5a", "#2f4a2f"])
    paper = (245, 236, 215)
    ink, faint = "#2b2118", "#7a6c58"
    hl = rnd.choice(["#ffe866", "#ffc2d1", "#bdf0c4", "#bfe1ff"])
    by0, by1 = H * 0.06, H * 0.95
    if land:
        bx0, bx1 = W * 0.05, W * 0.95
        pages = [(bx0, W / 2, "L"), (W / 2, bx1, "R")]
    else:
        bx0, bx1 = W * 0.0, W * 0.94
        pages = [(bx0, bx1, "R")]
    d = ImageDraw.Draw(img)
    shadow(img, (bx0, by0, bx1, by1), 10, offset=(0, int(u * 0.02)), blur=int(u * 0.03), alpha=150)
    d.rounded_rectangle((bx0 - u * 0.015, by0 - u * 0.01, bx1 + u * 0.015, by1 + u * 0.025), int(u * 0.015),
                        fill=cover)
    small = load_font(find_font("book"), max(10, int(u * 0.026)))
    lh = small.size * 1.5
    pno = rnd.randint(40, 300) * 2
    for px0, px1, side in pages:
        pw, ph = int(px1 - px0), int(by1 - by0)
        pg = noise_texture((pw, ph), paper, amount=6, seed=rnd.random())
        pd = ImageDraw.Draw(pg)
        # mép giấy xếp lớp ở cạnh ngoài
        for k in range(6):
            o = k * u * 0.003
            if side == "R":
                pd.line((pw - 1 - o, 0, pw - 1 - o, ph), fill=mix(paper, "#8a7a5a", 0.35), width=1)
            else:
                pd.line((o, 0, o, ph), fill=mix(paper, "#8a7a5a", 0.35), width=1)
            pd.line((0, ph - 1 - o, pw, ph - 1 - o), fill=mix(paper, "#8a7a5a", 0.3), width=1)
        # bóng gáy sách
        gl = Image.new("RGBA", (pw, ph), (0, 0, 0, 0))
        gw = int(pw * 0.14)
        for i in range(gw):
            a = int(110 * (1 - i / gw) ** 2)
            x = i if side == "R" else pw - 1 - i
            ImageDraw.Draw(gl).line((x, 0, x, ph), fill=(60, 40, 20, a))
        mx0 = pw * (0.14 if side == "R" else 0.1)
        mx1 = pw * (0.9 if side == "R" else 0.86)
        top, bot = ph * 0.1, ph * 0.9
        label(pd, (pw / 2, ph * 0.045), "Lời thì thầm của vũ trụ", "book", u * 0.022, faint, "mm")
        label(pd, (pw / 2, ph * 0.955), str(pno + (1 if side == "R" else 0)), "book",
              u * 0.024, faint, "mm")
        if side == "L":
            label(pd, (pw / 2, ph * 0.2), "Chương VII", "serif", u * 0.07, ink, "mm")
            pd.line((pw * 0.35, ph * 0.27, pw * 0.65, ph * 0.27), fill=faint, width=2)
            sparkle(pd, pw / 2, ph * 0.27, u * 0.015, faint)
            cy = ph * 0.34
            for line in wrap_text(_b2_filler(rnd, 200), small, mx1 - mx0):
                if cy + lh > bot:
                    break
                pd.text((mx0, cy), line, font=small, fill=faint)
                cy += lh
        else:
            mbox = (int(mx0), int(top), int(mx1), int(top + (bot - top) * 0.62))
            font, tw, th, mlh = measure_text(text, mbox, find_font("book"), int(u * 0.07), spacing=1.45)
            my0 = top + (bot - top - th) / 2
            cy = my0 - lh * 0.6
            lines = wrap_text(_b2_filler(rnd, 120), small, mx1 - mx0)
            above = [l for l in lines][:max(0, int((cy - top) // lh))]
            yy = cy - len(above) * lh
            for line in above:
                pd.text((mx0, yy), line, font=small, fill=faint)
                yy += lh

            def mark(im, x, y, w, h, f):
                if w < f.size * 0.6:
                    return
                ImageDraw.Draw(im).polygon([(x - f.size * 0.15, y + h * 0.18), (x + w + f.size * 0.2, y + h * 0.12),
                                            (x + w + f.size * 0.1, y + h * 0.92), (x - f.size * 0.1, y + h * 0.96)],
                                           fill=mix(paper, hl, 0.85))

            draw_text_block(pg, text, (int(mx0), int(my0), int(mx1), int(my0 + th)), find_font("book"), ink,
                            align="left", valign="top", max_size=font.size, spacing=1.45, line_bg=mark)
            yy = my0 + th + lh * 0.6
            for line in wrap_text(_b2_filler(rnd, 160), small, mx1 - mx0):
                if yy + lh > bot:
                    break
                pd.text((mx0, yy), line, font=small, fill=faint)
                yy += lh
        pg.alpha_composite(gl)
        img.alpha_composite(pg, (int(px0), int(by0)))
    # dải ruy băng đánh dấu trang
    rx = (W / 2 + u * 0.06) if land else (bx0 + (bx1 - bx0) * 0.78)
    rw_ = u * 0.035
    d.polygon([(rx, by0 - u * 0.01), (rx + rw_, by0 - u * 0.01), (rx + rw_, by0 + u * 0.12),
               (rx + rw_ / 2, by0 + u * 0.1), (rx, by0 + u * 0.12)], fill=rnd.choice(["#b3263a", "#d4a017", "#2b6cb0"]))
    vignette(img, 80)
    return img


def tpl_tear_calendar(text, W, H, rnd):
    """Lịch xé treo tường: ngày hôm nay số lớn, thứ tiếng Việt và lời nhắn."""
    u = min(W, H)
    wall = rnd.choice(["#f3e9dc", "#e4ecf2", "#f2e1e6", "#e6efe0"])
    img = Image.new("RGBA", (W, H), wall)
    d = ImageDraw.Draw(img)
    sw = int(u * 0.05)
    for x in range(0, W, sw * 2):
        d.rectangle((x, 0, x + sw, H), fill=mix(wall, "#ffffff", 0.35))
    today = datetime.date.today()
    wd = today.weekday()
    red = "#d62828"
    num_col = red if wd == 6 else "#1d3a8a"
    land = W > H
    bx0, bx1 = (W * 0.14, W * 0.86) if land else (W * 0.08, W * 0.92)
    by0, by1 = H * (0.1 if land else 0.09), H * (0.94 if land else 0.92)
    hh = u * 0.12
    # đinh + dây treo
    nx, ny = W / 2, H * 0.03
    d.line((nx, ny, bx0 + (bx1 - bx0) * 0.3, by0 + hh * 0.3), fill="#7a5a3a", width=max(2, int(u * 0.004)))
    d.line((nx, ny, bx0 + (bx1 - bx0) * 0.7, by0 + hh * 0.3), fill="#7a5a3a", width=max(2, int(u * 0.004)))
    _b2_pin(img, nx, ny, u * 0.015, "#8a8a8a")
    shadow(img, (bx0, by0, bx1, by1), 8, offset=(int(u * 0.01), int(u * 0.02)), blur=int(u * 0.025), alpha=110)
    # các tờ lịch phía dưới (độ dày)
    for k in range(5, 0, -1):
        o = k * u * 0.004
        d.rectangle((bx0 + o * 0.3, by0 + hh, bx1 - o * 0.3, by1 + o), fill=mix("#ffffff", "#c8c0b0", k * 0.12))
    d.rectangle((bx0, by0 + hh, bx1, by1), fill="#fffdf8")
    # bìa đầu lịch
    hc = rnd.choice(["#b5302c", "#2b4f81", "#2f6b4f"])
    d.rounded_rectangle((bx0 - u * 0.01, by0, bx1 + u * 0.01, by0 + hh), int(u * 0.015), fill=hc)
    label(d, ((bx0 + bx1) / 2, by0 + hh / 2), f"LỊCH {today.year}", "black", hh * 0.4, "#ffe9a8", "mm")
    for rx in (bx0 + (bx1 - bx0) * 0.18, bx1 - (bx1 - bx0) * 0.18):
        d.ellipse((rx - hh * 0.12, by0 + hh * 0.25, rx + hh * 0.12, by0 + hh * 0.49), fill="#3a3a3a")
    # răng cưa giấy xé còn sót
    pts, x, step = [(bx0, by0 + hh)], bx0, u * 0.018
    while x < bx1:
        pts.append((x + step / 2, by0 + hh + rnd.uniform(u * 0.008, u * 0.025)))
        x += step
        pts.append((min(x, bx1), by0 + hh))
    d.polygon(pts, fill="#e9e3d6")
    y0 = by0 + hh + u * 0.04
    pw = bx1 - bx0
    mon = f"THÁNG {today.month} · {today.year}"
    if land:
        dx1 = bx0 + pw * 0.4
        label(d, ((bx0 + dx1) / 2, y0 + u * 0.03), mon, "black", u * 0.045, red, "mt")
        draw_text_block(img, str(today.day), (int(bx0), int(y0 + u * 0.1), int(dx1), int(by1 - u * 0.2)),
                        find_font("black"), num_col, align="center", max_size=int(u * 0.42), spacing=1.0)
        label(d, ((bx0 + dx1) / 2, by1 - u * 0.12), VN_WEEKDAYS[wd], "serif", u * 0.065, num_col, "mm")
        dashed(d, (dx1, y0), (dx1, by1 - u * 0.04), u * 0.02, u * 0.012, "#c9bfae", max(2, int(u * 0.003)))
        tbox = (int(dx1 + pw * 0.06), int(y0 + u * 0.03), int(bx1 - pw * 0.06), int(by1 - u * 0.12))
        foot = ((dx1 + bx1) / 2, by1 - u * 0.06)
    else:
        label(d, ((bx0 + bx1) / 2, y0 + u * 0.02), mon, "black", u * 0.06, red, "mt")
        dbox = (int(bx0), int(y0 + u * 0.1), int(bx1), int(y0 + u * 0.1 + (by1 - y0) * 0.3))
        draw_text_block(img, str(today.day), dbox, find_font("black"), num_col, align="center",
                        max_size=int(u * 0.5), spacing=1.0)
        yb = dbox[3] + u * 0.05
        label(d, ((bx0 + bx1) / 2, yb), VN_WEEKDAYS[wd], "serif", u * 0.08, num_col, "mm")
        yb += u * 0.08
        dashed(d, (bx0 + pw * 0.08, yb), (bx1 - pw * 0.08, yb), u * 0.02, u * 0.012, "#c9bfae",
               max(2, int(u * 0.003)))
        tbox = (int(bx0 + pw * 0.08), int(yb + u * 0.04), int(bx1 - pw * 0.08), int(by1 - u * 0.12))
        foot = ((bx0 + bx1) / 2, by1 - u * 0.06)
    draw_text_block(img, text, tbox, find_font("round"), "#2b2b35", align="center", max_size=int(u * 0.075),
                    spacing=1.2)
    label(d, foot, "· Vũ Trụ nhắn gửi hôm nay ·", "hand", u * 0.032,
          "#9a8f7c", "mm")
    # góc giấy hơi cong
    curl = u * 0.08
    d.polygon([(bx1 - curl, by1), (bx1, by1 - curl), (bx1, by1)], fill=wall)
    d.polygon([(bx1 - curl, by1), (bx1, by1 - curl), (bx1 - curl * 0.85, by1 - curl * 0.85)], fill="#e6dfd0")
    return img


def tpl_love_letter(text, W, H, rnd):
    """Thư tình rút ra từ phong bì, con dấu sáp hình tim, chữ viết tay bay bướm."""
    u = min(W, H)
    img = gradient((W, H), rnd.choice([["#ffd6e0", "#f7a8b8"], ["#fbe3e8", "#e8b4c8"], ["#f6e1d3", "#e9b7a6"]]))
    hearts = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    hd = ImageDraw.Draw(hearts)
    for _ in range(int(W * H / (u * u) * 14)):
        s = u * rnd.uniform(0.03, 0.08)
        hd.polygon(heart_points(rnd.uniform(0, W), rnd.uniform(0, H), s), fill=(255, 255, 255, rnd.randint(60, 140)))
    img.alpha_composite(hearts)
    env, flapc = rnd.choice([("#f4c2cc", "#e8a5b3"), ("#e9dccb", "#d8c4aa"), ("#d9e4f5", "#bccde8")])
    ew = min(W * 0.88, H * 1.0)
    eh = ew * 0.62
    ex0, ex1 = W / 2 - ew / 2, W / 2 + ew / 2
    ey0 = max(H * 0.95 - eh, H * (0.5 if W > H else 0.6))
    ey1 = ey0 + eh
    side = ey0 + eh * 0.28
    d = ImageDraw.Draw(img)
    shadow(img, (ex0, ey0, ex1, ey1), 12, offset=(0, int(u * 0.015)), blur=int(u * 0.03), alpha=90)
    d.rounded_rectangle((ex0, ey0, ex1, ey1), int(u * 0.012), fill=mix(env, "#000000", 0.12))
    d.polygon([(ex0, ey0), (W / 2, ey0 - eh * 0.45), (ex1, ey0)], fill=flapc)  # nắp mở
    # lá thư
    lw = ew * 0.88
    lx0, ly0 = W / 2 - lw / 2, H * 0.06
    lh = side + u * 0.05 - ly0
    letter = noise_texture((int(lw), int(lh)), (255, 250, 240), amount=5, seed=rnd.random())
    ld = ImageDraw.Draw(letter)
    lcol = "#7a1f3d"
    ld.rectangle((u * 0.02, u * 0.02, lw - u * 0.02, lh + 10), outline=mix("#fffaf0", lcol, 0.25),
                 width=max(2, int(u * 0.003)))
    label(ld, (lw * 0.09, u * 0.05), rnd.choice(["Gửi người thương,", "Thân gửi cậu,", "Gửi em,"]), "script",
          u * 0.06, lcol)
    box = (int(lw * 0.09), int(u * 0.15), int(lw * 0.91), int(side - ly0 - u * 0.12))
    draw_text_block(letter, text, box, find_font("script"), lcol, align="center", max_size=int(u * 0.1),
                    spacing=1.25)
    label(ld, (lw * 0.9, side - ly0 - u * 0.03), "— Vũ Trụ", "script", u * 0.05, lcol, "rb")
    ImageDraw.Draw(letter).polygon(heart_points(lw * 0.12, side - ly0 - u * 0.06, u * 0.04), fill="#e85a7a")
    shadow(img, (lx0, ly0, lx0 + lw, ly0 + lh), 4, offset=(0, int(u * 0.008)), blur=int(u * 0.015), alpha=80)
    img.alpha_composite(letter, (int(lx0), int(ly0)))
    # túi phong bì phía trước
    cy = ey0 + eh * 0.62
    d.polygon([(ex0, side), (W / 2, cy), (ex1, side), (ex1, ey1), (ex0, ey1)], fill=env)
    d.line((ex0, side, W / 2, cy, ex1, side), fill=mix(env, "#000000", 0.1), width=max(2, int(u * 0.004)))
    d.line((ex0, ey1, W / 2, cy + eh * 0.02, ex1, ey1), fill=mix(env, "#000000", 0.07), width=max(2, int(u * 0.003)))
    # con dấu sáp
    r = u * 0.075
    wax = "#a4161a"
    blob = [(W / 2 + (r * rnd.uniform(0.92, 1.08)) * math.cos(a / 18 * math.pi),
             cy + (r * rnd.uniform(0.92, 1.08)) * math.sin(a / 18 * math.pi)) for a in range(36)]
    sh = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ImageDraw.Draw(sh).polygon([(x + r * 0.08, y + r * 0.15) for x, y in blob], fill=(60, 0, 0, 120))
    img.alpha_composite(sh.filter(ImageFilter.GaussianBlur(r * 0.12)))
    d.polygon(blob, fill=wax)
    d.ellipse((W / 2 - r * 0.72, cy - r * 0.72, W / 2 + r * 0.72, cy + r * 0.72), fill=mix(wax, "#000000", 0.18))
    d.ellipse((W / 2 - r * 0.62, cy - r * 0.62, W / 2 + r * 0.62, cy + r * 0.62), fill=mix(wax, "#ffffff", 0.05))
    d.polygon(heart_points(W / 2 + r * 0.03, cy + r * 0.1, r * 0.75), fill=mix(wax, "#ffffff", 0.25))
    d.polygon(heart_points(W / 2, cy + r * 0.07, r * 0.75), fill=mix(wax, "#000000", 0.3))
    d.ellipse((W / 2 - r * 0.5, cy - r * 0.62, W / 2 - r * 0.2, cy - r * 0.45), fill=mix(wax, "#ffffff", 0.35))
    return img


# --- batch 3 ---

def _b3_t(text):
    """Đổi chuỗi "\\n" (gõ tay trong file text) thành xuống dòng thật."""
    return text.replace("\\n", "\n")


def _b3_date():
    t = datetime.date.today()
    return f"{VN_WEEKDAYS[t.weekday()]}, {t.day:02d}/{t.month:02d}/{t.year}"


def _b3_center_box(W, H, pw, ph, lw, lh, dy=0.0):
    """Box giữa ảnh: tỉ lệ (pw, ph) khi dọc, (lw, lh) khi ngang; dy dời theo H."""
    fw, fh = (pw, ph) if H >= W else (lw, lh)
    w, h = int(W * fw), int(H * fh)
    x0, y0 = (W - w) // 2, (H - h) // 2 + int(H * dy)
    return (x0, y0, x0 + w, y0 + h)


def _b3_hard_shadow(d, box, off, radius, color, outline=None, width=0, fill="#ffffff"):
    """Thẻ kiểu neo-brutal: bóng đặc lệch + viền dày."""
    x0, y0, x1, y1 = box
    d.rounded_rectangle((x0 + off, y0 + off, x1 + off, y1 + off), radius, fill=color)
    d.rounded_rectangle(box, radius, fill=fill, outline=outline, width=width)


def _b3_scallop_rect(d, box, r, fill):
    """Hình chữ nhật viền răng cưa tròn (nhãn kẹo, tem)."""
    x0, y0, x1, y1 = box
    d.rectangle(box, fill=fill)
    for x0_, x1_, y in ((x0, x1, y0), (x0, x1, y1)):
        n = max(2, int((x1_ - x0_) / (r * 1.7)))
        for i in range(n + 1):
            x = x0_ + (x1_ - x0_) * i / n
            d.ellipse((x - r, y - r, x + r, y + r), fill=fill)
    for y0_, y1_, x in ((y0, y1, x0), (y0, y1, x1)):
        n = max(2, int((y1_ - y0_) / (r * 1.7)))
        for i in range(n + 1):
            y = y0_ + (y1_ - y0_) * i / n
            d.ellipse((x - r, y - r, x + r, y + r), fill=fill)


def _b3_plane(d, cx, cy, s, color, angle=0):
    """Máy bay nhìn từ trên (mũi hướng sang phải khi angle=0)."""
    a = math.radians(angle)
    ca, sa = math.cos(a), math.sin(a)

    def P(pts):
        return [(cx + (x * ca - y * sa) * s, cy + (x * sa + y * ca) * s) for x, y in pts]

    d.polygon(P([(-0.5, -0.06), (0.38, -0.06), (0.5, 0), (0.38, 0.06), (-0.5, 0.06)]), fill=color)
    d.polygon(P([(0.08, -0.05), (-0.12, -0.48), (-0.22, -0.48), (-0.12, -0.05)]), fill=color)
    d.polygon(P([(0.08, 0.05), (-0.12, 0.48), (-0.22, 0.48), (-0.12, 0.05)]), fill=color)
    d.polygon(P([(-0.36, -0.05), (-0.46, -0.22), (-0.52, -0.22), (-0.48, -0.05)]), fill=color)
    d.polygon(P([(-0.36, 0.05), (-0.46, 0.22), (-0.52, 0.22), (-0.48, 0.05)]), fill=color)


def _b3_perforation(d, p0, p1, r, color):
    """Hàng lỗ đục tròn dọc theo đoạn p0 -> p1."""
    (x0, y0), (x1, y1) = p0, p1
    L = math.hypot(x1 - x0, y1 - y0)
    n = max(2, int(L / (r * 3.2)))
    for i in range(1, n):
        x, y = x0 + (x1 - x0) * i / n, y0 + (y1 - y0) * i / n
        d.ellipse((x - r, y - r, x + r, y + r), fill=color)


def _b3_field(d, x, y, cap, val, s, cap_color, val_color, kind="black", anchor="l"):
    """Ô thông tin nhỏ: nhãn mờ phía trên + giá trị đậm phía dưới."""
    label(d, (x, y), cap, "bold", s * 0.42, cap_color, anchor=anchor + "t")
    label(d, (x, y + s * 0.58), val, kind, s * 0.8, val_color, anchor=anchor + "t")


def tpl_chalkboard(text, W, H, rnd):
    """Bảng đen khung gỗ, chữ phấn rỗ, bụi phấn và khay phấn."""
    text = _b3_t(text)
    u = min(W, H)
    img = noise_texture((W, H), (120, 78, 44), amount=22, seed=rnd.random())
    d = ImageDraw.Draw(img)
    for _ in range(int(H / u * 60)):  # vân gỗ
        y = rnd.uniform(0, H)
        d.line((0, y, W, y + rnd.uniform(-8, 8)), fill=(92, 58, 30), width=rnd.choice([1, 2]))
    f = int(u * 0.055)
    board = (f, f, W - f, H - int(f * 1.6))
    green = rnd.choice([(36, 64, 50), (40, 52, 48), (30, 58, 62)])
    bd = noise_texture((board[2] - board[0], board[3] - board[1]), green, amount=12, seed=rnd.random())
    img.paste(bd, board[:2])
    d.rectangle(board, outline=(70, 44, 22), width=max(3, f // 6))
    # bụi phấn loang
    dust = Image.new("RGBA", (W, H), (255, 255, 255, 0))
    dd = ImageDraw.Draw(dust)
    for _ in range(9):
        x, y = rnd.uniform(board[0], board[2]), rnd.uniform(board[1], board[3])
        rw, rh = u * rnd.uniform(0.15, 0.4), u * rnd.uniform(0.04, 0.1)
        dd.ellipse((x - rw, y - rh, x + rw, y + rh), fill=(255, 255, 255, rnd.randint(14, 30)))
    img.alpha_composite(dust.filter(ImageFilter.GaussianBlur(u * 0.03)))
    # khay phấn
    tray = (f * 0.6, board[3], W - f * 0.6, board[3] + f * 0.7)
    d.rectangle(tray, fill=(96, 60, 30), outline=(66, 40, 18), width=3)
    cx = W * rnd.uniform(0.6, 0.75)
    for col in ("#f4f1e8", "#f6c6d0", "#f7e08a"):
        L = u * rnd.uniform(0.07, 0.1)
        d.rounded_rectangle((cx, tray[1] - f * 0.32, cx + L, tray[1] - 2), int(f * 0.15), fill=col)
        cx += L + u * 0.03
    # tiêu đề + ngày bằng phấn
    chalk = (244, 241, 232)
    ink = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    di = ImageDraw.Draw(ink)
    pad = int(u * 0.08)
    ty = board[1] + int(u * 0.07)
    label(di, (board[0] + pad, ty), "Bài học hôm nay", "hand2", u * 0.065, rgba(chalk, 230), anchor="lm")
    label(di, (board[2] - pad, ty), _b3_date(), "hand2", u * 0.036, rgba(chalk, 190), anchor="rm")
    wy = ty + u * 0.05
    pts = [(board[0] + pad + i * u * 0.02, wy + math.sin(i * 0.9) * u * 0.006) for i in range(int(u * 0.5 / (u * 0.02)))]
    di.line(pts, fill=(247, 224, 138, 220), width=max(3, int(u * 0.006)), joint="curve")
    for _ in range(3):  # ngôi sao phấn
        sx = rnd.uniform(board[0] + pad, board[2] - pad)
        sy = rnd.choice([board[3] - u * 0.07, board[1] + u * 0.16])
        r = u * rnd.uniform(0.022, 0.035)
        pts = star_points(sx, sy, r, r * 0.45)
        di.line(pts + pts[:1], fill=(246, 198, 208, 210), width=max(2, int(u * 0.004)))
    noise = Image.effect_noise((W, H), 90).convert("L").point(lambda p: min(255, max(0, int((p - 128) * 2 + 210))))
    ink.putalpha(ImageChops.multiply(ink.getchannel("A"), noise))
    img.alpha_composite(ink)
    box = (board[0] + pad, board[1] + int(u * 0.2), board[2] - pad, board[3] - int(u * 0.12))
    rough_text(img, text, box, find_font("hand"), chalk, k=1.6, align="center", max_size=int(u * 0.115),
               spacing=1.3)
    return img


def tpl_whiteboard(text, W, H, rnd):
    """Bảng trắng viền nhôm, chữ bút lông, nam châm và giấy nhớ."""
    text = _b3_t(text)
    u = min(W, H)
    img = gradient((W, H), ["#e9e2d6", "#d9d0c2"])
    d = ImageDraw.Draw(img)
    m = int(u * 0.05)
    board = (m, m, W - m, H - int(m * 2.2))
    shadow(img, board, 10, offset=(0, int(u * 0.012)), blur=int(u * 0.02), alpha=90)
    d.rounded_rectangle(board, int(u * 0.012), fill="#b9bec4")
    fr = int(u * 0.018)
    inner = (board[0] + fr, board[1] + fr, board[2] - fr, board[3] - fr)
    img.paste(gradient((inner[2] - inner[0], inner[3] - inner[1]), ["#ffffff", "#f1f3f5"], angle=35), inner[:2])
    d.rectangle(inner, outline="#8e959c", width=2)
    d.line((board[0] + 3, board[1] + 3, board[2] - 3, board[1] + 3), fill="#e8ebee", width=3)
    # vệt bóng + dấu tẩy cũ
    fx = Image.new("RGBA", (W, H), (255, 255, 255, 0))
    fd = ImageDraw.Draw(fx)
    gx = inner[0] + (inner[2] - inner[0]) * 0.55
    fd.polygon([(gx, inner[1]), (gx + u * 0.18, inner[1]), (gx - u * 0.25, inner[3]), (gx - u * 0.43, inner[3])],
               fill=(255, 255, 255, 120))
    for _ in range(4):
        x, y = rnd.uniform(inner[0], inner[2]), rnd.uniform(inner[1], inner[3])
        fd.line((x, y, x + u * rnd.uniform(0.1, 0.3), y + rnd.uniform(-1, 1) * u * 0.03),
                fill=(120, 140, 170, 22), width=int(u * 0.03))
    img.alpha_composite(fx.filter(ImageFilter.GaussianBlur(u * 0.01)))
    # khay bút
    tray = (board[0] + u * 0.06, board[3], board[2] - u * 0.06, board[3] + m * 0.7)
    d.rectangle(tray, fill="#a7adb3", outline="#7f868d", width=2)
    x = tray[0] + u * 0.08
    for col in rnd.sample(["#d62828", "#1f4fa8", "#2a9d5c", "#222222"], 3):
        L, th = u * 0.15, m * 0.5
        y1 = tray[1] - 2
        d.rounded_rectangle((x, y1 - th, x + L, y1), int(th / 2), fill="#f4f4f4", outline="#9aa0a6", width=2)
        d.rounded_rectangle((x + L * 0.72, y1 - th - 2, x + L + u * 0.012, y1 + 1), int(th / 2), fill=col)
        x += L + u * 0.05
    pen = rnd.choice(["#1f4fa8", "#222222", "#174b8f"])
    red = "#d62828"
    pad = int(u * 0.07)
    # tiêu đề đỏ gạch chân
    tf = load_font(find_font("marker"), int(u * 0.075))
    tx, ty = inner[0] + pad, inner[1] + int(u * 0.05)
    d.text((tx, ty), "GHI NHỚ !", font=tf, fill=red, anchor="lt")
    tw = tf.getlength("GHI NHỚ !")
    yb = ty + tf.size * 1.25
    d.line([(tx + i * tw / 12, yb + math.sin(i) * u * 0.004) for i in range(13)], fill=red,
           width=max(4, int(u * 0.007)), joint="curve")
    # giấy nhớ + nam châm góc phải
    sn = int(u * 0.2)
    note = Image.new("RGBA", (sn, sn), (0, 0, 0, 0))
    nd = ImageDraw.Draw(note)
    nd.rectangle((0, 0, sn - 1, sn - 1), fill=rnd.choice(["#fff27a", "#ffd1dc", "#c8f1ff"]))
    nd.polygon([(sn * 0.78, sn), (sn, sn * 0.78), (sn, sn)], fill=(0, 0, 0, 30))
    label(nd, (sn / 2, sn * 0.55), "nhớ nha", "hand", sn * 0.2, "#3a3a3a", anchor="mm")
    ncx, ncy = inner[2] - pad - sn * 0.45, inner[1] + pad * 0.3 + sn * 0.5
    shadow(img, (ncx - sn / 2, ncy - sn / 2, ncx + sn / 2, ncy + sn / 2), 2, offset=(4, 8), blur=10, alpha=60)
    paste_rotated(img, note, (ncx, ncy), rnd.uniform(-8, 8))
    r = u * 0.022
    for mx, mc in ((ncx, rnd.choice(["#e63946", "#2a9d8f", "#f4a261"])),):
        d.ellipse((mx - r, ncy - sn * 0.45 - r, mx + r, ncy - sn * 0.45 + r), fill=mc, outline=(0, 0, 0), width=1)
        d.ellipse((mx - r * 0.5, ncy - sn * 0.45 - r * 0.6, mx - r * 0.1, ncy - sn * 0.45 - r * 0.2), fill="#ffffff")
    top = max(yb + u * 0.05, ncy + sn * 0.55) if H >= W else yb + u * 0.05
    right = inner[2] - pad if H >= W else ncx - sn * 0.7
    box = (inner[0] + pad, int(top), int(right), inner[3] - pad)
    draw_text_block(img, text, box, find_font("marker"), pen, align="left", valign="center" if H >= W else "top",
                    max_size=int(u * 0.11), spacing=1.32)
    return img


def tpl_neon(text, W, H, rnd):
    """Biển neon phát sáng trên tường gạch tối."""
    text = _b3_t(text)
    u = min(W, H)
    img = Image.new("RGBA", (W, H), (22, 16, 20, 255))
    d = ImageDraw.Draw(img)
    bh = int(u * 0.055)
    bw, gap = int(bh * 2.3), max(3, int(u * 0.006))
    base = rnd.choice([(74, 38, 36), (58, 40, 48), (48, 42, 50)])
    for row, y in enumerate(range(0, H, bh)):
        off = -bw // 2 if row % 2 else 0
        for x in range(off, W, bw):
            k = rnd.uniform(0.7, 1.15)
            d.rectangle((x + gap, y + gap, x + bw - gap, y + bh - gap), fill=tuple(int(c * k) for c in base))
    add_grain(img, 22)
    tube, core_txt = rnd.choice([("#ff3ea5", "#36f1ff"), ("#36f1ff", "#ff4fd8"), ("#ffb21f", "#ff3e6c"),
                                 ("#b14dff", "#3dffb5")])
    # quầng sáng hắt lên tường
    spill = Image.new("RGBA", (W, H), rgba(tube, 0))
    ImageDraw.Draw(spill).ellipse((W * 0.1, H * 0.15, W * 0.9, H * 0.85), fill=rgba(tube, 70))
    img.alpha_composite(spill.filter(ImageFilter.GaussianBlur(u * 0.15)))
    vignette(img, 190)
    sign = _b3_center_box(W, H, 0.8, 0.62, 0.62, 0.72, dy=0.02)
    lw = max(4, int(u * 0.009))
    neon = Image.new("RGBA", (W, H), rgba(tube, 0))
    nd = ImageDraw.Draw(neon)
    nd.rounded_rectangle(sign, int(u * 0.06), outline=rgba(tube, 255), width=lw)
    i = int(u * 0.025)
    nd.rounded_rectangle((sign[0] + i, sign[1] + i, sign[2] - i, sign[3] - i), int(u * 0.045),
                         outline=rgba(tube, 200), width=max(2, lw // 2))
    # tim neon nhỏ trên khung
    hx, hy, hs = W / 2, sign[1] - u * 0.07, u * 0.09
    pts = heart_points(hx, hy, hs)
    nd.line(pts + pts[:1], fill=rgba(core_txt, 255), width=lw, joint="curve")
    glow(img, neon, radii=(0.04, 0.012))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle(sign, int(u * 0.06), outline=mix(tube, "#ffffff", 0.55), width=max(2, lw // 3))
    pts = heart_points(hx, hy, hs)
    d.line(pts + pts[:1], fill=mix(core_txt, "#ffffff", 0.6), width=max(2, lw // 3), joint="curve")
    # dây treo + ốc vít
    for sx in (sign[0] + u * 0.08, sign[2] - u * 0.08):
        d.line((sx, 0, sx, sign[1] - 2), fill=(15, 12, 14), width=max(2, int(u * 0.003)))
        d.ellipse((sx - u * 0.008, sign[1] - u * 0.008, sx + u * 0.008, sign[1] + u * 0.008), fill="#555")
    cap = (sign[0], sign[3] + u * 0.035, sign[2], sign[3] + u * 0.1)
    glow_text(img, "~ mở cửa cả đêm ~", cap, find_font("retro"), tube, align="center", max_size=int(u * 0.05))
    p = int(u * 0.09)
    box = (sign[0] + p, sign[1] + p, sign[2] - p, sign[3] - p)
    glow_text(img, text, box, find_font("retro"), core_txt, align="center", max_size=int(u * 0.1), spacing=1.25)
    return img


def tpl_movie_ticket(text, W, H, rnd):
    """Vé xem phim giấy kem có cuống xé, nền rèm nhung đỏ."""
    text = _b3_t(text)
    u = min(W, H)
    port = H >= W
    curtain = rnd.choice([("#5a0a14", "#a3172b"), ("#2b0f3d", "#5d2a7e"), ("#0f2c3d", "#1f5f7e")])
    n = 400
    strip = Image.new("RGB", (n, 1))
    folds = W / (u * 0.11)
    strip.putdata([mix(curtain[0], curtain[1], (math.sin(i / n * folds * math.pi * 2) + 1) / 2 * 0.85)
                   for i in range(n)])
    img = strip.resize((W, H)).convert("RGBA")
    spot = Image.new("RGBA", (W, H), (255, 240, 200, 0))
    ImageDraw.Draw(spot).ellipse((W * 0.15, -H * 0.2, W * 0.85, H * 0.75), fill=(255, 230, 180, 70))
    img.alpha_composite(spot.filter(ImageFilter.GaussianBlur(u * 0.12)))
    vignette(img, 170)
    accent = rnd.choice(["#c8102e", "#1f6f78", "#d9822b", "#3a3f8f"])
    paper, ink = "#fbf1dc", "#2b1d14"
    tk = _b3_center_box(W, H, 0.84, 0.8, 0.8, 0.84)
    x0, y0, x1, y1 = tk
    cut = (y0 + (y1 - y0) * 0.76) if port else (x0 + (x1 - x0) * 0.74)
    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    d.rounded_rectangle(tk, int(u * 0.02), fill=paper)
    r = int(u * 0.035)
    clear = (0, 0, 0, 0)
    ends = [(x0, cut), (x1, cut)] if port else [(cut, y0), (cut, y1)]
    for ex, ey in ends:
        d.ellipse((ex - r, ey - r, ex + r, ey + r), fill=clear)
    _b3_perforation(d, ends[0], ends[1], max(3, u * 0.006), mix(paper, ink, 0.35))
    main = (x0, y0, x1, cut) if port else (x0, y0, cut, y1)
    stub = (x0, cut, x1, y1) if port else (cut, y0, x1, y1)
    q = int(u * 0.03)
    mb = (main[0] + q, main[1] + q, main[2] - q, main[3] - q)
    d.rectangle(mb, outline=accent, width=max(3, int(u * 0.005)))
    d.rectangle((mb[0] + 8, mb[1] + 8, mb[2] - 8, mb[3] - 8), outline=accent, width=2)
    mw = mb[2] - mb[0]
    cx = (mb[0] + mb[2]) / 2
    hy = mb[1] + u * 0.06
    label(d, (cx, hy), "RẠP CHIẾU VŨ TRỤ", "bold", u * 0.032, accent, anchor="mm")
    title_f = load_font(find_font("black"), int(min(u * 0.1, mw * 0.11)))
    d.text((cx, hy + u * 0.035), "VÉ XEM PHIM", font=title_f, fill=ink, anchor="mt")
    ty = hy + u * 0.035 + title_f.size * 1.15
    sw = title_f.getlength("VÉ XEM PHIM") / 2 + u * 0.05
    for sx in (cx - sw, cx + sw):
        d.polygon(star_points(sx, hy + u * 0.035 + title_f.size * 0.55, u * 0.025, u * 0.011), fill=accent)
    d.line((mb[0] + u * 0.05, ty + u * 0.02, mb[2] - u * 0.05, ty + u * 0.02), fill=accent, width=2)
    # hàng thông tin
    fs = u * 0.05
    iy = mb[3] - u * 0.04 - fs * 1.4
    cols = [("PHÒNG", "07"), ("HÀNG", rnd.choice("DEFGH")), ("GHẾ", str(rnd.randint(1, 18))), ("SUẤT", "19:30")]
    for k, (c, v) in enumerate(cols):
        _b3_field(d, mb[0] + mw * (k + 0.5) / 4, iy, c, v, fs, mix(ink, paper, 0.45), ink, anchor="m")
    d.line((mb[0] + u * 0.05, iy - u * 0.025, mb[2] - u * 0.05, iy - u * 0.025), fill=accent, width=2)
    # cuống vé
    scx, scy = (stub[0] + stub[2]) / 2, (stub[1] + stub[3]) / 2
    sh, sw_ = stub[3] - stub[1], stub[2] - stub[0]
    if port:
        label(d, (stub[0] + u * 0.06, scy - sh * 0.18), "VÀO CỬA", "black", u * 0.05, accent, anchor="lm")
        label(d, (stub[0] + u * 0.06, scy + sh * 0.12), "1 NGƯỜI", "bold", u * 0.035, ink, anchor="lm")
        barcode(d, (stub[2] - u * 0.06 - sw_ * 0.42, scy - sh * 0.3, stub[2] - u * 0.06, scy + sh * 0.18), rnd, ink)
        label(d, (stub[2] - u * 0.06 - sw_ * 0.21, scy + sh * 0.3), f"No. {rnd.randint(100000, 999999)}", "mono",
              u * 0.028, ink, anchor="mm")
    else:
        label(d, (scx, stub[1] + sh * 0.14), "VÀO CỬA", "black", min(u * 0.055, sw_ * 0.17), accent, anchor="mm")
        label(d, (scx, stub[1] + sh * 0.24), "1 NGƯỜI", "bold", u * 0.035, ink, anchor="mm")
        barcode(d, (stub[0] + sw_ * 0.18, stub[1] + sh * 0.36, stub[2] - sw_ * 0.18, stub[1] + sh * 0.76), rnd, ink)
        label(d, (scx, stub[1] + sh * 0.84), f"No. {rnd.randint(100000, 999999)}", "mono", u * 0.028, ink,
              anchor="mm")
    box = (mb[0] + u * 0.06, ty + u * 0.05, mb[2] - u * 0.06, iy - u * 0.05)
    draw_text_block(layer, text, tuple(int(v) for v in box), find_font("serif"), ink, align="center",
                    max_size=int(u * 0.085), spacing=1.25)
    sl = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    sl.putalpha(layer.getchannel("A").point(lambda a: a * 120 // 255))
    img.alpha_composite(sl.filter(ImageFilter.GaussianBlur(u * 0.02)), (0, int(u * 0.015)))
    img.alpha_composite(layer)
    add_grain(img, 10)
    return img


def tpl_boarding_pass(text, W, H, rnd):
    """Thẻ lên máy bay "VŨ TRỤ AIRLINES" trên nền trời xanh mây trắng."""
    text = _b3_t(text)
    u = min(W, H)
    port = H >= W
    sky = rnd.choice([["#5aa8f0", "#bfe0ff", "#eaf5ff"], ["#f6a6b2", "#fcd5ce", "#fff1e6"],
                      ["#7b8cde", "#b8c0ff", "#e7e9ff"]])
    img = gradient((W, H), sky)
    cl = Image.new("RGBA", (W, H), (255, 255, 255, 0))
    cd = ImageDraw.Draw(cl)
    for _ in range(7):
        cloud(cd, rnd.uniform(0, W), rnd.uniform(0, H), u * rnd.uniform(0.25, 0.45), (255, 255, 255, 170))
    img.alpha_composite(cl.filter(ImageFilter.GaussianBlur(u * 0.006)))
    navy, ink, soft = rnd.choice([("#1d3b6e", "#14213d", "#8a94a6"), ("#7a1f3d", "#2b1320", "#a08a94"),
                                  ("#2d3a8c", "#141a40", "#8e93b5")])
    card = _b3_center_box(W, H, 0.86, 0.84, 0.86, 0.8)
    x0, y0, x1, y1 = card
    cut = (y0 + (y1 - y0) * 0.8) if port else (x0 + (x1 - x0) * 0.75)
    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    rad = int(u * 0.035)
    d.rounded_rectangle(card, rad, fill="#ffffff")
    main = (x0, y0, x1, cut) if port else (x0, y0, cut, y1)
    stub = (x0, cut, x1, y1) if port else (cut, y0, x1, y1)
    bh = int(u * 0.13)
    d.rounded_rectangle((x0, y0, x1, y0 + bh), rad, fill=navy)
    d.rectangle((x0, y0 + bh - rad, x1, y0 + bh), fill=navy)
    _b3_plane(d, x0 + u * 0.08, y0 + bh / 2, u * 0.08, "#ffffff", angle=-30)
    label(d, (x0 + u * 0.14, y0 + bh / 2), "VŨ TRỤ AIRLINES", "black", u * 0.045, "#ffffff", anchor="lm")
    room = x1 - x0 - u * 0.19 - load_font(find_font("black"), int(u * 0.045)).getlength("VŨ TRỤ AIRLINES")
    if room > load_font(find_font("bold"), int(u * 0.028)).getlength("THẺ LÊN MÁY BAY") + u * 0.04:
        label(d, (x1 - u * 0.05, y0 + bh / 2), "THẺ LÊN MÁY BAY", "bold", u * 0.028, (255, 255, 255, 200),
              anchor="rm")
    r = int(u * 0.03)
    ends = [(x0, cut), (x1, cut)] if port else [(cut, y0 + bh), (cut, y1)]
    for ex, ey in ends:
        d.ellipse((ex - r, ey - r, ex + r, ey + r), fill=(0, 0, 0, 0))
    dashed(d, ends[0], ends[1], u * 0.02, u * 0.015, "#c9ced8", max(2, int(u * 0.004)))
    p = u * 0.06
    mx0, mx1 = main[0] + p, main[2] - p
    # tuyến bay
    ry = y0 + bh + u * 0.05
    code_f = u * 0.11
    label(d, (mx0, ry), "TỪ", "bold", u * 0.025, soft, anchor="lt")
    label(d, (mx1, ry), "ĐẾN", "bold", u * 0.025, soft, anchor="rt")
    label(d, (mx0, ry + u * 0.03), "TĐT", "black", code_f, ink, anchor="lt")
    label(d, (mx1, ry + u * 0.03), "MMN", "black", code_f, ink, anchor="rt")
    cy = ry + u * 0.03 + code_f * 0.62
    dashed(d, (mx0 + code_f * 2.3, cy), (mx1 - code_f * 2.6, cy), u * 0.012, u * 0.012, soft, 3)
    _b3_plane(d, (mx0 + mx1) / 2, cy, u * 0.075, navy)
    label(d, (mx0, ry + u * 0.04 + code_f * 1.25), "Trái Đất", "bold", u * 0.03, soft, anchor="lt")
    label(d, (mx1, ry + u * 0.04 + code_f * 1.25), "Bến May Mắn", "bold", u * 0.03, soft, anchor="rt")
    # hàng thông tin
    t = datetime.date.today()
    fs = u * 0.045
    fy = main[3] - p - fs * 1.4
    cols = [("CHUYẾN", f"VT{rnd.randint(100, 999)}"), ("NGÀY", f"{t.day:02d}/{t.month:02d}"),
            ("CỔNG", f"{rnd.choice('ABC')}{rnd.randint(1, 12)}"), ("GHẾ", f"{rnd.randint(1, 30)}{rnd.choice('ABCDEF')}")]
    for k, (c, v) in enumerate(cols):
        _b3_field(d, mx0 + (mx1 - mx0) * k / 4, fy, c, v, fs, soft, ink)
    d.line((mx0, fy - u * 0.03, mx1, fy - u * 0.03), fill="#e3e6ec", width=2)
    top = ry + u * 0.12 + code_f * 1.3
    label(d, (mx0, top), "LỜI NHẮN", "bold", u * 0.025, navy, anchor="lt")
    box = (int(mx0), int(top + u * 0.04), int(mx1), int(fy - u * 0.05))
    draw_text_block(layer, text, box, find_font("bold"), ink, align="left", max_size=int(u * 0.08), spacing=1.25)
    # cuống vé
    sx0, sy0, sx1, sy1 = stub
    if port:
        sp = u * 0.06
        label(d, (sx0 + sp, sy0 + sp * 0.8), "LÊN MÁY BAY", "bold", u * 0.025, soft, anchor="lt")
        label(d, (sx0 + sp, sy0 + sp * 0.8 + u * 0.035), "19:30", "black", u * 0.07, navy, anchor="lt")
        barcode(d, (sx0 + (sx1 - sx0) * 0.45, sy0 + sp * 0.8, sx1 - sp, sy1 - sp * 0.8), rnd, ink)
    else:
        scx, sw_ = (sx0 + sx1) / 2, sx1 - sx0
        label(d, (scx, sy0 + bh + u * 0.06), "LÊN MÁY BAY", "bold", u * 0.025, soft, anchor="mt")
        label(d, (scx, sy0 + bh + u * 0.1), "19:30", "black", u * 0.08, navy, anchor="mt")
        label(d, (scx, sy0 + bh + u * 0.22), "GHẾ " + cols[3][1], "bold", u * 0.035, ink, anchor="mt")
        barcode(d, (sx0 + sw_ * 0.15, sy1 - u * 0.3, sx1 - sw_ * 0.15, sy1 - u * 0.07), rnd, ink)
    shadow(img, card, rad, offset=(0, int(u * 0.02)), blur=int(u * 0.03), alpha=80)
    img.alpha_composite(layer)
    return img


def tpl_postcard(text, W, H, rnd):
    """Bưu thiếp giấy kem có tem răng cưa, dấu bưu điện và dòng địa chỉ."""
    text = _b3_t(text)
    u = min(W, H)
    port = H >= W
    img = noise_texture((W, H), rnd.choice([(176, 196, 177), (214, 196, 170), (184, 196, 214)]), amount=14,
                        seed=rnd.random())
    vignette(img, 90)
    ink, sepia = rnd.choice([("#24365e", "#7a5a3a"), ("#3b2a1f", "#8a4b2a"), ("#1f3d2f", "#7a5a3a")])
    pc = _b3_center_box(W, H, 0.86, 0.8, 0.82, 0.8)
    pw, ph = pc[2] - pc[0], pc[3] - pc[1]
    card = Image.new("RGBA", (pw, ph), (0, 0, 0, 0))
    d = ImageDraw.Draw(card)
    d.rectangle((0, 0, pw - 1, ph - 1), fill="#fbf6ea")
    q = int(u * 0.022)
    d.rectangle((q, q, pw - q, ph - q), outline=mix(sepia, "#fbf6ea", 0.5), width=2)
    p = int(u * 0.06)
    # tem
    sw, sh = int(u * 0.17), int(u * 0.21)
    stamp = Image.new("RGBA", (sw, sh), (0, 0, 0, 0))
    sd = ImageDraw.Draw(stamp)
    sd.rectangle((0, 0, sw - 1, sh - 1), fill="#ffffff")
    rr = max(3, sw // 28)
    for x in range(0, sw + 1, rr * 3):
        sd.ellipse((x - rr, -rr, x + rr, rr), fill=(0, 0, 0, 0))
        sd.ellipse((x - rr, sh - rr, x + rr, sh + rr), fill=(0, 0, 0, 0))
    for y in range(0, sh + 1, rr * 3):
        sd.ellipse((-rr, y - rr, rr, y + rr), fill=(0, 0, 0, 0))
        sd.ellipse((sw - rr, y - rr, sw + rr, y + rr), fill=(0, 0, 0, 0))
    ib = (rr * 2, rr * 2, sw - rr * 2, sh - rr * 2)
    pic = gradient((ib[2] - ib[0], ib[3] - ib[1]), rnd.choice([["#ffb4a2", "#ffe5d9"], ["#90e0ef", "#e0fbfc"],
                                                               ["#cdb4db", "#ffc8dd"]]))
    pd = ImageDraw.Draw(pic)
    w_, h_ = pic.size
    pd.ellipse((w_ * 0.55, h_ * 0.18, w_ * 0.85, h_ * 0.18 + w_ * 0.3), fill="#fff3b0")
    pd.polygon([(0, h_), (0, h_ * 0.62), (w_ * 0.35, h_ * 0.4), (w_ * 0.65, h_ * 0.65), (w_ * 0.8, h_ * 0.55),
                (w_, h_ * 0.7), (w_, h_)], fill=mix(ink, "#ffffff", 0.35))
    label(pd, (w_ * 0.08, h_ * 0.06), "5000đ", "bold", w_ * 0.17, ink)
    stamp.paste(pic, ib[:2])
    sx, sy = pw - p - sw, p
    card.alpha_composite(stamp, (sx, sy))
    d.rectangle((sx - 1, sy - 1, sx + sw, sy + sh), outline=(0, 0, 0, 25), width=1)
    # dấu bưu điện
    pm = Image.new("RGBA", (pw, ph), (0, 0, 0, 0))
    md = ImageDraw.Draw(pm)
    pr = u * 0.085
    pcx, pcy = sx + sw * 0.05, sy + sh * 0.8
    col = rgba(ink, 150)
    md.ellipse((pcx - pr, pcy - pr, pcx + pr, pcy + pr), outline=col, width=max(3, int(u * 0.005)))
    md.ellipse((pcx - pr * 0.78, pcy - pr * 0.78, pcx + pr * 0.78, pcy + pr * 0.78), outline=col, width=2)
    t = datetime.date.today()
    label(md, (pcx, pcy - pr * 0.3), "VŨ TRỤ", "bold", pr * 0.28, col, anchor="mm")
    label(md, (pcx, pcy + pr * 0.15), f"{t.day:02d}.{t.month:02d}.{t.year}", "mono", pr * 0.22, col, anchor="mm")
    for k in range(4):
        yy = pcy - pr * 0.45 + k * pr * 0.3
        md.line([(pcx - pr * 1.2 - i * u * 0.02, yy + math.sin(i * 1.3) * u * 0.006) for i in range(14)],
                fill=col, width=max(2, int(u * 0.004)), joint="curve")
    card.alpha_composite(pm.rotate(rnd.uniform(-15, 15), center=(pcx, pcy)))
    hand = find_font("hand")
    tl = load_font(find_font("serif"), int(u * 0.06))
    d.text((p, p), "Bưu Thiếp", font=tl, fill=sepia, anchor="lt")
    label(d, (p, p + tl.size * 1.3), "gửi từ một nơi rất xa", "script", u * 0.035, mix(sepia, "#fbf6ea", 0.2))
    lh = u * 0.075
    if port:
        ax0, ax1, ay = p, sx - u * 0.12, sy + sh + u * 0.05
        dv = ay + lh * 2 + u * 0.06
        for k, s in enumerate(("Gửi: Người có duyên", "Từ: Vũ Trụ")):
            yy = ay + lh * (k + 1)
            d.line((ax0, yy, pw - p, yy), fill=mix(sepia, "#fbf6ea", 0.55), width=2)
            label(d, (ax0 + u * 0.01, yy - u * 0.012), s, "hand", u * 0.04, ink, anchor="ls")
        d.line((p, dv, pw - p, dv), fill=mix(sepia, "#fbf6ea", 0.4), width=2)
        box = (p, int(dv + u * 0.05), pw - p, ph - p)
    else:
        dvx = int(pw * 0.6)
        d.line((dvx, p * 2.2, dvx, ph - p), fill=mix(sepia, "#fbf6ea", 0.4), width=2)
        ay = sy + sh + u * 0.1
        for k, s in enumerate(("Gửi: Người có duyên", "Từ: Vũ Trụ", "", "")):
            yy = ay + lh * (k + 1)
            d.line((dvx + p * 0.6, yy, pw - p, yy), fill=mix(sepia, "#fbf6ea", 0.55), width=2)
            if s:
                label(d, (dvx + p * 0.7, yy - u * 0.012), s, "hand", u * 0.04, ink, anchor="ls")
        box = (p, int(p + tl.size * 1.3 + u * 0.09), dvx - p // 2, ph - p)
    ruled_text(card, text, box, hand, ink, mix(sepia, "#fbf6ea", 0.7), int(u * 0.08), spacing=1.45)
    ang = rnd.uniform(-2, 2)
    shadow(img, pc, 4, offset=(int(u * 0.01), int(u * 0.02)), blur=int(u * 0.025), alpha=90)
    paste_rotated(img, card, ((pc[0] + pc[2]) / 2, (pc[1] + pc[3]) / 2), ang)
    add_grain(img, 10)
    return img


def tpl_gingham(text, W, H, rnd):
    """Nền vải caro picnic, tờ giấy dán băng keo và chùm anh đào."""
    text = _b3_t(text)
    u = min(W, H)
    col, dark = rnd.choice([("#e5383b", "#9d0208"), ("#4d7fd6", "#1d3f8a"), ("#5aa469", "#1f5f30"),
                            ("#f28ab2", "#a83265"), ("#f2b134", "#9a5b00")])
    img = Image.new("RGBA", (W, H), "#fffaf3")
    s = int(u * 0.075)
    for horiz in (True, False):
        band = Image.new("RGBA", (W, H), rgba(col, 0))
        bd = ImageDraw.Draw(band)
        for v in range(0, W + H, s * 2):
            bd.rectangle((0, v, W, v + s) if horiz else (v, 0, v + s, H), fill=rgba(col, 120))
        img.alpha_composite(band)
    weave = Image.new("RGBA", (W, H), (255, 255, 255, 0))
    wd = ImageDraw.Draw(weave)
    for v in range(0, W + H, max(4, s // 6)):
        wd.line((v, 0, v - H, H), fill=(255, 255, 255, 22), width=1)
    img.alpha_composite(weave)
    add_grain(img, 12)
    card = _b3_center_box(W, H, 0.78, 0.66, 0.6, 0.74)
    cw, ch = card[2] - card[0], card[3] - card[1]
    paper = Image.new("RGBA", (cw, ch), (0, 0, 0, 0))
    d = ImageDraw.Draw(paper)
    d.rounded_rectangle((0, 0, cw - 1, ch - 1), int(u * 0.02), fill="#fffdf8")
    q = int(u * 0.03)
    dashed_rect(d, (q, q, cw - q, ch - q), u * 0.02, u * 0.012, mix(col, "#ffffff", 0.3), max(2, int(u * 0.004)))
    hs = u * 0.07
    d.polygon(heart_points(cw / 2, q + u * 0.075, hs), fill=col)
    label(d, (cw / 2, q + u * 0.15), "ghi chú dã ngoại", "hand2", u * 0.04, dark, anchor="mt")
    p = int(u * 0.08)
    box = (p, int(q + u * 0.23), cw - p, ch - p)
    draw_text_block(paper, text, box, find_font("round"), dark, align="center", max_size=int(u * 0.085),
                    spacing=1.2)
    cx, cy = (card[0] + card[2]) / 2, (card[1] + card[3]) / 2
    ang = rnd.uniform(-3, 3)
    shadow(img, card, int(u * 0.02), offset=(int(u * 0.01), int(u * 0.02)), blur=int(u * 0.025), alpha=80)
    paste_rotated(img, paper, (cx, cy), ang)
    # băng keo 2 góc
    tw, th = int(u * 0.22), int(u * 0.06)
    for (tx, ty), a in (((card[0] + u * 0.03, card[1] + u * 0.01), 35), ((card[2] - u * 0.03, card[1] + u * 0.01), -35)):
        tape = Image.new("RGBA", (tw, th), (255, 250, 220, 165))
        ImageDraw.Draw(tape).rectangle((0, 0, tw - 1, th - 1), outline=(255, 255, 255, 120), width=2)
        paste_rotated(img, tape, (tx, ty), a)
    # anh đào góc dưới
    ch_ = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    cd = ImageDraw.Draw(ch_)
    bx, by, r = card[2] - u * 0.04, card[3] - u * 0.01, u * 0.045
    top = (bx + r * 0.6, by - r * 3.2)
    for ox in (-r * 1.1, r * 1.0):
        cd.line((bx + ox, by - r * 0.6, top[0], top[1]), fill="#3d5a1e", width=max(3, int(u * 0.006)))
    cd.ellipse((top[0] - r * 0.1, top[1] - r * 0.5, top[0] + r * 1.4, top[1] + r * 0.2), fill="#5a9a2e")
    for ox in (-r * 1.1, r * 1.0):
        cd.ellipse((bx + ox - r, by - r, bx + ox + r, by + r), fill="#d00000")
        cd.ellipse((bx + ox - r * 0.55, by - r * 0.6, bx + ox - r * 0.2, by - r * 0.25), fill=(255, 255, 255, 200))
    shadow_ = ch_.copy()
    shadow_.putalpha(ch_.getchannel("A").point(lambda a: a // 3))
    img.alpha_composite(Image.merge("RGBA", (*Image.new("RGB", (W, H), 0).split(), shadow_.getchannel("A")))
                        .filter(ImageFilter.GaussianBlur(u * 0.01)), (int(u * 0.008), int(u * 0.012)))
    img.alpha_composite(ch_)
    return img


def tpl_polka_dot(text, W, H, rnd):
    """Nền chấm bi pastel, thẻ viền đậm bóng đặc kiểu sticker."""
    text = _b3_t(text)
    u = min(W, H)
    bg, dot, ink = rnd.choice([("#ffc8dd", "#ffffff", "#5c1a3a"), ("#bde0fe", "#ffffff", "#123a63"),
                               ("#ffe066", "#ffffff", "#5a3b00"), ("#cdeac0", "#ffffff", "#1e4a2a"),
                               ("#e0c3fc", "#ffffff", "#3f1d6b")])
    img = Image.new("RGBA", (W, H), bg)
    d = ImageDraw.Draw(img)
    g = int(u * 0.1)
    dots(d, (0, 0, W, H), g, int(g * 0.22), mix(bg, dot, 0.75))
    card = _b3_center_box(W, H, 0.8, 0.62, 0.6, 0.7, dy=0.02)
    off, bw = int(u * 0.025), max(4, int(u * 0.008))
    _b3_hard_shadow(d, card, off, int(u * 0.05), ink, outline=ink, width=bw, fill="#fffdf7")
    # nhãn tab trên đầu
    tf = load_font(find_font("round"), int(u * 0.045))
    tt = "lời nhắn nhỏ"
    tw = tf.getlength(tt) + u * 0.08
    cx = (card[0] + card[2]) / 2
    tab = (cx - tw / 2, card[1] - u * 0.04, cx + tw / 2, card[1] + u * 0.04)
    d.rounded_rectangle(tab, int(u * 0.04), fill=mix(bg, ink, 0.15), outline=ink, width=bw)
    d.text((cx, (tab[1] + tab[3]) / 2), tt, font=tf, fill=ink, anchor="mm")
    # 3 chấm màu dưới đáy
    for k in range(3):
        x, y, r = cx + (k - 1) * u * 0.06, card[3] - u * 0.06, u * 0.016
        d.ellipse((x - r, y - r, x + r, y + r), fill=[bg, ink, mix(bg, ink, 0.5)][k], outline=ink, width=2)
    # tim + sparkle trang trí ngoài thẻ
    d.polygon(heart_points(card[0] + u * 0.02, card[3] + u * 0.01, u * 0.1), fill="#ff5d8f", outline=ink)
    sparkle(d, card[2] - u * 0.01, card[1] + u * 0.01, u * 0.05, ink)
    sparkle(d, card[2] - u * 0.01, card[1] + u * 0.01, u * 0.03, "#ffffff")
    p = int(u * 0.08)
    box = (card[0] + p, card[1] + int(u * 0.09), card[2] - p, card[3] - int(u * 0.11))
    draw_text_block(img, text, box, find_font("round"), ink, align="center", max_size=int(u * 0.09),
                    spacing=1.15)
    return img


def tpl_candy_stripes(text, W, H, rnd):
    """Nền sọc kẹo chéo, nhãn răng cưa và viên kẹo gói giấy."""
    text = _b3_t(text)
    u = min(W, H)
    a, b, ink = rnd.choice([("#ff8fab", "#ffffff", "#b0174f"), ("#7bdff2", "#ffffff", "#0b5e79"),
                            ("#ff6b6b", "#fff4e0", "#a4161a"), ("#b8f2a1", "#ffffff", "#2d6a1f"),
                            ("#c3a6ff", "#fffaf0", "#4b2a91")])
    img = Image.new("RGBA", (W, H), b)
    d = ImageDraw.Draw(img)
    gap = int(u * 0.12)
    diag_stripes(d, W, H, gap, int(gap * 0.5), a)
    sh = Image.new("RGBA", (W, H), (255, 255, 255, 0))
    ImageDraw.Draw(sh).ellipse((W * 0.05, H * 0.05, W * 0.6, H * 0.45), fill=(255, 255, 255, 60))
    img.alpha_composite(sh.filter(ImageFilter.GaussianBlur(u * 0.12)))
    card = _b3_center_box(W, H, 0.74, 0.58, 0.58, 0.66, dy=0.04)
    r = int(u * 0.03)
    lay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    _b3_scallop_rect(ImageDraw.Draw(lay), card, r, (255, 255, 255, 255))
    sl = Image.new("RGBA", (W, H), rgba(ink, 0))
    sl.putalpha(lay.getchannel("A").point(lambda v: v * 90 // 255))
    img.alpha_composite(sl.filter(ImageFilter.GaussianBlur(u * 0.015)), (0, int(u * 0.018)))
    img.alpha_composite(lay)
    d = ImageDraw.Draw(img)
    q = int(u * 0.035)
    dashed_rect(d, (card[0] + q, card[1] + q, card[2] - q, card[3] - q), u * 0.025, u * 0.015, a,
                max(3, int(u * 0.006)))
    # viên kẹo gói giấy phía trên
    cx, cy, cr = (card[0] + card[2]) / 2, card[1] - u * 0.02, u * 0.075
    for sgn in (-1, 1):
        d.polygon([(cx + sgn * cr * 0.8, cy), (cx + sgn * cr * 2.1, cy - cr * 0.75), (cx + sgn * cr * 1.9, cy),
                   (cx + sgn * cr * 2.1, cy + cr * 0.75)], fill=a, outline=ink)
    d.ellipse((cx - cr, cy - cr, cx + cr, cy + cr), fill=a, outline=ink, width=max(2, int(u * 0.004)))
    sw = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    swd = ImageDraw.Draw(sw)
    for k in range(3):
        swd.arc((cx - cr * (0.85 - k * 0.25), cy - cr * (0.85 - k * 0.25), cx + cr * (0.85 - k * 0.25),
                 cy + cr * (0.85 - k * 0.25)), 200 + k * 40, 360 + k * 40, fill="#ffffff", width=max(3, int(u * 0.008)))
    img.alpha_composite(sw)
    label(d, ((card[0] + card[2]) / 2, card[1] + u * 0.12), "ngọt ngào mỗi ngày", "hand2", u * 0.042, ink,
          anchor="mm")
    p = int(u * 0.085)
    box = (card[0] + p, card[1] + int(u * 0.17), card[2] - p, card[3] - p)
    draw_text_block(img, text, box, find_font("round"), ink, align="center", max_size=int(u * 0.1), spacing=1.15)
    return img


def tpl_checker(text, W, H, rnd):
    """Bàn cờ retro + cửa sổ kiểu máy tính cổ, sao lấp lánh."""
    text = _b3_t(text)
    u = min(W, H)
    c1, c2, bar, ink = rnd.choice([("#fdf0d5", "#1b1b1b", "#ff5d8f", "#1b1b1b"),
                                   ("#ffd6e8", "#ff7aa8", "#7b2cbf", "#2b0a3d"),
                                   ("#e9f5db", "#90a955", "#ff9f1c", "#1f2a10"),
                                   ("#dbeafe", "#3b82f6", "#facc15", "#0b1f4d")])
    img = Image.new("RGBA", (W, H), c1)
    d = ImageDraw.Draw(img)
    s = int(u * 0.09)
    checker(d, W, H, s, c2)
    add_grain(img, 12)
    vignette(img, 70)
    win = _b3_center_box(W, H, 0.84, 0.6, 0.64, 0.7, dy=0.01)
    off, bw = int(u * 0.022), max(4, int(u * 0.007))
    d.rectangle((win[0] + off, win[1] + off, win[2] + off, win[3] + off), fill=ink)
    d.rectangle(win, fill="#ffffff", outline=ink, width=bw)
    tb = int(u * 0.075)
    d.rectangle((win[0], win[1], win[2], win[1] + tb), fill=bar, outline=ink, width=bw)
    label(d, (win[0] + u * 0.03, win[1] + tb / 2), "loi_nhan.txt", "mono", u * 0.032, ink, anchor="lm")
    r = u * 0.014
    for k in range(3):
        x = win[2] - u * 0.04 - k * u * 0.045
        d.ellipse((x - r, win[1] + tb / 2 - r, x + r, win[1] + tb / 2 + r), fill="#ffffff", outline=ink, width=3)
    # thanh cuộn bên phải
    sbw = int(u * 0.035)
    d.rectangle((win[2] - sbw, win[1] + tb, win[2], win[3]), fill=mix(c1, "#ffffff", 0.5), outline=ink, width=3)
    d.rectangle((win[2] - sbw + 6, win[1] + tb + u * 0.04, win[2] - 6, win[1] + tb + u * 0.16), fill=bar,
                outline=ink, width=2)
    for (x, y, rr) in ((win[0], win[1] - u * 0.02, 0.07), (win[2] + u * 0.01, win[3] - u * 0.03, 0.06),
                       (win[0] + u * 0.08, win[3] + u * 0.05, 0.035)):
        sparkle(d, x, y, u * rr, ink)
        sparkle(d, x, y, u * rr * 0.62, bar)
    p = int(u * 0.07)
    box = (win[0] + p, win[1] + tb + p, win[2] - sbw - p, win[3] - p)
    draw_text_block(img, text, box, find_font("black"), ink, align="left", max_size=int(u * 0.085), spacing=1.26,
                    upper=True)
    return img


def tpl_film_strip(text, W, H, rnd):
    """Cuộn phim âm bản trên bàn đèn, khung giữa chứa lời nhắn."""
    text = _b3_t(text)
    u = min(W, H)
    port = H >= W
    img = gradient((W, H), ["#fbf7ef", "#efe6d6"])
    lg = Image.new("RGBA", (W, H), (255, 255, 255, 0))
    ImageDraw.Draw(lg).ellipse((W * 0.1, H * 0.1, W * 0.9, H * 0.9), fill=(255, 255, 255, 160))
    img.alpha_composite(lg.filter(ImageFilter.GaussianBlur(u * 0.15)))
    L, S = (H + int(u * 0.2), int(W * 0.84)) if port else (W + int(u * 0.2), int(H * 0.8))
    film = rnd.choice([(34, 26, 20), (24, 22, 22), (44, 30, 18)])
    st = Image.new("RGBA", (L, S), film + (255,))
    d = ImageDraw.Draw(st)
    edge = int(S * 0.13)
    hw, hh = int(edge * 0.42), int(edge * 0.55)
    pitch = int(hw * 2.2)
    for x in range(pitch // 2, L, pitch):
        for y in (edge * 0.5, S - edge * 0.5):
            d.rounded_rectangle((x - hw / 2, y - hh / 2, x + hw / 2, y + hh / 2), max(2, hw // 5),
                                fill=(0, 0, 0, 0))
    gapf = int(S * 0.05)
    fh = S - 2 * edge
    big = int(min(fh * 1.25, L - 2 * gapf) if not port else min(fh * 1.3, L * 0.62))
    a0 = (L - big) // 2
    frames = [(a0, a0 + big)]
    small = int(fh * 1.3)
    x = a0 - gapf
    while x > 0:
        frames.append((x - small, x)); x -= small + gapf
    x = a0 + big + gapf
    while x < L:
        frames.append((x, x + small)); x += small + gapf
    pal = rnd.choice([["#f4a261", "#e76f51", "#264653"], ["#ffafcc", "#cdb4db", "#a2d2ff"],
                      ["#e9c46a", "#2a9d8f", "#f4a261"]])
    for k, (f0, f1) in enumerate(frames):
        fb = (f0, edge, f1, S - edge)
        fw_, fh_ = f1 - f0, S - 2 * edge
        if k == 0:
            ph = gradient((fw_, fh_), ["#fff8ec", "#fde7cf"], angle=30)
        else:
            ph = gradient((fw_, fh_), rnd.sample(pal, 2), angle=rnd.choice([0, 45, 90]))
            pd = ImageDraw.Draw(ph)
            rr = fh_ * rnd.uniform(0.12, 0.22)
            sx, sy = fw_ * rnd.uniform(0.25, 0.75), fh_ * rnd.uniform(0.25, 0.55)
            pd.ellipse((sx - rr, sy - rr, sx + rr, sy + rr), fill="#fff3c4")
            pd.polygon([(0, fh_), (0, fh_ * 0.7), (fw_ * 0.4, fh_ * 0.5), (fw_, fh_ * 0.75), (fw_, fh_)],
                       fill=mix(pal[2], "#000000", 0.25))
            ph = ph.filter(ImageFilter.GaussianBlur(u * 0.004))
        m = Image.new("L", ph.size, 0)
        ImageDraw.Draw(m).rounded_rectangle((0, 0, fw_ - 1, fh_ - 1), int(u * 0.01), fill=255)
        st.paste(ph, fb[:2], m)
    # chữ in mép phim (màu cam)
    orange = (255, 150, 40, 230)
    ef = load_font(find_font("mono"), max(10, int(edge * 0.2)))
    base_n = rnd.randint(8, 24)
    for k, (f0, f1) in enumerate(sorted(frames)):
        n = base_n + k
        d.text(((f0 + f1) / 2, edge * 0.06), f"{n}", font=ef, fill=orange, anchor="mt")
        d.text(((f0 + f1) / 2 + edge * 0.6, edge * 0.06), f"{n}A", font=ef, fill=orange, anchor="lt")
        d.polygon([((f0 + f1) / 2 - edge * 0.5, S - edge * 0.06), ((f0 + f1) / 2 - edge * 0.3, S - edge * 0.2),
                   ((f0 + f1) / 2 - edge * 0.1, S - edge * 0.06)], fill=orange)
        d.text(((f0 + f1) / 2 + edge * 0.05, S - edge * 0.04), "VŨ TRỤ 400", font=ef, fill=orange, anchor="lb")
    if port:
        st = st.transpose(Image.ROTATE_270)
    ox, oy = (W - st.width) // 2, (H - st.height) // 2
    sl = Image.new("RGBA", st.size, (0, 0, 0, 0))
    sl.putalpha(st.getchannel("A").point(lambda v: v * 90 // 255))
    img.alpha_composite(sl.filter(ImageFilter.GaussianBlur(u * 0.012)), (ox + int(u * 0.008), oy + int(u * 0.016)))
    img.alpha_composite(st, (ox, oy))
    f0, f1 = frames[0]
    if port:  # ROTATE_270: (x, y) -> (S - y, x)
        fb = (ox + edge, oy + f0, ox + S - edge, oy + f1)
    else:
        fb = (ox + f0, oy + edge, ox + f1, oy + S - edge)
    p = int(u * 0.06)
    box = (fb[0] + p, fb[1] + p, fb[2] - p, fb[3] - p)
    draw_text_block(img, text, box, find_font("book"), "#3a2414", align="center", max_size=int(u * 0.08),
                    spacing=1.25)
    add_grain(img, 10)
    return img


def tpl_warning_tape(text, W, H, rnd):
    """Biển cảnh báo vàng đen trên tường bê tông, băng cảnh báo chéo."""
    text = _b3_t(text)
    u = min(W, H)
    port = H >= W
    img = noise_texture((W, H), (150, 150, 145), amount=20, seed=rnd.random())
    soft_blobs(img, rnd, [(120, 120, 116), (170, 170, 164), (135, 132, 125)], n=8, alpha=120)
    add_grain(img, 18)
    vignette(img, 150)
    yel, blk = "#ffd60a", "#141414"
    sign = _b3_center_box(W, H, 0.8, 0.64, 0.64, 0.7, dy=0.01)
    d = ImageDraw.Draw(img)
    shadow(img, sign, int(u * 0.03), offset=(0, int(u * 0.02)), blur=int(u * 0.025), alpha=110)
    d.rounded_rectangle(sign, int(u * 0.03), fill=yel, outline=blk, width=max(6, int(u * 0.014)))
    q = int(u * 0.03)
    d.rounded_rectangle((sign[0] + q, sign[1] + q, sign[2] - q, sign[3] - q), int(u * 0.02), outline=blk,
                        width=max(3, int(u * 0.005)))
    for sx in (sign[0] + q * 0.55, sign[2] - q * 0.55):  # đinh tán
        for sy in (sign[1] + q * 0.55, sign[3] - q * 0.55):
            d.ellipse((sx - u * 0.007, sy - u * 0.007, sx + u * 0.007, sy + u * 0.007), fill="#6b6b6b")
    cx = (sign[0] + sign[2]) / 2
    tr = u * (0.085 if port else 0.065)
    ty = sign[1] + q + u * 0.04 + tr
    d.polygon([(cx, ty - tr), (cx + tr * 1.1, ty + tr * 0.8), (cx - tr * 1.1, ty + tr * 0.8)], fill=blk)
    d.polygon([(cx, ty - tr * 0.6), (cx + tr * 0.75, ty + tr * 0.58), (cx - tr * 0.75, ty + tr * 0.58)], fill=yel)
    d.rounded_rectangle((cx - tr * 0.08, ty - tr * 0.28, cx + tr * 0.08, ty + tr * 0.22), int(tr * 0.05), fill=blk)
    d.ellipse((cx - tr * 0.09, ty + tr * 0.3, cx + tr * 0.09, ty + tr * 0.48), fill=blk)
    tf = load_font(find_font("black"), int(u * 0.07))
    d.text((cx, ty + tr * 0.95), "CẢNH BÁO", font=tf, fill=blk, anchor="mt")
    hy = ty + tr * 0.95 + tf.size * 1.25
    d.line((sign[0] + q * 2.5, hy, sign[2] - q * 2.5, hy), fill=blk, width=max(3, int(u * 0.006)))
    p = int(u * 0.08)
    box = (sign[0] + p, int(hy + u * 0.04), sign[2] - p, sign[3] - p)
    draw_text_block(img, text, box, find_font("black"), blk, align="center", max_size=int(u * 0.085),
                    spacing=1.18)
    # băng cảnh báo
    Lt, th = int(math.hypot(W, H) * 1.2), int(u * 0.085)
    tape1 = Image.new("RGBA", (Lt, th), yel)
    t1 = ImageDraw.Draw(tape1)
    for x in range(-th, Lt, int(th * 1.4)):
        t1.polygon([(x, th), (x + th * 0.7, th), (x + th * 1.4, 0), (x + th * 0.7, 0)], fill=blk)
    tape2 = Image.new("RGBA", (Lt, th), yel)
    t2 = ImageDraw.Draw(tape2)
    t2.rectangle((0, 0, Lt, th * 0.12), fill=blk)
    t2.rectangle((0, th * 0.88, Lt, th), fill=blk)
    ff = load_font(find_font("black"), int(th * 0.5))
    seg = "CẢNH BÁO   •   VŨ TRỤ ĐANG GỬI TÍN HIỆU   •   "
    sw = ff.getlength(seg)
    x = 0
    while x < Lt:
        t2.text((x, th / 2), seg, font=ff, fill=blk, anchor="lm"); x += sw
    for tp in (tape1, tape2):
        tp.putalpha(Image.new("L", tp.size, 240))
    a1, a2 = (11, -9) if port else (4, -3.5)
    sy1, sy2 = (sign[1] - u * 0.03, sign[3] + u * 0.035) if port else (sign[1] - u * 0.06, sign[3] + u * 0.06)
    for tp, c, a in ((tape1, (W / 2, sy1), a1), (tape2, (W / 2, sy2), a2)):
        sh = Image.new("RGBA", tp.size, (0, 0, 0, 90))
        paste_rotated(img, sh.filter(ImageFilter.GaussianBlur(4)), (c[0] + 4, c[1] + int(u * 0.01)), a)
        paste_rotated(img, tp, c, a)
    return img


# --- batch 4 ---

def _b4_today():
    t = datetime.date.today()
    return t, VN_WEEKDAYS[t.weekday()]


def _b4_shadow_text(img, text, box, fp, color, shade, off, blur=0, **kw):
    """Chữ có bóng (đổ cứng nếu blur=0, mờ nếu blur>0)."""
    layer = Image.new("RGBA", img.size, rgba(shade, 0))
    sb = (box[0] + off[0], box[1] + off[1], box[2] + off[0], box[3] + off[1])
    draw_text_block(layer, text, sb, fp, shade, **kw)
    if blur:
        layer = layer.filter(ImageFilter.GaussianBlur(blur))
    img.alpha_composite(layer)
    return draw_text_block(img, text, box, fp, color, **kw)


def _b4_text_mask(size, text, box, fp, **kw):
    """Mask (L) của khối chữ, để tô gradient/chrome lên chữ."""
    layer = Image.new("RGBA", size, (255, 255, 255, 0))
    font = draw_text_block(layer, text, box, fp, (255, 255, 255, 255), **kw)
    return layer.getchannel("A"), font


def _b4_persp_grid(d, W, H, hy, color, width, nv=14, nh=10, cx=None):
    """Lưới phối cảnh từ đường chân trời hy xuống đáy ảnh."""
    cx = W / 2 if cx is None else cx
    span = W * 2.2
    for i in range(nv + 1):
        x = cx - span / 2 + span * i / nv
        d.line((cx + (x - cx) * 0.04, hy, x, H), fill=color, width=width)
    for i in range(1, nh + 1):
        y = hy + (H - hy) * (i / nh) ** 2
        d.line((0, y, W, y), fill=color, width=width)


def _b4_wave_band(d, W, y, amp, length, phase, fill, bottom):
    """Dải sóng: viền trên hình sin tại y, tô xuống tới bottom."""
    pts = [(x, y + amp * math.sin(2 * math.pi * x / length + phase)) for x in range(-10, W + 20, 8)]
    d.polygon(pts + [(W + 20, bottom), (-10, bottom)], fill=fill)


def tpl_mesh_gradient(text, W, H, rnd):
    """Gradient lưới pastel loang mờ + grain, chữ đậm căn giữa."""
    pal = rnd.choice([
        ["#ffd6e8", "#c9e4ff", "#e5d4ff", "#fff3c4", "#c8f5e4"],
        ["#ffe0d1", "#ffc2d9", "#d6e6ff", "#fbe7ff", "#ffeab0"],
        ["#d3f4ff", "#e0d9ff", "#ffdcf1", "#d9ffe8", "#fff0d6"],
    ])
    u = min(W, H)
    img = gradient((W, H), pal[:2], angle=rnd.choice([30, 120, 210]))
    soft_blobs(img, rnd, pal, n=9, blur=0.14, rmin=0.25, rmax=0.55)
    add_grain(img, 18)
    d = ImageDraw.Draw(img)
    fg = "#2a2140"
    t, wd = _b4_today()
    label(d, (W / 2, H * 0.07), f"{wd.upper()}  ·  {t:%d.%m}", "bold", u * 0.026, rgba(fg, 255), "mm")
    for _ in range(5):
        sparkle(d, rnd.uniform(W * 0.06, W * 0.94), rnd.choice([rnd.uniform(H * 0.1, H * 0.18),
                                                                 rnd.uniform(H * 0.82, H * 0.92)]),
                u * rnd.uniform(0.012, 0.026), "#ffffff")
    mx = W * (0.1 if H > W else 0.16)
    box = (mx, H * 0.18, W - mx, H * 0.8)
    draw_text_block(img, text, box, find_font("black"), fg, align="center", max_size=int(u * 0.1), spacing=1.25)
    d.line((W / 2 - u * 0.06, H * 0.9, W / 2 + u * 0.06, H * 0.9), fill=fg, width=max(2, int(u * 0.004)))
    label(d, (W / 2, H * 0.93), "vũ trụ gửi bạn", "book", u * 0.028, fg, "mm")
    return img


def tpl_glass(text, W, H, rnd):
    """Thẻ kính mờ (glassmorphism) trên các khối màu rực, chữ trắng."""
    bg, blobs = rnd.choice([
        (["#1b1446", "#3a1c71"], ["#ff4fa3", "#7b5cff", "#00d4ff", "#ff9f43"]),
        (["#0d1b2a", "#1b3a5c"], ["#00f5d4", "#9b5de5", "#f15bb5", "#fee440"]),
        (["#2b0f3a", "#541b5e"], ["#ff6b6b", "#ffd93d", "#6bcbff", "#c77dff"]),
    ])
    u = min(W, H)
    img = gradient((W, H), bg, angle=45)
    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    spots = [(0.2, 0.22), (0.85, 0.35), (0.25, 0.8), (0.8, 0.85), (0.55, 0.55)]
    for i, (fx, fy) in enumerate(spots):
        r = u * rnd.uniform(0.2, 0.32)
        x, y = W * fx + rnd.uniform(-1, 1) * u * 0.05, H * fy + rnd.uniform(-1, 1) * u * 0.05
        d.ellipse((x - r, y - r, x + r, y + r), fill=blobs[i % len(blobs)])
    img.alpha_composite(layer.filter(ImageFilter.GaussianBlur(u * 0.03)))
    if H > W:
        card = (W * 0.08, H * 0.2, W * 0.92, H * 0.8)
    else:
        card = (W * 0.18, H * 0.12, W * 0.82, H * 0.88)
    shadow(img, card, int(u * 0.05), offset=(0, int(u * 0.02)), blur=int(u * 0.04), alpha=90)
    frosted(img, card, int(u * 0.05), tint=(255, 255, 255, 48), blur=int(u * 0.04), outline=(255, 255, 255, 150))
    d = ImageDraw.Draw(img)
    p = u * 0.06
    r = u * 0.012
    for i in range(3):
        cx = card[0] + p + i * r * 3.2
        d.ellipse((cx - r, card[1] + p - r, cx + r, card[1] + p + r), fill=(255, 255, 255, 220))
    label(d, (card[2] - p, card[1] + p), "Thông điệp", "bold", u * 0.024, (255, 255, 255, 230), "rm")
    box = (card[0] + p, card[1] + p * 2, card[2] - p, card[3] - p * 1.6)
    _b4_shadow_text(img, text, box, find_font("bold"), "#ffffff", (0, 0, 0, 90), (0, int(u * 0.004)),
                 blur=u * 0.006, align="left", max_size=int(u * 0.085), spacing=1.3)
    t, wd = _b4_today()
    label(d, (card[0] + p, card[3] - p * 0.9), f"{wd} · {t:%d/%m/%Y}", "regular", u * 0.024,
          (255, 255, 255, 200), "lm")
    return img


def tpl_brutalist(text, W, H, rnd):
    """Neo-brutalism: màu chói, viền đen dày, bóng đổ cứng, nhãn dán xoay."""
    bg, card_c, tag_c = rnd.choice([
        ("#ffde59", "#ffffff", "#ff5c8a"), ("#a3f7bf", "#fffbe8", "#7b61ff"),
        ("#ff90e8", "#ffffff", "#ffc900"), ("#90cdf4", "#fff7d6", "#ff6b35"),
    ])
    u = min(W, H)
    k = max(4, int(u * 0.009))
    img = Image.new("RGBA", (W, H), bg)
    d = ImageDraw.Draw(img)
    grid(d, (0, 0, W, H), int(u * 0.07), mix(bg, "#000000", 0.12), max(1, k // 3))
    if H > W:
        card = (W * 0.08, H * 0.16, W * 0.88, H * 0.84)
    else:
        card = (W * 0.12, H * 0.14, W * 0.84, H * 0.84)
    off = int(u * 0.03)
    d.rectangle((card[0] + off, card[1] + off, card[2] + off, card[3] + off), fill="#000000")
    d.rectangle(card, fill=card_c, outline="#000000", width=k)
    # thanh tiêu đề
    bar = card[1] + u * 0.09
    d.rectangle((card[0], card[1], card[2], bar), fill=tag_c, outline="#000000", width=k)
    label(d, (card[0] + u * 0.04, (card[1] + bar) / 2), "TIN NÓNG", "black", u * 0.04, "#000000", "lm")
    for i in range(3):
        s = u * 0.022
        x = card[2] - u * 0.05 - i * s * 1.8
        y = (card[1] + bar) / 2
        d.rectangle((x - s / 2, y - s / 2, x + s / 2, y + s / 2), fill="#ffffff", outline="#000000", width=k // 2)
    p = u * 0.06
    box = (card[0] + p, bar + p * 0.8, card[2] - p, card[3] - p)
    draw_text_block(img, text, box, find_font("black"), "#111111", align="left", max_size=int(u * 0.095),
                    spacing=1.2)
    # sticker ngôi sao xoay
    sz = int(u * 0.24)
    st = Image.new("RGBA", (sz, sz), (0, 0, 0, 0))
    sd = ImageDraw.Draw(st)
    pts = star_points(sz / 2, sz / 2, sz * 0.48, sz * 0.33, 12)
    sd.polygon(pts, fill="#000000")
    sd.polygon(star_points(sz / 2 - k / 2, sz / 2 - k / 2, sz * 0.44, sz * 0.3, 12), fill=tag_c)
    label(sd, (sz / 2, sz / 2), "HOT", "black", sz * 0.2, "#000000", "mm")
    paste_rotated(img, st, (card[2] - u * 0.02, card[3] - u * 0.01), rnd.uniform(-20, 20))
    # mũi tên trang trí
    ax, ay = card[0] - u * 0.0, card[1] - u * 0.06
    d.rectangle((ax, ay - k, ax + u * 0.12, ay + k), fill="#000000")
    d.polygon([(ax + u * 0.12, ay - k * 3), (ax + u * 0.16, ay), (ax + u * 0.12, ay + k * 3)], fill="#000000")
    return img


def tpl_swiss(text, W, H, rnd):
    """Phong cách Swiss: lưới, khối đỏ, số lớn, chữ đen căn trái."""
    red = rnd.choice(["#e63027", "#d7261e", "#ef3b24"])
    paper = rnd.choice(["#f4f1ea", "#ffffff", "#efece4"])
    u = min(W, H)
    img = Image.new("RGBA", (W, H), paper)
    d = ImageDraw.Draw(img)
    cols = 6
    m = u * 0.06
    lw = max(1, int(u * 0.0015))
    for i in range(cols + 1):
        x = m + (W - 2 * m) * i / cols
        d.line((x, 0, x, H), fill=mix(paper, "#000000", 0.1), width=lw)
    t, wd = _b4_today()
    num = f"{t.day:02d}"
    big = load_font(find_font("black"), int(u * (0.42 if H > W else 0.44)))
    if H > W:
        d.rectangle((W * 0.55, 0, W, H * 0.3), fill=red)
        d.text((m, H * 0.02), num, font=big, fill="#111111", anchor="lt")
        d.ellipse((W * 0.7, H * 0.08, W * 0.7 + u * 0.14, H * 0.08 + u * 0.14), fill=paper)
        box = (m, H * 0.36, W - m, H * 0.84)
        rule_y = H * 0.33
    else:
        d.rectangle((0, H * 0.62, W * 0.34, H), fill=red)
        d.text((m, H * 0.04), num, font=big, fill="#111111", anchor="lt")
        d.ellipse((W * 0.2, H * 0.72, W * 0.2 + u * 0.16, H * 0.72 + u * 0.16), fill=paper)
        box = (W * 0.45, H * 0.14, W - m, H * 0.84)
        rule_y = H * 0.1
    d.rectangle((box[0], rule_y, box[2], rule_y + u * 0.008), fill="#111111")
    label(d, (box[0], rule_y - u * 0.012), f"{wd.upper()} / THÁNG {t.month:02d}", "bold", u * 0.022,
          "#111111", "lb")
    label(d, (box[2], rule_y - u * 0.012), "NO. " + num, "bold", u * 0.022, red, "rb")
    draw_text_block(img, text, box, find_font("black"), "#111111", align="left", valign="top",
                    max_size=int(u * 0.085), spacing=1.18)
    fy = H - m * 0.9
    label(d, (box[0], fy), "THÔNG ĐIỆP TỪ VŨ TRỤ", "bold", u * 0.02, "#111111", "ls")
    label(d, (W - m, fy), "Bản tin ngày", "regular", u * 0.02, "#111111", "rs")
    return img


def tpl_minimal_serif(text, W, H, rnd):
    """Tối giản: nền kem, chữ serif thanh lịch, đường kẻ mảnh."""
    bg, fg, acc = rnd.choice([
        ("#f6f1e9", "#2b2622", "#a58b6f"), ("#eef0ea", "#22302a", "#7d8f7a"),
        ("#f4ece8", "#3a2a2a", "#b98a7e"), ("#1f1d1b", "#f1e9dc", "#c4a77d"),
    ])
    u = min(W, H)
    img = Image.new("RGBA", (W, H), bg)
    add_grain(img, 8)
    d = ImageDraw.Draw(img)
    lw = max(1, int(u * 0.002))
    m = u * 0.05
    d.rectangle((m, m, W - m, H - m), outline=acc, width=lw)
    t, wd = _b4_today()
    label(d, (W / 2, H * 0.12), "— Thư gửi bạn —", "book", u * 0.03, acc, "mm")
    r = u * 0.006
    for i, y in enumerate((H * 0.17, H * 0.83)):
        d.line((W / 2 - u * 0.1, y, W / 2 - r * 3, y), fill=acc, width=lw)
        d.line((W / 2 + r * 3, y, W / 2 + u * 0.1, y), fill=acc, width=lw)
        d.ellipse((W / 2 - r, y - r, W / 2 + r, y + r), fill=acc)
    mx = W * (0.14 if H > W else 0.2)
    box = (mx, H * 0.22, W - mx, H * 0.78)
    draw_text_block(img, text, box, find_font("serif"), fg, align="center", max_size=int(u * 0.085), spacing=1.4)
    label(d, (W / 2, H * 0.88), f"{wd}, {t.day} tháng {t.month}", "book", u * 0.026, fg, "mm")
    return img


def tpl_highlighter(text, W, H, rnd):
    """Giấy trắng, chữ đen, vệt bút dạ quang lệch nhẹ sau từng dòng."""
    hl = rnd.choice(["#fff35c", "#b8ff6b", "#ffb3dd", "#9fe8ff", "#ffcc66"])
    u = min(W, H)
    img = Image.new("RGBA", (W, H), "#fbfaf6")
    d = ImageDraw.Draw(img)
    h_lines(d, (0, 0, W, H), int(u * 0.06), "#eceae2", max(1, int(u * 0.002)))
    d.line((W * 0.09, 0, W * 0.09, H), fill="#f2b8b8", width=max(2, int(u * 0.003)))
    rr = random.Random(rnd.random())

    def line_bg(im, x, y, w, lh, font):
        layer = Image.new("RGBA", im.size, (0, 0, 0, 0))
        ld = ImageDraw.Draw(layer)
        pad = font.size * 0.15
        top = y + lh * 0.5 - font.size * 0.2
        bot = y + lh * 0.5 + font.size * 0.5
        j = font.size * 0.06
        ld.polygon([(x - pad, top + rr.uniform(-j, j)), (x + w + pad, top + rr.uniform(-j, j)),
                    (x + w + pad * 1.4, bot + rr.uniform(-j, j)), (x - pad * 0.6, bot + rr.uniform(-j, j))],
                   fill=rgba(hl, 210))
        im.alpha_composite(layer)

    mx = W * (0.15 if H > W else 0.16)
    box = (mx, H * 0.14, W - W * 0.1, H * 0.84)
    draw_text_block(img, text, box, find_font("black"), "#151515", align="left", max_size=int(u * 0.09),
                    spacing=1.45, line_bg=line_bg)
    t, wd = _b4_today()
    label(d, (mx, H * 0.07), f"Ghi chú · {t:%d/%m}", "hand2", u * 0.035, "#555555", "lm")
    # nắp bút dạ quang
    pen = Image.new("RGBA", (int(u * 0.5), int(u * 0.08)), (0, 0, 0, 0))
    pd = ImageDraw.Draw(pen)
    pw, ph = pen.size
    pd.rounded_rectangle((0, 0, pw * 0.72, ph), int(ph * 0.3), fill="#2b2b2b")
    pd.rounded_rectangle((pw * 0.66, ph * 0.08, pw * 0.95, ph * 0.92), int(ph * 0.3), fill=hl)
    pd.polygon([(pw * 0.95, ph * 0.25), (pw, ph * 0.4), (pw, ph * 0.6), (pw * 0.95, ph * 0.75)], fill="#2b2b2b")
    pd.rectangle((pw * 0.1, ph * 0.2, pw * 0.5, ph * 0.32), fill=hl)
    paste_rotated(img, pen, (W - u * 0.22, H - u * 0.09), 12)
    return img


def tpl_bold_gradient(text, W, H, rnd):
    """Gradient đậm rực, chữ in hoa rất to màu trắng có bóng mờ."""
    cols = rnd.choice([
        ["#ff0f7b", "#f89b29"], ["#4f46e5", "#ec4899"], ["#0061ff", "#60efff"],
        ["#7f00ff", "#e100ff"], ["#ff512f", "#dd2476"], ["#00b09b", "#3a47d5"],
    ])
    u = min(W, H)
    img = gradient((W, H), cols, angle=rnd.choice([35, 60, 145]))
    soft_blobs(img, rnd, [mix(cols[0], "#ffffff", 0.15), mix(cols[1], "#000000", 0.2)], n=4, alpha=170,
               blur=0.18, rmin=0.3, rmax=0.5)
    add_grain(img, 12)
    d = ImageDraw.Draw(img)
    m = u * 0.07
    label(d, (m, m), "TIN VUI", "black", u * 0.03, "#ffffff", "lm")
    label(d, (W - m, m), f"VŨ TRỤ / {datetime.date.today().year}", "bold", u * 0.022, (255, 255, 255, 200), "rm")
    d.line((m, H - m, W - m, H - m), fill="#ffffff", width=max(2, int(u * 0.004)))
    mx = W * (0.08 if H > W else 0.1)
    box = (mx, H * 0.1, W - mx, H - m * 1.6)
    _b4_shadow_text(img, text, box, find_font("black"), "#ffffff", (0, 0, 0, 110), (0, int(u * 0.01)),
                 blur=u * 0.012, align="left", upper=True, max_size=int(u * 0.13), spacing=1.24)
    return img


def tpl_retro_sunset(text, W, H, rnd):
    """Hoàng hôn 80s: mặt trời sọc, lưới neon phối cảnh, chữ phát sáng."""
    sky, sun, gridc = rnd.choice([
        (["#120338", "#4a0d67", "#c2185b"], ["#ffe259", "#ff4e8a"], "#ff3fd1"),
        (["#0b0b2b", "#2d1b69", "#ff6a3d"], ["#ffd23f", "#ff3d68"], "#00e5ff"),
    ])
    u = min(W, H)
    img = gradient((W, H), sky)
    d = ImageDraw.Draw(img)
    star_field(d, rnd, (0, 0, W, H * 0.45), int(W * H / 9000), (255, 255, 255, 255), max(2, u * 0.003))
    portrait = H > W
    hy = H * (0.66 if portrait else 0.64)
    sx = W / 2 if portrait else W * 0.72
    sr = u * (0.3 if portrait else 0.26)
    sy = hy - sr * 0.45
    # mặt trời gradient + sọc ngang ở nửa dưới
    sl = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    gradient_fill(sl, sun, lambda m: m.ellipse((sx - sr, sy - sr, sx + sr, sy + sr), fill=255))
    sd = ImageDraw.Draw(sl)
    n = 7
    for i in range(n):
        y = sy + sr * (0.05 + i * 0.14)
        sd.rectangle((sx - sr, y, sx + sr, y + sr * 0.02 * (i + 1)), fill=(0, 0, 0, 0))
    gl = Image.new("RGBA", (W, H), rgba(sun[1], 0))
    ImageDraw.Draw(gl).ellipse((sx - sr, sy - sr, sx + sr, sy + sr), fill=rgba(sun[1], 150))
    img.alpha_composite(gl.filter(ImageFilter.GaussianBlur(u * 0.06)))
    img.alpha_composite(sl)
    # mặt đất + lưới
    d.rectangle((0, hy, W, H), fill="#0a0420")
    gr = Image.new("RGBA", (W, H), rgba(gridc, 0))
    _b4_persp_grid(ImageDraw.Draw(gr), W, H, hy, rgba(gridc, 255), max(2, int(u * 0.004)), cx=sx)
    glow(img, gr, radii=(0.008,))
    d.line((0, hy, W, hy), fill=mix(gridc, "#ffffff", 0.5), width=max(2, int(u * 0.005)))
    if portrait:
        box = (W * 0.08, H * 0.07, W * 0.92, sy - sr - H * 0.03)
    else:
        box = (W * 0.06, H * 0.1, W * 0.5, hy - H * 0.06)
    # nền tối nhẹ sau chữ cho dễ đọc
    sh = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ImageDraw.Draw(sh).rectangle(box, fill=(10, 0, 30, 110))
    img.alpha_composite(sh.filter(ImageFilter.GaussianBlur(u * 0.05)))
    glow_text(img, text, box, find_font("black"), gridc, core="#ffffff", radii=(0.02, 0.006), align="center",
              max_size=int(u * 0.085), spacing=1.25)
    label(ImageDraw.Draw(img), (W / 2 if portrait else W * 0.28, H - u * 0.05), "KÊNH VŨ TRỤ  ·  1986",
          "pixel", u * 0.04, mix(gridc, "#ffffff", 0.6), "mm")
    return img


def tpl_vaporwave(text, W, H, rnd):
    """Vaporwave: gradient hồng-tím-xanh, sàn lưới, cửa sổ máy tính cũ chứa chữ."""
    u = min(W, H)
    sky = rnd.choice([["#ff71ce", "#b967ff", "#01cdfe"], ["#ff9de6", "#a98bff", "#7ef9ff"]])
    img = gradient((W, H), sky)
    d = ImageDraw.Draw(img)
    hy = H * 0.7
    d.rectangle((0, hy, W, H), fill="#2a0a4a")
    _b4_persp_grid(d, W, H, hy, "#05ffa1", max(2, int(u * 0.004)), nv=18, nh=9)
    # mặt trời nhỏ sau cửa sổ
    portrait = H > W
    sr = u * (0.3 if portrait else 0.2)
    sx, sy = (W / 2 if portrait else W * 0.8), hy - sr * 0.3
    sl = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    gradient_fill(sl, ["#fffb96", "#ff71ce"], lambda m: m.ellipse((sx - sr, sy - sr, sx + sr, sy + sr), fill=255))
    sm = Image.new("L", (W, H), 255)
    ImageDraw.Draw(sm).rectangle((0, hy, W, H), fill=0)
    sl.putalpha(ImageChops.multiply(sl.getchannel("A"), sm))
    img.alpha_composite(sl)
    d = ImageDraw.Draw(img)
    for _ in range(14):
        sparkle(d, rnd.uniform(0, W), rnd.uniform(0, hy * 0.9), u * rnd.uniform(0.006, 0.016), "#ffffff")
    # cửa sổ
    if portrait:
        win = (W * 0.08, H * 0.1, W * 0.92, H * 0.56)
    else:
        win = (W * 0.08, H * 0.1, W * 0.62, H * 0.84)
    k = max(3, int(u * 0.005))
    off = int(u * 0.02)
    d.rectangle((win[0] + off, win[1] + off, win[2] + off, win[3] + off), fill="#2a0a4a")
    d.rectangle(win, fill="#fdf6ff", outline="#2a0a4a", width=k)
    tb = win[1] + u * 0.075
    gradient_fill(img, ["#ff71ce", "#01cdfe"],
                  lambda m: m.rectangle((win[0] + k, win[1] + k, win[2] - k, tb), fill=255), angle=90)
    d.line((win[0], tb, win[2], tb), fill="#2a0a4a", width=k)
    label(d, (win[0] + u * 0.03, (win[1] + tb) / 2), "vutru_mo_ao.txt", "pixel", u * 0.045, "#ffffff", "lm")
    bs = u * 0.045
    for i in range(2):
        bx = win[2] - u * 0.025 - bs - i * bs * 1.25
        by = (win[1] + tb) / 2 - bs / 2
        d.rectangle((bx, by, bx + bs, by + bs), fill="#fdf6ff", outline="#2a0a4a", width=max(2, k // 2))
        if i == 0:
            d.line((bx + bs * 0.25, by + bs * 0.25, bx + bs * 0.75, by + bs * 0.75), fill="#2a0a4a", width=k)
            d.line((bx + bs * 0.75, by + bs * 0.25, bx + bs * 0.25, by + bs * 0.75), fill="#2a0a4a", width=k)
        else:
            d.line((bx + bs * 0.25, by + bs * 0.7, bx + bs * 0.75, by + bs * 0.7), fill="#2a0a4a", width=k)
    p = u * 0.05
    box = (win[0] + p, tb + p, win[2] - p, win[3] - p)
    _b4_shadow_text(img, text, box, find_font("bold"), "#3b0f6b", "#ff71ce", (int(u * 0.004), int(u * 0.004)),
                 align="left", max_size=int(u * 0.08), spacing=1.3)
    label(d, (W / 2, H - u * 0.05), "V Ũ   T R Ụ   M Ộ N G   M Ơ", "bold", u * 0.03, "#fdf6ff", "mm")
    return img


def tpl_y2k_sparkle(text, W, H, rnd):
    """Y2K: nền bạc-xanh-hồng, sao lấp lánh, chữ chrome viền đậm."""
    u = min(W, H)
    bg = rnd.choice([["#cfe3ff", "#f3c6ff", "#bdf3ff"], ["#e7e9f0", "#bcd4ff", "#ffc8ec"],
                     ["#d6f8ff", "#e5d2ff", "#ffe3f5"]])
    img = gradient((W, H), bg, angle=30)
    # bong bóng chrome
    for _ in range(5):
        r = u * rnd.uniform(0.08, 0.16)
        x, y = rnd.uniform(0, W), rnd.choice([rnd.uniform(0, H * 0.2), rnd.uniform(H * 0.8, H)])
        bl = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        gradient_fill(bl, ["#ffffff", "#9fb7e8", "#ffffff", "#c79ff0"],
                      lambda m: m.ellipse((x - r, y - r, x + r, y + r), fill=255), angle=40)
        ImageDraw.Draw(bl).ellipse((x - r * 0.55, y - r * 0.6, x - r * 0.15, y - r * 0.25), fill=(255, 255, 255, 230))
        img.alpha_composite(bl)
    d = ImageDraw.Draw(img)
    for _ in range(26):
        sparkle(d, rnd.uniform(0, W), rnd.uniform(0, H), u * rnd.uniform(0.008, 0.035),
                rnd.choice(["#ffffff", "#ffffff", "#ff7ad9", "#7ab8ff"]))
    mx = W * (0.08 if H > W else 0.14)
    box = (mx, H * 0.2, W - mx, H * 0.8)
    fp = find_font("round")
    kw = dict(align="center", max_size=int(u * 0.11), spacing=1.12)
    sw = max(3, int(u * 0.008))
    # viền đậm + bóng
    draw_text_block(img, text, (box[0] + sw, box[1] + sw * 1.5, box[2] + sw, box[3] + sw * 1.5), fp,
                    "#ff4fb8", stroke=sw, stroke_color="#ff4fb8", **kw)
    draw_text_block(img, text, box, fp, "#1d2a6b", stroke=sw, stroke_color="#1d2a6b", **kw)
    mask, font = _b4_text_mask((W, H), text, box, fp, **kw)
    bb = mask.getbbox() or (0, 0, W, H)
    # dải chrome lặp theo từng dòng
    lh = int(font.size * kw["spacing"])
    stops = ["#ffffff", "#a9bde3", "#5a6fa3", "#e9f0ff", "#ffffff"]
    band = gradient((bb[2] - bb[0], lh), stops)
    chrome = Image.new("RGBA", (bb[2] - bb[0], bb[3] - bb[1]))
    for y in range(0, chrome.height, lh):
        chrome.paste(band, (0, y))
    full = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    full.paste(chrome, bb[:2])
    img.paste(full, (0, 0), mask)
    d = ImageDraw.Draw(img)
    pill = (W / 2 - u * 0.2, H * 0.1 - u * 0.035, W / 2 + u * 0.2, H * 0.1 + u * 0.035)
    d.rounded_rectangle(pill, int(u * 0.035), fill="#1d2a6b")
    label(d, (W / 2, H * 0.1), "lấp lánh 2000", "round", u * 0.035, "#ffffff", "mm")
    sparkle(d, pill[0] - u * 0.04, H * 0.1, u * 0.025, "#1d2a6b")
    sparkle(d, pill[2] + u * 0.04, H * 0.1, u * 0.025, "#1d2a6b")
    return img


def tpl_comic(text, W, H, rnd):
    """Truyện tranh: nền halftone + tia, khung đen dày, bong bóng thoại."""
    bg, dot_c, burst = rnd.choice([
        ("#ffd23f", "#ff5c39", "#ff3b3b"), ("#4fc3f7", "#1565c0", "#ffeb3b"),
        ("#ff8fb1", "#d81b60", "#fff176"),
    ])
    u = min(W, H)
    img = Image.new("RGBA", (W, H), bg)
    d = ImageDraw.Draw(img)
    cx, cy = W * 0.5, H * 0.5
    R = math.hypot(W, H)
    n = 28
    for i in range(n):
        if i % 2:
            continue
        a0, a1 = 2 * math.pi * i / n, 2 * math.pi * (i + 1) / n
        d.polygon([(cx, cy), (cx + R * math.cos(a0), cy + R * math.sin(a0)),
                   (cx + R * math.cos(a1), cy + R * math.sin(a1))], fill=mix(bg, "#ffffff", 0.25))
    # halftone: chấm to dần ra mép
    gap = int(u * 0.035)
    for y in range(0, H + gap, gap):
        for x in range((y // gap % 2) * gap // 2, W + gap, gap):
            t = min(1, math.hypot((x - cx) / W, (y - cy) / H) * 1.7)
            r = gap * 0.42 * t
            if r > 1:
                d.ellipse((x - r, y - r, x + r, y + r), fill=dot_c)
    k = max(5, int(u * 0.012))
    m = u * 0.035
    d.rectangle((m, m, W - m, H - m), outline="#000000", width=k)
    # nổ "BÙM!" góc trên
    bx, by = W * 0.24, H * 0.13 if H > W else H * 0.2
    br = u * 0.15
    pts = [(bx + (br if i % 2 == 0 else br * 0.62) * math.cos(math.radians(i * 360 / 22 + 7)) * 1.25,
            by + (br if i % 2 == 0 else br * 0.62) * math.sin(math.radians(i * 360 / 22 + 7)))
           for i in range(22)]
    d.polygon([(x + k, y + k) for x, y in pts], fill="#000000")
    d.polygon(pts, fill=burst, outline="#000000", width=k // 2)
    bang = Image.new("RGBA", (int(br * 2.4), int(br * 1.2)), (0, 0, 0, 0))
    label(ImageDraw.Draw(bang), (bang.width / 2, bang.height / 2), "BÙM!", "comic", br * 0.6, "#000000", "mm")
    paste_rotated(img, bang, (bx, by), -10)
    # bong bóng thoại
    if H > W:
        maxwh = (W * 0.76, H * 0.52)
    else:
        maxwh = (W * 0.58, H * 0.5)
    fp = find_font("comic")
    font, tw, th, _ = measure_text(text, (0, 0, int(maxwh[0]), int(maxwh[1])), fp, int(u * 0.11), 1.12, True)
    pad = u * 0.06
    bw, bh = tw + 2 * pad, th + 2 * pad
    top = max(H * (0.26 if H > W else 0.3), H * 0.48 - bh / 2)
    x0 = (W - bw) / 2 + (W * 0.05 if W > H else 0)
    bub = (x0, top, x0 + bw, top + bh)
    tail = [(bub[0] + bw * 0.6, bub[3] - k), (bub[0] + bw * 0.82, bub[3] + u * 0.14), (bub[0] + bw * 0.78, bub[3] - k)]
    d.rounded_rectangle([v + k * 1.5 for v in bub], int(u * 0.08), fill="#000000")
    d.polygon([(x + k * 1.5, y + k * 1.5) for x, y in tail], fill="#000000")
    d.rounded_rectangle(bub, int(u * 0.08), fill="#ffffff", outline="#000000", width=k)
    d.polygon(tail, fill="#ffffff")
    d.line(tail[:2], fill="#000000", width=k)
    d.line(tail[1:], fill="#000000", width=k)
    draw_text_block(img, text, (bub[0] + pad, bub[1] + pad, bub[2] - pad, bub[3] - pad), fp, "#111111",
                    align="center", upper=True, max_size=font.size, spacing=1.12)
    # nhãn chương
    cap = (W - m - u * 0.36, H - m - u * 0.1, W - m, H - m)
    d.rectangle(cap, fill="#fff8d6", outline="#000000", width=k)
    label(d, ((cap[0] + cap[2]) / 2, (cap[1] + cap[3]) / 2), "TẬP 10", "comic", u * 0.05, "#000000", "mm")
    return img


def tpl_sunburst(text, W, H, rnd):
    """Tia nắng retro toả từ tâm, huy hiệu tròn kem chứa chữ."""
    c1, c2, ink, badge = rnd.choice([
        ("#f6a43a", "#f9c56a", "#5a2a0c", "#fff3dc"), ("#e85d4a", "#f3907c", "#4a1410", "#fff1e6"),
        ("#3aa6a0", "#7fcfc4", "#0f3b3a", "#fdf6e3"), ("#f2c14e", "#f7dc8a", "#5b3a06", "#fffaf0"),
    ])
    u = min(W, H)
    img = Image.new("RGBA", (W, H), c1)
    d = ImageDraw.Draw(img)
    cx, cy = W / 2, H / 2
    R = math.hypot(W, H)
    n = 32
    for i in range(0, n, 2):
        a0, a1 = 2 * math.pi * i / n, 2 * math.pi * (i + 1) / n
        d.polygon([(cx, cy), (cx + R * math.cos(a0), cy + R * math.sin(a0)),
                   (cx + R * math.cos(a1), cy + R * math.sin(a1))], fill=c2)
    vignette(img, 70)
    add_grain(img, 14)
    d = ImageDraw.Draw(img)
    if H > W:
        rx, ry = W * 0.44, H * 0.34
    else:
        rx, ry = W * 0.33, H * 0.42
    k = max(4, int(u * 0.008))
    d.ellipse((cx - rx - k * 3, cy - ry - k * 3, cx + rx + k * 3, cy + ry + k * 3), fill=ink)
    d.ellipse((cx - rx, cy - ry, cx + rx, cy + ry), fill=badge)
    d.ellipse((cx - rx + k * 3, cy - ry + k * 3, cx + rx - k * 3, cy + ry - k * 3), outline=ink, width=max(2, k // 2))
    # sao nhỏ trên/dưới
    for sy in (cy - ry * 0.78, cy + ry * 0.78):
        for dx in (-1, 0, 1):
            s = u * (0.022 if dx else 0.032)
            d.polygon(star_points(cx + dx * u * 0.07, sy, s, s * 0.45), fill=ink)
    box = (cx - rx * 0.72, cy - ry * 0.6, cx + rx * 0.72, cy + ry * 0.6)
    draw_text_block(img, text, box, find_font("black"), ink, align="center", max_size=int(u * 0.085), spacing=1.2)
    t, wd = _b4_today()
    tag = (cx - u * 0.22, cy + ry + u * 0.04, cx + u * 0.22, cy + ry + u * 0.12)
    if tag[3] < H - u * 0.02:
        d.rounded_rectangle(tag, int(u * 0.04), fill=ink)
        label(d, (cx, (tag[1] + tag[3]) / 2), f"{wd} · {t:%d.%m}", "bold", u * 0.03, badge, "mm")
    return img


def tpl_groovy_waves(text, W, H, rnd):
    """Sóng 70s nhiều tầng màu đất, thẻ bo tròn chữ Lobster."""
    pal = rnd.choice([
        ["#f4e1c1", "#f2a541", "#e4572e", "#a33b20", "#5b2a1c"],
        ["#fbe8c8", "#f6c453", "#e98a3c", "#c75b39", "#6d8b74"],
        ["#f7e4d0", "#e8a87c", "#d27d5d", "#8e5c49", "#41658a"],
    ])
    u = min(W, H)
    img = Image.new("RGBA", (W, H), pal[0])
    d = ImageDraw.Draw(img)
    n = 10
    length = W * rnd.uniform(0.7, 1.0)
    phase = rnd.uniform(0, math.pi * 2)
    for i in range(n):
        y = H * (i + 0.3) / n
        _b4_wave_band(d, W, y, u * 0.04, length, phase + i * 0.6, pal[1 + i % 4], H + 20)
    add_grain(img, 14)
    d = ImageDraw.Draw(img)
    ink = pal[4] if luminance(pal[4]) < 120 else "#3b1d12"
    if H > W:
        card = (W * 0.09, H * 0.24, W * 0.91, H * 0.76)
    else:
        card = (W * 0.2, H * 0.14, W * 0.8, H * 0.86)
    rad = int(u * 0.12)
    k = max(4, int(u * 0.008))
    off = int(u * 0.02)
    d.rounded_rectangle((card[0] + off, card[1] + off, card[2] + off, card[3] + off), rad, fill=ink)
    d.rounded_rectangle(card, rad, fill=pal[0], outline=ink, width=k)
    p = u * 0.08
    label(d, ((card[0] + card[2]) / 2, card[1] + p * 0.8), "good vibes", "brush", u * 0.045, pal[3], "mm")
    box = (card[0] + p, card[1] + p * 1.5, card[2] - p, card[3] - p)
    draw_text_block(img, text, box, find_font("retro"), ink, align="center", max_size=int(u * 0.095),
                    spacing=1.25)
    # hoa 70s
    for fx, fy, fs in ((card[2] - u * 0.02, card[1] + u * 0.02, 0.09), (card[0] + u * 0.03, card[3] - u * 0.02, 0.07)):
        s = u * fs
        for j in range(6):
            a = math.radians(j * 60)
            px, py = fx + s * 0.55 * math.cos(a), fy + s * 0.55 * math.sin(a)
            d.ellipse((px - s * 0.42, py - s * 0.42, px + s * 0.42, py + s * 0.42), fill=pal[2], outline=ink,
                      width=max(2, k // 2))
        d.ellipse((fx - s * 0.4, fy - s * 0.4, fx + s * 0.4, fy + s * 0.4), fill=pal[1], outline=ink,
                  width=max(2, k // 2))
    return img


# --- batch 5 ---

def _b5_layer(W, H):
    return Image.new("RGBA", (W, H), (0, 0, 0, 0))


def _b5_stars(img, rnd, n, color="#ffffff", rmax=3.0, box=None):
    """Sao li ti bán trong suốt (vẽ trên layer riêng)."""
    W, H = img.size
    x0, y0, x1, y1 = box or (0, 0, W, H)
    lay = _b5_layer(W, H)
    d = ImageDraw.Draw(lay)
    for _ in range(n):
        x, y, r = rnd.uniform(x0, x1), rnd.uniform(y0, y1), rnd.uniform(0.6, rmax)
        d.ellipse((x - r, y - r, x + r, y + r), fill=rgba(color, rnd.randint(90, 255)))
    img.alpha_composite(lay)


def _b5_glow_sparkles(img, rnd, n, box, rmin, rmax, color="#ffffff"):
    """Vài ngôi sao 4 cánh có quầng sáng."""
    lay = Image.new("RGBA", img.size, rgba(color, 0))
    d = ImageDraw.Draw(lay)
    x0, y0, x1, y1 = box
    for _ in range(n):
        sparkle(d, rnd.uniform(x0, x1), rnd.uniform(y0, y1), rnd.uniform(rmin, rmax), rgba(color, 255))
    glow(img, lay, (0.012,))


def _b5_wave_pts(W, y, amp, length, phase, step=8, bottom=None):
    pts = [(x, y + amp * math.sin(x / length * 2 * math.pi + phase)
            + amp * 0.35 * math.sin(x / length * 5.3 + phase * 1.7)) for x in range(-step, W + 2 * step, step)]
    return pts + [(W + step, bottom), (-step, bottom)] if bottom is not None else pts


def _b5_flower(d, cx, cy, r, petal, center):
    """Hoa 5 cánh (hoa mai, hoa nhí)."""
    for k in range(5):
        a = math.radians(k * 72 - 90)
        px, py = cx + r * 0.55 * math.cos(a), cy + r * 0.55 * math.sin(a)
        d.ellipse((px - r * 0.5, py - r * 0.5, px + r * 0.5, py + r * 0.5), fill=petal)
    d.ellipse((cx - r * 0.25, cy - r * 0.25, cx + r * 0.25, cy + r * 0.25), fill=center)


def _b5_texture_alpha(layer, k=1.6, base=200):
    """Nhân alpha của layer với nhiễu (vân sáp màu / mực khô)."""
    noise = Image.effect_noise(layer.size, 90).convert("L").point(
        lambda p: min(255, max(0, int((p - 128) * k + base))))
    layer.putalpha(ImageChops.multiply(layer.getchannel("A"), noise))
    return layer


def _b5_crayon(d, pts, color, w, rnd, passes=3):
    """Nét sáp màu: vài nét run tay chồng lên nhau."""
    for _ in range(passes):
        j = w * 0.35
        q = [(x + rnd.uniform(-j, j), y + rnd.uniform(-j, j)) for x, y in pts]
        d.line(q, fill=color, width=max(1, int(w * 0.6)), joint="curve")


def _b5_circle_pts(cx, cy, r, n=40, jitter=0, rnd=None, a0=0, sweep=360):
    return [(cx + (r + (rnd.uniform(-jitter, jitter) if rnd else 0)) * math.cos(math.radians(a0 + sweep * i / n)),
             cy + (r + (rnd.uniform(-jitter, jitter) if rnd else 0)) * math.sin(math.radians(a0 + sweep * i / n)))
            for i in range(n + 1)]


ZODIAC_ORDER = ["Tý", "Sửu", "Dần", "Mão", "Thìn", "Tỵ", "Ngọ", "Mùi", "Thân", "Dậu", "Tuất", "Hợi"]


ZODIAC_ALIAS = {"tí": "tý", "tị": "tỵ", "mẹo": "mão"}


def zodiac_index(text):
    """Vị trí (0-11) của con giáp được nhắc trong text ("tuổi Sửu" -> 1), không có thì None."""
    m = ZODIAC_RE.search(unicodedata.normalize("NFC", text).lower())
    if not m:
        return None
    key = ZODIAC_ALIAS.get(m.group(1), m.group(1))
    return [z.lower() for z in ZODIAC_ORDER].index(key)


def _b5_tarot_card(img, box, rnd, gold, fill, art, numeral, title):
    """Vẽ lá tarot: viền vàng kép, góc sao, số La Mã, trăng khuyết tại art=(cx, cy, r), băng tên."""
    W, H = img.size
    u = min(W, H)
    x0, y0, x1, y1 = box
    shadow(img, box, int(u * 0.02), offset=(0, int(u * 0.015)), blur=int(u * 0.03), alpha=150)
    d = ImageDraw.Draw(img)
    d.rounded_rectangle(box, int(u * 0.02), fill=fill, outline=gold, width=max(3, int(u * 0.007)))
    m = int(u * 0.028)
    inner = (x0 + m, y0 + m, x1 - m, y1 - m)
    d.rectangle(inner, outline=gold, width=max(2, int(u * 0.003)))
    m2 = int(u * 0.04)
    dashed_rect(d, (x0 + m2, y0 + m2, x1 - m2, y1 - m2), int(u * 0.006), int(u * 0.008), mix(gold, fill, 0.45),
                max(1, int(u * 0.002)))
    for cx, cy in ((inner[0], inner[1]), (inner[2], inner[1]), (inner[0], inner[3]), (inner[2], inner[3])):
        d.ellipse((cx - u * 0.016, cy - u * 0.016, cx + u * 0.016, cy + u * 0.016), fill=fill, outline=gold, width=2)
        sparkle(d, cx, cy, u * 0.012, gold)
    # sao li ti trong lá bài
    lay = _b5_layer(W, H)
    star_field(ImageDraw.Draw(lay), rnd, (inner[0] + m, inner[1] + m, inner[2] - m, inner[3] - m),
               int((x1 - x0) * (y1 - y0) / 9000), rgba(gold, 150), rmax=u * 0.003)
    img.alpha_composite(lay)
    # số La Mã + băng tên
    cx = (x0 + x1) / 2
    label(d, (cx, inner[1] + u * 0.03), numeral, "serif", u * 0.045, gold, "mt")
    bw, bh = (x1 - x0) * 0.62, u * 0.065
    by = inner[3] - u * 0.04 - bh
    band = (cx - bw / 2, by, cx + bw / 2, by + bh)
    d.polygon([(band[0] - bh * 0.4, by), (band[2] + bh * 0.4, by), (band[2], by + bh / 2),
               (band[2] + bh * 0.4, by + bh), (band[0] - bh * 0.4, by + bh), (band[0], by + bh / 2)],
              fill=mix(fill, gold, 0.18), outline=gold)
    label(d, (cx, by + bh / 2), title, "serif", bh * 0.5, gold, "mm")
    # trăng khuyết + vòng + sao quanh
    ax, ay, r = art
    halo = Image.new("RGBA", (W, H), rgba(gold, 0))
    hd = ImageDraw.Draw(halo)
    hd.ellipse((ax - r * 1.05, ay - r * 1.05, ax + r * 1.05, ay + r * 1.05), fill=rgba(gold, 70))
    img.alpha_composite(halo.filter(ImageFilter.GaussianBlur(r * 0.35)))
    d.ellipse((ax - r * 1.35, ay - r * 1.35, ax + r * 1.35, ay + r * 1.35), outline=gold, width=max(2, int(u * 0.003)))
    dl = Image.new("RGBA", (W, H), rgba(gold, 0))
    ddl = ImageDraw.Draw(dl)
    for k in range(24):
        a = math.radians(k * 15)
        rr = r * (1.55 if k % 2 else 1.5)
        L = r * (0.22 if k % 2 else 0.12)
        ddl.line((ax + rr * math.cos(a), ay + rr * math.sin(a), ax + (rr + L) * math.cos(a),
                  ay + (rr + L) * math.sin(a)), fill=rgba(gold, 255), width=max(2, int(u * 0.003)))
    crescent(dl, ax, ay, r, rgba(gold, 255), cut=0.42)
    for k in range(4):
        a = math.radians(45 + k * 90)
        sparkle(ddl, ax + r * 2.05 * math.cos(a), ay + r * 2.05 * math.sin(a), r * 0.18, rgba(gold, 255))
    sparkle(ddl, ax + r * 0.35, ay - r * 0.1, r * 0.22, rgba(gold, 255))
    glow(img, dl, (0.006,))


def tpl_tarot(text, W, H, rnd):
    """Lá bài tarot tím than viền vàng, trăng khuyết + sao; ngang thì lá bài bên trái, chữ bên phải."""
    u = min(W, H)
    top, bot, fill = rnd.choice([("#140d33", "#2c1652", "#1d1240"), ("#0b1630", "#1f2d5e", "#13204a"),
                                 ("#1c0f26", "#3b1a3d", "#2a1330")])
    gold = rnd.choice(["#e9c46a", "#f2d27a", "#d9b25f"])
    img = gradient((W, H), [top, bot])
    _b5_stars(img, rnd, W * H // 4500, rmax=u * 0.003)
    _b5_glow_sparkles(img, rnd, 10, (0, 0, W, H), u * 0.008, u * 0.018, "#fff4d6")
    numeral, title = rnd.choice([("XVIII", "MẶT TRĂNG"), ("XVII", "NGÔI SAO"), ("XXI", "VŨ TRỤ"),
                                 ("X", "VÒNG MAY MẮN")])
    serif = find_font("serif")
    cream = mix(gold, "#ffffff", 0.45)
    if W >= H:
        ch = H * 0.86
        cw = ch * 0.6
        box = (W * 0.07, (H - ch) / 2, W * 0.07 + cw, (H + ch) / 2)
        _b5_tarot_card(img, box, rnd, gold, fill, ((box[0] + box[2]) / 2, H * 0.47, cw * 0.2), numeral, title)
        tb = (box[2] + W * 0.07, H * 0.2, W * 0.93, H * 0.8)
        d = ImageDraw.Draw(img)
        mx = (tb[0] + tb[2]) / 2
        for y in (H * 0.13, H * 0.87):
            d.line((mx - W * 0.12, y, mx + W * 0.12, y), fill=gold, width=2)
            sparkle(d, mx, y, u * 0.018, gold)
        draw_text_block(img, text, tb, serif, cream, align="center", max_size=int(u * 0.085), spacing=1.3)
    else:
        box = (W * 0.07, H * 0.05, W * 0.93, H * 0.95)
        cw = box[2] - box[0]
        _b5_tarot_card(img, box, rnd, gold, fill, (W / 2, H * 0.215, cw * 0.11), numeral, title)
        tb = (box[0] + cw * 0.12, H * 0.37, box[2] - cw * 0.12, H * 0.82)
        draw_text_block(img, text, tb, serif, cream, align="center", max_size=int(u * 0.085), spacing=1.3)
    return img


def tpl_starry_night(text, W, H, rnd):
    """Bầu trời đêm đầy sao, trăng khuyết phát sáng, đồi tối phía dưới, chữ trắng phát sáng."""
    u = min(W, H)
    sky = rnd.choice([["#070b26", "#1a2766", "#5a3b82", "#c27a9e"], ["#050a1f", "#0f2a5c", "#2f5d8f", "#7fa6c9"],
                      ["#0c0820", "#2a1a5e", "#6b3f8f", "#e09a8a"]])
    img = gradient((W, H), sky)
    _b5_stars(img, rnd, W * H // 2200, rmax=u * 0.0025, box=(0, 0, W, H * 0.85))
    _b5_glow_sparkles(img, rnd, 14, (0, 0, W, H * 0.7), u * 0.006, u * 0.016)
    # sao băng
    lay = _b5_layer(W, H)
    d = ImageDraw.Draw(lay)
    sx, sy, L = W * rnd.uniform(0.15, 0.4), H * rnd.uniform(0.08, 0.18), u * 0.25
    for i in range(20):
        t0, t1 = i / 20, (i + 1) / 20
        d.line((sx - L * t0, sy - L * 0.4 * t0, sx - L * t1, sy - L * 0.4 * t1),
               fill=(255, 255, 255, int(230 * (1 - t0))), width=max(2, int(u * 0.004 * (1 - t0))))
    img.alpha_composite(lay)
    # trăng
    mx, my, r = W * 0.76, H * 0.12 if H > W else H * 0.2, u * 0.085
    moon = Image.new("RGBA", (W, H), (255, 245, 210, 0))
    crescent(moon, mx, my, r, (255, 245, 210, 255), cut=0.4)
    glow(img, moon, (0.05, 0.02))
    # đồi núi
    base = H * 0.86
    for k, col in enumerate([mix(sky[-1], "#0a0a20", 0.6), mix(sky[-1], "#050512", 0.8), "#05060f"]):
        hl = _b5_layer(W, H)
        ImageDraw.Draw(hl).polygon(_b5_wave_pts(W, base + k * H * 0.04, H * 0.025, W * rnd.uniform(0.6, 1.1),
                                             rnd.uniform(0, 6), bottom=H + 5), fill=col)
        img.alpha_composite(hl)
    tb = (W * 0.1, H * 0.25, W * 0.9, H * 0.76) if H > W else (W * 0.14, H * 0.3, W * 0.86, H * 0.78)
    glow_text(img, text, tb, find_font("serif"), "#9fb4ff", core="#ffffff", align="center",
              max_size=int(u * 0.09), spacing=1.28, radii=(0.02, 0.008))
    return img


def tpl_cloud_sky(text, W, H, rnd):
    """Trời xanh dễ thương: mặt trời, mây bông, chữ tròn xanh đậm trên tấm mây lớn."""
    u = min(W, H)
    sky, fg = rnd.choice([(["#6ec1f5", "#a9dcfb", "#e6f5ff"], "#2b5a8c"),
                          (["#8fb8ff", "#c4d8ff", "#fbe6f3"], "#4a4f9c"),
                          (["#7fd3e8", "#bdeaf3", "#f2fbff"], "#1f6b80")])
    img = gradient((W, H), sky)
    # mặt trời
    sun = Image.new("RGBA", (W, H), (255, 220, 110, 0))
    sd = ImageDraw.Draw(sun)
    sx, sy, sr = W * 0.14, H * 0.08 if H > W else H * 0.15, u * 0.08
    sd.ellipse((sx - sr, sy - sr, sx + sr, sy + sr), fill=(255, 214, 90, 255))
    for k in range(12):
        a = math.radians(k * 30 + 15)
        sd.line((sx + sr * 1.3 * math.cos(a), sy + sr * 1.3 * math.sin(a), sx + sr * 1.65 * math.cos(a),
                 sy + sr * 1.65 * math.sin(a)), fill=(255, 214, 90, 255), width=int(u * 0.012))
    glow(img, sun, (0.03,))
    # mây nhỏ rải rác
    cl = _b5_layer(W, H)
    cd = ImageDraw.Draw(cl)
    spots = [(0.72, 0.1), (0.35, 0.2), (0.85, 0.32), (0.12, 0.62), (0.8, 0.72), (0.4, 0.9), (0.15, 0.88)]
    for fx, fy in spots:
        cloud(cd, W * fx + rnd.uniform(-1, 1) * u * 0.04, H * fy, u * rnd.uniform(0.16, 0.26), (255, 255, 255, 235))
    sh = _b5_layer(W, H)
    sh.paste((120, 160, 200, 60), (0, 0), cl.getchannel("A"))
    img.alpha_composite(sh.filter(ImageFilter.GaussianBlur(u * 0.01)), (0, int(u * 0.01)))
    img.alpha_composite(cl)
    # chim nhỏ
    d = ImageDraw.Draw(img)
    for _ in range(3):
        bx, by, bs = W * rnd.uniform(0.45, 0.65), H * rnd.uniform(0.06, 0.14), u * rnd.uniform(0.015, 0.025)
        d.arc((bx - bs, by - bs * 0.5, bx, by + bs * 0.5), 200, 340, fill="#4a6a8a", width=max(2, int(u * 0.003)))
        d.arc((bx, by - bs * 0.5, bx + bs, by + bs * 0.5), 200, 340, fill="#4a6a8a", width=max(2, int(u * 0.003)))
    # tấm mây lớn chứa chữ
    font = find_font("round")
    pw = W * (0.78 if H > W else 0.62)
    pad = u * 0.07
    f, tw, th, _ = measure_text(text, (0, 0, int(pw - 2 * pad), int(H * 0.5)), font, int(u * 0.09), 1.2)
    ph = th + 2 * pad
    x0, y0 = (W - pw) / 2, (H - ph) / 2 + H * 0.02
    panel = (x0, y0, x0 + pw, y0 + ph)
    big = _b5_layer(W, H)
    bd = ImageDraw.Draw(big)
    rb = u * 0.07
    bd.rounded_rectangle(panel, int(rb), fill=(255, 255, 255, 255))
    n = max(3, int(pw / (rb * 1.5)))
    for i in range(n):
        cx = x0 + rb * 0.6 + (pw - rb * 1.2) * i / (n - 1)
        r1, r2 = rb * rnd.uniform(0.85, 1.25), rb * rnd.uniform(0.6, 0.9)
        bd.ellipse((cx - r1, y0 + rb * 0.3 - r1, cx + r1, y0 + rb * 0.3 + r1), fill="#ffffff")
        bd.ellipse((cx - r2, panel[3] - rb * 0.25 - r2, cx + r2, panel[3] - rb * 0.25 + r2), fill="#ffffff")
    s2 = _b5_layer(W, H)
    s2.paste((90, 130, 180, 70), (0, 0), big.getchannel("A"))
    img.alpha_composite(s2.filter(ImageFilter.GaussianBlur(u * 0.02)), (0, int(u * 0.02)))
    img.alpha_composite(big)
    d = ImageDraw.Draw(img)
    for sx2, sy2 in ((panel[0] + pad * 0.5, panel[1] + pad * 0.2), (panel[2] - pad * 0.5, panel[3] - pad * 0.2)):
        sparkle(d, sx2, sy2, u * 0.022, "#ffd35a")
    draw_text_block(img, text, (x0 + pad, y0 + pad, x0 + pw - pad, y0 + ph - pad), font, fg, align="center",
                    max_size=f.size, spacing=1.2)
    return img


def tpl_aurora(text, W, H, rnd):
    """Cực quang xanh lục/tím uốn lượn trên nền đêm, dãy núi tối, chữ trắng phát sáng."""
    u = min(W, H)
    img = gradient((W, H), ["#02040e", "#061428", "#0a2236", "#081521"])
    _b5_stars(img, rnd, W * H // 3000, rmax=u * 0.0022)
    cols = rnd.choice([["#3dffb2", "#2fd2ff", "#b06bff"], ["#56ff8a", "#1fe0c0", "#ff6bd0"],
                       ["#7dff6b", "#36d7ff", "#7b6bff"]])
    k = 4
    w, h = W // k, H // k
    au = _b5_layer(w, h)
    d = ImageDraw.Draw(au)
    for b, col in enumerate(cols):
        base = h * (0.18 + 0.12 * b) if H > W else h * (0.15 + 0.13 * b)
        amp, length, ph = h * rnd.uniform(0.04, 0.08), w * rnd.uniform(0.5, 0.9), rnd.uniform(0, 6)
        L = h * rnd.uniform(0.16, 0.26)
        for x in range(w):
            y = base + amp * math.sin(x / length * 2 * math.pi + ph) + amp * 0.4 * math.sin(x / length * 7 + ph)
            ray = 0.55 + 0.45 * math.sin(x * 0.35 + ph) * math.sin(x * 0.09)
            for j in range(8):
                a = int(170 * ray * (1 - j / 8) ** 1.6)
                d.line((x, y - L * j / 8, x, y - L * (j + 1) / 8), fill=rgba(col, a))
            d.line((x, y, x, y + L * 0.12), fill=rgba(mix(col, "#ffffff", 0.3), int(200 * ray)))
    au = au.filter(ImageFilter.GaussianBlur(1.2)).resize((W, H), Image.BICUBIC)
    img.alpha_composite(au.filter(ImageFilter.GaussianBlur(u * 0.03)))
    img.alpha_composite(au)
    # núi
    for i, col in enumerate(["#0b1a2a", "#050b14"]):
        pts, x = [(-10, H)], -10
        top = H * (0.8 + 0.06 * i)
        while x < W + 10:
            pts.append((x, top - rnd.uniform(0, H * 0.09)))
            x += rnd.uniform(u * 0.06, u * 0.16)
        pts += [(W + 10, top), (W + 10, H)]
        ml = _b5_layer(W, H)
        ImageDraw.Draw(ml).polygon(pts, fill=col)
        img.alpha_composite(ml)
    tb = (W * 0.1, H * 0.34, W * 0.9, H * 0.74) if H > W else (W * 0.14, H * 0.3, W * 0.86, H * 0.76)
    glow_text(img, text, tb, find_font("round"), cols[0], core="#ffffff", align="center",
              max_size=int(u * 0.09), spacing=1.2, radii=(0.025, 0.008))
    return img


def tpl_ocean(text, W, H, rnd):
    """Biển hoàng hôn: mặt trời chạm chân trời, nhiều lớp sóng bọt trắng, chữ trên nền trời."""
    u = min(W, H)
    sky, sea, sun_c, fg = rnd.choice([
        (["#ffd6a5", "#ffb4a2", "#e5989b"], ["#5fa8d3", "#1b4965"], "#fff1c1", "#5a2a3a"),
        (["#bde0fe", "#e2f0ff", "#fff6e6"], ["#48cae4", "#023e8a"], "#ffe08a", "#123a6b"),
        (["#ffcad4", "#f4acb7", "#cdb4db"], ["#7aa6c2", "#2a4d6e"], "#fff3d6", "#4a2545"),
    ])
    hz = H * 0.64
    img = gradient((W, H), sky)
    sx, sr = W * 0.5, u * 0.14
    sun = Image.new("RGBA", (W, H), rgba(sun_c, 0))
    ImageDraw.Draw(sun).ellipse((sx - sr, hz - sr * 0.8, sx + sr, hz + sr * 1.2), fill=rgba(sun_c, 255))
    glow(img, sun, (0.06, 0.02))
    sea_img = gradient((W, int(H - hz) + 1), sea)
    img.paste(sea_img, (0, int(hz)))
    # vệt nắng trên mặt nước
    d = ImageDraw.Draw(img)
    for i in range(10):
        y = hz + (i + 1) * H * 0.012
        hw = sr * (1 - i / 12) * rnd.uniform(0.6, 1.0)
        d.line((sx - hw, y, sx + hw, y), fill=mix(sun_c, sea[0], i / 12), width=max(2, int(u * 0.004)))
    # mòng biển
    for _ in range(3):
        bx, by, bs = W * rnd.uniform(0.72, 0.92), hz - H * rnd.uniform(0.03, 0.08), u * rnd.uniform(0.018, 0.03)
        for x0 in (bx - bs, bx):
            d.arc((x0, by - bs * 0.4, x0 + bs, by + bs * 0.4), 200, 340, fill=fg, width=max(2, int(u * 0.004)))
    # các lớp sóng
    n = 5
    for i in range(n):
        t = (i + 1) / n
        y = hz + (H - hz) * (0.12 + 0.8 * t * t)
        col = mix(sea[0], sea[1], 0.25 + 0.6 * t)
        amp, length = u * (0.012 + 0.02 * t), W * rnd.uniform(0.3, 0.5)
        ph = rnd.uniform(0, 6)
        wl = _b5_layer(W, H)
        wd = ImageDraw.Draw(wl)
        wd.polygon(_b5_wave_pts(W, y, amp, length, ph, bottom=H + 5), fill=col)
        wd.line(_b5_wave_pts(W, y, amp, length, ph), fill=(255, 255, 255, 210), width=max(2, int(u * (0.004 + 0.006 * t))),
                joint="curve")
        img.alpha_composite(wl)
    tb = (W * 0.1, H * 0.1, W * 0.9, hz - H * 0.1) if H > W else (W * 0.14, H * 0.08, W * 0.86, hz - H * 0.12)
    draw_text_block(img, text, tb, find_font("serif"), fg, align="center", max_size=int(u * 0.09), spacing=1.25)
    return img


def tpl_blueprint(text, W, H, rnd):
    """Bản vẽ kỹ thuật nền xanh: lưới, khung tên, đường kích thước, compa; chữ mono in hoa trắng."""
    u = min(W, H)
    bg = rnd.choice(["#1c4f8c", "#173f78", "#20579a"])
    img = Image.new("RGBA", (W, H), bg)
    lay = _b5_layer(W, H)
    d = ImageDraw.Draw(lay)
    g = int(u * 0.025)
    grid(d, (0, 0, W, H), g, (255, 255, 255, 28), 1)
    grid(d, (0, 0, W, H), g * 5, (255, 255, 255, 60), 2)
    img.alpha_composite(lay)
    line = (230, 240, 255, 230)
    lay = _b5_layer(W, H)
    d = ImageDraw.Draw(lay)
    m = u * 0.05
    d.rectangle((m, m, W - m, H - m), outline=line, width=max(3, int(u * 0.004)))
    d.rectangle((m + u * 0.012, m + u * 0.012, W - m - u * 0.012, H - m - u * 0.012), outline=line, width=1)
    mono = find_font("mono")
    # khung tên góc phải dưới
    tw, th = u * 0.5, u * 0.17
    tbx = (W - m - u * 0.012 - tw, H - m - u * 0.012 - th, W - m - u * 0.012, H - m - u * 0.012)
    d.rectangle(tbx, outline=line, width=2)
    rows = ["BẢN VẼ: KÊNH VŨ TRỤ", f"SỐ: {rnd.randint(1, 99):02d}-{rnd.randint(100, 999)}",
            "NGÀY: " + datetime.date.today().strftime("%d/%m/%Y"), "TỶ LỆ: 1:1"]
    for i, r in enumerate(rows):
        y = tbx[1] + th * i / 4
        if i:
            d.line((tbx[0], y, tbx[2], y), fill=line, width=1)
        label(d, (tbx[0] + u * 0.015, y + th / 8), r, "mono", th * 0.12, line, "lm")
    # compa / vòng tròn kỹ thuật góc trái trên
    cx, cy, r = m + u * 0.16, m + u * 0.16, u * 0.1
    d.ellipse((cx - r, cy - r, cx + r, cy + r), outline=line, width=2)
    d.ellipse((cx - r * 0.6, cy - r * 0.6, cx + r * 0.6, cy + r * 0.6), outline=(230, 240, 255, 140), width=1)
    dashed(d, (cx - r * 1.4, cy), (cx + r * 1.4, cy), int(u * 0.012), int(u * 0.006), line, 1)
    dashed(d, (cx, cy - r * 1.4), (cx, cy + r * 1.4), int(u * 0.012), int(u * 0.006), line, 1)
    label(d, (cx + r * 0.75, cy - r * 0.95), f"R{rnd.randint(20, 90)}", "mono", u * 0.022, line, "lb")
    # vùng chữ + đường kích thước
    tb = (W * 0.14, H * 0.26, W * 0.86, H * 0.76) if H > W else (W * 0.18, H * 0.3, W * 0.78, H * 0.74)
    f, w_, h_, _ = measure_text(text, tb, mono, int(u * 0.075), 1.3, upper=True)
    bx0, by0 = tb[0], (tb[1] + tb[3] - h_) / 2
    bx1, by1 = bx0 + w_, by0 + h_
    a = u * 0.012

    def dim(p0, p1, txt, vertical=False):
        d.line((*p0, *p1), fill=line, width=2)
        for (x, y), s in ((p0, 1), (p1, -1)):
            if vertical:
                d.polygon([(x, y), (x - a * 0.5, y + s * a * 1.4), (x + a * 0.5, y + s * a * 1.4)], fill=line)
            else:
                d.polygon([(x, y), (x + s * a * 1.4, y - a * 0.5), (x + s * a * 1.4, y + a * 0.5)], fill=line)
        mx, my = (p0[0] + p1[0]) / 2, (p0[1] + p1[1]) / 2
        fnt = load_font(mono, max(8, int(u * 0.022)))
        tl = fnt.getlength(txt) + u * 0.02
        if vertical:
            d.rectangle((mx - u * 0.02, my - tl / 2, mx + u * 0.02, my + tl / 2), fill=bg)
            lab = Image.new("RGBA", (int(tl), int(u * 0.04)), (0, 0, 0, 0))
            ImageDraw.Draw(lab).text((tl / 2, u * 0.02), txt, font=fnt, fill=line, anchor="mm")
            paste_rotated(lay, lab, (mx, my), 90)
        else:
            d.rectangle((mx - tl / 2, my - u * 0.02, mx + tl / 2, my + u * 0.02), fill=bg)
            d.text((mx, my), txt, font=fnt, fill=line, anchor="mm")

    oy, ox = by0 - u * 0.05, bx0 - u * 0.05
    for x in (bx0, bx1):
        d.line((x, oy - a, x, by0 - a), fill=(230, 240, 255, 150), width=1)
    for y in (by0, by1):
        d.line((ox - a, y, bx0 - a, y), fill=(230, 240, 255, 150), width=1)
    dim((bx0, oy), (bx1, oy), f"{int(w_)} mm")
    dim((ox, by0), (ox, by1), f"{int(h_)} mm", vertical=True)
    img.alpha_composite(lay)
    draw_text_block(img, text, (bx0, by0, bx1, by1), mono, "#f2f7ff", align="left", upper=True,
                    max_size=f.size, spacing=1.3)
    return img


def tpl_lixi(text, W, H, rnd):
    """Bao lì xì Tết đỏ viền vàng, nắp gập với dấu tròn chữ LỘC, hoa mai rơi, chữ vàng."""
    u = min(W, H)
    red, dark, gold = rnd.choice([("#d7262e", "#9e1219", "#ffd36b"), ("#c8102e", "#860a1c", "#f7c948"),
                                  ("#e03a3e", "#a3161c", "#ffdc80")])
    img = gradient((W, H), [mix(dark, "#000000", 0.25), dark, mix(dark, "#000000", 0.35)])
    # hoạ tiết đồng xu mờ
    lay = _b5_layer(W, H)
    d = ImageDraw.Draw(lay)
    gap = int(u * 0.12)
    for j, y in enumerate(range(0, H + gap, gap)):
        for x in range(-gap // 2 * (j % 2), W + gap, gap):
            r = gap * 0.28
            d.ellipse((x - r, y - r, x + r, y + r), outline=rgba(gold, 40), width=max(2, int(u * 0.003)))
            d.rectangle((x - r * 0.3, y - r * 0.3, x + r * 0.3, y + r * 0.3), outline=rgba(gold, 40), width=2)
    img.alpha_composite(lay)
    # bao lì xì
    env = (W * 0.1, H * 0.05, W * 0.9, H * 0.95) if H > W else (W * 0.17, H * 0.05, W * 0.83, H * 0.95)
    x0, y0, x1, y1 = env
    ew, eh = x1 - x0, y1 - y0
    shadow(img, env, int(u * 0.03), offset=(0, int(u * 0.02)), blur=int(u * 0.03), alpha=140)
    d = ImageDraw.Draw(img)
    rad = int(u * 0.03)
    d.rounded_rectangle(env, rad, fill=red)
    tip = y0 + eh * (0.3 if H > W else 0.27)
    flap = [(x0, y0 + rad), (x0 + rad, y0), (x1 - rad, y0), (x1, y0 + rad), ((x0 + x1) / 2, tip)]
    d.polygon(flap, fill=mix(red, dark, 0.45))
    lw = max(3, int(u * 0.005))
    d.line([(x0 + lw, y0 + rad), ((x0 + x1) / 2, tip), (x1 - lw, y0 + rad)], fill=gold, width=lw)
    m = u * 0.03
    d.rounded_rectangle((x0 + m, y0 + m, x1 - m, y1 - m), int(rad * 0.6), outline=gold, width=lw)
    # góc vân mây vàng
    for cx, cy, s in ((x0 + m, y1 - m, 1), (x1 - m, y1 - m, -1)):
        for k in range(3):
            rr = u * (0.03 + 0.025 * k)
            d.arc((cx - rr, cy - rr, cx + rr, cy + rr), 270 if s > 0 else 180, 360 if s > 0 else 270, fill=gold,
                  width=max(2, int(u * 0.004)))
    # dấu tròn LỘC
    sr = u * (0.1 if H > W else 0.08)
    sx, sy = (x0 + x1) / 2, tip
    seal = Image.new("RGBA", (W, H), rgba(gold, 0))
    ImageDraw.Draw(seal).ellipse((sx - sr, sy - sr, sx + sr, sy + sr), fill=rgba(gold, 255))
    glow(img, seal, (0.03,))
    d = ImageDraw.Draw(img)
    d.ellipse((sx - sr * 0.84, sy - sr * 0.84, sx + sr * 0.84, sy + sr * 0.84), outline=red, width=max(2, int(u * 0.004)))
    label(d, (sx, sy), "LỘC", "serif", sr * 0.62, red, "mm")
    # hoa mai
    fl = _b5_layer(W, H)
    fd = ImageDraw.Draw(fl)
    for _ in range(14):
        fx, fy = rnd.uniform(0, W), rnd.uniform(0, H)
        if x0 < fx < x1 and y0 < fy < y1:
            fx = x0 - rnd.uniform(0, W * 0.08) if fx < W / 2 else x1 + rnd.uniform(0, W * 0.08)
        _b5_flower(fd, fx, fy, u * rnd.uniform(0.02, 0.04), rgba("#ffd84a", 235), rgba("#e0701a", 255))
    img.alpha_composite(fl)
    d = ImageDraw.Draw(img)
    label(d, ((x0 + x1) / 2, y1 - m - eh * 0.06), "AN KHANG THỊNH VƯỢNG", "serif", u * 0.032, gold, "mm")
    tb = (x0 + ew * 0.12, sy + sr * 1.35, x1 - ew * 0.12, y1 - m - eh * 0.12)
    draw_text_block(img, text, tb, find_font("black"), gold, align="center", max_size=int(u * 0.08), spacing=1.22)
    return img


def tpl_enso(text, W, H, rnd):
    """Thiền: vòng tròn mực enso trên giấy gạo, dấu triện đỏ, chữ mực đen ở giữa vòng."""
    u = min(W, H)
    paper = rnd.choice([(242, 235, 218), (238, 232, 220), (245, 239, 226)])
    img = noise_texture((W, H), paper, amount=10, seed=rnd.random())
    ink = rnd.choice([(28, 26, 24), (35, 32, 40), (40, 30, 26)])
    cx, cy, r = W / 2, H * 0.45 if H > W else H / 2, u * 0.4
    hw = u * 0.035
    lay = _b5_layer(W, H)
    d = ImageDraw.Draw(lay)
    a0, sweep = rnd.uniform(-150, -100), rnd.uniform(305, 335)
    K, steps = 28, 260
    for b in range(K):
        off = (b / (K - 1) - 0.5) * 2
        end = rnd.uniform(0.72, 1.0) if abs(off) > 0.3 else rnd.uniform(0.88, 1.0)
        pts = []
        for i in range(int(steps * end)):
            t = i / steps
            w = hw * (0.55 + 0.45 * math.sin(math.pi * min(1, t * 1.6))) * (1 - 0.4 * t)
            rr = r + off * w + u * 0.008 * math.sin(t * 9)
            a = math.radians(a0 + sweep * t)
            pts.append((cx + rr * math.cos(a), cy + rr * math.sin(a)))
        if len(pts) > 1:
            d.line(pts, fill=ink + (rnd.randint(170, 240),), width=max(2, int(hw * 2 / K * 1.9)), joint="curve")
    # giọt mực đầu nét
    a = math.radians(a0)
    d.ellipse((cx + r * math.cos(a) - hw * 0.8, cy + r * math.sin(a) - hw * 0.8,
               cx + r * math.cos(a) + hw * 0.8, cy + r * math.sin(a) + hw * 0.8), fill=ink + (230,))
    lay = _b5_texture_alpha(lay.filter(ImageFilter.GaussianBlur(1)), k=1.2, base=225)
    img.alpha_composite(lay)
    # dấu triện đỏ
    s = u * 0.075
    stamp = Image.new("RGBA", (int(s), int(s)), (0, 0, 0, 0))
    sd = ImageDraw.Draw(stamp)
    sd.rounded_rectangle((0, 0, s - 1, s - 1), int(s * 0.12), fill=(178, 34, 34, 235))
    sd.rectangle((s * 0.1, s * 0.1, s * 0.9, s * 0.9), outline=(250, 235, 220, 255), width=max(2, int(s * 0.04)))
    sd.text((s / 2, s / 2), "TÂM", font=load_font(find_font("serif"), max(8, int(s * 0.3))), fill=(250, 235, 220, 255),
            anchor="mm")
    stamp = _b5_texture_alpha(stamp, k=1.0, base=235)
    px, py = (cx + r * 0.95, cy + r * 0.95) if H > W else (cx + r * 1.35, cy + r * 0.8)
    paste_rotated(img, stamp, (px, py), rnd.uniform(-6, 6))
    d = ImageDraw.Draw(img)
    label(d, (px - s * 0.75, py), "an nhiên", "script", u * 0.045, ink, "rm")
    side = r * 1.25
    tb = (cx - side / 2, cy - side / 2, cx + side / 2, cy + side / 2)
    draw_text_block(img, text, tb, find_font("book"), ink, align="center", max_size=int(u * 0.075), spacing=1.3)
    return img


def tpl_confetti(text, W, H, rnd):
    """Pháo giấy đủ màu bay quanh tấm thẻ trắng bo góc, chữ đậm căn giữa."""
    u = min(W, H)
    bg, fg = rnd.choice([("#fff4e0", "#2b2240"), ("#ffe6ef", "#3a1f3d"), ("#e8f4ff", "#1d2f52"),
                         (("#2b2240", "#4b2d6b"), "#2b2240")])
    cols = ["#ff5d8f", "#ffb703", "#3ec1d3", "#8f6bff", "#5bd17a", "#ff7b39"]
    img = gradient((W, H), bg) if isinstance(bg, tuple) else Image.new("RGBA", (W, H), bg)
    font = find_font("black")
    cw = W * (0.8 if H > W else 0.56)
    pad = u * 0.07
    f, tw, th, _ = measure_text(text, (0, 0, int(cw - 2 * pad), int(H * 0.55)), font, int(u * 0.085), 1.2)
    ch = th + 2 * pad + u * 0.06
    card = ((W - cw) / 2, (H - ch) / 2, (W + cw) / 2, (H + ch) / 2)

    def pieces(d, n, avoid):
        for _ in range(n):
            x, y = rnd.uniform(-20, W + 20), rnd.uniform(-20, H + 20)
            if avoid and card[0] - u * 0.02 < x < card[2] + u * 0.02 and card[1] - u * 0.02 < y < card[3] + u * 0.02:
                continue
            c, s, kind = rnd.choice(cols), u * rnd.uniform(0.012, 0.03), rnd.random()
            if kind < 0.4:
                d.polygon(rot_rect_points(x, y, s * 2, s * 0.9, rnd.uniform(0, 180)), fill=c)
            elif kind < 0.6:
                d.ellipse((x - s * 0.6, y - s * 0.6, x + s * 0.6, y + s * 0.6), fill=c)
            elif kind < 0.75:
                a = rnd.uniform(0, 6.28)
                d.polygon([(x + s * math.cos(a + k * 2.09), y + s * math.sin(a + k * 2.09)) for k in range(3)], fill=c)
            elif kind < 0.9:
                a, L = rnd.uniform(0, 6.28), s * 4
                pts = [(x + math.cos(a) * L * t - math.sin(a) * s * 0.5 * math.sin(t * 12),
                        y + math.sin(a) * L * t + math.cos(a) * s * 0.5 * math.sin(t * 12)) for t in
                       (i / 20 for i in range(21))]
                d.line(pts, fill=c, width=max(2, int(s * 0.35)), joint="curve")
            else:
                sparkle(d, x, y, s * 1.1, c)

    pieces(ImageDraw.Draw(img), int(W * H / 5000), True)
    shadow(img, card, int(u * 0.04), offset=(0, int(u * 0.02)), blur=int(u * 0.03), alpha=80)
    d = ImageDraw.Draw(img)
    d.rounded_rectangle(card, int(u * 0.04), fill="#ffffff")
    tag = rnd.choice(["TIN VUI!", "YAY!", "CHÚC MỪNG!"])
    tf = load_font(find_font("comic"), int(u * 0.05))
    tl = tf.getlength(tag) + u * 0.06
    tx = (W - tl) / 2
    d.rounded_rectangle((tx, card[1] - u * 0.035, tx + tl, card[1] + u * 0.035), int(u * 0.035), fill=rnd.choice(cols))
    d.text((W / 2, card[1]), tag, font=tf, fill="#ffffff", anchor="mm")
    # vài mảnh rơi đè lên mép thẻ
    over = _b5_layer(W, H)
    od = ImageDraw.Draw(over)
    for x, y in ((card[0], card[1] + ch * 0.3), (card[2], card[3] - ch * 0.25), (card[0] + cw * 0.2, card[3])):
        od.polygon(rot_rect_points(x, y, u * 0.04, u * 0.018, rnd.uniform(0, 180)), fill=rnd.choice(cols))
    img.alpha_composite(over)
    draw_text_block(img, text, (card[0] + pad, card[1] + pad + u * 0.03, card[2] - pad, card[3] - pad), font, fg,
                    align="center", max_size=f.size, spacing=1.2)
    return img


def tpl_heart_frame(text, W, H, rnd):
    """Khung trái tim lớn viền đôi trên nền hồng, tim nhỏ rải rác, chữ tròn bên trong tim."""
    u = min(W, H)
    bg, line, fg = rnd.choice([(["#ffd6e4", "#ffb0c8"], "#e8467c", "#b3164f"),
                               (["#ffe3d6", "#ffc0b0"], "#e0604a", "#a33325"),
                               (["#efe0ff", "#d9c2ff"], "#9b5de5", "#5a2a9c")])
    img = gradient((W, H), bg, angle=30)
    lay = _b5_layer(W, H)
    d = ImageDraw.Draw(lay)
    dots(d, (0, 0, W, H), int(u * 0.06), max(2, int(u * 0.004)), (255, 255, 255, 120))
    for _ in range(18):
        x, y, s = rnd.uniform(0, W), rnd.uniform(0, H), u * rnd.uniform(0.03, 0.08)
        d.polygon(heart_points(x, y, s, 40), fill=(255, 255, 255, rnd.randint(110, 200)) if rnd.random() < 0.6
                  else rgba(line, rnd.randint(90, 170)))
    img.alpha_composite(lay)
    s = min(W * 0.92 / 0.94, H * (0.78 if H > W else 0.86) / 0.85)
    cx, cy = W / 2, H / 2 - s * 0.075 + (H * 0.03 if H > W else H * 0.02)
    pts = heart_points(cx, cy, s, 180)
    sh = _b5_layer(W, H)
    ImageDraw.Draw(sh).polygon([(x, y + u * 0.02) for x, y in pts], fill=rgba(line, 90))
    img.alpha_composite(sh.filter(ImageFilter.GaussianBlur(u * 0.025)))
    d = ImageDraw.Draw(img)
    d.polygon(pts, fill="#fffafc")
    d.line(pts + pts[:1], fill=line, width=max(4, int(u * 0.012)), joint="curve")
    inner = heart_points(cx, cy + s * 0.012, s * 0.93, 180)
    for i in range(0, len(inner), 3):
        a, b = inner[i], inner[(i + 1) % len(inner)]
        d.line((*a, *b), fill=mix(line, "#ffffff", 0.35), width=max(2, int(u * 0.004)))
    for k, (x, y) in enumerate(((cx - s * 0.24, cy - s * 0.2), (cx + s * 0.24, cy - s * 0.2))):
        sparkle(d, x, y, u * 0.02, mix(line, "#ffffff", 0.2))
    label(d, (cx, cy - s * 0.15), rnd.choice(["thương gửi", "gửi bạn", "love note"]), "script", u * 0.05, line, "mm")
    tb = (cx - s * 0.26, cy - s * 0.11, cx + s * 0.26, cy + s * 0.18)
    draw_text_block(img, text, tb, find_font("round"), fg, align="center", max_size=int(u * 0.075), spacing=1.15)
    return img


def tpl_crayon(text, W, H, rnd):
    """Tranh sáp màu trẻ con: mặt trời, cầu vồng, mây, cỏ hoa; chữ sáp nhiều màu."""
    u = min(W, H)
    img = noise_texture((W, H), rnd.choice([(255, 252, 242), (250, 248, 240)]), amount=6, seed=rnd.random())
    lay = _b5_layer(W, H)
    d = ImageDraw.Draw(lay)
    w = u * 0.014
    # mặt trời góc trái
    sx, sy, sr = W * 0.16, H * 0.09 if H > W else H * 0.17, u * 0.075
    for k in range(int(sr * 2 / (w * 0.6))):
        yy = sy - sr + k * w * 0.6
        dx = math.sqrt(max(0, sr * sr - (yy - sy) ** 2))
        _b5_crayon(d, [(sx - dx, yy), (sx + dx, yy + w * 0.3)], "#ffc93c", w, rnd, 1)
    _b5_crayon(d, _b5_circle_pts(sx, sy, sr, 30, w * 0.3, rnd), "#ff9f1c", w, rnd)
    for k in range(10):
        a = math.radians(k * 36 + 10)
        _b5_crayon(d, [(sx + sr * 1.3 * math.cos(a), sy + sr * 1.3 * math.sin(a)),
                    (sx + sr * 1.8 * math.cos(a), sy + sr * 1.8 * math.sin(a))], "#ff9f1c", w, rnd)
    # cầu vồng góc phải
    rx, ry = W * 0.86, H * 0.17 if H > W else H * 0.3
    for i, c in enumerate(["#ff595e", "#ff924c", "#ffca3a", "#8ac926", "#1982c4", "#6a4c93"]):
        _b5_crayon(d, _b5_circle_pts(rx, ry, u * (0.17 - i * 0.022), 24, w * 0.2, rnd, 180, 180), c, w * 1.4, rnd)
    # mây viền
    for fx, fy in ((0.45, 0.07), (0.62, 0.13)) if H > W else ((0.42, 0.1), (0.6, 0.18)):
        x, y, s = W * fx, H * fy, u * 0.14
        for dx, dy, r in ((-0.25, 0.05, 0.2), (0, -0.08, 0.26), (0.25, 0.05, 0.2)):
            _b5_crayon(d, _b5_circle_pts(x + dx * s, y + dy * s, r * s, 18, w * 0.2, rnd, 160, 220), "#5aa9e6", w, rnd)
    # cỏ + hoa
    gy = H * 0.9
    x = -10
    while x < W + 10:
        hgt = u * rnd.uniform(0.03, 0.06)
        _b5_crayon(d, [(x, H), (x + u * 0.008, gy - hgt), (x + u * 0.02, H)], rnd.choice(["#52b788", "#74c69d", "#40916c"]),
                w, rnd, 2)
        x += u * 0.018
    for _ in range(int(W / (u * 0.18))):
        fx, fy = rnd.uniform(W * 0.04, W * 0.96), gy - u * rnd.uniform(0.06, 0.1)
        _b5_crayon(d, [(fx, fy), (fx + rnd.uniform(-5, 5), H)], "#2d6a4f", w, rnd, 2)
        c = rnd.choice(["#ff595e", "#ff70a6", "#ffca3a", "#9b5de5"])
        for k in range(5):
            a = math.radians(k * 72)
            _b5_crayon(d, _b5_circle_pts(fx + u * 0.018 * math.cos(a), fy + u * 0.018 * math.sin(a), u * 0.014, 10,
                                   w * 0.2, rnd), c, w * 0.8, rnd, 2)
    img.alpha_composite(_b5_texture_alpha(lay, k=1.8, base=190))
    palette = ["#e63946", "#1d70b8", "#2a9d8f", "#9b5de5", "#f3722c"]
    idx = [rnd.randrange(len(palette))]

    def word_color(_img, x, baseline, ww, font):
        idx[0] = (idx[0] + 1) % len(palette)
        return rgb(palette[idx[0]])

    tb = (W * 0.1, H * 0.25, W * 0.9, H * 0.8) if H > W else (W * 0.12, H * 0.34, W * 0.88, H * 0.8)
    rough_text(img, text, tb, find_font("marker"), palette[0], k=1.3, align="center", max_size=int(u * 0.09),
               spacing=1.25, word_bg=word_color)
    return img


def tpl_zodiac_wheel(text, W, H, rnd):
    """Vòng 12 con giáp (Tý...Hợi) viền vàng, con giáp nhắc trong text được tô sáng; chữ bên dưới/bên phải."""
    u = min(W, H)
    top, bot, ring_c = rnd.choice([("#5c0f1a", "#24050a", "#2f070d"), ("#14183d", "#070918", "#0c1030"),
                                   ("#123d33", "#04140f", "#082a22")])
    gold = "#f0c75e"
    cream = "#fbeccb"
    img = gradient((W, H), [top, bot])
    _b5_stars(img, rnd, W * H // 7000, color=gold, rmax=u * 0.0025)
    if H > W:
        cx, cy, R = W / 2, H * 0.3, W * 0.42
        tb = (W * 0.1, cy + R * 1.2, W * 0.9, H * 0.93)
    else:
        cx, cy, R = W * 0.28, H / 2, H * 0.41
        tb = (W * 0.53, H * 0.14, W * 0.93, H * 0.86)
    hit = zodiac_index(text)
    lw = max(2, int(u * 0.004))
    # quầng sáng sau vòng
    halo = Image.new("RGBA", (W, H), rgba(gold, 0))
    ImageDraw.Draw(halo).ellipse((cx - R, cy - R, cx + R, cy + R), fill=rgba(gold, 60))
    img.alpha_composite(halo.filter(ImageFilter.GaussianBlur(u * 0.05)))
    d = ImageDraw.Draw(img)
    d.ellipse((cx - R, cy - R, cx + R, cy + R), fill=ring_c, outline=gold, width=lw * 2)
    # vạch chia độ ngoài cùng
    for k in range(72):
        a = math.radians(k * 5 - 90)
        r0 = R * (0.94 if k % 6 == 3 else 0.965)
        d.line((cx + r0 * math.cos(a), cy + r0 * math.sin(a), cx + R * 0.985 * math.cos(a), cy + R * 0.985 * math.sin(a)),
               fill=gold, width=max(1, lw // 2))
    r_out, r_in = R * 0.92, R * 0.62
    if hit is not None:
        seg = Image.new("RGBA", (W, H), rgba(gold, 0))
        sd = ImageDraw.Draw(seg)
        a0 = hit * 30 - 90 - 15
        sd.pieslice((cx - r_out, cy - r_out, cx + r_out, cy + r_out), a0, a0 + 30, fill=rgba(gold, 255))
        sd.ellipse((cx - r_in, cy - r_in, cx + r_in, cy + r_in), fill=(0, 0, 0, 0))
        glow(img, seg, (0.03, 0.01))
        d = ImageDraw.Draw(img)
    d.ellipse((cx - r_out, cy - r_out, cx + r_out, cy + r_out), outline=gold, width=lw)
    d.ellipse((cx - r_in, cy - r_in, cx + r_in, cy + r_in), outline=gold, width=lw)
    serif = find_font("serif")
    for k, name in enumerate(ZODIAC_ORDER):
        a = math.radians(k * 30 - 90 - 15)
        d.line((cx + r_in * math.cos(a), cy + r_in * math.sin(a), cx + r_out * math.cos(a), cy + r_out * math.sin(a)),
               fill=gold, width=lw)
        a = math.radians(k * 30 - 90)
        rm = (r_out + r_in) / 2
        on = k == hit
        label(d, (cx + rm * math.cos(a), cy + rm * math.sin(a)), name, "serif", R * (0.115 if on else 0.095),
              top if on else cream, "mm")
        dr = R * 0.018
        px, py = cx + R * 0.94 * math.cos(a), cy + R * 0.94 * math.sin(a)
        d.ellipse((px - dr, py - dr, px + dr, py + dr), fill=gold)
    # tâm vòng
    rc = R * 0.5
    d.ellipse((cx - rc, cy - rc, cx + rc, cy + rc), fill=mix(ring_c, top, 0.5), outline=gold, width=lw)
    dashed(d, (cx - rc * 0.7, cy - rc * 0.25), (cx + rc * 0.7, cy - rc * 0.25), int(u * 0.008), int(u * 0.006), gold, 1)
    for k in range(8):
        a = math.radians(k * 45)
        sparkle(d, cx + rc * 0.82 * math.cos(a), cy + rc * 0.82 * math.sin(a), R * 0.025, gold)
    if hit is not None:
        label(d, (cx, cy - rc * 0.42), "TUỔI", "serif", rc * 0.18, cream, "mm")
        label(d, (cx, cy + rc * 0.15), ZODIAC_ORDER[hit].upper(), "serif", rc * 0.42, gold, "mm")
    else:
        label(d, (cx, cy - rc * 0.42), "VŨ TRỤ", "serif", rc * 0.16, cream, "mm")
        label(d, (cx, cy + rc * 0.05), "12", "serif", rc * 0.45, gold, "mm")
        label(d, (cx, cy + rc * 0.5), "CON GIÁP", "serif", rc * 0.16, cream, "mm")
    draw_text_block(img, text, tb, find_font("serif"), cream, align="center", max_size=int(u * 0.08), spacing=1.25)
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
    "phone_notes": tpl_phone_notes,
    "chat_bubble": tpl_chat_bubble,
    "lock_screen": tpl_lock_screen,
    "social_post": tpl_social_post,
    "win95": tpl_win95,
    "terminal": tpl_terminal,
    "code_editor": tpl_code_editor,
    "browser": tpl_browser,
    "music_player": tpl_music_player,
    "y2k_error": tpl_y2k_error,
    "rpg_dialog": tpl_rpg_dialog,
    "breaking_news": tpl_breaking_news,
    "sticky_cork": tpl_sticky_cork,
    "polaroid": tpl_polaroid,
    "receipt": tpl_receipt,
    "typewriter": tpl_typewriter,
    "legal_pad": tpl_legal_pad,
    "index_card": tpl_index_card,
    "newspaper": tpl_newspaper,
    "ransom": tpl_ransom,
    "scrapbook": tpl_scrapbook,
    "book_page": tpl_book_page,
    "tear_calendar": tpl_tear_calendar,
    "love_letter": tpl_love_letter,
    "chalkboard": tpl_chalkboard,
    "whiteboard": tpl_whiteboard,
    "neon": tpl_neon,
    "movie_ticket": tpl_movie_ticket,
    "boarding_pass": tpl_boarding_pass,
    "postcard": tpl_postcard,
    "gingham": tpl_gingham,
    "polka_dot": tpl_polka_dot,
    "candy_stripes": tpl_candy_stripes,
    "checker": tpl_checker,
    "film_strip": tpl_film_strip,
    "warning_tape": tpl_warning_tape,
    "mesh_gradient": tpl_mesh_gradient,
    "glass": tpl_glass,
    "brutalist": tpl_brutalist,
    "swiss": tpl_swiss,
    "minimal_serif": tpl_minimal_serif,
    "highlighter": tpl_highlighter,
    "bold_gradient": tpl_bold_gradient,
    "retro_sunset": tpl_retro_sunset,
    "vaporwave": tpl_vaporwave,
    "y2k_sparkle": tpl_y2k_sparkle,
    "comic": tpl_comic,
    "sunburst": tpl_sunburst,
    "groovy_waves": tpl_groovy_waves,
    "tarot": tpl_tarot,
    "starry_night": tpl_starry_night,
    "cloud_sky": tpl_cloud_sky,
    "aurora": tpl_aurora,
    "ocean": tpl_ocean,
    "blueprint": tpl_blueprint,
    "lixi": tpl_lixi,
    "enso": tpl_enso,
    "confetti": tpl_confetti,
    "heart_frame": tpl_heart_frame,
    "crayon": tpl_crayon,
    "zodiac_wheel": tpl_zodiac_wheel,
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
