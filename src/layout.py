"""Detect layout, refine Han/Viet regions, and propose verse-line pairs for Kinh Thi.

PP-DocLayout labels geometry, not languages. Existing PaddleOCR line boxes/text
are used only as fallible hints; the resulting regions/pairs require review.
"""
from __future__ import annotations

import argparse
from collections import defaultdict
from difflib import SequenceMatcher
import hashlib
import importlib.metadata
import json
import re
from statistics import median
import unicodedata
from pathlib import Path

from ocr import ROOT


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def normalized(text):
    text = unicodedata.normalize("NFD", text.lower().replace("đ", "d"))
    return "".join(c for c in text if "a" <= c <= "z")


def script(text):
    han = sum("CJK" in unicodedata.name(c, "") or
              "IDEOGRAPH" in unicodedata.name(c, "") for c in text)
    latin = sum("LATIN" in unicodedata.name(c, "") for c in text)
    return "mixed" if han and latin else "han" if han else "viet" if latin else "other"


def overlap_y(a, b):
    return max(0, min(a[3], b[3]) - max(a[1], b[1])) / max(1, min(a[3]-a[1], b[3]-b[1]))


def contains(box, line):
    x, y = (line[0]+line[2])/2, (line[1]+line[3])/2
    return box[0] <= x <= box[2] and box[1] <= y <= box[3]


def covers_line(box, line):
    area = max(0, min(box[2], line[2])-max(box[0], line[0])) * max(0, min(box[3], line[3])-max(box[1], line[1]))
    return area / max(1, (line[2]-line[0])*(line[3]-line[1]))


def heading(text):
    value = normalized(text)
    for key, section in (("dichnghia", "dich_sat"), ("dichtho", "dich_tho"),
                         ("chugiaicuachuhy", "chu_thich"), ("chugiai", "chu_thich")):
        if SequenceMatcher(None, value, key).ratio() >= .82:
            return section
    return None


def verse_index(text):
    return re.match(r"\s*[.·]*\s*(\d+)\s*[.,):]", text)


def refine(lines, boxes, initial_section):
    """Rules for horizontal verse and commentary; no automatic translation alignment."""
    lines = sorted(lines, key=lambda line: ((line["bbox"][1]+line["bbox"][3])/2, line["bbox"][0]))
    section, segment = initial_section, 0
    for i, line in enumerate(lines):
        line["id"] = f"l{i+1:03d}"
        line["script"] = script(line["text"])
        matches = [b for b in boxes if contains(b["coordinate"], line["bbox"])]
        titles = [b for b in matches if b["label"] in ("doc_title", "paragraph_title")]
        numbers = [b for b in matches if b["label"] in ("number", "page_number")]
        next_section = heading(line["text"])
        if next_section:
            section = next_section
            segment += 1
            layer = "tieu_de"
        elif titles:
            layer = "tieu_de"
            if normalized(line["text"]).startswith(("chuong", "baithu")):
                section = "main"
                segment += 1
        elif numbers and line["text"].strip().isdigit():
            layer = "so_trang"
        elif not matches and len(line["text"].strip()) <= 2:
            layer = "can_kiem_tra"
        elif section == "main":
            layer = "han" if line["script"] == "han" else "phien_am" if line["script"] == "viet" else "can_kiem_tra"
        elif section in ("dich_sat", "dich_tho", "chu_thich"):
            layer = section
        else:
            layer = "can_kiem_tra"
        texts = [b for b in matches if b["label"] == "text"]
        parent = max(texts, key=lambda b: (b["coordinate"][2]-b["coordinate"][0]) *
                     (b["coordinate"][3]-b["coordinate"][1]), default=None)
        line.update(layer=layer, section=section, segment=segment,
                    layout_block=parent["id"] if parent else None)
        line["flags"] = []
        if line["score"] < .8:
            line["flags"].append("low_ocr_confidence")
        if line["script"] == "mixed":
            line["flags"].append("mixed_script_keep_intact")
        if layer == "can_kiem_tra":
            line["flags"].append("unknown_layer")
        if not matches:
            line["flags"].append("unassigned_layout")

    # Pair only Han/phonetic lines with matching vertical spans and a clear gutter.
    # A Han heading beside an unnumbered Viet heading is kept out of the poem text.
    pairs, used = [], set()
    for han in [line for line in lines if line["layer"] == "han"]:
        candidates = [v for v in lines if v["layer"] == "phien_am" and v["id"] not in used
                      and v["segment"] == han["segment"]
                      and v["bbox"][0] > han["bbox"][2]
                      and overlap_y(han["bbox"], v["bbox"]) >= .5]
        if not candidates:
            han["flags"].append("unpaired_han")
            continue
        viet = min(candidates, key=lambda v: abs(sum(v["bbox"][1::2])-sum(han["bbox"][1::2])))
        used.add(viet["id"])
        index = verse_index(viet["text"])
        if not index:
            han["layer"], viet["layer"] = "tieu_de_han", "tieu_de_viet"
            continue
        if han["bbox"][2]-han["bbox"][0] < 1.5*(han["bbox"][3]-han["bbox"][1]) or len(han["text"].strip()) < 3:
            used.remove(viet["id"])
            han["flags"].append("fragmented_han_detection")
            continue
        pairs.append({"id": f"p{len(pairs)+1:03d}", "han_line": han["id"],
                      "viet_line": viet["id"], "source_index_hint": int(index[1]),
                      "relation": "han_phien_am", "level": "sentence_candidate",
                      "status": "needs_review"})
    for line in lines:
        if line["layer"] == "phien_am" and line["id"] not in used:
            line["flags"].append("unpaired_viet")
    return lines, pairs, section


