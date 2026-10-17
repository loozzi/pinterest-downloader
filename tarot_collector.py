"""
Thu thập ảnh chụp chủ đề tarot (bàn bói, nến, pha lê, không khí huyền bí)
từ các nguồn ảnh có API chính thức và giấy phép cho phép dùng lại.

Nguồn:
    - Openverse  : không cần key (chỉ lấy ảnh có giấy phép cho phép thương mại)
    - Pexels     : cần biến môi trường PEXELS_API_KEY
    - Unsplash   : cần biến môi trường UNSPLASH_ACCESS_KEY
    - Pixabay    : cần biến môi trường PIXABAY_API_KEY

Key có thể đặt trong file .env cạnh script (vd: PIXABAY_API_KEY=xxx).
Nguồn nào không có key sẽ tự động bị bỏ qua.
Thông tin tác giả / giấy phép của từng ảnh được ghi vào credits.csv.

Ví dụ:
    python tarot_collector.py
    python tarot_collector.py --per-query 50 --sources pexels openverse
    python tarot_collector.py --queries "tarot cards" "crystal ball"
    python tarot_collector.py --sources pixabay --crop-9x16 --per-query 100
"""

import argparse
import csv
import io
import json
import os
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed

from PIL import Image

USER_AGENT = "tarot-collector/1.0 (personal image collection script)"

DEFAULT_QUERIES = [
    "tarot cards",
    "tarot reading",
    "tarot candles",
    "crystal ball",
    "fortune teller",
    "mystic candles",
    "witchcraft altar",
    "crystals healing",
    "astrology",
    "occult",
]

CREDIT_FIELDS = [
    "file",
    "source",
    "id",
    "query",
    "author",
    "license",
    "page_url",
    "image_url",
]


