"""Render PDF pages and run the three week-2 OCR engines independently."""
from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
os.environ.setdefault("HF_HOME", str(ROOT / ".cache/ocr/huggingface"))
os.environ.setdefault("PADDLE_HOME", str(ROOT / ".cache/ocr/paddle"))
os.environ.setdefault("PADDLE_PDX_CACHE_HOME", str(ROOT / ".cache/ocr/paddlex"))
# Skip only the SDK's eager host-connectivity probe; normal model downloads remain enabled.
os.environ.setdefault("PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK", "True")
os.environ.setdefault("TORCH_HOME", str(ROOT / ".cache/ocr/torch"))
os.environ.setdefault("CUDA_CACHE_PATH", str(ROOT / ".cache/ocr/cuda"))
MODELS = {
    "qwen2.5-vl": "Qwen/Qwen2.5-VL-7B-Instruct",
    "got-ocr2": "stepfun-ai/GOT-OCR-2.0-hf",
}
MODEL_REVISIONS = {
    "Qwen/Qwen2.5-VL-7B-Instruct": "cc594898137f460bfe9f0759e9844b3ce807cfb5",
    "stepfun-ai/GOT-OCR-2.0-hf": "d3017ef2c2c1395888c8d635c5e0508bcb0ac78d",
}
PROMPT = (
    "Transcribe all visible text in reading order. Preserve traditional Chinese "
    "characters, Vietnamese diacritics, original spelling, punctuation and line breaks. "
    "Do not translate, correct, explain or invent text. Output only the transcription."
)


def save_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temp.replace(path)


def page_numbers(value):
    pages = set()
    try:
        for part in value.split(","):
            bounds = [int(x) for x in part.strip().split("-")]
            if len(bounds) == 1:
                start = end = bounds[0]
            elif len(bounds) == 2:
                start, end = bounds
            else:
                raise ValueError
            if start < 1 or end < start:
                raise ValueError
            pages.update(range(start, end + 1))
    except ValueError as exc:
        raise argparse.ArgumentTypeError("Pages must be positive, e.g. 38-44 or 38,40-42") from exc
    if not pages:
        raise argparse.ArgumentTypeError("Select at least one page")
    return sorted(pages)


def render(args):
    pdf = args.pdf.resolve(strict=True)
    args.output.mkdir(parents=True, exist_ok=True)
    digest = hashlib.sha256(pdf.read_bytes()).hexdigest()
    records = []
    for page in args.pages:
        stem = args.output / f"page-{page:04d}"
        png = stem.with_suffix(".png")
        meta = stem.with_suffix(".json")
        settings = {"pdf": str(pdf), "pdf_sha256": digest, "page": page, "dpi": args.dpi}
        if png.exists() and not args.overwrite:
            if not meta.exists() or json.loads(meta.read_text()) != settings:
                raise ValueError(f"Different or missing render metadata for {png}; use --overwrite")
            print(f"Already rendered: {png}", flush=True)
        else:
            subprocess.run(["pdftoppm", "-f", str(page), "-l", str(page), "-r", str(args.dpi),
                            "-singlefile", "-png", str(pdf), str(stem)], check=True)
            if not png.is_file():
                raise ValueError(f"PDF page {page} did not produce an image")
            save_json(meta, settings)
            print(f"Rendered: {png}", flush=True)
        records.append({"image": png.name, **settings})
    # Includes all rendered pages, so later additions preserve the original sample list.
    records = [json.loads(p.read_text()) | {"image": p.with_suffix('.png').name}
               for p in sorted(args.output.glob("page-*.json")) if p.with_suffix('.png').is_file()]
    save_json(args.output / "pages.json", records)


def doctor(_args):
    print(f"Python: {sys.version.split()[0]} ({sys.executable})")
    for package in ("paddlepaddle", "paddleocr", "torch", "torchvision", "transformers", "accelerate"):
        try:
            print(f"{package}: {importlib.metadata.version(package)}")
        except importlib.metadata.PackageNotFoundError:
            print(f"{package}: MISSING")
    if importlib.util.find_spec("torch"):
        import torch
        print(f"CUDA available: {torch.cuda.is_available()}; PyTorch CUDA: {torch.version.cuda}")
        if torch.cuda.is_available():
            print(f"GPU: {torch.cuda.get_device_name(0)}")
    print(f"Model cache: {ROOT / '.cache/ocr'}")


def crop(args):
    from PIL import Image
    x0, y0, x1, y1 = args.box
    if not (0 <= x0 < x1 <= 1 and 0 <= y0 < y1 <= 1):
        raise ValueError("Crop box must satisfy 0 <= left < right <= 1 and 0 <= top < bottom <= 1")
    if args.output.exists() and not args.overwrite:
        raise ValueError(f"Already exists: {args.output}; use --overwrite")
    if args.input.resolve() == args.output.resolve():
        raise ValueError("Use a different path for the crop")
    with Image.open(args.input) as image:
        width, height = image.size
        box = tuple(round(v * d) for v, d in zip(args.box, (width, height, width, height)))
        if box[0] >= box[2] or box[1] >= box[3]:
            raise ValueError("Crop is smaller than one pixel")
        args.output.parent.mkdir(parents=True, exist_ok=True)
        image.crop(box).save(args.output)
    save_json(args.output.with_suffix('.json'), {
        "source_image": str(args.input.resolve()), "box_normalized": args.box,
        "box_pixels": box, "source_sha256": hashlib.sha256(args.input.read_bytes()).hexdigest()})
    print(f"Cropped: {args.output}")


