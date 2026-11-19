"""Report OCR CER by engine, layer, and script for the week-two sample."""
from __future__ import annotations

import argparse
from collections import defaultdict
import json
from pathlib import Path
import sys

from ocr_vote import ENGINES, FIELDS, edit_distance, is_han, normalized

VOTE = "voting"


def parse_pages(value: str) -> list[int]:
    pages: set[int] = set()
    try:
        for item in value.split(","):
            if "-" in item:
                start, end = (int(part) for part in item.split("-", 1))
                if end < start:
                    raise ValueError
                pages.update(range(start, end + 1))
            else:
                pages.add(int(item))
        if not pages or min(pages) < 1:
            raise ValueError
        return sorted(pages)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("use pages like 38-48 or 38,40,42") from exc


def available_engines(prediction_dir: Path) -> list[str]:
    engines = list(ENGINES)
    if (prediction_dir / VOTE).is_dir():
        engines.append(VOTE)
    return engines


def collect(reference_dir: Path, prediction_dir: Path, pages: list[int]):
    engines = available_engines(prediction_dir)
    per_field = defaultdict(lambda: [0, 0])
    by_language = {engine: {language: [0, 0]
                            for language in ("han", "vietnamese")}
                   for engine in engines}
    for page in pages:
        name = f"page-{page:04}.json"
        ref = json.loads((reference_dir / name).read_text(encoding="utf-8"))
        for engine in engines:
            pred = json.loads((prediction_dir / engine / name).read_text(encoding="utf-8"))
            for field in FIELDS:
                ref_text = normalized(ref.get(field, []), field)
                pred_text = normalized(pred.get(field, []), field)
                errors = edit_distance(ref_text, pred_text)
                per_field[engine, field][0] += errors
                per_field[engine, field][1] += len(ref_text)
                for language in ("han", "vietnamese"):
                    script_filter = is_han if language == "han" else lambda char: not is_han(char)
                    ref_chars = "".join(c for c in ref_text if not c.isspace() and script_filter(c))
                    pred_chars = "".join(c for c in pred_text if not c.isspace() and script_filter(c))
                    by_language[engine][language][0] += edit_distance(ref_chars, pred_chars)
                    by_language[engine][language][1] += len(ref_chars)
    return engines, per_field, by_language


def metric(errors: int, characters: int) -> str:
    return f"{100 * errors / characters:.2f}% ({errors}/{characters})" if characters else "—"


def render(engines, per_field, by_language, pages) -> str:
    lines = [
        f"# OCR tuần 2 — CER trên trang PDF {min(pages)}–{max(pages)}",
        "",
        f"Tập đánh giá gồm {len(pages)} trang: {', '.join(map(str, pages))}.",
        "Nguồn: `Kinh Thi - Ta Quang Phát 1 (tr1-346).pdf`.",
        "",
        "## CER tách chữ Hán và tiếng Việt",
        "",
        "| Kết quả | Hán | Việt | Gộp Hán + Việt |",
        "| --- | ---: | ---: | ---: |",
    ]
    for engine in engines:
        han_errors, han_chars = by_language[engine]["han"]
        vi_errors, vi_chars = by_language[engine]["vietnamese"]
        lines.append("| " + engine + " | " + " | ".join((
            metric(han_errors, han_chars), metric(vi_errors, vi_chars),
            metric(han_errors + vi_errors, han_chars + vi_chars),
        )) + " |")

    lines.extend(["", "## CER theo tầng nội dung", "",
                  "| Kết quả | " + " | ".join(FIELDS) + " |",
                  "| --- | " + " | ".join("---:" for _ in FIELDS) + " |"])
    for engine in engines:
        values = [metric(*per_field[engine, field]) for field in FIELDS]
        lines.append("| " + engine + " | " + " | ".join(values) + " |")

    lines.extend([
        "",
        "CER là khoảng cách Levenshtein ký tự chia cho số ký tự tham chiếu. Dữ liệu được chuẩn hóa NFC; khoảng trắng bị bỏ khi tính CER tách Hán/Việt để không tính khác biệt xuống dòng.",
        "Chữ Hán gồm ký tự CJK trong mọi tầng, kể cả tiêu đề và chú giải; phần Việt gồm các ký tự còn lại. `can_kiem_tra` bị loại khỏi voting và CER.",
        "Voting căn chỉnh chuỗi ba công cụ bằng Levenshtein rồi chọn đa số ký tự. Khi hai công cụ chọn hai ký tự khác nhau, dùng công cụ có CER thấp hơn theo ngôn ngữ trên chính tập trang này; vì vậy đây là số liệu hiệu chỉnh, không phải holdout độc lập.",
        "",
    ])
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reference", type=Path, default=Path("gold/ocr/week2"))
    parser.add_argument("--predictions", type=Path, default=Path("out/ocr/week2/pages"))
    parser.add_argument("--pages", type=parse_pages, default=list(range(38, 49)))
    parser.add_argument("--output", type=Path, default=Path("out/ocr/week2/comparison.md"))
    args = parser.parse_args()
    try:
        engines, per_field, by_language = collect(args.reference, args.predictions, args.pages)
    except FileNotFoundError as exc:
        parser.error(f"missing input: {exc.filename}")
    report = render(engines, per_field, by_language, args.pages)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(report + "\n", encoding="utf-8")
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    print(report)


if __name__ == "__main__":
    main()
