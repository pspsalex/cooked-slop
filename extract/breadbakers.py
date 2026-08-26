# SPDX-License-Identifier: MIT
"""Bread-Bakers Mailing List archive extraction and preprocessing script."""

import argparse
import concurrent.futures
import csv
import logging
import os
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# RFC 822 Email Headers and Digest Message Delimiters
HEADER_PATTERN = re.compile(
    r"^(?:From|Subject|Date|To|Reply-To|Message-ID|Message-Id|X-[^:]*|Sender|Return-Path|Lines|Organization|MIME-Version|Content-Type|Content-Transfer-Encoding):\s*",
    re.IGNORECASE,
)
DELIM_PATTERN = re.compile(
    r"^-+\s*(?:MESSAGE|BEGIN|END)\b.*",
    re.IGNORECASE,
)

# Quotes and Editorial Annotations
QUOTE_PATTERN = re.compile(r"^\s*>")
EDITOR_NOTE_PATTERN = re.compile(r"\[Editor's Note:.*?\]", re.DOTALL | re.IGNORECASE)

# Standard Signature Marker
SIG_PATTERN = re.compile(r"^--\s*$")

# Common Footers
FOOTER_PATTERNS = [
    re.compile(r"Rainbow V\s*\d+\.\d+", re.IGNORECASE),
    re.compile(r"\bCHRONIX\b", re.IGNORECASE),
    re.compile(r"\bBestserv\b", re.IGNORECASE),
]

# Admin / Help Message Indicators
ADMIN_PATTERNS = [
    re.compile(r"BEGIN INFO bread-bakers", re.IGNORECASE),
    re.compile(r"Command:\s*info", re.IGNORECASE),
    re.compile(r"To unsubscribe", re.IGNORECASE),
    re.compile(r"Welcome to bread-bakers", re.IGNORECASE),
    re.compile(r"bread-bakers mailing list info", re.IGNORECASE),
]

# Table of Contents Line Pattern (e.g. "    001 - Reggie Dwork ...")
TOC_LINE_PATTERN = re.compile(r"^\s*\d{3}\s*-\s*.*")

# Ingredient Match Patterns
INGREDIENT_PATTERN_1 = re.compile(
    r"\b\d+(?:[\s/.-]*\d+)?\s*(?:cup|cups|tablespoon|tablespoons|teaspoon|teaspoons|tbsp|tsp|ounce|ounces|oz|pound|pounds|lb|lbs|package|pkg|can|stick|sticks|clove|cloves|bunch|head|slice|slices|pinch|dash|quart|gallon|pint)s?\b",
    re.IGNORECASE,
)
INGREDIENT_PATTERN_2 = re.compile(
    r"\b\d+(?:[/-]\d+)?\s+(?:t\.|T\.|T|c\.|c|ea|pk|sm|md|lg|ts|tb|ds|pn|dr)\s+\w+",
    re.IGNORECASE,
)


def read_file_text(filepath: Path) -> str:
    """Read text file with fallback encodings."""
    for enc in ("utf-8", "cp1252", "latin-1"):
        try:
            return filepath.read_text(encoding=enc)
        except (UnicodeDecodeError, OSError):
            continue
    return filepath.read_text(encoding="utf-8", errors="replace")


def preprocess_message(raw_text: str) -> str:
    """Preprocess message by stripping RFC headers, quotes, footers, and signatures."""
    lines = raw_text.splitlines()
    cleaned_lines: List[str] = []

    for line in lines:
        if DELIM_PATTERN.match(line):
            continue
        if HEADER_PATTERN.match(line):
            continue
        if QUOTE_PATTERN.match(line):
            continue
        if any(pat.search(line) for pat in FOOTER_PATTERNS):
            continue
        cleaned_lines.append(line)

    text = "\n".join(cleaned_lines)
    text = EDITOR_NOTE_PATTERN.sub("", text)

    final_lines: List[str] = []
    for line in text.splitlines():
        if SIG_PATTERN.match(line):
            break
        final_lines.append(line)

    return "\n".join(final_lines)


