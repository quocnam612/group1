"""Run the same layout crops with each engine and write text-only page JSONs."""
from __future__ import annotations

from copy import copy, deepcopy
import hashlib
import json
import os
from pathlib import Path
import time

FIELDS = ("tieu_de", "han", "phien_am", "dich_sat", "dich_tho", "chu_thich", "can_kiem_tra")
HAN_LAYERS = ("han", "tieu_de_han")


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def compatible_native_record(source_settings, record, args, image_sha256):
    """Reuse only equivalent native-image Qwen inference, never reviewed text."""
    import ocr
    keys = ("engine", "device", "seed", "quantization", "max_pixels", "model", "revision")
    if any(source_settings.get(key) != getattr(args, key, None) for key in keys):
        return False
    if bool(source_settings.get("cpu_offload")) != bool(getattr(args, "cpu_offload", False)):
        return False
    return (record.get("image_sha256") == image_sha256 and record.get("prompt") == ocr.PROMPT
            and record.get("model") == args.model and record.get("revision") == args.revision
            and not record.get("possibly_truncated") and isinstance(record.get("generated_tokens"), int)
            and record["generated_tokens"] < args.max_new_tokens)


def write_crop_manifest(page_paths, assets_dir, output):
    """Keep crop geometry and hashes, without OCR hints or corrected text."""
    from pages import read_page, regions, save_json
    output, assets_dir = Path(output), Path(assets_dir)
    entries = []
    sources = []
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
                if "bbox" in region:
                    items[-1]["bbox"] = region["bbox"]
        entry = {"file": Path(path).name, "page": page["page"], "regions": items}
        source = page.get("source", {})
        if source.get("image"):
            from PIL import Image
            image = Path(source["image"])
            with Image.open(image) as im:
                size = list(im.size)
            entry.update(image=os.path.relpath(image.resolve(), assets_dir.resolve()),
                         image_sha256=sha256(image), image_size=size)
        if source.get("pdf_sha256") and source.get("dpi"):
            sources.append({"pdf_sha256": source["pdf_sha256"], "dpi": source["dpi"]})
        entries.append(entry)
    if not entries:
        raise ValueError("No page layouts available to make a crop manifest")
    manifest = {"schema_version": 2,
                "assets_dir": os.path.relpath(assets_dir.resolve(), output.parent.resolve()), "pages": entries}
    if len(sources) == len(entries) and all(s == sources[0] for s in sources):
        manifest["source"] = sources[0]
    save_json(output, manifest)
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
    balanced = getattr(args, "profile", None) == "balanced"
    if scan or balanced:
        selected_pages = [dict(page, regions=[r for r in page["regions"] if r["layer"] != "can_kiem_tra"])
                          for page in selected_pages]
    if args.engine != "qwen2.5-vl":
        args.quantization = "none"
    if args.engine in ocr.MODELS:
        args.lang = None
        args.model = args.model or ocr.MODELS[args.engine]
        args.revision = args.revision or ocr.MODEL_REVISIONS.get(args.model)
    ignored = {"func", "input", "output", "overwrite", "limit", "layers", "pages", "layout", "format", "native_cache"}
    settings = {k: v for k, v in vars(args).items() if k not in ignored}
    if scan:
        from ocr_preprocess import SCAN_SETTINGS
        settings["preprocessing"] = SCAN_SETTINGS
        if args.engine == "got-ocr2":
            settings["got_profile"] = {"unit": "han-lines; other crops unchanged", "crop_to_patches": False}
    if balanced:
        from ocr_preprocess import SCAN_SETTINGS
        settings["preprocessing"] = {"han": SCAN_SETTINGS, "vietnamese": "original block image"}
    if args.engine == "tesseract":
        if not (scan or balanced):
            raise ValueError("Tesseract requires --profile scan or balanced")
        installation = ocr.ROOT / ".cache/ocr/tesseract/installation.json"
        settings["tesseract"] = json.loads(installation.read_text(encoding="utf-8"))
        settings["language_policy"] = "chi_tra for Han, vie+chi_tra for commentary, vie otherwise"
        settings["psm"] = "7 for Han; 6 for Vietnamese" if balanced else 7
        settings["oem"] = 1
        settings["decoder_dictionaries"] = "Vietnamese only" if balanced else False
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
    native_cache = None
    cache_path = getattr(args, "native_cache", None)
    if cache_path:
        if not balanced or args.engine != "qwen2.5-vl":
            raise ValueError("--native-cache requires Qwen with --profile balanced")
        native_cache = json.loads(cache_path.read_text(encoding="utf-8"))
        native_cache["source_sha256"] = sha256(cache_path)
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
        if args.engine == "tesseract":
            mode = "chi_tra" if mode == "han" else "vie+chi_tra" if region["layer"] == "chu_thich" else "vie"
        key = mode if args.engine in ("paddleocr", "tesseract") else args.engine
        if key not in runners:
            options = copy(args)
            if args.engine == "paddleocr":
                options.lang = "chinese_cht" if mode == "han" else "vi"
                options.paddle_mode = "han-lines" if mode == "han" else "viet-lines" if scan else "page"
                runners[key] = ocr.paddle_runner(options)
            elif args.engine == "tesseract":
                options.tesseract_language = mode
                options.tesseract_psm = 6 if balanced and mode != "chi_tra" else 7
                options.tesseract_dictionaries = balanced and mode != "chi_tra"
                runners[key] = ocr.tesseract_runner(options)
            else:
                runners[key] = ocr.vlm_runner(options)
        return runners[key](image)
    completed = {}
    for index, (page, region, image) in enumerate(jobs, 1):
        identity = f"{page['file']}:{region['id']}"
        record = metadata["records"].get(identity)
        reused_native = False
        if native_cache and region["layer"] not in HAN_LAYERS:
            candidate = native_cache.get("records", {}).get(identity)
            if candidate and compatible_native_record(native_cache["settings"], candidate, args, region["image_sha256"]):
                record = deepcopy(candidate)
                record["settings_sha256"] = settings_hash
                record["native_cache"] = {"file": str(cache_path), "sha256": native_cache["source_sha256"],
                                          "reason": "Same source pixels, model, prompt, seed and decoder; token limit not binding."}
                metadata["records"][identity] = record
                save_json(metadata_path, metadata)
                reused_native = True
        if record and (not args.overwrite or reused_native):
            if record["image_sha256"] != region["image_sha256"]:
                raise ValueError(f"Saved OCR uses a different crop: {identity}; use --overwrite")
            if record.get("settings_sha256", settings_hash) != settings_hash:
                raise ValueError(f"Saved OCR uses different settings: {identity}; use --overwrite")
            print(f"[{index}/{len(jobs)}] Cached{' native' if reused_native else ''}: {image.name}", flush=True)
        else:
            started = time.perf_counter()
            if (scan and args.engine != "got-ocr2") or (scan or balanced) and region["layer"] in HAN_LAYERS:
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
    # A cache-only run must also persist the current manifest identity.
    save_json(metadata_path, metadata)
    print(f"Done: {len(selected_pages)} pages -> {output}; run metadata -> {metadata_path}", flush=True)