def paddle_runner(args):
    from paddleocr import PaddleOCR
    if args.device not in ("auto", "cpu"):
        raise ValueError("This setup uses CPU PaddlePaddle. Use --device cpu for PaddleOCR.")
    model = PaddleOCR(lang=args.lang, ocr_version="PP-OCRv5", device="cpu",
                      use_doc_orientation_classify=False, use_doc_unwarping=False,
                      use_textline_orientation=False)

    def recognize(path):
        results = []
        texts = []
        for result in model.predict(str(path)):
            data = result.json
            if callable(data):
                data = data()
            if isinstance(data, str):
                data = json.loads(data)
            results.append(data)
            texts.extend(data.get("res", data).get("rec_texts", []))
        return "\n".join(texts), {"raw": results, "ocr_version": "PP-OCRv5"}
    return recognize


def vlm_runner(args):
    Path(os.environ["CUDA_CACHE_PATH"]).mkdir(parents=True, exist_ok=True)
    import torch
    from PIL import Image
    from transformers import AutoProcessor, BitsAndBytesConfig, GotOcr2ForConditionalGeneration, Qwen2_5_VLForConditionalGeneration
    torch.manual_seed(args.seed)
    device = args.device
    if device == "auto":
        device = "cuda:0" if torch.cuda.is_available() else "cpu"
    if device.startswith("cuda") and not torch.cuda.is_available():
        raise ValueError("CUDA is unavailable. Check NVIDIA driver / CUDA PyTorch, or use a GPU runtime.")
    if args.engine == "qwen2.5-vl" and device == "cpu" and not args.allow_cpu:
        raise ValueError("Qwen 7B needs substantial RAM on CPU. Use a GPU runtime, or explicitly add --allow-cpu.")
    model_id = args.model or MODELS[args.engine]
    # Resolve the branch to a commit once; model and processor then use the same revision.
    from huggingface_hub import HfApi
    revision = args.revision
    if not revision or len(revision) != 40 or any(c not in '0123456789abcdef' for c in revision):
        revision = HfApi().model_info(model_id, revision=revision or "main").sha
    processor_kwargs = {"revision": revision}
    if args.engine == "qwen2.5-vl":
        processor_kwargs.update(min_pixels=256 * 28 * 28, max_pixels=args.max_pixels)
    processor = AutoProcessor.from_pretrained(model_id, **processor_kwargs)
    model_class = Qwen2_5_VLForConditionalGeneration if args.engine == "qwen2.5-vl" else GotOcr2ForConditionalGeneration
    dtype = torch.float16 if device.startswith("cuda") else torch.float32
    load_options = {"revision": revision, "torch_dtype": dtype,
                    "low_cpu_mem_usage": True, "device_map": {"": device}}
    if args.engine == "qwen2.5-vl" and args.quantization == "4bit":
        if not device.startswith("cuda"):
            raise ValueError("The 4-bit Qwen setup requires CUDA. For CPU use --quantization none --allow-cpu.")
        load_options["quantization_config"] = BitsAndBytesConfig(
            load_in_4bit=True, bnb_4bit_quant_type="nf4", bnb_4bit_use_double_quant=True,
            bnb_4bit_compute_dtype=torch.float16)
    model = model_class.from_pretrained(model_id, **load_options).eval()

    def recognize(path):
        with Image.open(path) as opened:
            picture = opened.convert("RGB")
        if args.engine == "qwen2.5-vl":
            messages = [{"role": "user", "content": [
                {"type": "image", "image": picture}, {"type": "text", "text": PROMPT}]}]
            prompt = processor.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
            inputs = processor(text=[prompt], images=[picture], return_tensors="pt").to(device)
        else:
            inputs = processor(picture, return_tensors="pt").to(device)
        options = {"do_sample": False, "max_new_tokens": args.max_new_tokens}
        if args.engine == "got-ocr2":
            options.update(tokenizer=processor.tokenizer, stop_strings="<|im_end|>")
        with torch.inference_mode():
            output = model.generate(**inputs, **options)
        generated = output[:, inputs["input_ids"].shape[1]:]
        text = processor.batch_decode(generated, skip_special_tokens=True)[0]
        return text, {"model": model_id, "revision": revision, "device": device,
                      "generated_tokens": generated.shape[1],
                      "possibly_truncated": generated.shape[1] >= args.max_new_tokens,
                      "quantization": args.quantization if args.engine == "qwen2.5-vl" else "none",
                      "prompt": PROMPT if args.engine == "qwen2.5-vl" else None}
    return recognize