def classify_message(
    cleaned_text: str, raw_text: str
) -> Tuple[Optional[str], List[str]]:
    """Classify message as recipe or non-recipe with reason."""
    non_blank = [line.strip() for line in cleaned_text.splitlines() if line.strip()]

    # 1. Admin check
    if any(pat.search(raw_text) for pat in ADMIN_PATTERNS):
        return "admin_only", non_blank

    # 2. Table of contents check
    toc_matches = sum(1 for line in non_blank if TOC_LINE_PATTERN.match(line))
    if toc_matches >= 3 or (
        len(non_blank) > 0 and (toc_matches / len(non_blank)) > 0.4
    ):
        return "toc_only", non_blank

    # 3. Line count check
    if len(non_blank) <= 10:
        return "too_short", non_blank

    # 4. Ingredient pattern check
    text_to_search = "\n".join(non_blank)
    matches_1 = INGREDIENT_PATTERN_1.findall(text_to_search)
    matches_2 = INGREDIENT_PATTERN_2.findall(text_to_search)
    distinct_matches = set(matches_1 + matches_2)

    if len(distinct_matches) < 2:
        return "no_ingredients", non_blank

    return None, non_blank


def process_single_file(filepath: Path, output_dir: Path) -> Optional[Dict[str, Any]]:
    """Process a single file, saving valid recipe or returning failure record."""
    try:
        raw_text = read_file_text(filepath)
        cleaned_text = preprocess_message(raw_text)
        reason, non_blank = classify_message(cleaned_text, raw_text)

        if reason is not None:
            sample_line = non_blank[0] if non_blank else ""
            return {
                "file": str(filepath),
                "reason": reason,
                "line_count": len(non_blank),
                "sample_line": sample_line,
            }

        out_filename = (
            filepath.name
            if filepath.name.endswith(".txt")
            else f"{filepath.name}.txt"
        )
        out_path = output_dir / out_filename
        out_path.write_text(cleaned_text, encoding="utf-8")
        return None
    except Exception as exc:
        logger.error("Error processing %s: %s", filepath, exc)
        return {
            "file": str(filepath),
            "reason": "error",
            "line_count": 0,
            "sample_line": str(exc),
        }


def process_directory(
    input_dir: Path | str,
    output_dir: Path | str,
    report_file: Path | str = "failures.csv",
    workers: Optional[int] = None,
) -> Tuple[int, int]:
    """Process input directory of split messages and log failures to report CSV."""
    in_path = Path(input_dir)
    out_path = Path(output_dir)
    report_path = Path(report_file)

    out_path.mkdir(parents=True, exist_ok=True)
    if report_path.parent:
        report_path.parent.mkdir(parents=True, exist_ok=True)

    files = [p for p in in_path.iterdir() if p.is_file()]
    logger.info("Found %d files to process in %s", len(files), in_path)

    failures: List[Dict[str, Any]] = []
    recipe_count = 0

    if workers == 1:
        for f in files:
            res = process_single_file(f, out_path)
            if res:
                failures.append(res)
            else:
                recipe_count += 1
    else:
        with concurrent.futures.ProcessPoolExecutor(max_workers=workers) as executor:
            futures = {
                executor.submit(process_single_file, f, out_path): f for f in files
            }
            for future in concurrent.futures.as_completed(futures):
                res = future.result()
                if res:
                    failures.append(res)
                else:
                    recipe_count += 1

    with report_path.open("w", newline="", encoding="utf-8") as csvfile:
        fieldnames = ["file", "reason", "line_count", "sample_line"]
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(failures)

    logger.info(
        "Processing complete: %d recipes extracted, %d non-recipes logged to %s",
        recipe_count,
        len(failures),
        report_path,
    )
    return recipe_count, len(failures)


def main() -> None:
    """CLI entry point for breadbakers extraction script."""
    parser = argparse.ArgumentParser(
        description="Bread-Bakers Mailing List archive extraction script"
    )
    parser.add_argument("input_dir", type=str, help="Directory containing split files")
    parser.add_argument("output_dir", type=str, help="Directory for cleaned recipe text files")
    parser.add_argument(
        "--report",
        type=str,
        default="failures.csv",
        help="Path to CSV failure report output file (default: failures.csv)",
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=None,
        help="Number of worker processes (default: cpu count)",
    )
    parser.add_argument(
        "-v", "--verbose", action="store_true", help="Enable verbose log output"
    )

    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    recipes, failures = process_directory(
        args.input_dir, args.output_dir, args.report, args.workers
    )
    sys.exit(0)


if __name__ == "__main__":
    main()
