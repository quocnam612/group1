"""Run the configured week-two OCR, majority voting and CER pipeline."""
from __future__ import annotations

import argparse
import os
from pathlib import Path
import shlex
import subprocess
import sys

import yaml

ROOT = Path(__file__).resolve().parents[1]


def commands(config, overwrite=False, skip_ocr=False):
    ocr = config["ocr"]
    engines = ocr["engines"]
    if len(set(engines)) < 3 or len(engines) != len(set(engines)):
        raise ValueError("Configure at least three distinct OCR engines")
    pages = str(ocr.get("evaluation_pages", "38-48"))
    output = Path(config.get("out_dir", "out")) / "ocr/week2"
    plan = []
    allowed = {"device", "lang", "profile", "max_new_tokens", "max_pixels", "quantization",
               "cpu_offload", "allow_cpu", "model", "revision"}
    if not skip_ocr:
        pdf = Path(config.get("data_dir", ".")) / ocr["sample_pdf"]
        plan.append([sys.executable, str(ROOT / "src/ocr_prepare.py"),
                     "--layout", str(output / "layout/regions.json"), "--pdf", str(pdf),
                     "--dpi", str(ocr.get("dpi", 300)), "--pages", pages])
        for engine in engines:
            command = [sys.executable, str(ROOT / "src/ocr.py"), "run", "--format", "reference",
                       "--engine", engine, "--pages", pages, "--seed", str(config.get("seed", 42)),
                       "--output", str(output / "pages"), "--layout", str(output / "layout/regions.json")]
            for key, value in ocr.get("engine_options", {}).get(engine, {}).items():
                if key not in allowed:
                    raise ValueError(f"Unsupported OCR setting: {engine}.{key}")
                flag = "--"+key.replace("_", "-")
                if value is True:
                    command.append(flag)
                elif value is not False and value is not None:
                    command.extend([flag, str(value)])
            if overwrite:
                command.append("--overwrite")
            plan.append(command)
    voters = ocr.get("vote_engines", engines)
    if len(set(voters)) < 3 or len(voters) != len(set(voters)) or not set(voters) <= set(engines):
        raise ValueError("Voting requires at least three distinct configured engines")
    vi_voters = ocr.get("vote_vietnamese_engines", voters)
    if len(set(vi_voters)) < 3 or len(vi_voters) != len(set(vi_voters)) or not set(vi_voters) <= set(voters):
        raise ValueError("Vietnamese voting requires at least three distinct participating engines")
    plan.append([sys.executable, str(ROOT / "src/ocr_vote.py"), "--pages", pages,
                 "--predictions", str(output / "pages"), "--reference", "gold/ocr/week2",
                 "--output", str(output / "pages/voting"), "--alignment", ocr.get("vote_alignment", "star"),
                 "--engines", *voters])
    if ocr.get("vote_vietnamese_engines"):
        plan[-1].extend(["--vietnamese-engines", *ocr["vote_vietnamese_engines"]])
    plan.append([sys.executable, str(ROOT / "src/ocr_week2_report.py"), "--pages", pages,
                 "--predictions", str(output / "pages"), "--reference", "gold/ocr/week2",
                 "--output", str(output / "comparison.md")])
    return plan


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=ROOT / "config.yaml")
    parser.add_argument("--overwrite", action="store_true", help="Force fresh inference instead of compatible cached OCR")
    parser.add_argument("--skip-ocr", action="store_true", help="Recompute voting and CER from existing raw OCR")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    try:
        config = yaml.safe_load(args.config.read_text(encoding="utf-8"))
        plan = commands(config, args.overwrite, args.skip_ocr)
        env = os.environ.copy()
        env.setdefault("OMP_NUM_THREADS", "1")
        for variable in ("MKL_NUM_THREADS", "OPENBLAS_NUM_THREADS"):
            env.setdefault(variable, "2")
        for command in plan:
            print("Running:", shlex.join(command), flush=True)
            if not args.dry_run:
                subprocess.run(command, cwd=ROOT, env=env, check=True)
    except (ValueError, KeyError, FileNotFoundError, subprocess.CalledProcessError) as exc:
        parser.exit(1, f"Error: {exc}\n")


if __name__ == "__main__":
    main()
