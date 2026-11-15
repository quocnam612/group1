"""Run the same layout crops with each engine and write text-only page JSONs."""
from __future__ import annotations

from copy import copy
import hashlib
import json
import os
from pathlib import Path
import time

FIELDS = ("tieu_de", "han", "phien_am", "dich_sat", "dich_tho", "chu_thich", "can_kiem_tra")
HAN_LAYERS = ("han", "tieu_de_han")


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write_crop_manifest(page_paths, assets_dir, output):
    """Keep crop order and hashes, without OCR hints or corrected text."""
    from pages import read_page, regions, save_json
    output, assets_dir = Path(output), Path(assets_dir)
    entries = []
    for path in sorted(page_paths):
        page = read_page(path)
        by_id = {r["id"]: r for r in regions(page)}
        items = []
        for id_ in page["layout"]["region_order"]:
            region = by_id[id_]
            group = "tieu_de" if region["layer"].startswith("tieu_de") else region["layer"]
            if group in FIELDS:
                crop = assets_dir / region["crop"]
                items.append({"id": id_, "layer": region["layer"], "crop": region["crop"],
                              "image_sha256": sha256(crop)})
        entries.append({"file": Path(path).name, "page": page["page"], "regions": items})
    if not entries:
        raise ValueError("No page layouts available to make a crop manifest")
    save_json(output, {"schema_version": 1,
                       "assets_dir": os.path.relpath(assets_dir.resolve(), output.parent.resolve()),
                       "pages": entries})
    return output


