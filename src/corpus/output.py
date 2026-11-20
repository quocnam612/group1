"""Export the shared CV18 schema and honest coverage/progress statistics."""
from __future__ import annotations

from collections import Counter, defaultdict
import hashlib
import json
import math
from pathlib import Path
import re

from .align import estimate_parameters, gale_church, Link
from .normalize import han_len, norm_viet, normalization_flags, vi_len
from .segments import join_lines

SLUGS = {"Kinh Thi (Quyển I)": "kinh-thi", "Vi Chánh": "vi-chanh",
         "Đạo Đức Kinh": "dao-duc-kinh", "Tăng Quảng Hiền Văn": "tang-quang-hien-van"}


def atomic_jsonl(path, rows):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix+".tmp")
    with temporary.open("w", encoding="utf-8") as stream:
        for row in rows:
            stream.write(json.dumps(row, ensure_ascii=False)+"\n")
    temporary.replace(path)


def sentences(text, han=False):
    stops = r"[。！？]+" if han else r"[.!?]+"
    return max(1, len([s for s in re.split(stops, text) if s.strip(' ”“\"\'」』')]))


def align_segments(segments, book, group, method):
    parameters = {kind: estimate_parameters([("".join(u.text for u in s.han), join_lines(s.viet))
                                             for s in segments if s.viet_type == kind])
                  for kind in {s.viet_type for s in segments}}
    rows = []
    for segment in segments:
        ratio, variance = parameters[segment.viet_type]
        hu, vu = [u.text for u in segment.han], segment.viet
        hi = [u.source_index for u in segment.han]
        vi = segment.viet_indices
        anchors = []
        missing_han, missing_viet = [], []
        valid_indices = (hi and vi and all(n is not None for n in hi+vi)
                         and hi == sorted(set(hi)) and vi == sorted(set(vi))
                         and "reading_mismatch" not in segment.flags)
        if valid_indices:
            destinations = {number: i for i, number in enumerate(vi)}
            anchors = [(i, destinations[number]) for i, number in enumerate(hi) if number in destinations]
            missing_han = [i for i, number in enumerate(hi) if number not in destinations]
            missing_viet = [i for i, number in enumerate(vi) if number not in hi]
        links = gale_church(hu, vu, ratio, variance, anchors=anchors,
                           unmatched_han=missing_han, unmatched_viet=missing_viet)
        # Without Han sentence boundaries, keep one honest paragraph instead of
        # labelling a long source block plus orphan Vietnamese sentences as 1:1.
        if (not segment.verse and len(hu) == 1 and len(vu) > 2
                and han_len(hu[0]) > 30):
            links = [Link(0, 1, 0, len(vu), sum(l.cost for l in links))]
        for link in links:
            selected = segment.han[link.han_start:link.han_end]
            han = "".join(u.text for u in selected)
            viet = join_lines(vu[link.viet_start:link.viet_end])
            readings = [r for u in selected for r in u.readings]
            original = " ".join(u.original_reading for u in selected).strip()
            flags = set(segment.flags)
            flags.update(f for u in selected for f in u.flags)
            flags.update(normalization_flags(han+viet+original))
            if not han:
                flags.add("viet_only")
            if not viet:
                flags.add("han_only")
            if han and viet and not .4*ratio <= vi_len(viet)/max(han_len(han), 1) <= 2.5*ratio:
                flags.add("length_ratio")
            if len(readings) != han_len(han):
                readings = ["〓"]*han_len(han)
                flags.add("reading_mismatch")
            if "〓" in readings:
                flags.add("reading_mismatch")
            a, b = link.han_end-link.han_start, link.viet_end-link.viet_start
            small = (a <= 2 and b <= 2 and sentences(han, True) <= 2 and sentences(viet) <= 2)
            if not segment.verse and han_len(han) > 60 and not re.search(r"[。！？]", han):
                small = False
                flags.add("sentence_boundary_uncertain")
            level = "sentence" if small and han and viet else "paragraph"
            pages = sorted({p for u in selected for p in u.pages}) or segment.pages
            translation_pages = ({p for ps in segment.viet_pages[link.viet_start:link.viet_end] for p in ps}
                                 if segment.viet_pages else set(segment.pages))
            pages = sorted(set(pages)|translation_pages)
            identity = f"{book['file']}:{segment.id}:{link.han_start}:{link.han_end}:{link.viet_start}:{link.viet_end}:{segment.viet_type}"
            id_ = f"g{group}-{SLUGS[book['book']]}-{hashlib.sha256(identity.encode()).hexdigest()[:12]}"
            phien_am = " ".join(readings).lower()
            row = {"id": id_, "group": group, "book": book["book"], "file": book["file"],
                   "pages": [p+book.get("page_offset", 0) for p in pages], "level": level,
                   "align": f"{a}-{b}", "han": han, "phien_am": phien_am,
                   "phien_am_goc": original if original != phien_am else None,
                   "viet": norm_viet(viet), "viet_type": segment.viet_type,
                   "source_layer": "ocr" if book["type"] == "scan" else "text",
                   "method": method+("+verse_indices" if anchors else ""),
                   "score": round(max(0., min(1., math.exp(-max(0., link.cost)/max(a+b, 1)))), 4),
                   "flags": sorted(flags),
                   "extra": {"segment": segment.id, "pdf_pages": pages,
                             "han_units": [link.han_start, link.han_end],
                             "viet_units": [link.viet_start, link.viet_end],
                             "verse_units": segment.verse}}
            rows.append(row)
    return rows, {kind: {"ratio": values[0], "variance": values[1]} for kind, values in parameters.items()}


