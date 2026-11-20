"""Full-book scan layout and voting with frozen week-two calibration ranks."""
from __future__ import annotations

from argparse import Namespace
import copy
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
import unicodedata

from pages import save_json
from ocr import ROOT
from ocr_reference import sha256

VERSION = 1


def selected_pages(book, pages=None):
    return list(pages) if pages is not None else list(range(1, book["total_pages"]+1))


def prepare(book, config, cache, pages=None):
    from PIL import Image
    from layout import (assign_region_ids, make_regions, normalized, recover_han_titles,
                        refine, script, verse_index)
    from paddleocr import LayoutDetection, PaddleOCR
    from ocr_preprocess import scan_line_boxes

    cache = Path(cache)
    pdf = ROOT / config.get("data_dir", ".") / book["file"]
    pdf_hash = sha256(pdf)
    dpi = config["ocr"]["dpi"]
    max_lines = config.get("corpus", {}).get("max_crop_lines", 8)
    hints_runner = detector = None
    hint_settings = {"cpu_threads": 2, "enable_mkldnn": False, "text_recognition_batch_size": 4,
                     "text_det_limit_type": "max", "text_det_limit_side_len": 1280}
    artifacts = {}
    for name in ("PP-OCRv5_server_det", "PP-OCRv5_server_rec", "PP-DocLayout_plus-L"):
        directory = ROOT/".cache/ocr/paddlex/official_models"/name
        artifacts[name] = {p.name: sha256(p) for p in sorted(directory.glob("inference.*")) if p.is_file()}
    incoming = "unknown"
    entries = []
    for number in selected_pages(book, pages):
        image_path = cache / "images" / f"page-{number:04d}.png"
        record_path = cache / "layout/pages" / f"page-{number:04d}.json"
        signature = {"pdf_sha256": pdf_hash, "dpi": dpi, "rules_version": VERSION,
                     "max_crop_lines": max_lines, "incoming_section": incoming,
                     "hint_settings": hint_settings, "model_artifacts_sha256": artifacts}
        if record_path.exists():
            page = json.loads(record_path.read_text(encoding="utf-8"))
            if page["signature"] != signature:
                raise ValueError(f"Layout configuration changed: {record_path}; use a fresh cache directory")
            if not image_path.exists() or sha256(image_path) != page["image_sha256"]:
                raise ValueError(f"Missing/changed source image: {image_path}")
            for region in page["regions"]:
                path = cache / "layout" / region["crop"]
                if not path.exists() or sha256(path) != region["image_sha256"]:
                    raise ValueError(f"Missing/changed cached crop: {path}")
            incoming = page["outgoing_section"]
            entries.append(page)
            print(f"Layout cached: {number}/{book['total_pages']}", flush=True)
            continue
        image_path.parent.mkdir(parents=True, exist_ok=True)
        if not image_path.exists():
            subprocess.run(["pdftoppm", "-f", str(number), "-l", str(number), "-r", str(dpi),
                            "-singlefile", "-png", str(pdf), str(image_path.with_suffix(""))], check=True)
        hint_path = cache / "hints" / f"page-{number:04d}.json"
        if hint_path.exists():
            hint = json.loads(hint_path.read_text(encoding="utf-8"))
            if hint["image_sha256"] != sha256(image_path):
                raise ValueError(f"Hint/image mismatch: {hint_path}")
        else:
            if hints_runner is None:
                hints_runner = PaddleOCR(lang="chinese_cht", ocr_version="PP-OCRv5", device="cpu",
                                        use_doc_orientation_classify=False, use_doc_unwarping=False,
                                        use_textline_orientation=False, **hint_settings)
            raw_results = []
            for result in hints_runner.predict(str(image_path)):
                data = result.json
                data = data() if callable(data) else data
                raw_results.append(json.loads(data) if isinstance(data, str) else data)
            hint = {"image_sha256": sha256(image_path), "raw": raw_results, "settings": hint_settings}
            save_json(hint_path, hint)
        lines = []
        for raw in hint["raw"]:
            raw = raw.get("res", raw)
            for text, bbox, score in zip(raw["rec_texts"], raw["rec_boxes"], raw["rec_scores"], strict=True):
                lines.append({"text": text, "bbox": bbox, "score": score})
        if detector is None:
            detector = LayoutDetection(model_name="PP-DocLayout_plus-L", device="cpu",
                                       cpu_threads=2, enable_mkldnn=False)
        raw = detector.predict(str(image_path), batch_size=1, layout_nms=True, threshold=.5)[0].json
        raw = raw() if callable(raw) else raw
        raw = json.loads(raw) if isinstance(raw, str) else raw
        boxes = raw.get("res", raw)["boxes"]
        for i, box in enumerate(boxes):
            box["id"] = f"b{i:04d}"
        # Chapter labels reliably reset state even when the layout model calls
        # them ordinary text; numbered verses must not become headings.
        for line in lines:
            text = normalized(line["text"])
            if text.startswith(("chuong", "baithu")) and len(text) < 28:
                boxes.append({"id": f"heading-{len(boxes)}", "label": "paragraph_title", "coordinate": line["bbox"]})
        numbered = [l for l in lines if verse_index(l["text"])]
        for box in boxes:
            if box["label"] in ("paragraph_title", "doc_title"):
                from layout import contains
                if any(contains(box["coordinate"], line["bbox"]) for line in numbered):
                    box["label"] = "text"
        lines, pairs, outgoing = refine(lines, boxes, incoming)
        with Image.open(image_path) as opened:
            image = opened.convert("RGB")
        lines = recover_han_titles(image, lines)
        regions = make_regions(lines, image.size, 8)
        # Keep uncertain text for review and OCR rather than dropping it. Its
        # original proposed layer remains in the per-page audit record.
        for region in regions:
            if region["layer"] == "can_kiem_tra":
                region["original_layer"] = "can_kiem_tra"
                region["layer"] = "chu_thich"
                region["flags"] = sorted(set(region["flags"])|{"unknown_layer"})
        chunks = []
        for region in regions:
            x0, y0, x1, y1 = region["bbox"]
            row_boxes = (scan_line_boxes(image.crop((x0, y0, x1, y1)))
                         if region["layer"] not in ("han", "tieu_de_han", "so_trang") else [])
            if len(row_boxes) <= max_lines:
                chunks.append(region)
                continue
            boundaries = [0]+[(row_boxes[i-1][3]+row_boxes[i][1])//2
                              for i in range(max_lines, len(row_boxes), max_lines)]+[y1-y0]
            for start, end in zip(boundaries, boundaries[1:]):
                chunks.append(dict(region, bbox=[x0, y0+start, x1, y0+end]))
        regions = sorted(chunks, key=lambda r: (r["bbox"][1], r["bbox"][0]))
        assign_region_ids(regions, image_path.stem)
        filtered = []
        for region in regions:
            path = cache / "layout" / region["crop"]
            path.parent.mkdir(parents=True, exist_ok=True)
            image.crop(region["bbox"]).save(path)
            region["image_sha256"] = sha256(path)
            if region["layer"] != "so_trang":
                filtered.append(region)
        page = {"page": number, "file": f"page-{number:04d}.json", "signature": signature,
                "image": "../images/"+image_path.name, "image_sha256": sha256(image_path),
                "image_size": list(image.size), "regions": filtered, "lines": lines,
                "outgoing_section": outgoing}
        save_json(record_path, page)
        entries.append(page)
        incoming = outgoing
        # Publish after each page so an interrupted layout pass can resume.
        save_manifest(cache, entries, pdf_hash, dpi)
        print(f"Layout: {number}/{book['total_pages']} ({len(filtered)} crops)", flush=True)
    save_manifest(cache, entries, pdf_hash, dpi)
    return entries


