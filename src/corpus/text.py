"""Page checkpoints for vertical text PDFs; the supplied demo is not rerun."""
from __future__ import annotations

from dataclasses import asdict
import hashlib
import json
from pathlib import Path

from pages import save_json
from .extract_vertical import extract_page
from .normalize import is_pua

VERSION = 1


def checksum(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def extract_book(pdf_path, cache, selected=None, overwrite=False):
    import pdfplumber
    pdf_path, cache = Path(pdf_path), Path(cache)
    source_hash = checksum(pdf_path)
    records = []
    with pdfplumber.open(pdf_path) as pdf:
        pages = selected if selected is not None else range(1, len(pdf.pages)+1)
        for number in pages:
            if not 1 <= number <= len(pdf.pages):
                raise ValueError(f"Page {number} is outside {pdf_path}")
            target = cache / f"page-{number:04d}.json"
            identity = {"pdf_sha256": source_hash, "extractor_version": VERSION}
            if target.exists() and not overwrite:
                data = json.loads(target.read_text(encoding="utf-8"))
                if data["source"] != identity:
                    raise ValueError(f"Source/extractor changed: {target}; use --overwrite")
            else:
                page = pdf.pages[number-1]
                data = {"page": number, "source": identity,
                        "items": [asdict(item) for item in extract_page(page, number)],
                        "pua": sorted({f"U+{ord(c):04X}" for ch in page.chars for c in ch["text"] if is_pua(c)})}
                save_json(target, data)
                page.close()
            records.append(data)
            print(f"Text: {pdf_path.name} {number}/{len(pdf.pages)}", flush=True)
    return records


def text_layers(records, book):
    from .segments import is_chapter_title
    for record in records:
        layers = {k: [] for k in ("han", "phien_am", "dich_sat", "dich_tho", "chu_thich", "tieu_de")}
        for item in record["items"]:
            if item["kind"] == "grid":
                for column in item["columns"]:
                    text = "".join(c for c, top in column["chars"])
                    if is_chapter_title(text):
                        layers["tieu_de"].append(text)
                        continue
                    layers["han"].append(text)
                    layers["phien_am"].append(" ".join(c for c, top in column["readings"]))
            else:
                text = item["text"]
                key = "tieu_de" if text.isupper() else "dich_sat"
                layers[key].append(text)
        yield {"pdf_page": record["page"], "page": record["page"]+book.get("page_offset", 0),
               "source_layer": "text", "layers": layers, "unmapped_pua": record["pua"]}