def recover_han_titles(image, lines):
    """Find a missed short Han title opposite an unnumbered Vietnamese title.

    The pixels supply only the crop geometry. Text remains empty until OCR;
    no title spelling is supplied by this rule.
    """
    from PIL import ImageOps
    additions = []
    for viet in lines:
        if viet["layer"] != "phien_am" or verse_index(viet["text"]):
            continue
        numbered = [l for l in lines if l["layer"] == "phien_am" and l["segment"] == viet["segment"]
                    and verse_index(l["text"])]
        han = [l for l in lines if l["layer"] == "han" and l["segment"] == viet["segment"]]
        if not numbered or not han or viet["bbox"][3] >= min(l["bbox"][1] for l in numbered):
            continue
        height = viet["bbox"][3]-viet["bbox"][1]
        left, right = min(l["bbox"][0] for l in han), max(l["bbox"][2] for l in han)
        top = max(0, int(viet["bbox"][1]-height*.3))
        bottom = min(image.height, int(viet["bbox"][3]+height*.3))
        right = min(right, viet["bbox"][0]-8)
        if right <= left:
            continue
        area = image.crop((left, top, right, bottom)).convert("L")
        ink = ImageOps.invert(area).point(lambda v: 255 if v > 75 else 0).getbbox()
        if ink is None:
            continue
        glyph_w, glyph_h = ink[2]-ink[0], ink[3]-ink[1]
        # A one/two-character title, not another four-character verse row.
        if glyph_h < height*.5 or not .8 <= glyph_w/max(1, glyph_h) <= 3:
            continue
        bbox = [left+ink[0], top+ink[1], left+ink[2], top+ink[3]]
        if any(l["layer"] == "tieu_de_han" and overlap_y(l["bbox"], bbox) >= .5 for l in lines):
            continue
        viet["layer"] = "tieu_de_viet"
        viet["flags"] = [f for f in viet["flags"] if f != "unpaired_viet"]
        additions.append({"id": f"l{len(lines)+len(additions)+1:03d}", "text": "", "bbox": bbox,
                          "score": None, "script": "han", "layer": "tieu_de_han",
                          "section": viet["section"], "segment": viet["segment"], "layout_block": None,
                          "flags": ["title_inferred_from_parallel_viet"], "source": "image_geometry"})
    return lines+additions


def assign_region_ids(regions, page_stem, previous=None):
    """Keep existing crop filenames stable when adding a newly found title."""
    previous = previous or []
    old_ids = {(r["layer"], tuple(r["line_ids"])): r["id"] for r in previous}
    next_id = max((int(r["id"][1:]) for r in previous), default=0)+1
    for region in regions:
        key = (region["layer"], tuple(region["line_ids"]))
        if key in old_ids:
            region["id"] = old_ids[key]
        else:
            region["id"] = f"r{next_id:03d}"
            next_id += 1
        region["crop"] = f'images/{region["layer"]}/{page_stem}-{region["id"]}.png'


