# Pinterest Image Downloader - Tool Tải Hình Ảnh Thời Trang (Đa luồng)

## Mô tả

Tool tự động tải hình ảnh từ Pinterest với các từ khóa về thời trang, váy xinh, và phối đồ nữ.
**Phiên bản mới hỗ trợ tải đa luồng với tối đa 5 luồng để tăng tốc độ tải xuống.**

## Tính năng mới ⚡

- **Tải đa luồng**: Tối đa 5 luồng song song
- **Tốc độ nhanh hơn**: Giảm thời gian tải xuống đáng kể
- **Thống kê chi tiết**: Hiển thị tốc độ tải (hình/giây)
- **Lựa chọn linh hoạt**: Có thể chọn tải đa luồng hoặc tuần tự
- **Progress tracking**: Hiển thị tiến trình theo thời gian thực

## Cài đặt

### 1. Cài đặt các thư viện Python

```bash
uv sync
# hoặc: pip install -r requirements.txt
```

### 2. Cài đặt Google Chrome

Selenium 4.6+ tự động tải ChromeDriver phù hợp, không cần cài thủ công.

### 3. Đăng nhập Pinterest (bắt buộc, chỉ làm một lần)

Pinterest không trả kết quả tìm kiếm khi chưa đăng nhập. Chạy tool, chọn
**10. Đăng nhập Pinterest**, đăng nhập trong cửa sổ Chrome vừa mở rồi nhấn Enter.
Phiên đăng nhập được lưu trong thư mục `chrome_profile/` và dùng lại cho các lần sau
(thư mục này đã nằm trong `.gitignore`, không commit lên git).

## Cách sử dụng

### 1. Chạy tool

```cmd
python pinterest.py
```

### 2. Menu chức năng:

- **1**: Tải hình ảnh với từ khóa mặc định (đa luồng) 🚀
- **2**: Tải hình ảnh với từ khóa mặc định (tuần tự) 🐌
- **3**: Tải hình ảnh với từ khóa tùy chỉnh
- **4**: Thêm từ khóa mới
- **5**: Xóa từ khóa
- **6**: Xem danh sách từ khóa
- **7**: Thay đổi số luồng (1-5)
- **8**: Xem thống kê tải về
- **9**: Xóa lịch sử tải (giữ file)
- **10**: Đăng nhập Pinterest 🔐
- **0**: Thoát

### 3. Từ khóa mặc định:

- váy xinh
- thời trang
- nữ phối đồ
- outfit
- fashion style
- cute dress

## Cấu trúc thư mục

```
cut video/
├── pinterest.py          # Tool chính
├── requirements.txt      # Danh sách thư viện
├── README.md            # Hướng dẫn này
└── pinterest_fashion_images/  # Thư mục chứa hình ảnh tải về
    ├── vay_xinh_001_12345678.jpg
    ├── thoi_trang_001_87654321.jpg
    └── ...
```

## Tính năng

### ✅ Các tính năng chính:

- **Tải đa luồng**: Sử dụng tối đa 5 luồng song song
- **Tốc độ cao**: Tăng tốc độ tải xuống 3-5 lần
- Tìm kiếm hình ảnh trên Pinterest
- Tải hình ảnh chất lượng cao
- Tự động đặt tên file theo từ khóa
- Tránh tải trùng lặp
- Kiểm tra kích thước hình ảnh
- Menu tương tác thân thiện
- **Thống kê real-time**: Hiển thị tiến trình và tốc độ

### 🔧 Cấu hình:

- **Số luồng**: 1-5 luồng (mặc định 5)
- Số lượng hình ảnh tối đa cho mỗi từ khóa
- Thư mục lưu trữ tùy chỉnh
- Chạy ở chế độ headless (không hiển thị browser)
- **Lựa chọn chế độ**: Đa luồng hoặc tuần tự

### 📊 Thống kê:

- Hiển thị số lượng hình ảnh tải thành công
- **Tốc độ tải**: Hình ảnh/giây
- **Thời gian hoàn thành**: Tính toán tự động
- Báo cáo chi tiết cho từng từ khóa
- **Phân loại kết quả**: Thành công/Thất bại/Bỏ qua
- Thông báo lỗi chi tiết

## Lưu ý quan trọng

### ⚠️ Yêu cầu hệ thống:

- Python 3.13+
- Google Chrome
- Tài khoản Pinterest
- Kết nối internet ổn định

### 🚨 Chú ý khi sử dụng:

- Tôn trọng bản quyền hình ảnh
- Sử dụng hình ảnh phù hợp với mục đích
- Không spam quá nhiều requests
- Kiểm tra terms of service của Pinterest

### 🛠️ Xử lý lỗi thường gặp:

1. **Lỗi khởi tạo Chrome driver**:

   - Kiểm tra đã cài Google Chrome
   - Đóng các cửa sổ Chrome khác đang dùng thư mục `chrome_profile/`

2. **Lỗi không tìm thấy hình ảnh**:

   - Đăng nhập Pinterest (menu 10) nếu chưa đăng nhập hoặc phiên đã hết hạn

   - Kiểm tra kết nối internet
   - Thử với từ khóa khác
   - Pinterest có thể đã thay đổi cấu trúc

3. **Lỗi quyền truy cập thư mục**:
   - Chạy với quyền administrator
   - Kiểm tra quyền ghi file

## Tùy chỉnh

### Thay đổi số luồng:

```python
downloader = PinterestImageDownloader("ten_thu_muc_moi", max_threads=3)
```

### Tải với chế độ tuần tự:

```python
downloader.download_all_keywords(max_images_per_keyword=20, use_multithreading=False)
```

### Chạy không hiển thị browser:

```python
downloader.setup_driver(headless=True)
```

## So sánh hiệu năng

### Tải tuần tự (single-thread):

- Tốc độ: ~1-2 hình/giây
- Sử dụng CPU: Thấp
- Phù hợp: Kết nối mạng chậm

### Tải đa luồng (5 threads):

- Tốc độ: ~5-10 hình/giây
- Sử dụng CPU: Trung bình
- Phù hợp: Kết nối mạng tốt

### Lời khuyên:

- Dùng 3-5 luồng cho kết nối tốt
- Dùng 1-2 luồng cho kết nối chậm
- Tránh quá 5 luồng để không bị Pinterest chặn

## Liên hệ

Nếu có vấn đề hoặc cần hỗ trợ, vui lòng tạo issue hoặc liên hệ trực tiếp.

## Phiên bản

- v1.0: Phiên bản đầu tiên với đầy đủ tính năng cơ bản
- **v2.0**: Nâng cấp đa luồng, tối đa 5 luồng song song 🚀
  - Tăng tốc độ tải 3-5 lần
  - Thống kê real-time
  - Menu nâng cấp với nhiều tùy chọn
  - Hiển thị progress và tốc độ
