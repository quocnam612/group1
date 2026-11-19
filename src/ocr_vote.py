"""Vote character by character across the week-two OCR page exports."""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import unicodedata

FIELDS = ("tieu_de", "han", "phien_am", "dich_sat", "dich_tho", "chu_thich")
ENGINES = ("paddleocr", "got-ocr2", "qwen2.5-vl")


def page_numbers(value: str) -> list[int]:
    pages: set[int] = set()
    for item in value.split(","):
        if "-" in item:
            start, end = (int(part) for part in item.split("-", 1))
            if end < start:
                raise argparse.ArgumentTypeError("page ranges must be ascending")
            pages.update(range(start, end + 1))
        else:
            pages.add(int(item))
    if not pages or min(pages) < 1:
        raise argparse.ArgumentTypeError("pages must be positive")
    return sorted(pages)


def normalized(lines, field: str) -> str:
    text = unicodedata.normalize("NFC", " ".join(lines))
    if field == "han":
        return "".join(text.split())
    return " ".join(text.split())


def is_han(char: str) -> bool:
    code = ord(char)
    return (
        0x2E80 <= code <= 0x2FDF
        or 0x3400 <= code <= 0x4DBF
        or 0x4E00 <= code <= 0x9FFF
        or 0xF900 <= code <= 0xFAFF
        or 0x20000 <= code <= 0x323AF
    )


def project_language(text: str, language: str) -> str:
    return "".join(
        char for char in text
        if not char.isspace() and (is_han(char) if language == "han" else not is_han(char))
    )


def edit_distance(left: str, right: str) -> int:
    if len(left) < len(right):
        left, right = right, left
    previous = list(range(len(right) + 1))
    for i, a in enumerate(left, 1):
        current = [i]
        for j, b in enumerate(right, 1):
            current.append(min(previous[j] + 1, current[-1] + 1,
                               previous[j - 1] + (a != b)))
        previous = current
    return previous[-1]


def align_pairwise(left: str, right: str) -> list[tuple[str | None, str | None]]:
    """Global Levenshtein alignment with deterministic diagonal-first ties."""
    rows, columns = len(left) + 1, len(right) + 1
    distance = [[0] * columns for _ in range(rows)]
    for i in range(rows):
        distance[i][0] = i
    for j in range(columns):
        distance[0][j] = j
    for i, a in enumerate(left, 1):
        for j, b in enumerate(right, 1):
            distance[i][j] = min(
                distance[i - 1][j - 1] + (a != b),
                distance[i - 1][j] + 1,
                distance[i][j - 1] + 1,
            )

    aligned = []
    i, j = len(left), len(right)
    while i or j:
        if i and j and distance[i][j] == distance[i - 1][j - 1] + (left[i - 1] != right[j - 1]):
            aligned.append((left[i - 1], right[j - 1]))
            i -= 1
            j -= 1
        elif i and distance[i][j] == distance[i - 1][j] + 1:
            aligned.append((left[i - 1], None))
            i -= 1
        else:
            aligned.append((None, right[j - 1]))
            j -= 1
    aligned.reverse()
    return aligned


def column_profile(columns: list[dict[str, str | None]], order: list[str]) -> str:
    profile = []
    for column in columns:
        counts = Counter(char for char in column.values() if char is not None)
        if not counts:
            profile.append("\uFFFD")
            continue
        top = max(counts.values())
        tied = {char for char, count in counts.items() if count == top}
        profile.append(next(column[engine] for engine in order
                            if column.get(engine) in tied))
    return "".join(profile)


def multiple_alignment(texts: dict[str, str], order: list[str]) -> list[dict[str, str | None]]:
    present = [order[0]]
    columns: list[dict[str, str | None]] = [{order[0]: char} for char in texts[order[0]]]
    for engine in order[1:]:
        profile = column_profile(columns, present)
        operations = align_pairwise(profile, texts[engine])
        expanded: list[dict[str, str | None]] = []
        old_index = 0
        for profile_char, new_char in operations:
            if profile_char is None:
                column = {previous: None for previous in present}
                column[engine] = new_char
                expanded.append(column)
            else:
                column = dict(columns[old_index])
                old_index += 1
                column[engine] = new_char
                expanded.append(column)
        columns = expanded
        present.append(engine)
    return columns


