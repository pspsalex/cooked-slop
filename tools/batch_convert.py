#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Batch conversion runner for recipe files."""

import argparse
import concurrent.futures
import csv
import json
import logging
import os
import subprocess
import sys
from pathlib import Path
from typing import Dict, List, Optional, Any

logger = logging.getLogger(__name__)

# Files excluded strictly based on file extension
EXCLUDED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".gif", ".bmp", ".mht", ".json"}


def is_skipped(rel_path: Path) -> bool:
    """Determine if a file path should be excluded based strictly on extension."""
    return rel_path.suffix.lower() in EXCLUDED_EXTENSIONS


def get_parser_format_id(file_path: Path) -> str:
    """Determine format_id of the parser that handles file_path."""
    try:
        from parsers import ParserRegistry, get_ingredient_parser
        ingredient_parser = get_ingredient_parser(use_nlp=False)
        parser = ParserRegistry.get_parser(file_path, ingredient_parser)
        if parser is not None:
            return parser.format_id()
    except Exception as e:
        logger.debug("Error detecting parser for %s: %s", file_path, e)

    ext = file_path.suffix.lower().lstrip(".")
    return ext if ext else "unknown"


def convert_file_job(
    input_root: Path,
    rel_path: Path,
    output_root: Path,
    convert_script: Path,
    resume: bool = False,
    timeout: int = 30,
) -> Dict[str, Any]:
    """Process a single file using convert.py via subprocess.

    Returns dict with keys: file, parser, recipes_extracted, status, error.
    """
    file_rel_str = rel_path.as_posix()
    input_file = input_root / rel_path
    output_json = output_root / rel_path.with_suffix(".json")

    detected_parser = get_parser_format_id(input_file)

    # Handle resume option if JSON output already exists
    if resume and output_json.exists():
        try:
            with open(output_json, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, list):
                extracted = len(data)
                status = "ok" if extracted > 0 else "empty"
                err = "" if status == "ok" else "No recipes extracted"
                return {
                    "file": file_rel_str,
                    "parser": detected_parser,
                    "recipes_extracted": extracted,
                    "status": status,
                    "error": err,
                }
        except Exception as e:
            logger.debug("Failed reading existing output for resume %s: %s", output_json, e)

    # Ensure parent output directory exists
    output_json.parent.mkdir(parents=True, exist_ok=True)

    cmd = [
        sys.executable,
        str(convert_script),
        str(input_file),
        "-o",
        str(output_json),
        "--no-nlp",
    ]

    try:
        proc = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        return {
            "file": file_rel_str,
            "parser": detected_parser,
            "recipes_extracted": 0,
            "status": "error",
            "error": f"Timeout after {timeout} seconds",
        }
    except Exception as e:
        return {
            "file": file_rel_str,
            "parser": detected_parser,
            "recipes_extracted": 0,
            "status": "error",
            "error": str(e),
        }

    if proc.returncode != 0:
        err_msg = proc.stderr.strip() or proc.stdout.strip() or f"Process failed with exit code {proc.returncode}"
        # Truncate error message if excessively long
        if len(err_msg) > 200:
            err_msg = err_msg[:197] + "..."
        return {
            "file": file_rel_str,
            "parser": detected_parser,
            "recipes_extracted": 0,
            "status": "error",
            "error": err_msg,
        }

    # Inspect generated JSON output file
    if output_json.exists():
        try:
            with open(output_json, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, list):
                extracted = len(data)
                if extracted > 0:
                    return {
                        "file": file_rel_str,
                        "parser": detected_parser,
                        "recipes_extracted": extracted,
                        "status": "ok",
                        "error": "",
                    }
                else:
                    return {
                        "file": file_rel_str,
                        "parser": detected_parser,
                        "recipes_extracted": 0,
                        "status": "empty",
                        "error": "No recipes extracted",
                    }
        except Exception as e:
            return {
                "file": file_rel_str,
                "parser": detected_parser,
                "recipes_extracted": 0,
                "status": "error",
                "error": f"Invalid JSON output: {e}",
            }

    return {
        "file": file_rel_str,
        "parser": detected_parser,
        "recipes_extracted": 0,
        "status": "empty",
        "error": "No recipes extracted",
    }


def find_all_files(root_dir: Path) -> List[Path]:
    """Recursively collect all files under root_dir."""
    files = []
    for dirpath, _, filenames in os.walk(root_dir):
        dp = Path(dirpath)
        for fname in filenames:
            files.append(dp / fname)
    return files


