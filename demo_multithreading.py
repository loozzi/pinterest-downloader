#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Demo script để test tính năng đa luồng của Pinterest Image Downloader
"""

import time

from pinterest import PinterestImageDownloader


def demo_single_vs_multi_thread():
    """So sánh hiệu năng giữa single-thread và multi-thread"""

    print("🧪 DEMO: So sánh hiệu năng Single-thread vs Multi-thread")
    print("=" * 60)

    # Test với từ khóa nhỏ
    test_keyword = "váy xinh"
    max_images = 10

    # Khởi tạo downloader với 1 luồng (single-thread)
    print("\n1️⃣ TEST SINGLE-THREAD (1 luồng)")
    downloader_single = PinterestImageDownloader("test_single_thread", max_threads=1)

    if downloader_single.setup_driver():
        start_time = time.time()
        try:
            # Test tải tuần tự
            count_single = downloader_single.download_images_by_keyword(
                test_keyword, max_images, use_multithreading=False
            )
            single_time = time.time() - start_time

        finally:
            if downloader_single.driver:
                downloader_single.driver.quit()

    # Khởi tạo downloader với 5 luồng (multi-thread)
    print("\n2️⃣ TEST MULTI-THREAD (5 luồng)")
    downloader_multi = PinterestImageDownloader("test_multi_thread", max_threads=5)

    if downloader_multi.setup_driver():
        start_time = time.time()
        try:
            # Test tải đa luồng
            count_multi = downloader_multi.download_images_by_keyword(
                test_keyword, max_images, use_multithreading=True
            )
            multi_time = time.time() - start_time

        finally:
            if downloader_multi.driver:
                downloader_multi.driver.quit()

    # So sánh kết quả
    print("\n📊 KẾT QUẢ SO SÁNH:")
    print("=" * 60)
    print(f"Single-thread: {count_single} hình trong {single_time:.1f}s")
    print(f"Multi-thread:  {count_multi} hình trong {multi_time:.1f}s")

    if single_time > 0 and multi_time > 0:
        speed_single = count_single / single_time
        speed_multi = count_multi / multi_time
        speedup = speed_multi / speed_single if speed_single > 0 else 0

        print(f"\nTốc độ single-thread: {speed_single:.2f} hình/giây")
        print(f"Tốc độ multi-thread:  {speed_multi:.2f} hình/giây")
        print(f"Tăng tốc: {speedup:.1f}x")

        if speedup > 1:
            print(f"✅ Multi-thread nhanh hơn {speedup:.1f} lần!")
        else:
            print("⚠️ Multi-thread không nhanh hơn trong test này")


def demo_thread_scaling():
    """Test hiệu năng với số luồng khác nhau"""

    print("\n🔬 DEMO: Test hiệu năng với số luồng khác nhau")
    print("=" * 60)

    test_keyword = "thời trang"
    max_images = 15
    thread_counts = [1, 2, 3, 5]

    results = {}

    for thread_count in thread_counts:
        print(f"\n🧵 Test với {thread_count} luồng...")

        downloader = PinterestImageDownloader(
            f"test_{thread_count}_threads", max_threads=thread_count
        )

        if downloader.setup_driver():
            start_time = time.time()
            try:
                count = downloader.download_images_by_keyword(
                    test_keyword, max_images, use_multithreading=(thread_count > 1)
                )
                elapsed_time = time.time() - start_time

                results[thread_count] = {
                    "count": count,
                    "time": elapsed_time,
                    "speed": count / elapsed_time if elapsed_time > 0 else 0,
                }

            finally:
                if downloader.driver:
                    downloader.driver.quit()

    # Hiển thị kết quả
    print("\n📈 KẾT QUẢ SCALING:")
    print("=" * 60)
    print("Luồng | Hình ảnh | Thời gian | Tốc độ")
    print("-" * 40)

    for thread_count in thread_counts:
        if thread_count in results:
            r = results[thread_count]
            print(
                f"{thread_count:5d} | {r['count']:8d} | {r['time']:8.1f}s | {r['speed']:6.2f}/s"
            )

    # Tìm cấu hình tối ưu
    best_thread = max(results.keys(), key=lambda x: results[x]["speed"])
    print(
        f"\n🏆 Cấu hình tối ưu: {best_thread} luồng với {results[best_thread]['speed']:.2f} hình/giây"
    )


def quick_demo():
    """Demo nhanh với ít hình ảnh"""

    print("⚡ QUICK DEMO: Tải nhanh 5 hình ảnh")
    print("=" * 50)

    downloader = PinterestImageDownloader("quick_demo", max_threads=3)

    if downloader.setup_driver():
        try:
            count = downloader.download_images_by_keyword(
                "cute dress", 5, use_multithreading=True
            )
            print(f"\n✅ Demo hoàn thành: {count} hình ảnh đã tải")

        finally:
            if downloader.driver:
                downloader.driver.quit()


if __name__ == "__main__":
    print("🎨 Pinterest Downloader - Demo Đa luồng")
    print("=" * 50)

    while True:
        print("\n📋 CHỌN DEMO:")
        print("1. So sánh Single vs Multi-thread")
        print("2. Test scaling với số luồng khác nhau")
        print("3. Quick demo (5 hình ảnh)")
        print("0. Thoát")

        choice = input("\nChọn demo (0-3): ").strip()

        if choice == "1":
            demo_single_vs_multi_thread()
        elif choice == "2":
            demo_thread_scaling()
        elif choice == "3":
            quick_demo()
        elif choice == "0":
            print("👋 Tạm biệt!")
            break
        else:
            print("❌ Lựa chọn không hợp lệ")
            print("❌ Lựa chọn không hợp lệ")
