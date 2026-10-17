import hashlib
import io
import os
import time
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed

from PIL import Image
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By


class PinterestImageDownloader:
    def __init__(
        self, download_folder="pinterest_images", max_threads=5, profile_dir=None
    ):
        """
        Khởi tạo Pinterest Image Downloader

        Args:
            download_folder (str): Thư mục lưu hình ảnh tải về
            max_threads (int): Số luồng tối đa cho tải đa luồng (tối đa 5)
            profile_dir (str): Thư mục Chrome profile lưu phiên đăng nhập Pinterest
        """
        self.download_folder = download_folder
        self.max_threads = min(max_threads, 5)  # Giới hạn tối đa 5 luồng
        # Pinterest không trả kết quả tìm kiếm khi chưa đăng nhập,
        # nên dùng một Chrome profile riêng để giữ phiên đăng nhập
        self.profile_dir = os.path.abspath(
            profile_dir
            or os.path.join(os.path.dirname(os.path.abspath(__file__)), "chrome_profile")
        )
        self.create_download_folder()
        self.driver = None
        self.download_stats = {
            "total_downloaded": 0,
            "total_failed": 0,
            "total_skipped": 0,
        }

        # Lưu trữ URL và hash đã tải để tránh trùng lặp
        self.downloaded_urls = set()
        self.downloaded_hashes = set()
        self.load_downloaded_history()

        # Từ khóa tìm kiếm mặc định
        self.keywords = [
            "váy xinh",
            "thời trang",
            "nữ phối đồ",
            "outfit",
            "fashion style",
            "cute dress",
        ]

    def create_download_folder(self):
        """Tạo thư mục download nếu chưa tồn tại"""
        if not os.path.exists(self.download_folder):
            os.makedirs(self.download_folder)
            print(f"Đã tạo thư mục: {self.download_folder}")

    def load_downloaded_history(self):
        """Load lịch sử URL và hash đã tải từ file"""
        try:
            history_file = os.path.join(self.download_folder, "download_history.txt")
            if os.path.exists(history_file):
                with open(history_file, "r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if line and "|" in line:
                            url, url_hash = line.split("|", 1)
                            self.downloaded_urls.add(url)
                            self.downloaded_hashes.add(url_hash)
                print(f"📚 Đã load {len(self.downloaded_urls)} URL đã tải từ lịch sử")
        except Exception as e:
            print(f"⚠️ Không thể load lịch sử: {e}")

    def save_downloaded_url(self, url, url_hash):
        """Lưu URL và hash đã tải vào file lịch sử"""
        try:
            history_file = os.path.join(self.download_folder, "download_history.txt")
            with open(history_file, "a", encoding="utf-8") as f:
                f.write(f"{url}|{url_hash}\n")
            self.downloaded_urls.add(url)
            self.downloaded_hashes.add(url_hash)
        except Exception as e:
            print(f"⚠️ Không thể lưu lịch sử: {e}")

    def is_already_downloaded(self, url):
        """Kiểm tra URL đã được tải chưa"""
        url_hash = hashlib.md5(url.encode()).hexdigest()[:8]
        return url in self.downloaded_urls or url_hash in self.downloaded_hashes

    def setup_driver(self, headless=True):
        """
        Thiết lập Chrome WebDriver

        Args:
            headless (bool): Chạy ở chế độ headless (không hiển thị trình duyệt)
        """
        try:
            chrome_options = Options()
            if headless:
                chrome_options.add_argument("--headless=new")
            chrome_options.add_argument(f"--user-data-dir={self.profile_dir}")
            chrome_options.add_argument("--no-sandbox")
            chrome_options.add_argument("--disable-dev-shm-usage")
            chrome_options.add_argument("--disable-gpu")
            chrome_options.add_argument("--window-size=1920,1080")

            self.driver = webdriver.Chrome(options=chrome_options)

            # Bỏ chữ "Headless" khỏi user agent thật của Chrome để tránh bị chặn
            user_agent = self.driver.execute_script("return navigator.userAgent")
            if "HeadlessChrome" in user_agent:
                self.driver.execute_cdp_cmd(
                    "Network.setUserAgentOverride",
                    {"userAgent": user_agent.replace("HeadlessChrome", "Chrome")},
                )

            print("✅ Đã khởi tạo Chrome driver thành công")
            return True

        except Exception as e:
            print(f"❌ Lỗi khi khởi tạo Chrome driver: {e}")
            print("💡 Hãy đảm bảo đã cài Google Chrome và không có cửa sổ Chrome")
            print(f"   nào khác đang dùng profile: {self.profile_dir}")
            return False

    def login_pinterest(self):
        """
        Mở Chrome (có giao diện) để người dùng đăng nhập Pinterest một lần.
        Phiên đăng nhập được lưu trong profile_dir và dùng lại ở các lần sau.
        """
        if not self.setup_driver(headless=False):
            return False

        try:
            self.driver.get("https://www.pinterest.com/login/")
            print("🔐 Hãy đăng nhập Pinterest trong cửa sổ Chrome vừa mở.")
            input("👉 Đăng nhập xong thì nhấn Enter tại đây...")
            while not self.is_logged_in():
                answer = input(
                    "⚠️ Chưa thấy đăng nhập. Nhấn Enter để kiểm tra lại, 'q' để hủy: "
                )
                if answer.strip().lower() == "q":
                    return False
            print("✅ Đã lưu phiên đăng nhập Pinterest")
            return True
        finally:
            self.driver.quit()
            self.driver = None

    def start_session(self):
        """
        Khởi tạo Chrome (headless) và đảm bảo đã đăng nhập Pinterest.
        Nếu chưa đăng nhập thì hỏi người dùng có muốn đăng nhập ngay không.

        Returns:
            bool: True nếu driver sẵn sàng và đã đăng nhập
        """
        if not self.setup_driver():
            return False

        self.driver.get("https://www.pinterest.com/")
        time.sleep(2)
        if self.is_logged_in():
            return True

        self.driver.quit()
        self.driver = None
        print("❌ Chưa đăng nhập Pinterest - Pinterest sẽ không trả kết quả tìm kiếm")
        answer = input("🔐 Mở Chrome để đăng nhập ngay? (y/n, mặc định y): ")
        if answer.strip().lower() == "n" or not self.login_pinterest():
            return False
        return self.setup_driver()

    def is_logged_in(self):
        """Kiểm tra trình duyệt hiện tại đã đăng nhập Pinterest chưa"""
        try:
            return any(
                c["name"] == "_auth" and c["value"] == "1"
                for c in self.driver.get_cookies()
            )
        except Exception:
            return False

    def search_pinterest(self, keyword, max_images=20):
        """
        Tìm kiếm hình ảnh trên Pinterest với từ khóa

        Args:
            keyword (str): Từ khóa tìm kiếm
            max_images (int): Số lượng hình ảnh tối đa cần tải

        Returns:
            list: Danh sách URL hình ảnh
        """
        if not self.driver:
            print("❌ Chrome driver chưa được khởi tạo")
            return []

        try:
            # Truy cập Pinterest
            search_url = (
                "https://www.pinterest.com/search/pins/?q="
                + urllib.parse.quote(keyword)
            )
            print(f"🔍 Đang tìm kiếm: {keyword}")
            print(f"📱 URL: {search_url}")

            self.driver.get(search_url)
            time.sleep(3)

            # Cuộn trang để tải thêm hình ảnh
            last_height = self.driver.execute_script(
                "return document.body.scrollHeight"
            )
            image_urls = set()
            scroll_attempts = 0
            max_scrolls = 5

            while len(image_urls) < max_images and scroll_attempts < max_scrolls:
                # Cuộn xuống
                self.driver.execute_script(
                    "window.scrollTo(0, document.body.scrollHeight);"
                )
                time.sleep(2)

                # Tìm hình ảnh của pin (i.pinimg.com); s.pinimg.com là ảnh giao diện
                images = self.driver.find_elements(
                    By.CSS_SELECTOR, 'img[src*="i.pinimg.com"]'
                )

                for img in images:
                    try:
                        src = img.get_attribute("src")
                        if src and "i.pinimg.com" in src and src not in image_urls:
                            # Chuyển đổi sang URL chất lượng cao
                            high_quality_url = self.get_high_quality_url(src)

                            # Kiểm tra xem URL đã được tải chưa
                            if not self.is_already_downloaded(high_quality_url):
                                image_urls.add(high_quality_url)

                                if len(image_urls) >= max_images:
                                    break
                            else:
                                print(
                                    f"⏭️ Bỏ qua URL đã tải: {high_quality_url[:50]}..."
                                )
                    except Exception:
                        continue

                # Kiểm tra xem trang có cuộn được nữa không
                new_height = self.driver.execute_script(
                    "return document.body.scrollHeight"
                )
                if new_height == last_height:
                    scroll_attempts += 1
                else:
                    scroll_attempts = 0
                last_height = new_height

                print(f"📊 Đã tìm thấy {len(image_urls)} hình ảnh...")

            print(f"✅ Hoàn thành tìm kiếm '{keyword}': {len(image_urls)} hình ảnh")
            return list(image_urls)

        except Exception as e:
            print(f"❌ Lỗi khi tìm kiếm '{keyword}': {e}")
            return []

    def get_high_quality_url(self, url):
        """
        Chuyển đổi URL sang chất lượng cao hơn

        Args:
            url (str): URL gốc

        Returns:
            str: URL chất lượng cao
        """
        try:
            # Thay thế kích thước nhỏ bằng kích thước lớn hơn
            if "236x" in url:
                url = url.replace("236x", "736x")
            elif "474x" in url:
                url = url.replace("474x", "736x")
            elif "564x" in url:
                url = url.replace("564x", "736x")

            return url
        except Exception:
            return url

    def download_image(self, url, filename):
        """
        Tải về một hình ảnh

        Args:
            url (str): URL hình ảnh
            filename (str): Tên file lưu

        Returns:
            bool: True nếu tải thành công
        """
        try:
            headers = {
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/91.0.4472.124 Safari/537.36"
                ),
                "Referer": "https://www.pinterest.com/",
            }

            request = urllib.request.Request(url, headers=headers)

            with urllib.request.urlopen(request, timeout=10) as response:
                if response.status == 200:
                    image_data = response.read()

                    # Kiểm tra và xử lý hình ảnh
                    try:
                        image = Image.open(io.BytesIO(image_data))

                        # Chỉ lưu hình ảnh có kích thước hợp lý
                        width, height = image.size
                        if width >= 200 and height >= 200:

                            # Chuyển đổi sang RGB nếu cần
                            if image.mode in ("RGBA", "P"):
                                image = image.convert("RGB")

                            filepath = os.path.join(self.download_folder, filename)
                            image.save(filepath, "JPEG", quality=90)

                            # Lưu URL vào lịch sử đã tải
                            url_hash = hashlib.md5(url.encode()).hexdigest()[:8]
                            self.save_downloaded_url(url, url_hash)

                            print(f"✅ Đã tải: {filename} ({width}x{height})")
                            return True
                        else:
                            print(f"⚠️ Bỏ qua hình ảnh quá nhỏ: {width}x{height}")
                            return False

                    except Exception as e:
                        print(f"❌ Lỗi xử lý hình ảnh: {e}")
                        return False

        except Exception as e:
            print(f"❌ Lỗi tải hình ảnh từ {url}: {e}")
            return False

    def download_image_thread_safe(self, url, filename):
        """
        Phương thức tải hình ảnh thread-safe cho đa luồng

        Args:
            url (str): URL hình ảnh
            filename (str): Tên file lưu

        Returns:
            tuple: (bool success, str filename, str status)
        """
        try:
            # Kiểm tra URL đã được tải chưa
            if self.is_already_downloaded(url):
                return (False, filename, "skipped_url_exists")

            # Kiểm tra file đã tồn tại chưa
            filepath = os.path.join(self.download_folder, filename)
            if os.path.exists(filepath):
                return (False, filename, "skipped_file_exists")

            headers = {
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/91.0.4472.124 Safari/537.36"
                ),
                "Referer": "https://www.pinterest.com/",
            }

            request = urllib.request.Request(url, headers=headers)

            with urllib.request.urlopen(request, timeout=15) as response:
                if response.status == 200:
                    image_data = response.read()

                    # Kiểm tra và xử lý hình ảnh
                    try:
                        image = Image.open(io.BytesIO(image_data))

                        # Chỉ lưu hình ảnh có kích thước hợp lý
                        width, height = image.size
                        if width >= 200 and height >= 200:

                            # Chuyển đổi sang RGB nếu cần
                            if image.mode in ("RGBA", "P"):
                                image = image.convert("RGB")

                            image.save(filepath, "JPEG", quality=90)

                            # Lưu URL vào lịch sử đã tải
                            url_hash = hashlib.md5(url.encode()).hexdigest()[:8]
                            self.save_downloaded_url(url, url_hash)

                            return (True, filename, f"success_{width}x{height}")
                        else:
                            return (False, filename, f"too_small_{width}x{height}")

                    except Exception as e:
                        return (False, filename, f"image_error_{str(e)}")
                else:
                    return (False, filename, f"http_error_{response.status}")

        except Exception as e:
            return (False, filename, f"download_error_{str(e)}")

    def download_images_multithreaded(self, image_urls, keyword):
        """
        Tải hình ảnh sử dụng đa luồng

        Args:
            image_urls (list): Danh sách URL hình ảnh
            keyword (str): Từ khóa để tạo tên file

        Returns:
            dict: Thống kê kết quả tải
        """
        if not image_urls:
            return {"success": 0, "failed": 0, "skipped": 0}

        print(
            f"🚀 Bắt đầu tải {len(image_urls)} hình ảnh với {self.max_threads} luồng..."
        )

        # Tạo danh sách tasks
        download_tasks = []
        for i, url in enumerate(image_urls, 1):
            filename = self.generate_filename(url, keyword, i)
            download_tasks.append((url, filename))

        # Thống kê
        stats = {"success": 0, "failed": 0, "skipped": 0}
        completed = 0
        total = len(download_tasks)

        # Sử dụng ThreadPoolExecutor
        with ThreadPoolExecutor(max_workers=self.max_threads) as executor:
            # Submit tất cả tasks
            future_to_task = {
                executor.submit(self.download_image_thread_safe, url, filename): (
                    url,
                    filename,
                )
                for url, filename in download_tasks
            }

            # Xử lý kết quả
            for future in as_completed(future_to_task):
                url, filename = future_to_task[future]
                completed += 1

                try:
                    success, file, status = future.result()

                    if success:
                        stats["success"] += 1
                        if "success_" in status:
                            size_info = status.replace("success_", "")
                            print(f"✅ [{completed}/{total}] {filename} ({size_info})")
                        else:
                            print(f"✅ [{completed}/{total}] {filename}")

                    elif "skipped_url_exists" in status:
                        stats["skipped"] += 1
                        print(f"⏭️ [{completed}/{total}] URL đã tải: {filename}")

                    elif "skipped_file_exists" in status:
                        stats["skipped"] += 1
                        print(f"⏭️ [{completed}/{total}] File đã tồn tại: {filename}")

                    elif "too_small_" in status:
                        stats["failed"] += 1
                        size_info = status.replace("too_small_", "")
                        print(
                            f"⚠️ [{completed}/{total}] Quá nhỏ ({size_info}): {filename}"
                        )

                    else:
                        stats["failed"] += 1
                        print(f"❌ [{completed}/{total}] Lỗi: {filename} - {status}")

                except Exception as e:
                    stats["failed"] += 1
                    print(f"❌ [{completed}/{total}] Exception: {filename} - {str(e)}")

        # Cập nhật thống kê tổng
        self.download_stats["total_downloaded"] += stats["success"]
        self.download_stats["total_failed"] += stats["failed"]
        self.download_stats["total_skipped"] += stats["skipped"]

        return stats

    def generate_filename(self, url, keyword, index):
        """
        Tạo tên file cho hình ảnh

        Args:
            url (str): URL hình ảnh
            keyword (str): Từ khóa tìm kiếm
            index (int): Số thứ tự

        Returns:
            str: Tên file
        """
        # Tạo hash từ URL để tránh trùng lặp
        url_hash = hashlib.md5(url.encode()).hexdigest()[:8]

        # Chuẩn hóa keyword
        safe_keyword = "".join(
            c for c in keyword if c.isalnum() or c in (" ", "-", "_")
        ).rstrip()
        safe_keyword = safe_keyword.replace(" ", "_")

        filename = f"{safe_keyword}_{index:03d}_{url_hash}.jpg"
        return filename

    def download_images_by_keyword(
        self, keyword, max_images=20, use_multithreading=True
    ):
        """
        Tải hình ảnh theo từ khóa

        Args:
            keyword (str): Từ khóa tìm kiếm
            max_images (int): Số lượng hình ảnh tối đa
            use_multithreading (bool): Sử dụng tải đa luồng

        Returns:
            int: Số lượng hình ảnh đã tải thành công
        """
        print(f"\n🎯 Bắt đầu tải hình ảnh cho từ khóa: '{keyword}'")

        # Tìm kiếm hình ảnh
        image_urls = self.search_pinterest(keyword, max_images)

        if not image_urls:
            print(f"❌ Không tìm thấy hình ảnh nào cho '{keyword}'")
            return 0

        total_urls = len(image_urls)
        print(f"📥 Tìm thấy {total_urls} hình ảnh để tải...")

        if use_multithreading and self.max_threads > 1:
            # Sử dụng tải đa luồng
            print(f"🔄 Sử dụng tải đa luồng với {self.max_threads} luồng")
            stats = self.download_images_multithreaded(image_urls, keyword)

            downloaded_count = stats["success"]
            print(
                f"✅ Hoàn thành '{keyword}': {downloaded_count}/{total_urls} hình ảnh"
            )
            print(
                f"   📊 Thành công: {stats['success']}, Thất bại: {stats['failed']}, Bỏ qua: {stats['skipped']}"
            )

        else:
            # Sử dụng tải tuần tự (single-thread)
            print("🔄 Sử dụng tải tuần tự")
            downloaded_count = 0

            for i, url in enumerate(image_urls, 1):
                try:
                    # Kiểm tra URL đã được tải chưa
                    if self.is_already_downloaded(url):
                        print(f"⏭️ [{i}/{total_urls}] URL đã tải trước đó")
                        continue

                    filename = self.generate_filename(url, keyword, i)

                    # Kiểm tra file đã tồn tại chưa
                    filepath = os.path.join(self.download_folder, filename)
                    if os.path.exists(filepath):
                        print(f"⏭️ [{i}/{total_urls}] File đã tồn tại: {filename}")
                        continue

                    if self.download_image(url, filename):
                        downloaded_count += 1

                    # Nghỉ giữa các lần tải để tránh bị chặn
                    time.sleep(1)

                except Exception as e:
                    print(f"❌ [{i}/{total_urls}] Lỗi tải hình ảnh: {e}")
                    continue

            print(
                f"✅ Hoàn thành '{keyword}': {downloaded_count}/{total_urls} hình ảnh"
            )

        return downloaded_count

    def download_all_keywords(self, max_images_per_keyword=20, use_multithreading=True):
        """
        Tải hình ảnh cho tất cả từ khóa

        Args:
            max_images_per_keyword (int): Số lượng hình ảnh tối đa cho mỗi từ khóa
            use_multithreading (bool): Sử dụng tải đa luồng

        Returns:
            dict: Thống kê tải về
        """
        if not self.start_session():
            return {}

        try:
            # Reset thống kê
            self.download_stats = {
                "total_downloaded": 0,
                "total_failed": 0,
                "total_skipped": 0,
            }

            total_downloaded = 0
            results = {}
            start_time = time.time()

            print("🚀 Pinterest Image Downloader - Phiên bản đa luồng")
            print(f"📁 Thư mục lưu: {os.path.abspath(self.download_folder)}")
            print(f"🔍 Từ khóa: {', '.join(self.keywords)}")
            print(f"📊 Tối đa {max_images_per_keyword} hình ảnh cho mỗi từ khóa")
            if use_multithreading:
                print(f"🔄 Chế độ đa luồng: {self.max_threads} luồng")
            else:
                print("🔄 Chế độ tuần tự (single-thread)")
            print("=" * 70)

            for keyword in self.keywords:
                try:
                    downloaded = self.download_images_by_keyword(
                        keyword, max_images_per_keyword, use_multithreading
                    )
                    results[keyword] = downloaded
                    total_downloaded += downloaded

                    print(f"✅ '{keyword}': {downloaded} hình ảnh")

                    # Nghỉ giữa các từ khóa
                    time.sleep(2)

                except Exception as e:
                    print(f"❌ Lỗi với từ khóa '{keyword}': {e}")
                    results[keyword] = 0

            end_time = time.time()
            elapsed_time = end_time - start_time

            print("=" * 70)
            print("🎉 HOÀN THÀNH!")
            print(f"⏱️ Thời gian: {elapsed_time:.1f} giây")
            print(f"📊 Tổng cộng: {total_downloaded} hình ảnh")
            print("📈 Thống kê chi tiết:")
            print(f"   ✅ Thành công: {self.download_stats['total_downloaded']}")
            print(f"   ❌ Thất bại: {self.download_stats['total_failed']}")
            print(f"   ⏭️ Bỏ qua: {self.download_stats['total_skipped']}")
            print(
                f"⚡ Tốc độ: {total_downloaded / elapsed_time:.1f} hình/giây"
                if elapsed_time > 0
                else ""
            )
            print(f"📁 Đã lưu trong: {os.path.abspath(self.download_folder)}")

            return results

        except Exception as e:
            print(f"❌ Lỗi chung: {e}")
            return {}

        finally:
            if self.driver:
                self.driver.quit()
                print("🔒 Đã đóng trình duyệt")

    def add_keyword(self, keyword):
        """Thêm từ khóa mới"""
        if keyword not in self.keywords:
            self.keywords.append(keyword)
            print(f"✅ Đã thêm từ khóa: '{keyword}'")
        else:
            print(f"⚠️ Từ khóa '{keyword}' đã tồn tại")

    def remove_keyword(self, keyword):
        """Xóa từ khóa"""
        if keyword in self.keywords:
            self.keywords.remove(keyword)
            print(f"✅ Đã xóa từ khóa: '{keyword}'")
        else:
            print(f"⚠️ Không tìm thấy từ khóa: '{keyword}'")

    def list_keywords(self):
        """Hiển thị danh sách từ khóa"""
        print("📝 Danh sách từ khóa hiện tại:")
        for i, keyword in enumerate(self.keywords, 1):
            print(f"  {i}. {keyword}")

    def show_download_stats(self):
        """Hiển thị thống kê tải về"""
        print("📊 THỐNG KÊ TỔNG QUAN:")
        print(f"📁 Thư mục: {os.path.abspath(self.download_folder)}")
        print(f"🔗 Tổng URL đã tải: {len(self.downloaded_urls)}")
        print(f"🗂️ Hash đã lưu: {len(self.downloaded_hashes)}")

        # Đếm file trong thư mục
        try:
            image_files = [
                f
                for f in os.listdir(self.download_folder)
                if f.lower().endswith((".jpg", ".jpeg", ".png"))
            ]
            print(f"🖼️ File hình ảnh hiện có: {len(image_files)}")

            history_file = os.path.join(self.download_folder, "download_history.txt")
            if os.path.exists(history_file):
                file_size = os.path.getsize(history_file) / 1024  # KB
                print(f"📚 File lịch sử: {file_size:.1f} KB")
            else:
                print("📚 File lịch sử: Chưa tồn tại")

        except Exception as e:
            print(f"⚠️ Lỗi đọc thông tin thư mục: {e}")

    def clear_download_history(self):
        """Xóa lịch sử tải (chỉ lịch sử, không xóa file)"""
        try:
            history_file = os.path.join(self.download_folder, "download_history.txt")
            if os.path.exists(history_file):
                os.remove(history_file)

            self.downloaded_urls.clear()
            self.downloaded_hashes.clear()
            print("✅ Đã xóa lịch sử tải (file hình ảnh vẫn được giữ)")
        except Exception as e:
            print(f"❌ Lỗi xóa lịch sử: {e}")