def http_get(url, headers=None, timeout=20):
    """GET trả về bytes, tự thêm User-Agent"""
    request = urllib.request.Request(
        url, headers={"User-Agent": USER_AGENT, **(headers or {})}
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return response.read()


def http_get_json(url, headers=None, retries=3):
    """GET JSON, thử lại khi lỗi mạng/timeout (API đôi khi phản hồi chậm)"""
    for attempt in range(1, retries + 1):
        try:
            return json.loads(http_get(url, headers, timeout=30))
        except urllib.error.HTTPError as e:
            if e.code in (401, 403) or attempt == retries:
                raise
        except (urllib.error.URLError, TimeoutError):
            if attempt == retries:
                raise
        time.sleep(2 * attempt)


# --------------------------------------------------------------------------
# Các nguồn ảnh. Mỗi hàm search trả về list dict với các key:
#   id, image_url, author, license, page_url (+ download_ping tùy chọn)
# --------------------------------------------------------------------------


def search_openverse(query, page, key, opts):
    params = {
        "q": query,
        "license_type": "commercial",
        "page_size": 20,  # giới hạn tối đa khi không có key
        "page": page,
    }
    if opts["orientation"] == "portrait":
        params["aspect_ratio"] = "tall"
    data = http_get_json(
        "https://api.openverse.org/v1/images/?" + urllib.parse.urlencode(params)
    )
    return [
        {
            "id": item["id"],
            "image_url": item["url"],
            "author": item.get("creator") or "",
            "license": f"CC {item['license'].upper()} {item.get('license_version') or ''}".strip(),
            "page_url": item.get("foreign_landing_url") or "",
        }
        for item in data.get("results", [])
    ]


def search_pexels(query, page, key, opts):
    params = {"query": query, "per_page": 80, "page": page}
    if opts["orientation"] == "portrait":
        params["orientation"] = "portrait"
    data = http_get_json(
        "https://api.pexels.com/v1/search?" + urllib.parse.urlencode(params),
        headers={"Authorization": key},
    )
    return [
        {
            "id": item["id"],
            "image_url": item["src"]["original"],
            "author": item.get("photographer") or "",
            "license": "Pexels License",
            "page_url": item.get("url") or "",
        }
        for item in data.get("photos", [])
    ]


def search_unsplash(query, page, key, opts):
    params = {"query": query, "per_page": 30, "page": page}
    if opts["orientation"] == "portrait":
        params["orientation"] = "portrait"
    headers = {"Authorization": f"Client-ID {key}"}
    data = http_get_json(
        "https://api.unsplash.com/search/photos?" + urllib.parse.urlencode(params),
        headers=headers,
    )
    return [
        {
            "id": item["id"],
            "image_url": item["urls"]["full"],
            "author": item["user"]["name"],
            "license": "Unsplash License",
            "page_url": item["links"]["html"],
            # Hướng dẫn API của Unsplash yêu cầu gọi endpoint này khi tải ảnh
            "download_ping": (item["links"]["download_location"], headers),
        }
        for item in data.get("results", [])
    ]


def search_pixabay(query, page, key, opts):
    params = {
        "key": key,
        "q": query,
        "image_type": opts["pixabay_type"],
        "safesearch": "true",
        "per_page": 200,
        "page": page,
    }
    if opts["orientation"] == "portrait":
        params["orientation"] = "vertical"
    data = http_get_json("https://pixabay.com/api/?" + urllib.parse.urlencode(params))
    return [
        {
            "id": item["id"],
            "image_url": item["largeImageURL"],
            "author": item.get("user") or "",
            "license": "Pixabay Content License",
            "page_url": item.get("pageURL") or "",
        }
        for item in data.get("hits", [])
    ]


SOURCES = {
    # tên: (hàm search, biến môi trường chứa key hoặc None nếu không cần)
    "openverse": (search_openverse, None),
    "pexels": (search_pexels, "PEXELS_API_KEY"),
    "unsplash": (search_unsplash, "UNSPLASH_ACCESS_KEY"),
    "pixabay": (search_pixabay, "PIXABAY_API_KEY"),
}


# --------------------------------------------------------------------------


class TarotCollector:
    def __init__(
        self,
        out_dir="tarot_images",
        max_threads=5,
        min_size=600,
        orientation="portrait",
        pixabay_type="photo",
        crop_9x16=False,
    ):
        self.out_dir = out_dir
        self.max_threads = max_threads
        self.min_size = min_size
        self.crop_9x16 = crop_9x16
        # Tùy chọn truyền xuống các hàm search
        self.opts = {"orientation": orientation, "pixabay_type": pixabay_type}
        self.credits_file = os.path.join(out_dir, "credits.csv")
        # Ảnh đã bị loại (quá nhỏ, sai định dạng) - không thử lại ở lần chạy sau
        self.rejected_file = os.path.join(out_dir, "rejected.txt")
        os.makedirs(out_dir, exist_ok=True)
        self.seen = self.load_seen()

    def load_seen(self):
        """Đọc credits.csv + rejected.txt để không tải lại ảnh (theo source + id)"""
        seen = set()
        if os.path.exists(self.credits_file):
            with open(self.credits_file, newline="", encoding="utf-8") as f:
                for row in csv.DictReader(f):
                    seen.add((row["source"], row["id"]))
        if os.path.exists(self.rejected_file):
            with open(self.rejected_file, encoding="utf-8") as f:
                for line in f:
                    source, _, image_id = line.strip().partition(":")
                    if image_id:
                        seen.add((source, image_id))
        return seen

    def save_rejected(self, source, image_id):
        self.seen.add((source, str(image_id)))
        with open(self.rejected_file, "a", encoding="utf-8") as f:
            f.write(f"{source}:{image_id}\n")

    def save_credit(self, row):
        is_new = not os.path.exists(self.credits_file)
        with open(self.credits_file, "a", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=CREDIT_FIELDS)
            if is_new:
                writer.writeheader()
            writer.writerow(row)

    def collect_query(self, source, query, per_query, key, max_pages=10):
        """
        Duyệt từng trang kết quả, tải ảnh mới đến khi đủ per_query ảnh đạt yêu cầu

        Returns:
            tuple: (số ảnh tải thành công, số ảnh lỗi/bị loại)
        """
        search, _ = SOURCES[source]
        ok = failed = 0

        for page in range(1, max_pages + 1):
            try:
                results = search(query, page, key, self.opts)
            except Exception as e:
                print(f"   ⚠️ {source} lỗi ở trang {page}: {e}")
                break
            if not results:
                break

            candidates = [
                item
                for item in results
                if (source, str(item["id"])) not in self.seen
            ][: per_query - ok]

            with ThreadPoolExecutor(max_workers=self.max_threads) as executor:
                futures = {
                    executor.submit(self.download, source, query, item): item
                    for item in candidates
                }
                for future in as_completed(futures):
                    item = futures[future]
                    status, filename = future.result()
                    if filename:
                        ok += 1
                        self.record_success(source, query, item, filename)
                        print(f"   ✅ {os.path.basename(filename)} ({status[3:]})")
                    else:
                        failed += 1
                        # Lỗi mạng thì để lần sau thử lại, còn ảnh không đạt thì ghi nhớ
                        if not status.startswith("error_"):
                            self.save_rejected(source, item["id"])
                        print(f"   ❌ {item['id']}: {status[:100]}")

            if ok >= per_query:
                break
            time.sleep(0.5)  # lịch sự với API

        return ok, failed

    def record_success(self, source, query, item, filename):
        self.seen.add((source, str(item["id"])))
        self.save_credit(
            {
                "file": os.path.relpath(filename, self.out_dir),
                "source": source,
                "id": item["id"],
                "query": query,
                "author": item["author"],
                "license": item["license"],
                "page_url": item["page_url"],
                "image_url": item["image_url"],
            }
        )

    def download(self, source, query, item):
        """
        Tải một ảnh, giữ nguyên dữ liệu gốc (trừ khi bật cắt 9:16).
        Trả về (status, filename)
        """
        try:
            if "download_ping" in item:
                ping_url, headers = item["download_ping"]
                http_get(ping_url, headers)

            data = http_get(item["image_url"], timeout=60)
            image = Image.open(io.BytesIO(data))
            width, height = image.size
            if min(width, height) < self.min_size:
                return f"too_small_{width}x{height}", None

            ext = {"JPEG": "jpg", "PNG": "png", "WEBP": "webp"}.get(image.format)
            if not ext:
                return f"unsupported_{image.format}", None

            query_dir = os.path.join(self.out_dir, slugify(query))
            os.makedirs(query_dir, exist_ok=True)

            cropped = self.crop_9x16 and crop_to_9x16(image)
            if cropped:
                filename = os.path.join(query_dir, f"{source}_{item['id']}.jpg")
                cropped.convert("RGB").save(filename, "JPEG", quality=95)
                return f"ok_{width}x{height}→{cropped.width}x{cropped.height}", filename

            filename = os.path.join(query_dir, f"{source}_{item['id']}.{ext}")
            with open(filename, "wb") as f:
                f.write(data)  # ghi bytes gốc, không nén lại
            return f"ok_{width}x{height}", filename
        except Exception as e:
            return f"error_{e}", None

    def run(self, sources, queries, per_query):
        totals = {"ok": 0, "failed": 0}
        for source in sources:
            _, key_env = SOURCES[source]
            key = os.environ.get(key_env) if key_env else None
            if key_env and not key:
                print(f"⏭️ Bỏ qua {source}: chưa đặt biến môi trường {key_env}")
                continue

            for query in queries:
                print(f"\n🔍 [{source}] '{query}'")
                ok, failed = self.collect_query(source, query, per_query, key)
                if ok == 0 and failed == 0:
                    print("   Không có ảnh mới")
                totals["ok"] += ok
                totals["failed"] += failed

        print("\n" + "=" * 60)
        print(f"🎉 Xong: {totals['ok']} ảnh mới, {totals['failed']} lỗi/bỏ qua")
        print(f"📁 {os.path.abspath(self.out_dir)}")
        print(f"📄 Thông tin tác giả/giấy phép: {os.path.abspath(self.credits_file)}")


def slugify(text):
    return re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_")


def crop_to_9x16(image):
    """
    Cắt giữa ảnh về tỉ lệ 9:16 (khổ dọc TikTok/Reels).
    Trả về None nếu ảnh đã đúng tỉ lệ (để giữ nguyên file gốc).
    """
    width, height = image.size
    target = 9 / 16
    ratio = width / height
    if abs(ratio - target) < 0.01:
        return None
    if ratio > target:  # ảnh quá rộng -> cắt bớt hai bên
        new_width = round(height * target)
        left = (width - new_width) // 2
        return image.crop((left, 0, left + new_width, height))
    new_height = round(width / target)  # ảnh quá cao -> cắt bớt trên dưới
    top = (height - new_height) // 2
    return image.crop((0, top, width, top + new_height))


def load_dotenv(path):
    """Đọc file .env dạng KEY=VALUE (không ghi đè biến môi trường đã có)"""
    if not os.path.exists(path):
        return
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                name, value = line.split("=", 1)
                os.environ.setdefault(name.strip(), value.strip().strip("\"'"))


def main():
    parser = argparse.ArgumentParser(description="Thu thập ảnh chụp chủ đề tarot")
    parser.add_argument(
        "--sources",
        nargs="+",
        choices=list(SOURCES),
        default=list(SOURCES),
        help="Các nguồn dùng (mặc định: tất cả nguồn có key)",
    )
    parser.add_argument(
        "--queries", nargs="+", default=DEFAULT_QUERIES, help="Từ khóa (tiếng Anh)"
    )
    parser.add_argument(
        "--per-query", type=int, default=20, help="Số ảnh mới mỗi từ khóa mỗi nguồn"
    )
    parser.add_argument("--out", default="tarot_images", help="Thư mục lưu ảnh")
    parser.add_argument("--threads", type=int, default=5, help="Số luồng tải")
    parser.add_argument(
        "--min-size", type=int, default=600, help="Cạnh ngắn tối thiểu (px)"
    )
    parser.add_argument(
        "--orientation",
        choices=["portrait", "any"],
        default="portrait",
        help="Chỉ lấy ảnh dọc (mặc định) hoặc mọi hướng",
    )
    parser.add_argument(
        "--pixabay-type",
        choices=["photo", "illustration", "all"],
        default="photo",
        help="Loại ảnh Pixabay (illustration có nhiều ảnh AI/digital art hơn)",
    )
    parser.add_argument(
        "--crop-9x16",
        action="store_true",
        help="Cắt giữa ảnh về tỉ lệ 9:16 cho TikTok/Reels",
    )
    args = parser.parse_args()

    load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env"))
    collector = TarotCollector(
        args.out,
        args.threads,
        args.min_size,
        args.orientation,
        args.pixabay_type,
        args.crop_9x16,
    )
    collector.run(args.sources, args.queries, args.per_query)


if __name__ == "__main__":
    main()
