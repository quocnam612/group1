"""Compare raw, reference-shaped OCR page JSONs using Levenshtein CER."""
from __future__ import annotations

import argparse
from collections import defaultdict
import json
from pathlib import Path
import unicodedata

FIELDS = ("tieu_de", "han", "phien_am", "dich_sat", "dich_tho", "chu_thich")
ENGINES = ("paddleocr", "got-ocr2", "qwen2.5-vl")


def normalized(lines, field):
    text = unicodedata.normalize("NFC", " ".join(lines))
    # Chinese whitespace and scan line wrapping are not transcription errors.
    return "".join(text.split()) if field == "han" else " ".join(text.split())


def edit_distance(reference, hypothesis):
    row = list(range(len(hypothesis)+1))
    for i, a in enumerate(reference, 1):
        current = [i]
        for j, b in enumerate(hypothesis, 1):
            current.append(min(row[j]+1, current[-1]+1, row[j-1]+(a != b)))
        row = current
    return row[-1]


def compare(reference_dir, predictions_dir, pages):
    results = []
    for page in pages:
        filename = f"page-{page:04}.json"
        reference = json.loads((reference_dir / filename).read_text(encoding="utf-8"))
        for engine in ENGINES:
            path = predictions_dir / engine / filename
            if not path.exists():
                raise ValueError(f"Missing prediction: {path}")
            prediction = json.loads(path.read_text(encoding="utf-8"))
            for field in FIELDS:
                ref = normalized(reference.get(field, []), field)
                hyp = normalized(prediction.get(field, []), field)
                errors = edit_distance(ref, hyp)
                results.append({"page": page, "engine": engine, "field": field,
                                "errors": errors, "reference_characters": len(ref),
                                "cer": errors/len(ref) if ref else None})
    return results


def markdown(results):
    grouped = defaultdict(lambda: [0, 0])
    for result in results:
        key = result["engine"], result["field"]
        grouped[key][0] += result["errors"]
        grouped[key][1] += result["reference_characters"]
    lines = ["| Model | " + " | ".join(FIELDS) + " |",
             "| --- | " + " | ".join("---:" for _ in FIELDS) + " |"]
    for engine in ENGINES:
        values = []
        for field in FIELDS:
            errors, chars = grouped[engine, field]
            values.append(f"{100*errors/chars:.2f}% ({errors}/{chars})" if chars else f"— ({errors} chèn)")
        lines.append("| " + engine + " | " + " | ".join(values) + " |")
    lines.extend(["", "CER = số phép chèn/xóa/thay tối thiểu / số ký tự tham chiếu; thấp hơn là tốt hơn.",
                  "Chuẩn hóa NFC, gộp khoảng trắng/xuống dòng; riêng `han` bỏ khoảng trắng. Giữ nguyên dấu, chữ hoa và dấu câu.",
                  "`can_kiem_tra` chứa nhiễu chưa phân loại, được bỏ khỏi bảng. Chữ Hán xen trong chú giải vẫn thuộc `chu_thich`.",
                  "Số liệu chỉ phản ánh bản tham chiếu đang có; các trang chưa kiểm ảnh không phải gold đã xác nhận."])
    return "\n".join(lines)+"\n"


def main():
    from ocr import page_numbers
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reference", type=Path, default=Path("gold/ocr/week2"))
    parser.add_argument("--predictions", type=Path, default=Path("out/ocr/week2/pages"))
    parser.add_argument("--pages", type=page_numbers, default=[38])
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    try:
        report = markdown(compare(args.reference, args.predictions, args.pages))
    except (ValueError, FileNotFoundError) as exc:
        parser.exit(1, f"Error: {exc}\n")
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(report, encoding="utf-8")
    print(report)


if __name__ == "__main__":
    main()
