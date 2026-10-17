"""
Tạo ảnh nền theo chủ đề (Phật / tarot) khổ dọc 9:16 bằng SDXL Lightning, chạy trên máy với GPU NVIDIA 8GB (vd RTX 3070).

Model mặc định: RealVisXL V4.0 Lightning (SDXL ảnh chân thực, 4-6 bước).
Lần chạy đầu sẽ tự tải model (~7GB) về cache của Hugging Face.

Cài đặt (một lần, trên máy có GPU):
    pip install torch --index-url https://download.pytorch.org/whl/cu128
    (cần Python 64-bit 3.10-3.13; lỗi "Could not find a version" thường do sai bản Python)
    pip install diffusers transformers accelerate safetensors pillow

Ví dụ:
    python gen_tarot.py                       # tạo 20 ảnh chủ đề Phật (mặc định)
    python gen_tarot.py --theme tarot         # chủ đề tarot
    python gen_tarot.py -n 200 --out batch1   # tạo 200 ảnh vào thư mục batch1
    python gen_tarot.py --style lotus -n 10   # chỉ một phong cách
    python gen_tarot.py --dry-run -n 5        # chỉ in prompt, không tạo ảnh
    python gen_tarot.py --low-vram            # nếu bị lỗi hết VRAM
    python gen_tarot.py --cfg 1 --steps 4     # nhanh nhất (~2.5x), bỏ qua negative prompt

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

DEVICE = "cuda"
DTYPE = "float16"

# --------------------------------------------------------------------------
# Các thành phần prompt, dựa trên các ảnh mẫu
# --------------------------------------------------------------------------

TAROT_STYLES = {
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

BUDDHA_STYLES = {
    "temple": {
        "subject": [
            "a serene golden Buddha statue in meditation inside an ancient temple",
            "a large bronze Buddha statue seated on a lotus throne in a temple hall",
        ],
        "props": [
            "incense smoke drifting in the air",
            "rows of lit candles",
            "red wooden pillars",
            "golden light rays through the temple doors",
            "offerings of fresh flowers",
        ],
        "mood": "sacred, peaceful and majestic, warm golden tones",
    },
    "lotus": {
        "subject": [
            "a white stone Buddha statue beside a calm lotus pond",
            "a small serene Buddha statue surrounded by blooming pink lotus flowers",
        ],
        "props": [
            "pink and white lotus blossoms",
            "large green lotus leaves with water droplets",
            "still reflective water",
            "soft morning mist",
            "floating candles on the water",
        ],
        "mood": "pure, calm and fresh, soft pastel pink and green tones",
    },
    "zen_garden": {
        "subject": [
            "a moss-covered stone Buddha head in a zen garden",
            "a weathered stone Buddha statue meditating in a quiet forest garden",
        ],
        "props": [
            "green moss and ferns",
            "raked sand and smooth river stones",
            "soft sunbeams through the trees",
            "morning mist",
            "a small bamboo water fountain",
        ],
        "mood": "tranquil, natural and meditative, soft green tones",
    },
    "altar": {
        "subject": [
            "a golden Buddha statue on a home altar",
            "a small jade Buddha statue on a wooden altar table",
        ],
        "props": [
            "burning incense sticks with curling smoke",
            "lit candles and oil lamps",
            "a plate of fresh fruit offerings",
            "vases of yellow chrysanthemums",
            "a brass bell",
        ],
        "mood": "warm, devotional and cozy, rich gold and red tones",
    },
    "lanterns": {
        "subject": [
            "a Buddha statue at night surrounded by glowing lanterns",
            "a peaceful Buddha statue in a temple courtyard during a lantern festival",
        ],
        "props": [
            "hundreds of glowing paper lanterns",
            "floating lotus lanterns on water",
            "string lights",
            "a starry night sky",
            "soft candlelight",
        ],
        "mood": "magical, festive and serene, deep blue night with warm golden glow",
    },
    "sunrise": {
        "subject": [
            "a giant Buddha statue on a mountain top at sunrise",
            "a silhouette of a meditating Buddha statue against the rising sun",
        ],
        "props": [
            "sea of clouds below",
            "golden sun rays",
            "distant misty mountains",
            "flying birds",
        ],
        "mood": "uplifting, hopeful and spiritual, golden and orange sky",
    },
}

THEMES = {
    "buddha": {
        "styles": BUDDHA_STYLES,
        "camera": [
            "eye-level shot",
            "close-up portrait of the statue's peaceful face",
            "low angle shot looking up",
            "wide shot",
        ],
        "common": (
            "vertical composition, photorealistic, cinematic lighting, soft glow, "
            "soft bokeh, shallow depth of field, highly detailed, 8k photo, "
            "respectful and serene, uncluttered center area"
        ),
    },
    "tarot": {
        "styles": TAROT_STYLES,
        "camera": [
            "overhead top-down shot",
            "close-up shot at a slight angle",
            "eye-level close-up",
            "low angle close-up across the table",
        ],
        "common": (
            "vertical composition, photorealistic, cinematic lighting, warm candlelight glow, "
            "soft bokeh, shallow depth of field, highly detailed, 8k photo, "
            "uncluttered center area"
        ),
    },
}

NEGATIVE = (
    "text, letters, words, watermark, logo, signature, caption, "
    "blurry, lowres, jpeg artifacts, deformed, distorted, extra fingers, "
    "mutated hands, bad anatomy, deformed face, broken statue, "
    "cartoon, anime, illustration, 3d render"
)


def build_prompt(rng, theme_name, style_name=None):
    """Ghép ngẫu nhiên một prompt. Trả về (style, prompt)"""
    theme = THEMES[theme_name]
    style_name = style_name or rng.choice(list(theme["styles"]))
    style = theme["styles"][style_name]
    props = rng.sample(style["props"], k=min(3, len(style["props"])))
    parts = [
        rng.choice(theme["camera"]),
        rng.choice(style["subject"]),
        ", ".join(props),
        style["mood"],
        theme["common"],
    ]
    return style_name, ", ".join(parts)


# --------------------------------------------------------------------------


def load_pipeline(model):
    """Tải pipeline SDXL lên RAM (chưa đưa lên GPU)"""
    import torch
    from diffusers import (
        AutoencoderKL,
        DPMSolverMultistepScheduler,
        StableDiffusionXLPipeline,
    )

    if DEVICE == "cuda" and not torch.cuda.is_available():
        raise SystemExit("❌ Không tìm thấy GPU CUDA. Kiểm tra driver NVIDIA và bản torch CUDA")

    print(f"🧠 Đang tải model {model} (lần đầu sẽ tải ~7GB)...")
    dtype = getattr(torch, DTYPE)
    vae = AutoencoderKL.from_pretrained(VAE_ID, torch_dtype=dtype)
    kwargs = {"vae": vae, "torch_dtype": dtype}
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
    return pipe


def encode_prompts(pipe, prompts, use_cfg):
    """
    Mã hóa trước toàn bộ prompt bằng 2 text encoder rồi đưa chúng ra khỏi VRAM.

    SDXL fp16 đủ bộ (~7GB) gần chạm 8GB VRAM của RTX 3070; trên Windows phần
    tràn sẽ bị đẩy sang RAM qua PCIe và chậm đi nhiều lần. Tách text encoder
    ra giúp UNet + VAE nằm gọn trong VRAM.

    Returns:
        dict: prompt -> (prompt_embeds, negative_embeds, pooled, negative_pooled)
    """
    import torch

    print(f"📝 Đang mã hóa {len(set(prompts))} prompt...")
    pipe.text_encoder.to(DEVICE)
    pipe.text_encoder_2.to(DEVICE)

    cache = {}
    with torch.no_grad():
        for prompt in prompts:
            if prompt in cache:
                continue
            embeds = pipe.encode_prompt(
                prompt=prompt,
                device=DEVICE,
                num_images_per_prompt=1,
                do_classifier_free_guidance=use_cfg,
                negative_prompt=NEGATIVE if use_cfg else None,
            )
            cache[prompt] = tuple(e.cpu() if e is not None else None for e in embeds)

    pipe.text_encoder.to("cpu")
    pipe.text_encoder_2.to("cpu")
    if DEVICE == "cuda":
        torch.cuda.empty_cache()
    return cache


def make_denoiser(pipe, low_vram):
    """Pipeline chỉ gồm UNet + VAE, nhận prompt đã mã hóa sẵn"""
    import torch
    from diffusers import StableDiffusionXLPipeline

    denoiser = StableDiffusionXLPipeline(
        vae=pipe.vae,
        text_encoder=None,
        text_encoder_2=None,
        tokenizer=None,
        tokenizer_2=None,
        unet=pipe.unet,
        scheduler=pipe.scheduler,
    )
    if low_vram:
        denoiser.enable_model_cpu_offload()  # chậm hơn nhưng dùng ít VRAM
    else:
        denoiser.to(DEVICE)
    denoiser.unet.to(memory_format=torch.channels_last)
    denoiser.set_progress_bar_config(disable=True)

    if DEVICE == "cuda":
        gpu = torch.cuda.get_device_name(0)
        total = torch.cuda.get_device_properties(0).total_memory / 1024**3
        used = torch.cuda.memory_allocated() / 1024**3
        print(f"✅ Sẵn sàng trên {gpu} (model chiếm {used:.1f}/{total:.1f}GB VRAM)")
    return denoiser


def generate(args):
    styles = THEMES[args.theme]["styles"]
    if args.style and args.style not in styles:
        raise SystemExit(
            f"❌ Chủ đề '{args.theme}' không có phong cách '{args.style}'. "
            f"Chọn một trong: {', '.join(styles)}"
        )
    args.out = args.out or f"generated_{args.theme}"

    rng = random.Random(args.seed)

    jobs = []
    for _ in range(args.count):
        style, prompt = build_prompt(rng, args.theme, args.style)
        seed = rng.randrange(2**32)
        jobs.append((style, prompt, seed))

    if args.dry_run:
        for style, prompt, seed in jobs:
            print(f"[{style}] seed={seed}\n  {prompt}\n")
        return

    os.makedirs(args.out, exist_ok=True)
    log_path = os.path.join(args.out, "prompts.jsonl")

    import torch

    # Giống diffusers: CFG <= 1 thì bỏ qua negative prompt, mỗi bước chỉ chạy UNet 1 lần
    use_cfg = args.cfg > 1
    pipe = load_pipeline(args.model)
    embeds = encode_prompts(pipe, [prompt for _, prompt, _ in jobs], use_cfg)
    pipe = make_denoiser(pipe, args.low_vram)

    start = time.time()
    for i, (style, prompt, seed) in enumerate(jobs, 1):
        t0 = time.time()
        prompt_embeds, negative_embeds, pooled, negative_pooled = embeds[prompt]
        generator = torch.Generator(DEVICE).manual_seed(seed)
        image = pipe(
            prompt_embeds=prompt_embeds,
            negative_prompt_embeds=negative_embeds,
            pooled_prompt_embeds=pooled,
            negative_pooled_prompt_embeds=negative_pooled,
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

        filename = f"{args.theme}_{style}_{int(time.time())}_{seed}.{args.format}"
        path = os.path.join(args.out, filename)
        if args.format == "jpg":
            image.save(path, "JPEG", quality=95)
        else:
            image.save(path)

        with open(log_path, "a", encoding="utf-8") as f:
            record = {
                "file": filename,
                "theme": args.theme,
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
    parser = argparse.ArgumentParser(description="Tạo ảnh nền theo chủ đề bằng SDXL Lightning")
    parser.add_argument("-n", "--count", type=int, default=20, help="Số ảnh cần tạo")
    parser.add_argument(
        "--theme", choices=list(THEMES), default="buddha", help="Chủ đề ảnh (mặc định: buddha)"
    )
    parser.add_argument(
        "--out", help="Thư mục lưu ảnh (mặc định: generated_<theme>)"
    )
    parser.add_argument(
        "--style",
        choices=sorted({name for t in THEMES.values() for name in t["styles"]}),
        help="Chỉ dùng một phong cách của chủ đề (mặc định: trộn ngẫu nhiên)",
    )
    parser.add_argument(
        "--seed", type=int, help="Seed gốc để tái tạo cùng một loạt ảnh"
    )
    parser.add_argument(
        "--model", default=MODEL_ID, help="Repo Hugging Face hoặc file .safetensors SDXL Lightning"
    )
    parser.add_argument("--steps", type=int, default=6, help="Số bước (Lightning: 4-6)")
    parser.add_argument("--cfg", type=float, default=1.5, help="CFG scale (Lightning: 1-2). CFG 1 nhanh gấp đôi nhưng bỏ qua negative prompt")
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
