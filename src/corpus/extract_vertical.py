"""Trích xuất sách nhóm A: chữ Hán in dọc (đọc phải -> trái, trên -> dưới),
mỗi chữ có âm Hán Việt nhỏ bên dưới hoặc bên phải, xen với các đoạn dịch nghĩa in ngang.

Đầu ra mỗi trang là một dòng chảy (stream) các phần tử theo thứ tự đọc:
  GridBlock  – một khối chữ Hán dọc (nhiều cột) kèm âm đọc từng chữ
  TextLine   – một dòng chữ ngang (dịch nghĩa, tiêu đề, chú thích...)
"""
# Coordinate extraction adapted from the provided CV18 demo.
# See README: geometry extraction is inherited; corpus alignment is our own.
from __future__ import annotations

import re
import statistics
from dataclasses import dataclass, field

import pdfplumber

from .normalize import is_han, is_han_punct, norm_han, norm_reading, norm_viet, is_pua


@dataclass
class Column:
    x0: float
    x1: float
    top: float
    bottom: float
    size: float
    chars: list = field(default_factory=list)      # [(char, top)]
    readings: list = field(default_factory=list)   # [(reading, top)]

    @property
    def han(self) -> str:
        return "".join(c for c, _ in self.chars)


@dataclass
class GridBlock:
    page: int
    top: float
    bottom: float
    columns: list  # đã sắp phải -> trái
    kind: str = "grid"


@dataclass
class TextLine:
    page: int
    top: float
    x0: float
    text: str
    size: float
    kind: str = "text"


def _cluster(values, tol):
    """Gom các giá trị 1 chiều đã sắp xếp thành cụm khi khoảng cách <= tol."""
    groups = []
    for v in sorted(values, key=lambda t: t[0]):
        if groups and v[0] - groups[-1][-1][0] <= tol:
            groups[-1].append(v)
        else:
            groups.append([v])
    return groups


