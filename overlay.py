"""
Chèn text kiểu TikTok lên ảnh có sẵn: mỗi dòng nằm trên 1 khung bo góc + nhãn "Claim <số>" nhỏ bên dưới.

Text lấy ngẫu nhiên từ file text (mỗi dòng 1 câu, "\\n" để xuống dòng), ảnh lấy từ thư mục (quét cả thư mục con).

Cách dùng:
    python overlay.py                                  # tarot_images + texts.txt -> output_overlay
    python overlay.py -i tarot_images -t texts.txt -o out -n 50
    python overlay.py --style red --seed 42
    python overlay.py --numbers 8888,8386,6868         # chỉ dùng các số này
"""

import argparse
import os
import random
import re
import unicodedata
from functools import lru_cache

from PIL import Image, ImageDraw, ImageFilter, ImageFont, ImageOps

# ---------------------------------------------------------------------------
# Fonts
# ---------------------------------------------------------------------------

WIN_FONTS = "/mnt/c/Windows/Fonts"
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
    "emoji": [
        f"{WIN_FONTS}/seguiemj.ttf",
        "C:/Windows/Fonts/seguiemj.ttf",
        "/usr/share/fonts/truetype/noto/NotoColorEmoji.ttf",
        "/System/Library/Fonts/Apple Color Emoji.ttc",
    ],
}


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
# Emoji + text layout
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


def read_lines(path):
    with open(path, encoding="utf-8") as f:
        lines = [unicodedata.normalize("NFC", l.strip()) for l in f]
    return [l.replace("\\n", "\n") for l in lines if l]


# ---------------------------------------------------------------------------
# Overlay
# ---------------------------------------------------------------------------

IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".webp", ".bmp"}
LUCKY_NUMBERS = ["8888", "8386", "6868", "6666", "3979", "7979", "8668", "1368", "5555", "9999", "1102", "2626"]

# (nền khung, màu chữ, viền chữ) — nền None = không khung, chữ có viền phát sáng
STYLES = {
    "red": ((226, 62, 62, 235), "#ffffff", None),
    "coral": ((238, 88, 72, 235), "#ffffff", None),
    "orange": ((243, 120, 40, 235), "#ffffff", None),
    "white": ((255, 255, 255, 240), "#111111", None),
    "glow": (None, "#ffffff", (122, 40, 200)),
}


def cover(img, W, H):
    """Crop giữa + resize để lấp đầy khung WxH."""
    return ImageOps.fit(ImageOps.exif_transpose(img).convert("RGB"), (W, H), Image.LANCZOS).convert("RGBA")


def draw_line(img, line, font, x, baseline, color, stroke=0, stroke_color=None):
    draw = ImageDraw.Draw(img)
    space = font.getlength(" ")
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


