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
SUPPORTED_ENGINES = (*ENGINES, "tesseract")


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
    if left == right:
        return 0
    start = 0
    while start < min(len(left), len(right)) and left[start] == right[start]:
        start += 1
    left, right = left[start:], right[start:]
    end = 0
    while end < min(len(left), len(right)) and left[-end-1] == right[-end-1]:
        end += 1
    if end:
        left, right = left[:-end], right[:-end]
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
    if left == right:
        return [(char, char) for char in left]
    if not left:
        return [(None, char) for char in right]
    if not right:
        return [(char, None) for char in left]
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


def star_alignment(texts: dict[str, str], order: list[str]) -> list[dict[str, str | None]]:
    """Align every engine to the same backbone, avoiding progressive drift."""
    anchor = texts[order[0]]
    bases = {engine: [None]*len(anchor) for engine in order}
    insertions = {engine: [[] for _ in range(len(anchor)+1)] for engine in order}
    for engine in order:
        index = 0
        for left, right in align_pairwise(anchor, texts[engine]):
            if left is None:
                insertions[engine][index].append(right)
            else:
                bases[engine][index] = right
                index += 1
    columns = []
    for index in range(len(anchor)+1):
        inserted = {engine: "".join(insertions[engine][index]) for engine in order}
        if any(inserted.values()):
            columns.extend(multiple_alignment(inserted, order))
        if index < len(anchor):
            columns.append({engine: bases[engine][index] for engine in order})
    return columns


def engine_language_ranks(reference_dir: Path, prediction_dir: Path,
                          pages: list[int], engines=ENGINES) -> tuple[dict[str, list[str]], dict]:
    totals = {language: {engine: [0, 0] for engine in engines}
              for language in ("han", "vietnamese")}
    for page in pages:
        name = f"page-{page:04}.json"
        reference = json.loads((reference_dir / name).read_text(encoding="utf-8"))
        for engine in engines:
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
    for language, values in totals.items():
        scores = {engine: errors / chars if chars else 1.0
                  for engine, (errors, chars) in values.items()}
        ranks[language] = sorted(engines, key=lambda engine: (scores[engine], engines.index(engine)))
        summary[language] = {
            engine: {"errors": errors, "reference_characters": chars,
                     "cer": errors / chars if chars else None}
            for engine, (errors, chars) in values.items()
        }
    return ranks, summary


def char_language(char: str) -> str:
    return "han" if is_han(char) else "vietnamese"


def vote_text(texts: dict[str, str], order: list[str], ranks: dict[str, list[str]],
              alignment: str = "star", voters_by_language=None) -> str:
    columns = (star_alignment if alignment == "star" else multiple_alignment)(texts, order)
    voted = []
    for column in columns:
        context = column.get(order[0])
        if context is None:
            context = next((column.get(engine) for engine in order if column.get(engine) is not None), "a")
        language = char_language(context)
        active = [engine for engine in order if voters_by_language is None
                  or engine in voters_by_language[language]]
        # A gap is a real vote for omission. Ignoring it biases three-way
        # ties toward insertions from weaker recognizers.
        counts = Counter(column.get(engine) for engine in active)
        largest = max(counts.values())
        candidates = {char for char, count in counts.items() if count == largest}
        if len(candidates) == 1:
            winner = next(iter(candidates))
            if winner is not None:
                voted.append(winner)
            continue
        winner = next(engine for engine in ranks[language]
                      if engine in active and column.get(engine) in candidates)
        if column.get(winner) is not None:
            voted.append(column[winner])
    text = "".join(voted)
    # Keep a readable single-space convention for Vietnamese layers.
    return " ".join(text.split())


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def vote(reference_dir: Path, prediction_dir: Path, pages: list[int], output_dir: Path,
         alignment: str = "star", engines=ENGINES, vietnamese_engines=None) -> dict:
    voters = {"han": list(engines), "vietnamese": list(vietnamese_engines or engines)}
    for selected in voters.values():
        if len(selected) != len(set(selected)) or len(set(selected)) < 3 or not set(selected) <= set(engines):
            raise ValueError("Each script needs at least three distinct available voting engines")
    ranks, calibration = engine_language_ranks(reference_dir, prediction_dir, pages, engines)
    output_dir.mkdir(parents=True, exist_ok=True)
    for page in pages:
        name = f"page-{page:04}.json"
        inputs = {
            engine: json.loads((prediction_dir / engine / name).read_text(encoding="utf-8"))
            for engine in engines
        }
        result = {}
        for field in FIELDS:
            language = "han" if field == "han" else "vietnamese"
            order = ranks[language]
            texts = {engine: normalized(inputs[engine].get(field, []), field)
                     for engine in engines}
            result[field] = [vote_text(texts, order, ranks, alignment, voters)] if any(texts.values()) else []
        result["can_kiem_tra"] = sorted({
            line for engine in engines
            for line in inputs[engine].get("can_kiem_tra", []) if line
        })
        (output_dir / name).write_text(
            json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )

    metadata = {
        "schema_version": 1,
        "pages": pages,
        "engines": list(engines),
        "voters_by_language": voters,
        "script_routing": "Unicode script of the backbone character, otherwise first non-gap OCR character; no reference text is consulted.",
        "method": f"{alignment.capitalize()} character-level Levenshtein alignment and majority vote, including gaps.",
        "alignment": alignment,
        "alignment_cost": "Unit-cost Levenshtein",
        "gap_policy": "A missing character is an omission vote; ties including omissions use the same CER ranking.",
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
            for engine in engines
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
    parser.add_argument("--alignment", choices=("star", "progressive"), default="star")
    parser.add_argument("--engines", nargs="+", choices=SUPPORTED_ENGINES, default=list(ENGINES))
    parser.add_argument("--vietnamese-engines", nargs="+", choices=SUPPORTED_ENGINES,
                        help="Optional fixed Vietnamese voting subset; at least three engines required")
    args = parser.parse_args()
    if len(set(args.engines)) < 3 or len(args.engines) != len(set(args.engines)):
        parser.error("Select at least three distinct OCR engines")
    if args.vietnamese_engines and (len(set(args.vietnamese_engines)) < 3
                                    or len(args.vietnamese_engines) != len(set(args.vietnamese_engines))
                                    or not set(args.vietnamese_engines) <= set(args.engines)):
        parser.error("Vietnamese voting requires at least three distinct selected engines")
    missing = []
    for page in args.pages:
        name = f"page-{page:04}.json"
        if not (args.reference / name).exists():
            missing.append(str(args.reference / name))
        missing.extend(str(args.predictions / engine / name) for engine in args.engines
                       if not (args.predictions / engine / name).exists())
    if missing:
        parser.error("Missing page files:\n" + "\n".join(missing))
    metadata = vote(args.reference, args.predictions, args.pages, args.output, args.alignment,
                    tuple(args.engines), args.vietnamese_engines)
    print(f"Saved {len(args.pages)} voted pages to {args.output}")
    print("CER tie-break ranks:")
    for language, order in metadata["engine_order_by_reference_cer"].items():
        print(f"  {language}: " + " < ".join(order))


if __name__ == "__main__":
    main()