def run_batch_conversion(
    input_dir: Path,
    output_dir: Path,
    csv_path: Path,
    workers: int = 4,
    dry_run: bool = False,
    resume: bool = False,
    verbose: bool = False,
    timeout: int = 120,
) -> int:
    """Run batch conversion across all processable files in input_dir."""
    convert_script = Path(__file__).parent / "convert.py"
    if not convert_script.exists():
        convert_script = Path(__file__).parent.parent / "convert.py"

    if not input_dir.exists():
        print(f"Error: Input directory {input_dir} does not exist.", file=sys.stderr)
        return 1

    all_files = find_all_files(input_dir)
    total_files = len(all_files)

    to_process: List[Path] = []
    skipped_count = 0

    for file_path in all_files:
        try:
            rel_path = file_path.relative_to(input_dir)
        except ValueError:
            rel_path = file_path

        if is_skipped(rel_path):
            skipped_count += 1
            if verbose:
                print(f"Skipping: {rel_path}")
        else:
            to_process.append(rel_path)

    if dry_run:
        print(f"Total files: {total_files}")
        print(f"Skipped: {skipped_count}")
        print("Success (≥1 recipe): 0")
        print("Empty (0 recipes): 0")
        print("Error: 0")
        print("Total recipes extracted: 0")
        return 0

    output_dir.mkdir(parents=True, exist_ok=True)
    if csv_path.parent:
        csv_path.parent.mkdir(parents=True, exist_ok=True)

    results: List[Dict[str, Any]] = []

    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as executor:
        future_to_rel = {
            executor.submit(
                convert_file_job,
                input_dir,
                rel_path,
                output_dir,
                convert_script,
                resume=resume,
                timeout=timeout,
            ): rel_path
            for rel_path in to_process
        }

        completed = 0
        total_to_process = len(to_process)
        for future in concurrent.futures.as_completed(future_to_rel):
            res = future.result()
            results.append(res)
            completed += 1
            if verbose:
                print(
                    f"[{completed}/{total_to_process}] {res['file']} -> "
                    f"status={res['status']}, parser={res['parser']}, recipes={res['recipes_extracted']}"
                )

    # Sort results by relative file path for deterministic CSV output
    results.sort(key=lambda r: r["file"])

    # Write CSV
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["file", "parser", "recipes_extracted", "status", "error"])
        for r in results:
            writer.writerow([r["file"], r["parser"], r["recipes_extracted"], r["status"], r["error"]])

    # Calculate summary statistics
    success_count = sum(1 for r in results if r["status"] == "ok")
    empty_count = sum(1 for r in results if r["status"] == "empty")
    error_count = sum(1 for r in results if r["status"] == "error")
    total_recipes = sum(r["recipes_extracted"] for r in results)

    print(f"Total files: {total_files}")
    print(f"Skipped: {skipped_count}")
    print(f"Success (≥1 recipe): {success_count}")
    print(f"Empty (0 recipes): {empty_count}")
    print(f"Error: {error_count}")
    print(f"Total recipes extracted: {total_recipes}")

    return 0


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="Run batch conversion on recipe files recursively."
    )
    parser.add_argument(
        "--dir",
        type=Path,
        default=Path("."),
        help="Root input directory (default: current directory)",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("batch_output"),
        help="Root directory for output JSON files (default: batch_output)",
    )
    parser.add_argument(
        "--csv",
        type=Path,
        default=Path("batch_results.csv"),
        help="Path for results CSV (default: batch_results.csv)",
    )
    parser.add_argument(
        "-w",
        "--workers",
        type=int,
        default=4,
        help="Number of concurrent workers (default: 4)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Perform a dry run to count processable and skipped files without converting",
    )
    parser.add_argument(
        "--resume",
        action="store_true",
        help="Skip files that already have JSON output in the output directory",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=120,
        help="Per-file timeout in seconds (default: 120)",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Enable verbose output",
    )

    args = parser.parse_args(argv)

    if args.verbose:
        logging.basicConfig(level=logging.DEBUG)

    return run_batch_conversion(
        input_dir=args.dir,
        output_dir=args.output_dir,
        csv_path=args.csv,
        workers=args.workers,
        dry_run=args.dry_run,
        resume=args.resume,
        verbose=args.verbose,
        timeout=args.timeout,
    )


if __name__ == "__main__":
    sys.exit(main())