def draw_label(img, lines, font, top, style, pad_x, pad_y, gap=0):
    """Vẽ các dòng căn giữa, mỗi dòng 1 khung bo góc. Trả về toạ độ y đáy."""
    W = img.width
    bg, fg, glow = STYLES[style]
    line_h = int(font.size * 1.12)
    widths = [word_width(l, font) for l in lines]
    radius = int(font.size * 0.28)

    if bg:
        boxes = Image.new("RGBA", img.size, (0, 0, 0, 0))
        d = ImageDraw.Draw(boxes)
        for i, lw in enumerate(widths):
            y = top + i * (line_h + gap)
            d.rounded_rectangle(((W - lw) / 2 - pad_x, y, (W + lw) / 2 + pad_x, y + line_h + 2 * pad_y),
                                radius, fill=bg)
        img.alpha_composite(boxes)

    text_layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
    stroke = max(3, font.size // 9) if glow else 0
    for i, (line, lw) in enumerate(zip(lines, widths)):
        baseline = top + i * (line_h + gap) + pad_y + int(line_h * 0.5 + font.size * 0.36)
        draw_line(text_layer, line, font, (W - lw) / 2, baseline, fg, stroke, glow)
    if glow:
        # quầng sáng tím phía sau chữ
        alpha = text_layer.getchannel("A").filter(ImageFilter.MaxFilter(5))
        halo = Image.new("RGBA", img.size, glow + (0,))
        halo.putalpha(alpha.filter(ImageFilter.GaussianBlur(font.size * 0.3)))
        for _ in range(3):
            img.alpha_composite(halo)
    img.alpha_composite(text_layer)
    return top + len(lines) * (line_h + gap) - gap + 2 * pad_y


def render(photo, text, number, style, W, H, rnd):
    img = cover(photo, W, H)
    font_path = find_font("bold")
    max_w = int(W * 0.72)

    size = int(W * rnd.uniform(0.052, 0.06))
    while True:
        font = load_font(font_path, size)
        lines = wrap_text(text, font, max_w)
        if len(lines) <= 5 or size <= int(W * 0.045):
            break
        size -= 2

    pad_x, pad_y = int(size * 0.35), int(size * 0.12)
    top = int(H * rnd.uniform(0.36, 0.44))
    bottom = draw_label(img, lines, font, top, style, pad_x, pad_y, gap=-pad_y)

    claim_font = load_font(font_path, int(size * 0.85))
    draw_label(img, [f"Claim {number}"], claim_font, bottom + int(size * 0.9), style,
               int(size * 0.4), pad_y)
    return img.convert("RGB")


def find_images(folder):
    out = []
    for root, _, files in os.walk(folder):
        out += [os.path.join(root, f) for f in sorted(files) if os.path.splitext(f)[1].lower() in IMAGE_EXTS]
    return sorted(out)


def main():
    parser = argparse.ArgumentParser(description="Chèn text + Claim số ngẫu nhiên lên ảnh")
    parser.add_argument("-i", "--images", default="tarot_images", help="Thư mục ảnh (quét cả thư mục con)")
    parser.add_argument("-t", "--texts", default="texts.txt", help="File text, mỗi dòng 1 câu")
    parser.add_argument("-o", "--output", default="output_overlay", help="Thư mục lưu ảnh")
    parser.add_argument("-n", "--count", type=int, default=None, help="Số ảnh tạo (mặc định = số ảnh nguồn)")
    parser.add_argument("--size", default="1080x1920", help="Kích thước WxH")
    parser.add_argument("--style", default="random", help=f"random | {' | '.join(STYLES)}")
    parser.add_argument("--numbers", default=None,
                        help="Danh sách số cách nhau dấu phẩy (mặc định: số đẹp + số 4 chữ số ngẫu nhiên)")
    parser.add_argument("--prefix", default="#thongdiepvutru #tinhieuvutru #thongdiepcuocsong",
                        help="Tiền tố tên file")
    parser.add_argument("--seed", type=int, default=None, help="Seed để kết quả lặp lại được")
    args = parser.parse_args()

    rnd = random.Random(args.seed)
    W, H = map(int, args.size.lower().split("x"))
    texts = read_lines(args.texts)
    images = find_images(args.images)
    if not texts or not images:
        raise SystemExit(f"Không có text ({len(texts)}) hoặc ảnh ({len(images)})")
    numbers = args.numbers.split(",") if args.numbers else None

    count = args.count or len(images)
    order = []
    while len(order) < count:  # duyệt hết ảnh theo thứ tự ngẫu nhiên rồi mới lặp lại
        batch = images[:]
        rnd.shuffle(batch)
        order += batch
    os.makedirs(args.output, exist_ok=True)

    for i, path in enumerate(order[:count], 1):
        if numbers:
            number = rnd.choice(numbers).strip()
        else:
            number = rnd.choice(LUCKY_NUMBERS) if rnd.random() < 0.7 else str(rnd.randint(1000, 9999))
        style = rnd.choice(list(STYLES)) if args.style == "random" else args.style
        try:
            with Image.open(path) as photo:
                img = render(photo, rnd.choice(texts), number, style, W, H, random.Random(rnd.random()))
        except Exception as e:
            print(f"[{i}/{count}] Bỏ qua {path}: {e}")
            continue
        out = os.path.join(args.output, f"{args.prefix} ({i}).jpg")
        img.save(out, quality=92)
        print(f"[{i}/{count}] {out}")


if __name__ == "__main__":
    main()
