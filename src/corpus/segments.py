"""Build source-linked segments without pairing commentary with the poem."""
from __future__ import annotations

from dataclasses import dataclass, field
import re

from .normalize import han_body, han_len, norm_han, norm_reading, norm_viet, vi_len

NUMBER = re.compile(r"^\s*(\d+)\s*[.)、,:]\s*")
HAN_SPLIT = re.compile(r"(?<=[。！？；])")
VI_SPLIT = re.compile(r'(?<=[.!?;])\s+(?=[“"(]?[A-ZÀ-Ỹ0-9])')


@dataclass
class Unit:
    text: str
    readings: list = field(default_factory=list)
    original_reading: str = ""
    pages: list = field(default_factory=list)
    flags: list = field(default_factory=list)
    source_index: int | None = None


@dataclass
class Segment:
    id: str
    han: list = field(default_factory=list)
    viet: list = field(default_factory=list)
    pages: list = field(default_factory=list)
    viet_type: str = "dich_sat"
    verse: bool = False
    flags: list = field(default_factory=list)
    viet_pages: list = field(default_factory=list)
    viet_indices: list = field(default_factory=list)


def is_heading(text):
    letters = [c for c in text if c.isalpha()]
    return bool(letters) and all(c.isupper() for c in letters)


def is_chapter_title(text):
    return bool(re.match(r"^第.{1,5}[章篇卷回節]", text)) and han_len(text) <= 12


def join_lines(lines):
    result = ""
    for line in lines:
        result += ("" if result.endswith("-") else " " if result else "")+line
    return norm_viet(result)


def column_unit(column, page):
    han = han_body("".join(c for c, top in column["chars"]))
    original = " ".join(c for c, top in column["readings"])
    tokens = [norm_reading(c) for c, top in column["readings"]]
    flags = []
    if len(tokens) != han_len(han) or any(not t or " " in t for t in tokens):
        tokens = ["〓"]*han_len(han)
        flags.append("reading_mismatch")
    return Unit(han, tokens, original, [page], flags)


def split_han_units(units, verse):
    if verse:
        return units
    text = "".join(u.text for u in units)
    readings = [r for u in units for r in u.readings]
    original = " ".join(u.original_reading for u in units)
    source_pages = [u.pages for u in units for _ in u.text]
    source_flags = [u.flags for u in units for _ in u.text]
    original_tokens = original.split()
    out, index, character_index = [], 0, 0
    for part in HAN_SPLIT.split(text):
        count = han_len(part)
        if count:
            pages = sorted({p for ps in source_pages[character_index:character_index+len(part)] for p in ps})
            flags = sorted({f for fs in source_flags[character_index:character_index+len(part)] for f in fs})
            source_reading = (" ".join(original_tokens[index:index+count])
                              if len(original_tokens) == len(readings) else original)
            out.append(Unit(part, readings[index:index+count], source_reading, pages, flags))
            index += count
        character_index += len(part)
    return out


def viet_units(lines, verse, source_pages=None):
    with_pages = source_pages is not None
    source_pages = source_pages if with_pages else [0]*len(lines)
    lines = [(norm_viet(line), page) for line, page in zip(lines, source_pages)
             if not is_heading(line) and vi_len(line)]
    if verse:
        result, origins = [], []
        for text, page in lines:
            is_numbered = NUMBER.match(text)
            text = NUMBER.sub("", text)
            # Lowercase short continuation after a wrapped physical line.
            if (result and text[:1].islower() and not is_numbered
                    and not re.search(r"[.!?;,…”]$", result[-1]) and vi_len(text) < 7):
                result[-1] = join_lines([result[-1], text])
                origins[-1] = sorted(set(origins[-1])|{page})
            else:
                result.append(norm_viet(text))
                origins.append([page])
        return (result, origins) if with_pages else result
    paragraphs = []
    for text, page in lines:
        if NUMBER.match(text) or not paragraphs:
            text = NUMBER.sub("", text)
            paragraphs.append((text, [page]*len(text)))
        else:
            previous, mapping = paragraphs[-1]
            separator = "" if previous.endswith("-") else " "
            paragraphs[-1] = (previous+separator+text, mapping+[page]*(len(separator)+len(text)))
    result, origins = [], []
    for text, mapping in paragraphs:
        index = 0
        for part in VI_SPLIT.split(text):
            start = text.find(part, index)
            index = start+len(part)
            if vi_len(part):
                result.append(norm_viet(part))
                origins.append(sorted(set(mapping[start:index])))
    return (result, origins) if with_pages else result


