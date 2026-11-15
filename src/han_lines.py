"""Split an already isolated horizontal Han column into text-line crops."""
from __future__ import annotations

LINE_SETTINGS = {"version": 1, "dark_threshold": 180, "padding": 4,
                 "min_ink_ratio": .01, "gap_ratio": .01, "min_height_ratio": .02}


def ink_bands(counts, min_ink, max_gap, min_height):
    """Merge small gaps inside glyphs while retaining whitespace between rows."""
    spans = []
    for y, count in enumerate(counts):
        if count < min_ink:
            continue
        if spans and y-spans[-1][1] <= max_gap:
            spans[-1][1] = y+1
        else:
            spans.append([y, y+1])
    return [(a, b) for a, b in spans if b-a >= min_height]


def split_han_lines(image):
    import numpy as np
    gray = np.asarray(image.convert("L"))
    height, width = gray.shape
    ink = gray < LINE_SETTINGS["dark_threshold"]
    bands = ink_bands(ink.sum(axis=1), max(2, round(width*LINE_SETTINGS["min_ink_ratio"])),
                      max(2, round(width*LINE_SETTINGS["gap_ratio"])),
                      max(3, round(width*LINE_SETTINGS["min_height_ratio"])))
    padding = LINE_SETTINGS["padding"]
    boxes = []
    for i, (top, bottom) in enumerate(bands):
        columns = np.flatnonzero(ink[top:bottom].any(axis=0))
        if not len(columns):
            continue
        # Limit padding to the whitespace separator so neighboring rows never overlap.
        previous_end = (bands[i-1][1]+top)//2 if i else 0
        next_start = (bottom+bands[i+1][0])//2 if i+1 < len(bands) else height
        boxes.append([max(0, int(columns[0])-padding), max(previous_end, top-padding),
                      min(width, int(columns[-1])+padding+1), min(next_start, bottom+padding)])
    if not boxes:
        raise ValueError("No horizontal Han rows found; check that input is a Han-only crop")
    return boxes