def run(args):
    if args.engine != "qwen2.5-vl":
        args.quantization = "none"
    if args.engine in MODELS:
        args.lang = None
        args.model = args.model or MODELS[args.engine]
        args.revision = args.revision or MODEL_REVISIONS.get(args.model)
    if args.input.is_file():
        images = [args.input]
    else:
        images = sorted(p for p in args.input.iterdir() if p.suffix.lower() in (".png", ".jpg", ".jpeg"))
    if not images:
        raise ValueError(f"No images in {args.input}")
    if args.limit:
        images = images[:args.limit]
    if len({image.stem for image in images}) != len(images):
        raise ValueError("Input images have duplicate stems; rename them before running OCR")
    if any(args.output.resolve() == image.parent.resolve() for image in images):
        raise ValueError("Use a separate output directory to preserve render/crop metadata")
    args.output.mkdir(parents=True, exist_ok=True)
    settings = {key: value for key, value in vars(args).items() if key not in ("func", "input", "output", "overwrite", "limit")}
    pending = []
    for image in images:
        target = args.output / (image.stem + ".json")
        digest = hashlib.sha256(image.read_bytes()).hexdigest()
        if target.exists() and not args.overwrite:
            saved = json.loads(target.read_text())
            if saved.get("image_sha256") != digest or saved.get("settings") != settings:
                raise ValueError(f"Settings/image changed for {target}; use another --output or --overwrite")
            print(f"Already recognized: {target}", flush=True)
        else:
            pending.append((image, target, digest))
    if not pending:
        return
    recognize = paddle_runner(args) if args.engine == "paddleocr" else vlm_runner(args)
    for image, target, digest in pending:
        started = time.perf_counter()
        text, details = recognize(image)
        record = {"image": str(image.resolve()), "image_sha256": digest, "engine": args.engine,
                  "settings": settings, "text": text, "seconds": round(time.perf_counter() - started, 3), **details}
        txt = target.with_suffix(".txt")
        txt.write_text(text + "\n", encoding="utf-8")
        save_json(target, record)
        print(f"OCR: {image.name} -> {txt}", flush=True)
        if details.get("possibly_truncated"):
            print("Token limit reached; review/crop this page or increase --max-new-tokens.", file=sys.stderr)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    check = commands.add_parser("doctor", help="Check installed packages and CUDA")
    check.set_defaults(func=doctor)
    renderer = commands.add_parser("render", help="Render selected PDF pages using Poppler")
    renderer.add_argument("--pdf", type=Path, required=True)
    renderer.add_argument("--pages", type=page_numbers, required=True)
    renderer.add_argument("--dpi", type=int, default=300)
    renderer.add_argument("--output", type=Path, default=Path("out/ocr/week2/images"))
    renderer.add_argument("--overwrite", action="store_true")
    renderer.set_defaults(func=render)
    cropper = commands.add_parser("crop", help="Crop the same source region for all OCR engines")
    cropper.add_argument("--input", type=Path, required=True)
    cropper.add_argument("--output", type=Path, required=True)
    cropper.add_argument("--box", type=float, nargs=4, metavar=("LEFT", "TOP", "RIGHT", "BOTTOM"), required=True)
    cropper.add_argument("--overwrite", action="store_true")
    cropper.set_defaults(func=crop)
    runner = commands.add_parser("run", help="Run one OCR engine on the same input images/crops")
    runner.add_argument("--engine", choices=("paddleocr", *MODELS), required=True)
    runner.add_argument("--input", type=Path, default=Path("out/ocr/week2/images"))
    runner.add_argument("--output", type=Path, required=True)
    runner.add_argument("--device", default="auto", choices=("auto", "cpu", "cuda:0"))
    runner.add_argument("--lang", choices=("chinese_cht", "vi"), default="chinese_cht", help="PaddleOCR recognition language")
    runner.add_argument("--model", help="Override Hugging Face model ID")
    runner.add_argument("--revision", help="Override pinned model commit; actual commit is saved in each JSON")
    runner.add_argument("--seed", type=int, default=42)
    runner.add_argument("--max-new-tokens", type=int, default=4096)
    runner.add_argument("--max-pixels", type=int, default=512 * 28 * 28, help="Qwen visual pixel budget; default sized for 8 GB GPU")
    runner.add_argument("--quantization", choices=("none", "4bit"), default="4bit", help="Qwen quantization; GOT is not quantized")
    runner.add_argument("--allow-cpu", action="store_true", help="Explicitly allow Qwen 7B on CPU (large RAM required)")
    runner.add_argument("--limit", type=int, help="Recognize only first N images for a smoke check")
    runner.add_argument("--overwrite", action="store_true")
    runner.set_defaults(func=run)
    args = parser.parse_args()
    if getattr(args, "dpi", 1) < 1 or getattr(args, "limit", 1) is not None and getattr(args, "limit", 1) < 1:
        parser.error("dpi/limit must be positive")
    try:
        args.func(args)
    except (ValueError, FileNotFoundError, subprocess.CalledProcessError) as exc:
        parser.exit(1, f"Error: {exc}\n")


if __name__ == "__main__":
    main()