def text_segments(records, slug):
    blocks, current = [], None
    for page in records:
        for item in page["items"]:
            if item["kind"] == "grid":
                last_han = current["han"][-1].text if current and current["han"] else ""
                next_han = "".join(c for col in item["columns"] for c, _ in col["chars"])
                continuation = (current is not None and current["lines"] and slug != "tang-quang-hien-van"
                                and current["pages"][-1]+1 == page["page"]
                                and not re.match(r"第.{1,6}[章篇卷回節]", next_han)
                                and (last_han[-1:] not in "。！？" or
                                     not re.search(r'[.!?…”]$', current["lines"][-1])))
                if current is None or current["lines"] and not continuation:
                    current = {"han": [], "lines": [], "line_pages": [], "pages": []}
                    blocks.append(current)
                current["han"].extend(column_unit(c, page["page"]) for c in item["columns"])
            elif current is not None:
                current["lines"].append(item["text"])
                current["line_pages"].append(page["page"])
            if current is not None and page["page"] not in current["pages"]:
                current["pages"].append(page["page"])
    segments, skipped = [], []
    for i, block in enumerate(blocks):
        hu = [u for u in block["han"] if han_len(u.text)]
        # Explicit chapter labels are titles, never sentence pairs.
        hu = [u for u in hu if not is_chapter_title(u.text)]
        h = sum(han_len(u.text) for u in hu)
        v = sum(vi_len(t) for t in block["lines"])
        if not h:
            skipped.append({"pages": block["pages"], "reason": "front_matter_or_no_han", "han_characters": h})
            continue
        verse = (slug == "tang-quang-hien-van" or
                 slug == "dao-duc-kinh" and max((han_len(u.text) for u in hu), default=0) <= 16
                 and abs(len(hu)-len(block["lines"])) <= 2)
        hu = split_han_units(hu, verse)
        vu, vp = viet_units(block["lines"], verse, block["line_pages"])
        flags = ["front_matter_suspected"] if v > 80 and v > 12*h else []
        segments.append(Segment(f"text-{i:05d}", hu, vu, block["pages"], verse=verse, flags=flags, viet_pages=vp))
    return segments, skipped


def indexed_viet(lines):
    out, numbers = [], []
    for line in lines:
        match = NUMBER.match(line)
        if match:
            out.append(NUMBER.sub("", line))
            numbers.append(int(match[1]))
        elif out:
            out[-1] = join_lines([out[-1], line])
        elif line.strip():
            out.append(line)
            numbers.append(None)
    return out, numbers


def scan_segments(layer_pages):
    """Collect each stanza across pages, keeping literal and poetic translations apart."""
    groups, current, previous = [], None, None
    for page in layer_pages:
        if previous is not None and page["pdf_page"] != previous+1:
            if current is not None:
                current["flags"].append("incomplete_scan_span")
            current = None
        previous = page["pdf_page"]
        for block in page["blocks"]:
            layer, text = block["layer"], block["text"]
            if layer.startswith("tieu_de") or layer == "so_trang":
                continue
            if layer == "han":
                if current is None or current["dich_sat"] or current["dich_tho"] or current["chu_thich"]:
                    current = {k: [] for k in ("han", "phien_am", "dich_sat", "dich_tho", "chu_thich", "pages", "flags")}
                    current["page_by_layer"] = {k: [] for k in ("han", "phien_am", "dich_sat", "dich_tho", "chu_thich")}
                    current["flags_by_layer"] = {k: [] for k in current["page_by_layer"]}
                    current["han_origins"] = []
                    groups.append(current)
                rows = [han_body(s, preserve_unknown=True) for s in text.splitlines() if s.strip()]
                current["han"].extend(rows)
                current["han_origins"].extend([page["pdf_page"]]*len(rows))
            elif current is not None and layer in current:
                current[layer].extend(s for s in text.splitlines() if s.strip())
            if current is not None:
                if layer in current["page_by_layer"]:
                    current["page_by_layer"][layer].append(page["pdf_page"])
                    current["flags_by_layer"][layer].extend(block.get("flags", []))
                if layer != "chu_thich" and page["pdf_page"] not in current["pages"]:
                    current["pages"].append(page["pdf_page"])
    segments = []
    for i, group in enumerate(groups):
        readings, numbers = indexed_viet(group["phien_am"])
        known = [n for n in numbers if n is not None]
        if len(readings) != len(group["han"]) or known and known != list(range(known[0],known[0]+len(known))):
            group["flags"].append("reading_mismatch")
        hu = []
        for j, text in enumerate(group["han"]):
            raw = readings[j] if j < len(readings) else ""
            tokens = [norm_reading(t) for t in re.findall(r"[^\W\d_]+", raw)]
            flags = []
            if len(tokens) != han_len(text):
                tokens = ["〓"]*han_len(text)
                flags.append("reading_mismatch")
            index = numbers[j] if len(numbers) == len(group["han"]) else None
            hu.append(Unit(text, tokens, raw, [group["han_origins"][j]], flags, index))
        if not hu:
            continue
        for kind in ("dich_sat", "dich_tho"):
            vu, indices = (indexed_viet(group[kind]) if kind == "dich_sat" else (list(group[kind]), []))
            if vu or kind == "dich_sat":
                origins = sorted({p for k in ("han", "phien_am", kind) for p in group["page_by_layer"][k]})
                flags = sorted(set(group["flags"])|{f for k in ("han", "phien_am", kind) for f in group["flags_by_layer"][k]})
                segments.append(Segment(f"ocr-{i:05d}", hu, vu, origins, kind, True,
                                        flags, viet_indices=indices))
    return segments, []
