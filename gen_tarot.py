"""
Tạo ảnh nền chủ đề tarot (nến, lá bài, pha lê, hoa, không khí huyền bí)
khổ dọc 9:16 bằng SDXL Lightning, chạy trên máy với GPU NVIDIA 8GB (vd RTX 3070).

Model mặc định: RealVisXL V4.0 Lightning (SDXL ảnh chân thực, 4-6 bước).
Lần chạy đầu sẽ tự tải model (~7GB) về cache của Hugging Face.

Cài đặt (một lần, trên máy có GPU):
    pip install torch --index-url https://download.pytorch.org/whl/cu128
    (cần Python 64-bit 3.10-3.13; lỗi "Could not find a version" thường do sai bản Python)
    pip install diffusers transformers accelerate safetensors pillow

Ví dụ:
    python gen_tarot.py                       # tạo 20 ảnh
    python gen_tarot.py -n 200 --out batch1   # tạo 200 ảnh vào thư mục batch1
    python gen_tarot.py --style pastel -n 10  # chỉ một phong cách
    python gen_tarot.py --dry-run -n 5        # chỉ in prompt, không tạo ảnh
    python gen_tarot.py --low-vram            # nếu bị lỗi hết VRAM

Mỗi ảnh được lưu kèm prompt + seed trong prompts.jsonl.
Cùng một --seed sẽ tạo lại đúng cả loạt ảnh (cùng prompt, cùng seed từng ảnh).
"""

import argparse
import json
import os
import random
import time

MODEL_ID = "SG161222/RealVisXL_V4.0_Lightning"
VAE_ID = "madebyollin/sdxl-vae-fp16-fix"  # tránh ảnh đen/NaN khi chạy fp16

# Kích thước gốc của SDXL gần 9:16 nhất (chia hết cho 64)
WIDTH, HEIGHT = 768, 1344

# --------------------------------------------------------------------------
# Các thành phần prompt, dựa trên các ảnh mẫu
# --------------------------------------------------------------------------

STYLES = {
    "flowers": {
        "subject": [
            "a fan of ornate tarot cards on a dark wooden table",
            "a spread of colorful tarot cards among flowers",
        ],
        "props": [
            "vivid orange and pink chrysanthemums",
            "purple flowers and scattered petals",
            "sparkling blue crystals and gemstones",
            "small lit tea candles",
            "dried golden flowers",
        ],
        "mood": "rich saturated colors, vibrant and magical",
    },
    "spellbook": {
        "subject": [
            "an old open spellbook and tarot cards on a table",
            "an ancient grimoire with tarot cards and a glowing zodiac circle above the table",
        ],
        "props": [
            "tall lit candles",
            "glowing turquoise astrology circle",
            "antique brass objects",
            "dice and old coins",
            "crystal ball",
        ],
        "mood": "dark moody background with golden light, mystical",
    },
    "hands": {
        "subject": [
            "close-up of a woman's hands with silver rings holding a spread of vintage tarot cards",
            "a fortune teller's hands with rings laying out tarot cards",
        ],
        "props": [
            "many candles glowing in the blurred background",
            "lace tablecloth",
            "small crystals",
        ],
        "mood": "intimate, warm and mysterious",
    },
    "roses": {
        "subject": [
            "a single ornate tarot card lying on a rustic dark wooden table",
            "two tarot cards on an old wooden table",
        ],
        "props": [
            "lit pillar candles",
            "red roses",
            "scattered rose petals",
            "melted wax",
        ],
        "mood": "dark romantic atmosphere, deep red and warm tones",
    },
    "dark_spread": {
        "subject": [
            "a tarot spread of three large ornate cards on a dark table",
            "many tarot cards spread across a dark wooden table in a fortune teller's room",
        ],
        "props": [
            "dozens of melting candles",
            "wisps of mystical smoke",
            "crystal ball",
            "antique decor",
            "dim window light",
        ],
        "mood": "deep dark background with warm highlights, mysterious",
    },
    "pastel": {
        "subject": [
            "a deck of pastel blue and pink tarot cards on a fluffy white blanket",
            "pastel tarot cards fanned out on white linen",
        ],
        "props": [
            "white candles in glass jars",
            "rose quartz and amethyst crystals",
            "dried flowers",
            "fairy lights",
        ],
        "mood": "bright airy cozy aesthetic, soft morning light",
    },
}

CAMERA = [
    "overhead top-down shot",
    "close-up shot at a slight angle",
    "eye-level close-up",
    "low angle close-up across the table",
]

COMMON = (
    "vertical composition, photorealistic, cinematic lighting, warm candlelight glow, "
    "soft bokeh, shallow depth of field, highly detailed, 8k photo, "
    "uncluttered center area"
)

NEGATIVE = (
    "text, letters, words, watermark, logo, signature, caption, "
    "blurry, lowres, jpeg artifacts, deformed, distorted, extra fingers, "
    "mutated hands, bad anatomy, cartoon, anime, illustration, 3d render"
)


def build_prompt(rng, style_name=None):
    """Ghép ngẫu nhiên một prompt. Trả về (style, prompt)"""
    style_name = style_name or rng.choice(list(STYLES))
    style = STYLES[style_name]
    props = rng.sample(style["props"], k=min(3, len(style["props"])))
    parts = [
        rng.choice(CAMERA),
        rng.choice(style["subject"]),
        ", ".join(props),
        style["mood"],
        COMMON,
    ]
    return style_name, ", ".join(parts)


# --------------------------------------------------------------------------