def main():
    """Hàm chính để chạy tool"""
    print("🎨 Pinterest Image Downloader - Tool tải hình ảnh thời trang (Đa luồng)")
    print("=" * 70)

    # Hỏi số luồng tối đa
    while True:
        try:
            max_threads = input("🔄 Số luồng tối đa (1-5, mặc định 5): ").strip() or "5"
            max_threads = int(max_threads)
            if 1 <= max_threads <= 5:
                break
            else:
                print("❌ Vui lòng nhập số từ 1 đến 5")
        except ValueError:
            print("❌ Vui lòng nhập số hợp lệ")

    # Khởi tạo downloader với số luồng đã chọn
    downloader = PinterestImageDownloader("pinterest_fashion_images", max_threads)
    print(f"✅ Đã khởi tạo với {max_threads} luồng")

    while True:
        print(f"\n📋 MENU (Đang sử dụng {downloader.max_threads} luồng):")
        print("1. Tải hình ảnh với từ khóa mặc định (đa luồng)")
        print("2. Tải hình ảnh với từ khóa mặc định (tuần tự)")
        print("3. Tải hình ảnh với từ khóa tùy chỉnh")
        print("4. Thêm từ khóa mới")
        print("5. Xóa từ khóa")
        print("6. Xem danh sách từ khóa")
        print("7. Thay đổi số luồng")
        print("8. Xem thống kê tải về")
        print("9. Xóa lịch sử tải (giữ file)")
        print("10. Đăng nhập Pinterest (bắt buộc trước lần tải đầu tiên)")
        print("0. Thoát")

        choice = input("\n🔢 Chọn chức năng (0-10): ").strip()

        if choice == "1":
            # Tải với từ khóa mặc định - đa luồng
            try:
                max_images = int(
                    input("📊 Số lượng hình ảnh tối đa cho mỗi từ khóa (mặc định 20): ")
                    or "20"
                )
                results = downloader.download_all_keywords(
                    max_images, use_multithreading=True
                )

                if results:
                    print("\n📈 KẾT QUẢ CHI TIẾT:")
                    for keyword, count in results.items():
                        print(f"  • {keyword}: {count} hình ảnh")

            except ValueError:
                print("❌ Vui lòng nhập số hợp lệ")

        elif choice == "2":
            # Tải với từ khóa mặc định - tuần tự
            try:
                max_images = int(
                    input("📊 Số lượng hình ảnh tối đa cho mỗi từ khóa (mặc định 20): ")
                    or "20"
                )
                results = downloader.download_all_keywords(
                    max_images, use_multithreading=False
                )

                if results:
                    print("\n📈 KẾT QUẢ CHI TIẾT:")
                    for keyword, count in results.items():
                        print(f"  • {keyword}: {count} hình ảnh")

            except ValueError:
                print("❌ Vui lòng nhập số hợp lệ")

        elif choice == "3":
            # Tải với từ khóa tùy chỉnh
            custom_keyword = input("🔍 Nhập từ khóa tìm kiếm: ").strip()
            if custom_keyword:
                try:
                    max_images = int(
                        input("📊 Số lượng hình ảnh tối đa (mặc định 20): ") or "20"
                    )
                    use_multi = (
                        input("🔄 Sử dụng đa luồng? (y/n, mặc định y): ")
                        .strip()
                        .lower()
                    )
                    use_multithreading = use_multi != "n"

                    if downloader.start_session():
                        try:
                            count = downloader.download_images_by_keyword(
                                custom_keyword, max_images, use_multithreading
                            )
                            print(f"✅ Đã tải {count} hình ảnh cho '{custom_keyword}'")
                        finally:
                            if downloader.driver:
                                downloader.driver.quit()

                except ValueError:
                    print("❌ Vui lòng nhập số hợp lệ")
            else:
                print("❌ Vui lòng nhập từ khóa")

        elif choice == "4":
            # Thêm từ khóa
            new_keyword = input("➕ Nhập từ khóa mới: ").strip()
            if new_keyword:
                downloader.add_keyword(new_keyword)
            else:
                print("❌ Vui lòng nhập từ khóa")

        elif choice == "5":
            # Xóa từ khóa
            downloader.list_keywords()
            keyword_to_remove = input("➖ Nhập từ khóa cần xóa: ").strip()
            if keyword_to_remove:
                downloader.remove_keyword(keyword_to_remove)
            else:
                print("❌ Vui lòng nhập từ khóa")

        elif choice == "6":
            # Xem danh sách từ khóa
            downloader.list_keywords()

        elif choice == "7":
            # Thay đổi số luồng
            while True:
                try:
                    new_threads = input(
                        f"🔄 Số luồng mới (1-5, hiện tại {downloader.max_threads}): "
                    ).strip()
                    new_threads = int(new_threads)
                    if 1 <= new_threads <= 5:
                        downloader.max_threads = new_threads
                        print(f"✅ Đã thay đổi thành {new_threads} luồng")
                        break
                    else:
                        print("❌ Vui lòng nhập số từ 1 đến 5")
                except ValueError:
                    print("❌ Vui lòng nhập số hợp lệ")

        elif choice == "8":
            # Xem thống kê tải về
            downloader.show_download_stats()

        elif choice == "9":
            # Xóa lịch sử tải
            confirm = (
                input("⚠️ Bạn có chắc muốn xóa lịch sử tải? (y/n): ").strip().lower()
            )
            if confirm == "y":
                downloader.clear_download_history()
            else:
                print("❌ Đã hủy xóa lịch sử")

        elif choice == "10":
            # Đăng nhập Pinterest
            downloader.login_pinterest()

        elif choice == "0":
            print("👋 Tạm biệt!")
            break

        else:
            print("❌ Lựa chọn không hợp lệ. Vui lòng chọn từ 0-10")


if __name__ == "__main__":
    main()
