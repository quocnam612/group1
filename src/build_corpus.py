"""Build CV18 corpus v1 with page checkpoints and explicit partial progress."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import shlex
import subprocess
import sys

import yaml

from ocr import ROOT, page_numbers
from pages import save_json
from corpus.output import (SLUGS, align_segments, atomic_jsonl, book_stats, mark_duplicates,
                           validate, write_report)
from corpus.segments import scan_segments, text_segments
from corpus.text import extract_book, text_layers, checksum


def load(config_path):
    config = yaml.safe_load(Path(config_path).read_text(encoding="utf-8"))
    config["_config_path"] = str(Path(config_path).resolve())
    manifest = json.loads((ROOT/config.get("manifest", "manifest.json")).read_text())
    by_file = {b["file"]: b for b in manifest["files"]}
    books = []
    for assignment in config["assignments"]:
        if assignment["part"] != "chinh":
            continue
        book = dict(by_file[assignment["file"]])
        info = subprocess.check_output(["pdfinfo", str(ROOT/config.get("data_dir", ".")/book["file"])], text=True)
        book["total_pages"] = int(next(s.split(":", 1)[1] for s in info.splitlines() if s.startswith("Pages:")))
        book["slug"] = SLUGS[book["book"]]
        books.append(book)
    return config, books


def status(config, books, cache):
    data = []
    for b in books:
        base = cache/b["slug"]
        entry = {"book": b["book"], "total_pages": b["total_pages"]}
        if b["type"] == "scan":
            entry["layout_pages"] = len(list((base/"layout/pages").glob("page-*.json")))
            entry["ocr_pages"] = {e: len(list((base/"ocr/pages"/e).glob("page-*.json"))) for e in config["ocr"]["engines"]}
        else:
            entry["text_pages"] = len(list((base/"text").glob("page-*.json")))
        data.append(entry)
    return data


def assemble(config, books, cache, out):
    from corpus.scan import vote_pages
    rows, stats = [], []
    for b in books:
        base = cache/b["slug"]
        first_body = config.get("corpus", {}).get("first_body_page", {}).get(b["slug"], 1)
        if b["type"] == "text_vertical":
            records = [json.loads(p.read_text()) for p in sorted((base/"text").glob("page-*.json"))]
            expected_source = checksum(ROOT/config.get("data_dir", ".")/b["file"])
            if any(p["source"]["pdf_sha256"] != expected_source for p in records):
                raise ValueError(f"Text checkpoint source differs: {b['book']}")
            segments, skipped = text_segments([p for p in records if p["page"] >= first_body], b["slug"])
            skipped.insert(0, {"pages": list(range(1, first_body)), "reason": "configured_front_matter"})
            layers = list(text_layers(records, b))
            method = "gale_church"
            processed = len(records)
        else:
            # Export only pages finished by every engine. Partial runs remain
            # explicitly partial and can never masquerade as full coverage.
            ready = set(range(1, b["total_pages"]+1))
            for e in config["ocr"]["engines"]:
                ready &= {int(p.stem.split("-")[1]) for p in (base/"ocr/pages"/e).glob("page-*.json")}
            layers = vote_pages(config, base, cache/"calibration.json", sorted(ready)) if ready else []
            segments, skipped = scan_segments([p for p in layers if p["pdf_page"] >= first_body])
            skipped.insert(0, {"pages": list(range(1, first_body)), "reason": "configured_front_matter"})
            for p in layers:
                p["page"] = p["pdf_page"]+b.get("page_offset", 0)
            method = "gale_church+ocr_voting(paddleocr,got-ocr2,qwen2.5-vl,tesseract)"
            processed = len(layers)
        book_rows, parameters = align_segments(segments, b, config["group"], method)
        rows += book_rows
        s = book_stats(b, segments, book_rows, processed, b["total_pages"], skipped)
        s["alignment_parameters"] = parameters
        stats.append(s)
        atomic_jsonl(out/"layers"/(b["slug"]+".jsonl"), layers)
    mark_duplicates(rows)
    validate(rows)
    out.mkdir(parents=True, exist_ok=True)
    atomic_jsonl(out/"corpus.jsonl", rows)
    runtime = cache/"run.json"
    save_json(runtime, {"schema_version": 1, "updated_at": datetime.now(timezone.utc).isoformat(),
                       "complete": all(s["complete"] for s in stats), "books": stats,
                       "config_sha256": checksum(config["_config_path"]), "seed": config.get("seed", 42)})
    write_report(out, rows, stats, os.path.relpath(runtime, ROOT))
    print(f"Exported {len(rows)} pairs; complete={all(s['complete'] for s in stats)} -> {out/'corpus.jsonl'}", flush=True)
    return rows, stats


def run_logged(command, cache):
    log_path = cache/"run.log"
    with log_path.open("a", encoding="utf-8") as stream:
        message = "Running: "+shlex.join(command)
        print(message, flush=True)
        stream.write(message+"\n")
        stream.flush()
        process = subprocess.Popen(command, cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                   text=True, bufsize=1)
        for line in process.stdout:
            print(line, end="", flush=True)
            stream.write(line)
            stream.flush()
        if process.wait():
            raise subprocess.CalledProcessError(process.returncode, command)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=ROOT/"config.yaml")
    parser.add_argument("--stage", choices=("all", "text", "prepare", "ocr", "assemble", "status"), default="all")
    parser.add_argument("--engine", choices=("paddleocr", "got-ocr2", "qwen2.5-vl", "tesseract"))
    parser.add_argument("--pages", type=page_numbers, help="Restrict scan pages for a layout/OCR smoke check")
    parser.add_argument("--overwrite", action="store_true", help="Fresh OCR inference; keep the frozen week-two outputs")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    try:
        if args.engine and args.stage != "ocr":
            raise ValueError("--engine requires --stage ocr")
        config, books = load(args.config)
        cache = ROOT/config.get("corpus", {}).get("cache_dir", ".cache/corpus-v1")
        out = ROOT/config.get("out_dir", "out")
        if args.dry_run or args.stage == "status":
            print(json.dumps(status(config, books, cache), ensure_ascii=False, indent=2))
            if args.dry_run:
                print("Stages: text -> prepare -> one process per OCR engine -> voting -> Gale–Church -> export")
            return
        cache.mkdir(parents=True, exist_ok=True)
        driver_lock = None
        snapshot = cache/"config.snapshot.yaml"
        if snapshot.exists() and checksum(snapshot) != checksum(args.config):
            raise ValueError("Configuration differs from this corpus run; use a fresh cache directory")
        if args.stage == "all":
            import fcntl
            driver_lock = (cache/"pipeline.lock").open("a")
            try:
                fcntl.flock(driver_lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError as exc:
                raise ValueError("This corpus pipeline is already running; use --stage status") from exc
            if not snapshot.exists():
                snapshot.write_bytes(args.config.read_bytes())
        calibration_source = ROOT/config["corpus"]["calibration"]
        calibration = cache/"calibration.json"
        if calibration.exists() and checksum(calibration) != checksum(calibration_source):
            raise ValueError("Week-two calibration changed; use a fresh corpus cache directory")
        if not calibration.exists():
            calibration.write_bytes(calibration_source.read_bytes())
        if args.stage == "all":
            stages = [("text", None), ("prepare", None)]
            order = config.get("corpus", {}).get("engine_order", config["ocr"]["engines"])
            if set(order) != set(config["ocr"]["engines"]) or len(order) != len(set(order)):
                raise ValueError("Corpus execution order must contain every configured engine exactly once")
            stages += [("ocr", e) for e in order]
            for stage, engine in stages:
                save_json(cache/"job.json", {"pid": os.getpid(), "stage": stage, "engine": engine,
                                            "updated_at": datetime.now(timezone.utc).isoformat()})
                command = [sys.executable, str(Path(__file__).resolve()), "--config", str(snapshot), "--stage", stage]
                if engine:
                    command += ["--engine", engine]
                if args.pages and stage != "text":
                    command += ["--pages", ",".join(map(str, args.pages))]
                if args.overwrite and stage == "ocr":
                    command.append("--overwrite")
                run_logged(command, cache)
            save_json(cache/"job.json", {"pid": os.getpid(), "stage": "complete", "engine": None,
                                        "updated_at": datetime.now(timezone.utc).isoformat()})
            return
        if args.stage == "text":
            for b in books:
                if b["type"] == "text_vertical":
                    extract_book(ROOT/config.get("data_dir", ".")/b["file"], cache/b["slug"]/"text")
            assemble(config, books, cache, out)
        if args.stage == "prepare":
            from corpus.scan import prepare
            for b in books:
                if b["type"] == "scan":
                    prepare(b, config, cache/b["slug"], args.pages)
        if args.stage == "ocr":
            from corpus.scan import ocr_command
            for engine in ([args.engine] if args.engine else config["ocr"]["engines"]):
                for b in books:
                    if b["type"] != "scan":
                        continue
                    command = ocr_command(engine, b, config, cache/b["slug"], args.pages)
                    if args.overwrite:
                        command.append("--overwrite")
                    print("Running:", shlex.join(command), flush=True)
                    subprocess.run(command, cwd=ROOT, check=True)
        if args.stage in ("ocr", "assemble"):
            assemble(config, books, cache, out)
    except (ValueError, KeyError, FileNotFoundError, subprocess.CalledProcessError) as exc:
        parser.exit(1, f"Error: {exc}\n")


if __name__ == "__main__":
    for variable, default in (("OMP_NUM_THREADS", "1"), ("MKL_NUM_THREADS", "2"), ("OPENBLAS_NUM_THREADS", "2")):
        os.environ.setdefault(variable, default)
    main()