def extract_page(page, pno: int):
    chars = [c for c in page.chars if c["text"].strip()]
    if not chars:
        return []

    cjk = [c for c in chars if is_han(c["text"]) or is_han_punct(c["text"]) or is_pua(c["text"])]
    latin_sizes = [c["size"] for c in chars if not is_han(c["text"]) and c["text"].isalpha()]
    lat_med = statistics.median(latin_sizes) if latin_sizes else 10.0
    max_cjk = max((c["size"] for c in cjk), default=0)

    # Chữ Hán "lưới" = cỡ lớn hơn hẳn chữ Latin; chữ Hán nhỏ là chữ chèn trong câu dịch.
    is_grid_page = max_cjk >= 1.6 * lat_med
    grid_chars = [c for c in cjk if is_grid_page and c["size"] >= 0.6 * max_cjk]
    grid_ids = {id(c) for c in grid_chars}

    # ---- 1. Gom chữ Hán lớn thành cột (theo tâm x), tách cột khi có khoảng trống dọc lớn.
    columns: list[Column] = []
    if grid_chars:
        size = statistics.median(c["size"] for c in grid_chars)
        xs = [((c["x0"] + c["x1"]) / 2, c) for c in grid_chars]
        for grp in _cluster(xs, tol=0.45 * size):
            cs = sorted((c for _, c in grp), key=lambda c: c["top"])
            seg = [cs[0]]
            for c in cs[1:]:
                if c["top"] - seg[-1]["bottom"] > 1.6 * size:
                    columns.append(_mk_col(seg))
                    seg = [c]
                else:
                    seg.append(c)
            columns.append(_mk_col(seg))

    # ---- 2. Các từ không thuộc lưới: âm đọc, số thứ tự cột, hoặc dòng chữ ngang.
    rest = page.filter(lambda o: o.get("object_type") != "char" or id(o) not in grid_ids)
    words = rest.extract_words(extra_attrs=["size"], keep_blank_chars=False, x_tolerance=1.5)
    words = [w for w in words if w["text"].strip()]

    def near_col(w):
        """Cột gần nhất theo khoảng cách ngang; chỉ nhận nếu từ nằm trong vùng dọc của cột."""
        best, bd = None, 1e9
        wc = (w["x0"] + w["x1"]) / 2
        for col in columns:
            if not (col.top - 1.2 * col.size <= w["top"] <= col.bottom + 0.8 * col.size):
                continue
            if col.x0 - 2 <= wc <= col.x1 + 2:
                d = 0
            elif w["x0"] >= col.x1 - 2:          # âm đọc nằm bên phải chữ
                d = w["x0"] - col.x1
            else:
                d = col.x0 - w["x1"] + 5        # hơi phạt phía trái
            if d < bd:
                best, bd = col, d
        return best if bd <= 0.6 * (best.size if best else 0) else None

    # Từ có hàng xóm sát bên trên cùng dòng => thuộc một câu ngang, không phải âm đọc.
    def has_close_neighbor(w):
        for o in words:
            if o is w or abs(o["top"] - w["top"]) > 0.5 * w["size"]:
                continue
            gap = max(o["x0"] - w["x1"], w["x0"] - o["x1"])
            if gap < 0.9 * w["size"]:
                return True
        return False

    loose = []
    for w in words:
        t = w["text"]
        col = near_col(w) if columns else None
        single = " " not in t and not has_close_neighbor(w)
        if re.fullmatch(r"[\d\s.\-–]+", t):
            # Keep meaningful numbers in translations/chapter headings. Only
            # discard margin page numbers and indices above a Han column.
            if (w["top"] < 70 or w["bottom"] > page.height-70 or
                    col and single and w["bottom"] <= col.top):
                continue
        if col and single and w["size"] < 0.6 * col.size and any(ch.isalpha() for ch in t):
            col.readings.append((t, w["top"]))
        elif col and single and all(is_han_punct(ch) for ch in t):
            col.chars.append((t, w["top"]))  # dấu câu Hán cỡ nhỏ trong cột
        else:
            loose.append(w)

    # Cột chỉ có dấu câu = dấu bị tràn khỏi cuối cột trước nó (theo thứ tự đọc: cột kề bên PHẢI)
    # -> gắn vào cuối cột đó.
    real = [c for c in columns if any(is_han(ch) for ch, _ in c.chars)]
    for c in columns:
        if c in real or not real:
            continue
        right = [r for r in real if r.x0 >= c.x0 and r.top < c.bottom + 3 * r.size]
        tgt = min(right or real, key=lambda r: abs(r.x0 - c.x0))
        tgt.chars += [(ch, tgt.bottom + 1 + i) for i, (ch, _) in enumerate(c.chars)]

    columns = real

    # ---- 3. Gom cột thành khối theo chồng lấn dọc.
    blocks: list[GridBlock] = []
    for col in sorted(columns, key=lambda c: c.top):
        col.chars.sort(key=lambda t: t[1])
        col.readings.sort(key=lambda t: t[1])
        for b in blocks:
            if col.top < b.bottom and col.bottom > b.top:
                b.columns.append(col)
                b.top, b.bottom = min(b.top, col.top), max(b.bottom, col.bottom)
                break
        else:
            blocks.append(GridBlock(pno, col.top, col.bottom, [col]))
    for b in blocks:
        b.columns.sort(key=lambda c: -c.x0)  # phải -> trái

    # ---- 4. Dòng chữ ngang.
    lines: list[TextLine] = []
    for grp in _cluster([(w["top"], w) for w in loose], tol=0.4 * lat_med):
        ws = sorted((w for _, w in grp), key=lambda w: w["x0"])
        text = " ".join(w["text"] for w in ws)
        top = min(w["top"] for w in ws)
        # bỏ số trang ở lề trên/dưới
        if re.fullmatch(r"[\d\s\-–]+", text) and (top < 70 or top > page.height - 80):
            continue
        lines.append(TextLine(pno, top, ws[0]["x0"], norm_viet(text), statistics.median(w["size"] for w in ws)))

    return sorted(blocks + lines, key=lambda it: it.top)


def _mk_col(cs):
    return Column(
        x0=min(c["x0"] for c in cs), x1=max(c["x1"] for c in cs),
        top=min(c["top"] for c in cs), bottom=max(c["bottom"] for c in cs),
        size=statistics.median(c["size"] for c in cs),
        chars=[(c["text"], c["top"]) for c in cs],
    )


def extract_pdf(path: str, first: int | None = None, last: int | None = None):
    stream = []
    with pdfplumber.open(path) as pdf:
        pages = pdf.pages[(first or 1) - 1:last]
        for i, page in enumerate(pages, start=first or 1):
            stream.extend(extract_page(page, i))
    return stream


def column_pairs(col: Column):
    """Ghép chữ Hán <-> âm đọc trong một cột theo thứ tự trên -> dưới."""
    han = [h for h in (norm_han(c) for c, _ in col.chars) if h and is_han(h)]
    rd = [norm_reading(r) for r, _ in col.readings]
    return han, rd