def make_regions(lines, size, padding):
    groups = defaultdict(list)
    for line in lines:
        # Separate headings; merge body lines only within the same layout block/layer.
        parent = (line["id"] if line["layer"].startswith("tieu_de") else
                  f'segment-{line["segment"]}' if line["layer"] in ("han", "phien_am") else
                  line["layout_block"] or line["id"])
        groups[(line["layer"], line["section"], parent)].append(line)
    regions = []
    for (layer, section, _parent), group in groups.items():
        b = [min(l["bbox"][0] for l in group), min(l["bbox"][1] for l in group),
             max(l["bbox"][2] for l in group), max(l["bbox"][3] for l in group)]
        flags = {f for l in group for f in l["flags"]}
        if layer == "han":
            viet = [l for l in lines if l["layer"] == "phien_am" and l["segment"] == group[0]["segment"]
                    and verse_index(l["text"])]
            # Detection sometimes joins Han characters vertically or misses a row.
            # Keep the whole Han column, using parallel numbered Viet rows only
            # to extend its vertical bounds. Do not invent missing OCR text/pairs.
            if viet and (len(viet) != len(group) or "fragmented_han_detection" in flags):
                slack = median(l["bbox"][3]-l["bbox"][1] for l in viet) * .3
                b[1] = min(b[1], min(l["bbox"][1] for l in viet)-slack)
                b[3] = max(b[3], max(l["bbox"][3] for l in viet)+slack)
                flags.add("han_bounds_from_parallel_viet_needs_review")
        bbox = [max(0, int(b[0])-padding), max(0, int(b[1])-padding),
                min(size[0], int(b[2]+padding+1)), min(size[1], int(b[3]+padding+1))]
        regions.append({"layer": layer, "section": section, "bbox": bbox,
                        "line_ids": [l["id"] for l in group],
                        "ocr_hint": "\n".join(l["text"] for l in group),
                        "flags": sorted(flags),
                        "status": "needs_review"})
    for region in regions:
        if region["layer"] != "han":
            continue
        conflicting = [l["id"] for l in lines if l["script"] in ("viet", "mixed")
                       and l["id"] not in region["line_ids"] and covers_line(region["bbox"], l["bbox"]) > .05]
        if conflicting:
            # Never send a broad mixed-language box to the Han-only OCR folder.
            region.update(layer="can_kiem_tra", proposed_layer="han", conflicting_line_ids=conflicting)
            region["flags"].append("han_crop_overlaps_viet")
    return sorted(regions, key=lambda r: (r["bbox"][1], r["bbox"][0]))


def write_images(image, record, output):
    from PIL import ImageDraw, ImageFont
    preview = image.copy()
    draw = ImageDraw.Draw(preview)
    font = ImageFont.load_default(size=20)
    colors = {"han": "#8e44ad", "phien_am": "#168aad", "dich_sat": "#228b22",
              "dich_tho": "#d2691e", "chu_thich": "#bd8b00", "so_trang": "#666666"}
    for region in record["regions"]:
        target = output / region["crop"]
        target.parent.mkdir(parents=True, exist_ok=True)
        image.crop(region["bbox"]).save(target)
        color = colors.get(region["layer"], "#c0392b")
        draw.rectangle(region["bbox"], outline=color, width=3)
        x, y = region["bbox"][:2]
        draw.text((x, max(0, y-23)), f'{region["id"]} {region["layer"]}', fill=color, font=font)
    target = output / record["preview"]
    target.parent.mkdir(parents=True, exist_ok=True)
    preview.thumbnail((1000, 1500))
    preview.save(target)