def validate(rows):
    required = {"id", "group", "book", "file", "pages", "level", "align", "han", "phien_am",
                "phien_am_goc", "viet", "viet_type", "source_layer", "method", "score", "flags", "extra"}
    seen = set()
    for row in rows:
        if set(row) != required or row["id"] in seen:
            raise ValueError(f"Invalid schema or duplicate id: {row.get('id')}")
        seen.add(row["id"])
        if len(row["phien_am"].split()) != han_len(row["han"]):
            raise ValueError(f"Reading/character count mismatch: {row['id']}")
        if not 0 <= row["score"] <= 1 or not row["pages"]:
            raise ValueError(f"Invalid score/pages: {row['id']}")
        for key in ("viet", "phien_am"):
            if norm_viet(row[key]) != row[key]:
                raise ValueError(f"Non-NFC/whitespace content: {row['id']}.{key}")


def mark_duplicates(rows):
    seen = {}
    for row in rows:
        key = (row["han"], row["phien_am"], row["viet"], row["viet_type"])
        if not row["han"]:
            continue
        if key in seen:
            row["flags"] = sorted(set(row["flags"])|{"duplicate"})
            row["extra"]["duplicate_of"] = seen[key]
        else:
            seen[key] = row["id"]


def write_report(out, rows, stats, runtime):
    complete = all(s["complete"] for s in stats)
    lines = ["# Corpus v1 — Tuần 3", "",
             "Trạng thái: **"+("đủ phần chính" if complete else "đang xử lý; chưa đủ phần chính")+"**.", "",
             f"Tổng {len(rows):,} cặp; {sum(r['level']=='sentence' for r in rows):,} cặp cấp câu.", "",
             "| Sách | Trang đã xử lý/tổng | Cặp | Chữ Hán nguồn | Chữ Hán được giữ | Độ phủ | Hán cấp câu | Trạng thái |",
             "| --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |"]
    for s in stats:
        coverage = f"{100*s['retained_han']/max(s['source_han'],1):.2f}%" if s['source_han'] else "—"
        sentence = f"{100*s['sentence_han']/max(s['source_han'],1):.2f}%" if s['source_han'] else "—"
        lines.append(f"| {s['book']} | {s['processed_pages']}/{s['total_pages']} | {s['pairs']} | {s['source_han']} | {s['retained_han']} | {coverage} | {sentence} | "+("Đủ trang" if s['complete'] else "Chưa đủ")+" |")
    lines += ["", "Độ phủ tính trên nguyên văn đã trích xuất, sau khi loại bìa/mục lục được ghi nhận; chưa phải kiểm tay toàn bộ PDF.",
              "Một đoạn Hán có cả dịch sát và dịch thơ chỉ được đếm một lần khi tính độ phủ. Không dùng số cặp làm tỉ lệ chữ Hán cấp câu.",
              "", "## Cần kiểm tra", "", "| Cờ | Số cặp |", "| --- | ---: |"]
    for flag, count in Counter(f for r in rows for f in r["flags"]).most_common():
        lines.append(f"| {flag} | {count} |")
    lines += ["", "`score` là exp(-chi phí Gale–Church/số đơn vị), chỉ là điểm theo độ dài, không phải precision hoặc xác suất đã hiệu chuẩn.",
              "Âm không lấy được được ghi `〓` và gắn `reading_mismatch`; không điền âm đoán. Bản âm nguồn ở `phien_am_goc`.",
              "Không tự gán nghi vấn OCR thành lỗi sách gốc trong `source_errors.tsv`.",
              "Bộ gold căn chỉnh, precision/recall và cải tiến thuộc Tuần 4; bộ gold OCR Tuần 2 được giữ nguyên.",
              "", f"Cấu hình chạy: `{runtime}`.", ""]
    (Path(out)/"report.md").write_text("\n".join(lines), encoding="utf-8")


def book_stats(book, segments, rows, processed, total, skipped):
    sources = {}
    for s in segments:
        sources.setdefault(s.id, sum(han_len(u.text) for u in s.han))
    retained, sentence = {}, {}
    for r in rows:
        # Interval keys avoid counting the same Han twice for two translation types.
        key = (r["extra"]["segment"], tuple(r["extra"]["han_units"]))
        retained[key] = han_len(r["han"])
        if r["level"] == "sentence":
            sentence[key] = han_len(r["han"])
    # When the two translation variants induce different unit grouping, count
    # coverage from the literal translation only, whose alignment consumes all Han.
    literal = [r for r in rows if r["viet_type"] == "dich_sat"]
    return {"book": book["book"], "processed_pages": processed, "total_pages": total,
            "complete": processed == total, "pairs": len(rows), "source_han": sum(sources.values()),
            "retained_han": sum(han_len(r["han"]) for r in literal),
            "sentence_han": sum(han_len(r["han"]) for r in literal if r["level"] == "sentence"),
            "excluded_blocks": skipped}
