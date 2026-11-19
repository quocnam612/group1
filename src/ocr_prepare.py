"""Restore the frozen OCR sample images and crops without reading reference text."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess
import tempfile

from ocr import page_numbers
from ocr_reference import sha256


def verify(path, expected):
    if sha256(path) != expected:
        raise ValueError(f"Image/source differs from the frozen sample: {path}")


def prepare(manifest_path, pdf, dpi, pages=None):
    from PIL import Image

    manifest_path = Path(manifest_path).resolve(strict=True)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    source = manifest["source"]
    if dpi != source["dpi"]:
        raise ValueError(f"Frozen layout requires {source['dpi']} DPI, received {dpi}")
    assets = (manifest_path.parent / manifest["assets_dir"]).resolve()
    selected = [p for p in manifest["pages"] if pages is None or p["page"] in pages]
    if not selected or (pages is not None and set(pages) != {p["page"] for p in selected}):
        raise ValueError("Requested pages are missing from the frozen crop manifest")
    checked_pdf = None
    restored = 0
    for page in selected:
        image_path = (assets / page["image"]).resolve()
        if not image_path.is_file():
            if checked_pdf is None:
                checked_pdf = Path(pdf).resolve(strict=True)
                verify(checked_pdf, source["pdf_sha256"])
            # Validate rendering before publishing it; never change the original PDF.
            with tempfile.TemporaryDirectory(prefix="ocr-render-") as temporary:
                stem = Path(temporary) / "page"
                subprocess.run(["pdftoppm", "-f", str(page["page"]), "-l", str(page["page"]),
                                "-r", str(dpi), "-singlefile", "-png", str(checked_pdf), str(stem)], check=True)
                rendered = stem.with_suffix(".png")
                verify(rendered, page["image_sha256"])
                image_path.parent.mkdir(parents=True, exist_ok=True)
                image_path.write_bytes(rendered.read_bytes())
            restored += 1
        verify(image_path, page["image_sha256"])
        with Image.open(image_path) as raw_image:
            image = raw_image.convert("RGB")
        if list(image.size) != page["image_size"]:
            raise ValueError(f"Rendered dimensions differ from the frozen sample: {image_path}")
        for region in page["regions"]:
            crop = (assets / region["crop"]).resolve()
            if not crop.is_relative_to(assets):
                raise ValueError(f"Crop is outside layout assets: {crop}")
            x0, y0, x1, y1 = region["bbox"]
            if not (0 <= x0 < x1 <= image.width and 0 <= y0 < y1 <= image.height):
                raise ValueError(f"Crop coordinates are outside the source image: {crop}")
            if not crop.is_file():
                crop.parent.mkdir(parents=True, exist_ok=True)
                with tempfile.TemporaryDirectory(prefix="ocr-crop-") as temporary:
                    candidate = Path(temporary) / "crop.png"
                    image.crop((x0, y0, x1, y1)).save(candidate)
                    verify(candidate, region["image_sha256"])
                    crop.write_bytes(candidate.read_bytes())
                restored += 1
            verify(crop, region["image_sha256"])
        print(f"Verified page {page['page']}: source image and {len(page['regions'])} crops", flush=True)
    print(f"Prepared {len(selected)} pages; restored {restored} missing images/crops.", flush=True)
    return restored


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--layout", type=Path, required=True)
    parser.add_argument("--pdf", type=Path, required=True)
    parser.add_argument("--dpi", type=int, default=300)
    parser.add_argument("--pages", type=page_numbers)
    args = parser.parse_args()
    try:
        prepare(args.layout, args.pdf, args.dpi, args.pages)
    except (ValueError, KeyError, FileNotFoundError, subprocess.CalledProcessError) as exc:
        parser.exit(1, f"Error: {exc}\n")


if __name__ == "__main__":
    main()