def main():
    from pages import get_layout, json_hash, put_layout, read_page
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=Path("out/ocr/week2/images"))
    parser.add_argument("--output", type=Path, default=Path("out/ocr/week2/pages"), help="Shared per-page JSON folder")
    parser.add_argument("--assets-dir", type=Path, default=Path("out/ocr/week2/layout"), help="Crop images and review.html")
    parser.add_argument("--model", default="PP-DocLayout_plus-L")
    parser.add_argument("--threshold", type=float, default=.5)
    parser.add_argument("--padding", type=int, default=8)
    parser.add_argument("--initial-section", choices=("unknown", "main", "dich_sat", "dich_tho", "chu_thich"), default="unknown")
    parser.add_argument("--limit", type=int)
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args()
    if not 0 < args.threshold < 1 or args.padding < 0 or args.limit is not None and args.limit < 1:
        parser.error("threshold must be in (0,1), padding >= 0, limit >= 1")
    from PIL import Image
    images = [args.input] if args.input.is_file() else sorted(args.input.glob("*.png"))
    if args.limit:
        images = images[:args.limit]
    if not images:
        parser.error("No input PNG images")
    if args.output.resolve() == args.input.resolve() or any(args.output.resolve() == p.parent.resolve() for p in images):
        parser.error("Use a separate output folder")
    model = None
    def load_model():
        from paddleocr import LayoutDetection
        return LayoutDetection(model_name=args.model, device="cpu", cpu_threads=2, enable_mkldnn=False)
    cache = ROOT / ".cache/ocr/paddlex/official_models" / args.model
    if not cache.is_dir():
        model = load_model()
    artifacts = {p.name: digest(p) for p in sorted(cache.glob("inference.*")) if p.is_file()}
    settings = {"model": args.model, "model_artifacts_sha256": artifacts,
                "paddleocr": importlib.metadata.version("paddleocr"),
                "paddlex": importlib.metadata.version("paddlex"),
                "paddlepaddle": importlib.metadata.version("paddlepaddle"),
                "threshold": args.threshold, "padding": args.padding, "rules_version": 5,
                "device": "cpu", "cpu_threads": 2, "enable_mkldnn": False,
                "layout_nms": True, "initial_section": args.initial_section}
    section = args.initial_section
    for path in images:
        image_sha = digest(path)
        target = args.output / f"{path.stem}.json"
        page = read_page(target)
        previous = get_layout(page)
        hint = page.get("fullpage_ocr", {}).get("paddleocr:chinese_cht") if page else None
        if hint and hint.get("image_sha256") != image_sha:
            raise ValueError(f"PaddleOCR hints are not from this image: {target}")
        if previous and not args.overwrite:
            fingerprint = previous["fingerprint"]
            if (fingerprint["image_sha256"] != image_sha or fingerprint["settings"] != settings or
                    fingerprint["incoming_section"] != section or
                    hint and fingerprint["ocr_hint_sha256"] != json_hash(hint)):
                raise ValueError(f"Settings/source changed for {target}; use another --output or --overwrite")
            if Path(page["layout_assets"]).resolve() != args.assets_dir.resolve():
                raise ValueError(f"Layout assets directory changed for {target}; use --overwrite")
            if not all((args.assets_dir / r["crop"]).is_file() for r in previous["regions"]) or not (args.assets_dir / previous["preview"]).is_file():
                raise ValueError(f"Missing crop/preview for {target}; regenerate with --overwrite")
            section = previous["outgoing_section"]
            print(f"Already processed: {path.name}", flush=True)
            continue
        lines = []
        if hint:
            for raw_ocr in hint["raw"]:
                raw_ocr = raw_ocr.get("res", raw_ocr)
                for text, bbox, score in zip(raw_ocr["rec_texts"], raw_ocr["rec_boxes"], raw_ocr["rec_scores"], strict=True):
                    lines.append({"text": text, "bbox": bbox, "score": score})
        elif previous:
            # Legacy full-page files may have been deleted. Keep using the saved
            # line geometry/text; this does not invent a full-page OCR result.
            lines = [{key: line[key] for key in ("text", "bbox", "score")}
                     for line in previous["lines"] if line.get("source") != "image_geometry"]
        else:
            raise ValueError(f"No PaddleOCR full-page hints in {target}; run chinese_cht on the page first")
        fingerprint = {"image_sha256": image_sha, "ocr_hint_sha256": json_hash(hint or lines),
                       "incoming_section": section, "settings": settings}
        if model is None:
            model = load_model()
        result = model.predict(str(path), batch_size=1, layout_nms=True, threshold=args.threshold)[0]
        raw = result.json
        if callable(raw):
            raw = raw()
        if isinstance(raw, str):
            raw = json.loads(raw)
        boxes = raw.get("res", raw)["boxes"]
        for i, box in enumerate(boxes):
            box["id"] = f"b{i+1:03d}"
        lines, pairs, section = refine(lines, boxes, section)
        with Image.open(path) as opened:
            image = opened.convert("RGB")
        lines = recover_han_titles(image, lines)
        regions = make_regions(lines, image.size, args.padding)
        assign_region_ids(regions, path.stem, previous["regions"] if previous else None)
        record = {"image": str(path.resolve()), "fingerprint": fingerprint, "size": list(image.size),
                  "preview": f"images/preview/{path.stem}.png", "raw_layout_boxes": boxes,
                  "lines": lines, "regions": regions, "pairs": pairs, "outgoing_section": section,
                  "reading_order": "horizontal Kinh Thi; top-to-bottom within each region",
                  "limitations": ["OCR hints may misclassify language or headings", "Pairs require manual review",
                                  "No translation alignment, voting or CER computed"]}
        write_images(image, record, args.assets_dir)
        if previous:
            current = {r["crop"] for r in regions}
            for region in previous["regions"]:
                old_crop = args.assets_dir / region["crop"]
                if region["crop"] not in current and old_crop.resolve().is_relative_to((args.assets_dir / "images").resolve()):
                    old_crop.unlink(missing_ok=True)
        put_layout(args.output, record, args.assets_dir)
        print(f"Layout: {path.name}: {len(regions)} regions, {len(pairs)} Han/phonetic pairs", flush=True)
    args.assets_dir.mkdir(parents=True, exist_ok=True)
    from ocr_reference import write_crop_manifest
    write_crop_manifest(args.output.glob("page-*.json"), args.assets_dir, args.assets_dir / "regions.json")
    from review import build_review
    build_review(args.output)


if __name__ == "__main__":
    main()