def load_pipeline(model, low_vram):
    import torch
    from diffusers import (
        AutoencoderKL,
        DPMSolverMultistepScheduler,
        StableDiffusionXLPipeline,
    )

    if not torch.cuda.is_available():
        raise SystemExit("❌ Không tìm thấy GPU CUDA. Kiểm tra driver NVIDIA và bản torch CUDA")

    print(f"🧠 Đang tải model {model} (lần đầu sẽ tải ~7GB)...")
    vae = AutoencoderKL.from_pretrained(VAE_ID, torch_dtype=torch.float16)
    kwargs = {"vae": vae, "torch_dtype": torch.float16}
    if model.endswith(".safetensors"):
        pipe = StableDiffusionXLPipeline.from_single_file(model, **kwargs)
    else:
        pipe = StableDiffusionXLPipeline.from_pretrained(model, **kwargs)

    # Sampler khuyến nghị cho model Lightning: DPM++ SDE Karras
    pipe.scheduler = DPMSolverMultistepScheduler.from_config(
        pipe.scheduler.config,
        algorithm_type="sde-dpmsolver++",
        use_karras_sigmas=True,
    )

    if low_vram:
        pipe.enable_model_cpu_offload()  # chậm hơn nhưng dùng ít VRAM
    else:
        pipe.to("cuda")
    # Diffusers bản mới đã bỏ pipe.enable_vae_slicing(), gọi thẳng trên VAE
    pipe.vae.enable_slicing()
    pipe.set_progress_bar_config(disable=True)

    gpu = torch.cuda.get_device_name(0)
    vram = torch.cuda.get_device_properties(0).total_memory / 1024**3
    print(f"✅ Sẵn sàng trên {gpu} ({vram:.1f}GB VRAM)")
    return pipe


def generate(args):
    rng = random.Random(args.seed)
    os.makedirs(args.out, exist_ok=True)
    log_path = os.path.join(args.out, "prompts.jsonl")

    jobs = []
    for _ in range(args.count):
        style, prompt = build_prompt(rng, args.style)
        seed = rng.randrange(2**32)
        jobs.append((style, prompt, seed))

    if args.dry_run:
        for style, prompt, seed in jobs:
            print(f"[{style}] seed={seed}\n  {prompt}\n")
        return

    import torch

    pipe = load_pipeline(args.model, args.low_vram)

    start = time.time()
    for i, (style, prompt, seed) in enumerate(jobs, 1):
        t0 = time.time()
        generator = torch.Generator("cuda").manual_seed(seed)
        image = pipe(
            prompt=prompt,
            negative_prompt=NEGATIVE,
            width=WIDTH,
            height=HEIGHT,
            num_inference_steps=args.steps,
            guidance_scale=args.cfg,
            generator=generator,
        ).images[0]

        if args.upscale:
            # Phóng to về 1080x1890 rồi cắt giữa về đúng 1080x1920 (9:16)
            image = image.resize((1097, 1920), resample=3)  # 3 = BICUBIC
            left = (image.width - 1080) // 2
            image = image.crop((left, 0, left + 1080, 1920))

        filename = f"tarot_{style}_{int(time.time())}_{seed}.{args.format}"
        path = os.path.join(args.out, filename)
        if args.format == "jpg":
            image.save(path, "JPEG", quality=95)
        else:
            image.save(path)

        with open(log_path, "a", encoding="utf-8") as f:
            record = {
                "file": filename,
                "style": style,
                "seed": seed,
                "prompt": prompt,
                "negative": NEGATIVE,
                "model": args.model,
                "steps": args.steps,
                "cfg": args.cfg,
            }
            f.write(json.dumps(record, ensure_ascii=False) + "\n")

        print(f"✅ [{i}/{args.count}] {filename} ({time.time() - t0:.1f}s)")

    elapsed = time.time() - start
    print("=" * 60)
    print(f"🎉 Xong {args.count} ảnh trong {elapsed:.0f}s "
          f"({elapsed / max(args.count, 1):.1f}s/ảnh)")
    print(f"📁 {os.path.abspath(args.out)}")


def main():
    parser = argparse.ArgumentParser(description="Tạo ảnh nền tarot bằng SDXL Lightning")
    parser.add_argument("-n", "--count", type=int, default=20, help="Số ảnh cần tạo")
    parser.add_argument("--out", default="generated_tarot", help="Thư mục lưu ảnh")
    parser.add_argument(
        "--style", choices=list(STYLES), help="Chỉ dùng một phong cách (mặc định: trộn ngẫu nhiên)"
    )
    parser.add_argument(
        "--seed", type=int, help="Seed gốc để tái tạo cùng một loạt ảnh"
    )
    parser.add_argument(
        "--model", default=MODEL_ID, help="Repo Hugging Face hoặc file .safetensors SDXL Lightning"
    )
    parser.add_argument("--steps", type=int, default=6, help="Số bước (Lightning: 4-6)")
    parser.add_argument("--cfg", type=float, default=1.5, help="CFG scale (Lightning: 1-2)")
    parser.add_argument(
        "--upscale", action="store_true", help="Phóng to về 1080x1920 (mặc định 768x1344)"
    )
    parser.add_argument("--format", choices=["jpg", "png"], default="jpg")
    parser.add_argument(
        "--low-vram", action="store_true", help="Bật CPU offload nếu bị lỗi out of memory"
    )
    parser.add_argument("--dry-run", action="store_true", help="Chỉ in prompt, không tạo ảnh")
    generate(parser.parse_args())


if __name__ == "__main__":
    main()
