"""Image-only preprocessing for horizontal scan OCR; never reads reference text."""
from __future__ import annotations

from pathlib import Path

SCAN_SETTINGS = {"version": 1, "scale": 2, "border": 16, "padding": 6,
                 "dark_threshold": 200, "max_internal_gap": 2,
                 "grayscale": True, "autocontrast": True}


def scan_line_boxes(image):
    import numpy as np
    from han_lines import ink_bands
    ink = np.asarray(image.convert("L")) < SCAN_SETTINGS["dark_threshold"]
    height, width = ink.shape
    bands = ink_bands(ink.sum(axis=1), max(2, round(width*.002)),
                      SCAN_SETTINGS["max_internal_gap"], max(3, round(height*.015)))
    boxes = []
    pad = SCAN_SETTINGS["padding"]
    for i, (top, bottom) in enumerate(bands):
        columns = np.flatnonzero(ink[top:bottom].any(axis=0))
        if not len(columns):
            continue
        previous = (bands[i-1][1]+top)//2 if i else 0
        following = (bottom+bands[i+1][0])//2 if i+1 < len(bands) else height
        boxes.append([max(0, int(columns[0])-pad), max(previous, top-pad),
                      min(width, int(columns[-1])+pad+1), min(following, bottom+pad)])
    return boxes or [[0, 0, width, height]]


def prepare_scan_lines(path, cache):
    import hashlib
    import json
    from PIL import Image, ImageOps
    from ocr_reference import sha256
    path, cache = Path(path), Path(cache)
    with Image.open(path) as opened:
        image = opened.convert("RGB")
    layer = path.parent.name
    if layer.startswith("tieu_de") or layer == "can_kiem_tra":
        boxes = [[0, 0, *image.size]]
    elif layer == "han":
        from han_lines import split_han_lines
        boxes = split_han_lines(image)
    else:
        boxes = scan_line_boxes(image)
    settings_hash = hashlib.sha256(json.dumps(SCAN_SETTINGS, sort_keys=True).encode()).hexdigest()[:12]
    directory = cache / f"scan-v{SCAN_SETTINGS['version']}-{settings_hash}-lines" / sha256(path) / layer
    directory.mkdir(parents=True, exist_ok=True)
    result = []
    for i, box in enumerate(boxes, 1):
        target = directory / f"{path.stem}-line-{i:03}.png"
        if not target.exists():
            line = ImageOps.autocontrast(image.crop(box).convert("L"))
            line = line.resize(tuple(n*SCAN_SETTINGS["scale"] for n in line.size), Image.Resampling.LANCZOS)
            line = ImageOps.expand(line, border=SCAN_SETTINGS["border"], fill=255)
            line.convert("RGB").save(target)
        result.append((target, box))
    return result


def qwen_scan_prompt(layer):
    if layer in ("han", "tieu_de_han"):
        return ("Transcribe this single printed line of traditional Chinese, left to right. "
                "Copy every visible character, including repetitions and unusual printed variants. "
                "Do not replace it with a memorized poem or modern spelling. Output the line only.")
    return ("Transcribe this single printed Vietnamese line, which may be italic and include Chinese characters. "
            "Read the Vietnamese diacritics carefully, including dots below and tone marks above vowels. "
            "Preserve the printed spelling, capitalization, numbers, punctuation and word spaces exactly. "
            "Do not translate, correct the source, strip accents, or add explanations. Output only the line.")