def save_manifest(cache, entries, pdf_hash, dpi):
    save_json(Path(cache)/"layout/regions.json", {"schema_version": 2, "assets_dir": ".",
              "source": {"pdf_sha256": pdf_hash, "dpi": dpi},
              "pages": [{k: p[k] for k in ("page", "file", "image", "image_sha256", "image_size", "regions")} for p in entries]})


def ocr_command(engine, book, config, cache, pages=None):
    options = config["ocr"].get("engine_options", {}).get(engine, {})
    command = [sys.executable, str(ROOT/"src/ocr.py"), "run", "--engine", engine, "--format", "reference",
               "--layout", str(Path(cache)/"layout/regions.json"), "--output", str(Path(cache)/"ocr/pages"),
               "--pages", ",".join(map(str, selected_pages(book, pages))), "--seed", str(config.get("seed", 42))]
    for key, value in options.items():
        if value is True:
            command.append("--"+key.replace("_", "-"))
        elif value is not False and value is not None:
            command += ["--"+key.replace("_", "-"), str(value)]
    return command


def restore_line_breaks(text, original):
    """Project OCR line endings onto voted text; no gold/source corrections."""
    from ocr_vote import align_pairwise
    original = [" ".join(s.split()) for s in original.splitlines() if s.strip()]
    anchor = " ".join(original)
    ends, position = set(), 0
    for line in original[:-1]:
        position += len(line)
        ends.add(position)
        position += 1
    output, index = [], 0
    for left, right in align_pairwise(anchor, text):
        if right is not None:
            output.append(right)
        if left is not None:
            index += 1
            if index in ends:
                output.append("\n")
    return "\n".join(s.strip() for s in "".join(output).splitlines() if s.strip())


