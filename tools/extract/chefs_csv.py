# SPDX-License-Identifier: MIT
"""Extractor and converter for vintage Chef's Catalog / QuickBook CSV recipe dumps."""

import argparse
import csv
import logging
import re
import sys
from pathlib import Path
from typing import List, Optional

logger = logging.getLogger(__name__)


def convert_chefs_csv_to_markdown(input_path: Path, output_path: Path) -> int:
    """Read a chefs.csv file and convert its rows into a standard multi-recipe Markdown file.

    Args:
        input_path: Path to input CSV file.
        output_path: Path to output Markdown file.

    Returns:
        Number of recipes converted.
    """
    for enc in ("utf-8", "cp1252", "latin-1"):
        try:
            with open(input_path, "r", encoding=enc) as f:
                reader = csv.reader(f)
                rows = list(reader)
            break
        except UnicodeDecodeError:
            continue
    else:
        with open(input_path, "r", encoding="utf-8", errors="replace") as f:
            reader = csv.reader(f)
            rows = list(reader)

    recipes = []
    for row in rows:
        if not row or len(row) < 7:
            continue

        cat1 = row[2].strip()
        cat2 = row[3].strip()
        cat3 = row[4].strip()
        title = row[5].strip()
        source = row[6].strip()

        if not title:
            continue

        categories = [c for c in [cat1, cat2, cat3] if c]

        # In row[7:], columns before an empty column are ingredients; columns after are instructions
        items = row[7:]
        ing_items: List[str] = []
        inst_items: List[str] = []
        found_sep = False

        for item in items:
            item_str = item.strip()
            if not item_str:
                if ing_items:
                    found_sep = True
                continue

            if not found_sep:
                # Handle side-by-side ingredients separated by 3+ spaces
                subparts = re.split(r"\s{3,}", item_str)
                for sp in subparts:
                    if sp.strip():
                        ing_items.append(sp.strip())
            else:
                inst_items.append(item_str)

        recipes.append(
            {
                "title": title,
                "source": source,
                "categories": categories,
                "ingredients": ing_items,
                "instructions": inst_items,
            }
        )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as out:
        for r in recipes:
            out.write(f"# {r['title']}\n\n")
            if r["categories"]:
                out.write(f"**Category:** {', '.join(r['categories'])}\n\n")
            if r["source"]:
                out.write(f"**Source:** {r['source']}\n\n")
            if r["ingredients"]:
                out.write("## Ingredients\n\n")
                for ing in r["ingredients"]:
                    out.write(f"- {ing}\n")
                out.write("\n")
            if r["instructions"]:
                out.write("## Instructions\n\n")
                for inst in r["instructions"]:
                    out.write(f"{inst}\n\n")
            out.write("---\n\n")

    return len(recipes)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Convert vintage Chef's Catalog / QuickBook CSV file into standard Markdown recipes."
    )
    parser.add_argument("input", type=Path, help="Input CSV file path (e.g. chefs.csv)")
    parser.add_argument("output", type=Path, help="Output Markdown file path (e.g. chefs.md)")
    args = parser.parse_args()

    if not args.input.exists():
        print(f"Error: input file {args.input} not found.", file=sys.stderr)
        sys.exit(1)

    count = convert_chefs_csv_to_markdown(args.input, args.output)
    print(f"Successfully converted {count} recipes to '{args.output}'.")


if __name__ == "__main__":
    main()