def engine_language_ranks(reference_dir: Path, prediction_dir: Path,
                          pages: list[int]) -> tuple[dict[str, list[str]], dict]:
    totals = {language: {engine: [0, 0] for engine in ENGINES}
              for language in ("han", "vietnamese")}
    for page in pages:
        name = f"page-{page:04}.json"
        reference = json.loads((reference_dir / name).read_text(encoding="utf-8"))
        for engine in ENGINES:
            prediction = json.loads((prediction_dir / engine / name).read_text(encoding="utf-8"))
            for field in FIELDS:
                ref = normalized(reference.get(field, []), field)
                hyp = normalized(prediction.get(field, []), field)
                for language in ("han", "vietnamese"):
                    ref_part = project_language(ref, language)
                    hyp_part = project_language(hyp, language)
                    totals[language][engine][0] += edit_distance(ref_part, hyp_part)
                    totals[language][engine][1] += len(ref_part)
    ranks = {}
    summary = {}
    for language, engines in totals.items():
        scores = {engine: errors / chars if chars else 1.0
                  for engine, (errors, chars) in engines.items()}
        ranks[language] = sorted(ENGINES, key=lambda engine: (scores[engine], ENGINES.index(engine)))
        summary[language] = {
            engine: {"errors": errors, "reference_characters": chars,
                     "cer": errors / chars if chars else None}
            for engine, (errors, chars) in engines.items()
        }
    return ranks, summary


def char_language(char: str) -> str:
    return "han" if is_han(char) else "vietnamese"


def vote_text(texts: dict[str, str], order: list[str], ranks: dict[str, list[str]]) -> str:
    columns = multiple_alignment(texts, order)
    voted = []
    for column in columns:
        counts = Counter(char for char in column.values() if char is not None)
        if not counts:
            continue
        largest = max(counts.values())
        candidates = {char for char, count in counts.items() if count == largest}
        # A character seen by one engine and omitted by two has no majority.
        if largest <= len(ENGINES) // 2 and len(candidates) == 1:
            continue
        if len(candidates) == 1:
            voted.append(next(iter(candidates)))
            continue
        candidate_engines = [engine for engine in order if column.get(engine) in candidates]
        winner = min(
            candidate_engines,
            key=lambda engine: (
                ranks[char_language(column[engine])].index(engine), order.index(engine)
            ),
        )
        voted.append(column[winner])
    text = "".join(voted)
    # Keep a readable single-space convention for Vietnamese layers.
    return " ".join(text.split())


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def vote(reference_dir: Path, prediction_dir: Path, pages: list[int], output_dir: Path) -> dict:
    ranks, calibration = engine_language_ranks(reference_dir, prediction_dir, pages)
    output_dir.mkdir(parents=True, exist_ok=True)
    for page in pages:
        name = f"page-{page:04}.json"
        inputs = {
            engine: json.loads((prediction_dir / engine / name).read_text(encoding="utf-8"))
            for engine in ENGINES
        }
        result = {}
        for field in FIELDS:
            language = "han" if field == "han" else "vietnamese"
            order = ranks[language]
            texts = {engine: normalized(inputs[engine].get(field, []), field)
                     for engine in ENGINES}
            result[field] = [vote_text(texts, order, ranks)] if any(texts.values()) else []
        result["can_kiem_tra"] = sorted({
            line for engine in ENGINES
            for line in inputs[engine].get("can_kiem_tra", []) if line
        })
        (output_dir / name).write_text(
            json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )

    metadata = {
        "schema_version": 1,
        "pages": pages,
        "method": "Progressive character-level Levenshtein alignment and majority vote.",
        "tie_break": "Lowest per-language CER on this reference set; engine order breaks remaining ties.",
        "reference_set": str(reference_dir),
        "engine_order_by_reference_cer": ranks,
        "calibration_cer": calibration,
        "normalization": "NFC; collapse whitespace; ignore whitespace in Han/Vietnamese language CER.",
        "limitations": [
            "Tie-break rankings use the same pages being scored; treat these CER values as calibration results, not held-out estimates.",
            "can_kiem_tra is retained as a union and excluded from voting and CER.",
        ],
        "input_sha256": {
            engine: {
                f"page-{page:04}.json": sha256(prediction_dir / engine / f"page-{page:04}.json")
                for page in pages
            }
            for engine in ENGINES
        },
    }
    output_dir.parent.parent.joinpath("vote_settings.json").write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return metadata


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reference", type=Path, default=Path("gold/ocr/week2"))
    parser.add_argument("--predictions", type=Path, default=Path("out/ocr/week2/pages"))
    parser.add_argument("--pages", type=page_numbers, default=list(range(38, 49)))
    parser.add_argument("--output", type=Path, default=Path("out/ocr/week2/pages/voting"))
    args = parser.parse_args()
    missing = []
    for page in args.pages:
        name = f"page-{page:04}.json"
        if not (args.reference / name).exists():
            missing.append(str(args.reference / name))
        missing.extend(str(args.predictions / engine / name) for engine in ENGINES
                       if not (args.predictions / engine / name).exists())
    if missing:
        parser.error("Missing page files:\n" + "\n".join(missing))
    metadata = vote(args.reference, args.predictions, args.pages, args.output)
    print(f"Saved {len(args.pages)} voted pages to {args.output}")
    print("CER tie-break ranks:")
    for language, order in metadata["engine_order_by_reference_cer"].items():
        print(f"  {language}: " + " < ".join(order))


if __name__ == "__main__":
    main()