def vote_pages(config, cache, calibration_path, pages=None):
    from ocr_vote import normalized, vote_text
    cache = Path(cache)
    manifest = json.loads((cache/"layout/regions.json").read_text())
    calibration = json.loads(Path(calibration_path).read_text())
    engines = config["ocr"]["vote_engines"]
    voters = {"han": engines, "vietnamese": config["ocr"]["vote_vietnamese_engines"]}
    ranks = calibration["engine_order_by_reference_cer"]
    if voters != calibration["voters_by_language"] or set(engines) != set(calibration["engines"]):
        raise ValueError("Week-three voters must match the frozen week-two calibration")
    for selected in voters.values():
        if len(set(selected)) < 3:
            raise ValueError("Each script needs at least three engines")
    metadata = {e: json.loads((cache/"ocr/runs"/f"{e}.json").read_text()) for e in engines}
    result = []
    for page in manifest["pages"]:
        if pages is not None and page["page"] not in pages:
            continue
        blocks = []
        fields = {k: [] for k in ("tieu_de", "han", "phien_am", "dich_sat", "dich_tho", "chu_thich", "can_kiem_tra")}
        for region in page["regions"]:
            records = {e: metadata[e]["records"][f"{page['file']}:{region['id']}"] for e in engines}
            if any(r["image_sha256"] != region["image_sha256"] for r in records.values()):
                raise ValueError(f"OCR source differs from layout: {page['file']}:{region['id']}")
            layer = region["layer"]
            flags = set(region.get("flags", []))
            if any(r.get("possibly_truncated") for r in records.values()):
                flags.add("ocr_truncated")
            if layer == "han":
                rows = {e: r.get("lines", []) for e, r in records.items()}
                counts = {len(lines) for lines in rows.values()}
                if len(counts) == 1 and next(iter(counts)):
                    voted = []
                    for i in range(next(iter(counts))):
                        texts = {e: normalized([rows[e][i]["text"]], "han") for e in engines}
                        voted.append(vote_text(texts, ranks["han"], ranks, "star", voters))
                    text = "\n".join(voted)
                else:
                    raise ValueError(f"Han row segmentation differs between engines: {page['file']}:{region['id']}")
            else:
                texts = {e: normalized([r["text"]], layer) for e, r in records.items()}
                order = ranks["han" if layer == "tieu_de_han" else "vietnamese"]
                text = vote_text(texts, order, ranks, "star", voters)
                text = restore_line_breaks(text, records[order[0]]["text"])
            if len({r["text"] for r in records.values()}) > 1:
                flags.add("ocr_disagreement")
            fields["tieu_de" if layer.startswith("tieu_de") else layer].extend(text.splitlines())
            blocks.append({"id": region["id"], "layer": layer, "bbox": region["bbox"],
                           "text": text, "flags": sorted(flags)})
        result.append({"pdf_page": page["page"], "layers": fields, "blocks": blocks,
                       "source_layer": "ocr", "calibration_sha256": sha256(calibration_path)})
    return result