def run(args):
    import ocr
    from pages import save_json
    manifest_path = getattr(args, "layout", Path("out/ocr/week2/layout/regions.json")).resolve(strict=True)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assets = (manifest_path.parent / manifest["assets_dir"]).resolve()
    selected_pages = [p for p in manifest["pages"] if not getattr(args, "pages", None) or p["page"] in args.pages]
    if not selected_pages:
        raise ValueError("No pages match the crop manifest")
    if getattr(args, "pages", None) and set(args.pages)-{p["page"] for p in selected_pages}:
        raise ValueError("Some requested pages are missing from the crop manifest")
    if getattr(args, "layers", None) or args.limit:
        raise ValueError("Reference format processes complete pages; use --pages to select a small sample")
    if getattr(args, "paddle_mode", None):
        raise ValueError("Reference format selects PaddleOCR Han/Vietnamese mode automatically")
    scan = getattr(args, "profile", None) == "scan"
    if scan:
        selected_pages = [dict(page, regions=[r for r in page["regions"] if r["layer"] != "can_kiem_tra"])
                          for page in selected_pages]
    if args.engine != "qwen2.5-vl":
        args.quantization = "none"
    if args.engine in ocr.MODELS:
        args.lang = None
        args.model = args.model or ocr.MODELS[args.engine]
        args.revision = args.revision or ocr.MODEL_REVISIONS.get(args.model)
    ignored = {"func", "input", "output", "overwrite", "limit", "layers", "pages", "layout", "format"}
    settings = {k: v for k, v in vars(args).items() if k not in ignored}
    if scan:
        from ocr_preprocess import SCAN_SETTINGS
        settings["preprocessing"] = SCAN_SETTINGS
        if args.engine == "got-ocr2":
            settings["got_profile"] = {"unit": "han-lines; other crops unchanged", "crop_to_patches": False}
    settings["paddle_language_policy"] = "Han-only rows: chinese_cht; all other crops: vi" if args.engine == "paddleocr" else None
    output = args.output / args.engine
    # Model metadata is written once, outside the JSONs the user checks by hand.
    metadata_path = args.output.parent / "runs" / f"{args.engine}.json"
    if metadata_path.exists():
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        if metadata["settings"] != settings:
            if not args.overwrite:
                raise ValueError(f"OCR settings changed: {metadata_path}; use --overwrite")
            # Retain OCR records for pages outside this calibration run.
            previous = metadata["settings"]
            previous_hash = hashlib.sha256(json.dumps(previous, sort_keys=True).encode()).hexdigest()
            metadata.setdefault("settings_history", {})[previous_hash] = previous
            for record in metadata["records"].values():
                record.setdefault("settings_sha256", previous_hash)
            metadata["settings"] = settings
    else:
        metadata = {"settings": settings, "records": {}}
    metadata["layout_manifest_sha256"] = sha256(manifest_path)
    settings_hash = hashlib.sha256(json.dumps(settings, sort_keys=True).encode()).hexdigest()
    jobs = []
    for page in selected_pages:
        if Path(page["file"]).name != page["file"]:
            raise ValueError("Page filenames must not contain directories")
        for region in page["regions"]:
            image = (assets / region["crop"]).resolve(strict=True)
            if not image.is_relative_to(assets):
                raise ValueError(f"Crop is outside layout assets: {image}")
            if sha256(image) != region["image_sha256"]:
                raise ValueError(f"Crop changed: {image}; regenerate the layout manifest first")
            jobs.append((page, region, image))
    if not jobs:
        raise ValueError("No OCR crops in selected pages")
    runners = {}
    def recognize(region, image):
        mode = "han" if region["layer"] in HAN_LAYERS else "viet"
        key = mode if args.engine == "paddleocr" else args.engine
        if key not in runners:
            options = copy(args)
            if args.engine == "paddleocr":
                options.lang = "chinese_cht" if mode == "han" else "vi"
                options.paddle_mode = "han-lines" if mode == "han" else "viet-lines" if scan else "page"
                runners[key] = ocr.paddle_runner(options)
            else:
                runners[key] = ocr.vlm_runner(options)
        return runners[key](image)
    completed = {}
    for index, (page, region, image) in enumerate(jobs, 1):
        identity = f"{page['file']}:{region['id']}"
        record = metadata["records"].get(identity)
        if record and not args.overwrite:
            if record["image_sha256"] != region["image_sha256"]:
                raise ValueError(f"Saved OCR uses a different crop: {identity}; use --overwrite")
            if record.get("settings_sha256", settings_hash) != settings_hash:
                raise ValueError(f"Saved OCR uses different settings: {identity}; use --overwrite")
            print(f"[{index}/{len(jobs)}] Cached: {image.name}", flush=True)
        else:
            started = time.perf_counter()
            if scan and (args.engine != "got-ocr2" or region["layer"] in HAN_LAYERS):
                from ocr_preprocess import prepare_scan_lines
                parts = []
                for line_image, box in prepare_scan_lines(image, ocr.ROOT / ".cache/ocr/preprocessed"):
                    line_text, line_details = recognize(region, line_image)
                    parts.append({"box": box, "image_sha256": sha256(line_image),
                                  "text": line_text, **line_details})
                text = "\n".join(part["text"] for part in parts)
                details = {"lines": parts, "possibly_truncated": any(p.get("possibly_truncated") for p in parts)}
            else:
                text, details = recognize(region, image)
            record = {"image_sha256": region["image_sha256"], "text": text,
                      "settings_sha256": settings_hash,
                      "seconds": round(time.perf_counter()-started, 3), **details}
            metadata["records"][identity] = record
            save_json(metadata_path, metadata)
            print(f"[{index}/{len(jobs)}] OCR: {image.name}", flush=True)
        if record.get("possibly_truncated"):
            print(f"Warning: token limit reached for {image.name}; increase --max-new-tokens and use --overwrite", flush=True)
        completed.setdefault(page["file"], {})[region["id"]] = record
        if len(completed[page["file"]]) == len(page["regions"]):
            content = {key: [] for key in FIELDS}
            for item in page["regions"]:
                group = "tieu_de" if item["layer"].startswith("tieu_de") else item["layer"]
                content[group].extend(completed[page["file"]][item["id"]]["text"].splitlines())
            save_json(output / page["file"], content)
            print(f"Saved: {output / page['file']}", flush=True)
    print(f"Done: {len(selected_pages)} pages -> {output}; run metadata -> {metadata_path}", flush=True)
