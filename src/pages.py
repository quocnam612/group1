"""Store layout and every OCR variant in one lossless JSON document per page."""
from __future__ import annotations

import argparse
from contextlib import contextmanager
from copy import deepcopy
import csv
import hashlib
import json
from pathlib import Path
import re
import shutil
import tempfile

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PAGES = ROOT / "out/ocr/week2/pages"
LAYERS = ("tieu_de", "han", "phien_am", "dich_sat", "dich_tho", "chu_thich", "so_trang", "can_kiem_tra")
VIEW_FIELDS = {"ocr", "text", "text_source", "stale_ocr", "review", "review_stale"}


def checksum(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def json_hash(value):
    return hashlib.sha256((json.dumps(value, ensure_ascii=False, indent=2)+"\n").encode()).hexdigest()


def save_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix+".tmp")
    if isinstance(value, dict) and "layers" in value and "schema_version" in value:
        # Put line arrays first so readers do not have to scroll through raw OCR.
        first = {key: value[key] for key in ("page", "content", "content_status", "schema_version") if key in value}
        value = first | {key: item for key, item in value.items() if key not in first}
    tmp.write_text(json.dumps(value, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")
    tmp.replace(path)


@contextmanager
def page_lock(path):
    # Locks live in ignored cache, not beside the user's page documents.
    import fcntl
    lock = ROOT / ".cache/ocr/page-locks" / (hashlib.sha256(str(Path(path).resolve()).encode()).hexdigest()+".lock")
    lock.parent.mkdir(parents=True, exist_ok=True)
    with lock.open("a") as stream:
        fcntl.flock(stream, fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(stream, fcntl.LOCK_UN)


def image_identity(image):
    stem = Path(image).stem
    match = re.fullmatch(r"(page-\d+)-(r\d+)", stem)
    return (match[1], match[2]) if match else (stem, None)


def page_path(directory, image):
    return Path(directory) / (image_identity(image)[0]+".json")


def read_page(path):
    path = Path(path)
    if not path.exists():
        return None
    data = json.loads(path.read_text(encoding="utf-8"))
    if data.get("schema_version") != 1 or "layers" not in data:
        raise ValueError(f"Not a page JSON document: {path}; migrate legacy results first")
    return data


def new_page(page_id, image):
    image = Path(image).resolve()
    meta = image.with_suffix(".json")
    source = json.loads(meta.read_text(encoding="utf-8")) if meta.exists() else {}
    source.update(image=str(image), image_sha256=checksum(image))
    match = re.fullmatch(r"page-(\d+)", page_id)
    return {"schema_version": 1, "page": int(match[1]) if match else None,
            "source": source, "layers": {key: {"text": "", "status": "not_present", "regions": []} for key in LAYERS},
            "fullpage_ocr": {}, "layout": None, "layout_assets": None,
            "display_policy": "Unreviewed display: prefer matching-language PaddleOCR, then Qwen/GOT; retain all variants. Not a CER ranking."}


def regions(page):
    return [region for layer in page["layers"].values() for region in layer["regions"]]


def ocr_key(record):
    engine = record["engine"]
    lang = record.get("settings", {}).get("lang")
    return f"{engine}:{lang}" if engine == "paddleocr" and lang else engine


def refresh_text(page):
    for layer in page["layers"].values():
        statuses = set()
        for region in layer["regions"]:
            actual = region.get("ocr", {})
            han = region["layer"] in ("han", "tieu_de_han")
            preferred = ("paddleocr:chinese_cht", "qwen2.5-vl", "got-ocr2", "paddleocr:vi") if han else (
                "paddleocr:vi", "qwen2.5-vl", "got-ocr2", "paddleocr:chinese_cht")
            crop = Path(page["layout_assets"]) / region["crop"]
            current_hash = checksum(crop) if crop.is_file() else None
            stale = [key for key, record in actual.items() if current_hash and record["image_sha256"] != current_hash]
            region["stale_ocr"] = stale
            candidates = [k for k in (*preferred, *actual) if k in actual and k not in stale]
            capable = [k for k in candidates if han or actual[k].get("vietnamese_charset_complete") is not False]
            key = next(iter(capable or candidates), None)
            review = region.get("review")
            region["review_stale"] = bool(review and current_hash and review["image_sha256"] != current_hash)
            if review and not region["review_stale"]:
                region["text"], region["text_source"] = review["text"], "source_patch"
                statuses.add("source_checked")
            else:
                region["text"] = actual[key]["text"] if key else region.get("ocr_hint", "")
                region["text_source"] = key or "layout_hint"
                statuses.add("ocr_unreviewed" if key else "hint_only")
        layer["text"] = "\n".join(r["text"] for r in layer["regions"] if r["text"])
        layer["status"] = ("not_present" if not statuses else next(iter(statuses)) if len(statuses) == 1
                           else "mixed_sources" if "source_checked" in statuses else "mixed_ocr_and_hints")
    page["content"] = {key: layer["text"].splitlines() for key, layer in page["layers"].items()}
    page["content_status"] = {key: layer["status"] for key, layer in page["layers"].items()}
    page["display_policy"] = "View uses source-checked patches first, then matching-language OCR. Raw OCR stays unchanged for CER."


def set_layout(page, layout, assets):
    old = {r["id"]: r for r in regions(page)}
    page["layout"] = {key: deepcopy(value) for key, value in layout.items() if key != "regions"}
    page["layout"]["region_order"] = [r["id"] for r in layout["regions"]]
    page["layout_assets"] = str(Path(assets).resolve())
    page["layers"] = {key: {"text": "", "status": "not_present", "regions": []} for key in LAYERS}
    for value in layout["regions"]:
        region = deepcopy(value)
        previous = old.get(region["id"], {})
        region["ocr"] = previous.get("ocr", {}) if previous.get("layer") == region["layer"] else {}
        if previous.get("layer") == region["layer"] and previous.get("review"):
            region["review"] = deepcopy(previous["review"])
        layer = "tieu_de" if region["layer"].startswith("tieu_de") else region["layer"]
        page["layers"][layer]["regions"].append(region)
    refresh_text(page)


def get_layout(page):
    if not page or not page.get("layout"):
        return None
    data = deepcopy(page["layout"])
    order = data.pop("region_order")
    by_id = {r["id"]: r for r in regions(page)}
    data["regions"] = [{key: deepcopy(value) for key, value in by_id[id_].items() if key not in VIEW_FIELDS}
                       for id_ in order]
    return data


def put_layout(directory, layout, assets):
    target = page_path(directory, layout["image"])
    with page_lock(target):
        page = read_page(target) or new_page(target.stem, layout["image"])
        if page["source"]["image_sha256"] != layout["fingerprint"]["image_sha256"]:
            raise ValueError(f"Source page changed: {target}; use a separate output directory")
        set_layout(page, layout, assets)
        save_json(target, page)
    return target


def record_slot(page, image):
    _page_id, region_id = image_identity(image)
    if region_id is None:
        return page["fullpage_ocr"]
    region = next((r for r in regions(page) if r["id"] == region_id), None)
    if region is None:
        raise ValueError(f"Crop {image} is not registered in this page; run layout first")
    expected = Path(page["layout_assets"]) / region["crop"]
    if expected.resolve() != Path(image).resolve():
        raise ValueError(f"Crop path does not match layout: {image}")
    return region.setdefault("ocr", {})


def get_ocr(directory, image, key):
    page = read_page(page_path(directory, image))
    return record_slot(page, image).get(key) if page else None


def put_ocr(directory, image, record, overwrite=False):
    target = page_path(directory, image)
    with page_lock(target):
        page = read_page(target)
        if page is None:
            if image_identity(image)[1] is not None:
                raise ValueError(f"No page layout for {image}; run layout first")
            page = new_page(target.stem, image)
        if image_identity(image)[1] is None and page["source"]["image_sha256"] != record["image_sha256"]:
            raise ValueError(f"Different source image for {target}")
        slot = record_slot(page, image)
        key = ocr_key(record)
        saved = slot.get(key)
        if saved and not overwrite and (saved["settings"] != record["settings"] or saved["image_sha256"] != record["image_sha256"]):
            raise ValueError(f"Settings/image changed for {target} ({key}); use --overwrite or another output directory")
        if saved and overwrite and any(saved.get(k) != record.get(k) for k in ("settings", "image_sha256", "text")):
            identity = image_identity(image)[1] or "fullpage"
            history = page.setdefault("ocr_history", {}).setdefault(identity, {}).setdefault(key, [])
            if not any(json_hash(item) == json_hash(saved) for item in history):
                history.append(deepcopy(saved))
        slot[key] = deepcopy(record)
        refresh_text(page)
        save_json(target, page)
    return target


def migrate(week2, clean_legacy=False):
    """Import legacy files, verify lossless round-trips, then optionally remove them."""
    week2 = Path(week2)
    output = week2 / "pages"
    layouts = sorted((week2 / "layout").glob("page-*.json"))
    records = sorted((week2 / "results").rglob("*.json")) + sorted((week2 / "fullpage").rglob("*.json"))
    if not layouts and not records:
        return {"pages": len(list(output.glob("page-*.json"))), "ocr_records": 0, "removed": 0}
    parsed = [(path, json.loads(path.read_text(encoding="utf-8"))) for path in records]
    # Never delete a TXT that has been edited independently of its OCR JSON.
    for path, record in parsed:
        txt = path.with_suffix(".txt")
        if txt.exists() and txt.read_text(encoding="utf-8") != record["text"]+"\n":
            raise ValueError(f"TXT differs from raw OCR; preserve/reconcile edits before migration: {txt}")
    original_layouts = [(path, json.loads(path.read_text(encoding="utf-8"))) for path in layouts]
    for _path, layout in original_layouts:
        put_layout(output, layout, week2 / "layout")
    for _path, record in parsed:
        put_ocr(output, record["image"], record)
    for _path, layout in original_layouts:
        assert get_layout(read_page(page_path(output, layout["image"]))) == layout
    for _path, record in parsed:
        assert get_ocr(output, record["image"], ocr_key(record)) == record
    removed = []
    backup = None
    if clean_legacy:
        backup = Path(tempfile.mkdtemp(prefix="group1-page-json-backup-"))
        for path in [*layouts, *(p for p, _record in parsed)]:
            targets = [path] + ([path.with_suffix(".txt")] if path in records and path.with_suffix(".txt").exists() else [])
            for old in targets:
                saved = backup / old.relative_to(week2)
                saved.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(old, saved)
                old.unlink()
                removed.append(old)
        for folder in (week2 / "results", week2 / "fullpage"):
            if folder.exists():
                for path in sorted(folder.rglob("*"), key=lambda p: len(p.parts), reverse=True):
                    if path.is_dir() and not any(path.iterdir()):
                        path.rmdir()
                if not any(folder.iterdir()):
                    folder.rmdir()
    return {"pages": len(list(output.glob("page-*.json"))), "ocr_records": len(parsed),
            "removed": len(removed), "backup": str(backup) if backup else None}


def apply_review_patches(directory, patch_file):
    """Apply source-checked display corrections without editing model outputs."""
    patch_file = Path(patch_file).resolve()
    with patch_file.open(encoding="utf-8", newline="") as stream:
        reader = csv.DictReader(stream, delimiter="\t")
        required = {"page", "region_id", "image_sha256", "text", "note"}
        if not required.issubset(reader.fieldnames or []):
            raise ValueError(f"Missing patch columns: {required}")
        rows = list(reader)
    grouped = {}
    for row in rows:
        grouped.setdefault(int(row["page"]), []).append(row)
    reference = str(patch_file.relative_to(ROOT)) if patch_file.is_relative_to(ROOT) else str(patch_file)
    for number, changes in grouped.items():
        target = Path(directory) / f"page-{number:04d}.json"
        with page_lock(target):
            page = read_page(target)
            if page is None:
                raise ValueError(f"No page for corrections: {target}")
            by_id = {r["id"]: r for r in regions(page)}
            for row in changes:
                region = by_id[row["region_id"]]
                image = Path(page["layout_assets"]) / region["crop"]
                if checksum(image) != row["image_sha256"]:
                    raise ValueError(f"Correction source image changed: {image}")
                region["review"] = {"text": row["text"], "image_sha256": row["image_sha256"],
                                    "patch_file": reference, "patch_sha256": checksum(patch_file),
                                    "before_text": region.get("review", {}).get("before_text", region["text"]),
                                    "note": row["note"]}
            refresh_text(page)
            save_json(target, page)
    return {"pages": len(grouped), "regions": len(rows), "patch_file": reference}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--week2", type=Path, default=ROOT / "out/ocr/week2")
    parser.add_argument("--clean-legacy", action="store_true")
    parser.add_argument("--patches", type=Path, help="TSV source-checked display corrections; preserve raw OCR")
    args = parser.parse_args()
    result = (apply_review_patches(args.week2 / "pages", args.patches) if args.patches
              else migrate(args.week2, args.clean_legacy))
    print(json.dumps(result, ensure_ascii=False))
