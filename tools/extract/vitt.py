# SPDX-License-Identifier: MIT
"""Extractor and normalizer for vintage Vitt Cooking Echo CSV recipe dumps.

Normalizes raw BBS echo CSV exports (RNUM, NAME, KING, SOURCE, TXT, TAG)
into clean, standard Generic Markdown files tagged with <!-- format: generic_md -->
which can be processed directly by GenericMdParser.
"""

import argparse
import csv
import io
import logging
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

__all__ = [
    "extract_vitt_recipes",
    "convert_vitt_to_markdown",
    "convert_vitt_csv_to_markdown",
    "main",
]


def to_title_case(text: str) -> str:
    """Intelligently convert ALL-CAPS text to Title Case."""
    if not text:
        return text

    if any(c.islower() for c in text):
        return text

    words = text.split()
    small_words = {"a", "an", "and", "or", "but", "in", "on", "at", "to", "for", "of", "the", "with", "by", "w"}

    result = []
    for i, word in enumerate(words):
        if i == 0 or i == len(words) - 1:
            result.append(word.capitalize())
        elif word.lower() in small_words and not result[-1].endswith("("):
            result.append(word.lower())
        else:
            result.append(word.capitalize())

    return " ".join(result)


def handle_line_continuations(txt: str) -> str:
    """Merge lines ending with an underscore (_) with the subsequent line."""
    lines = txt.split("\n")
    result = []
    i = 0
    while i < len(lines):
        line = lines[i]
        while i < len(lines) and line.rstrip().endswith("_"):
            line = line.rstrip()[:-1]
            if i + 1 < len(lines):
                line = line + lines[i + 1]
                i += 1
            else:
                break
        result.append(line)
        i += 1
    return "\n".join(result)


def _looks_like_introduction(block: str) -> bool:
    """Check if a text block contains introductory or conversational commentary."""
    lines = block.split("\n")
    if len(lines) == 1 and re.match(r"^[A-Za-z\s]+:\s*$", lines[0].strip()):
        return False

    intro_patterns = [
        r"^contributed",
        r"^(i |you |he |she |we |they |my |your |his |her |our |their )",
        r"(thank|appreciate|enjoyed|wonderful|delicious|great)",
        r"^CC>",
        r"^(.*?ph\.?s\.?.*?)$",
    ]
    for line in lines:
        line_lower = line.strip().lower()
        if line_lower and any(re.search(pat, line_lower) for pat in intro_patterns):
            return True
    return False


def _looks_like_title(block: str) -> bool:
    """Check if a block is a standalone recipe title."""
    lines = [l.strip() for l in block.split("\n") if l.strip()]
    if len(lines) != 1:
        return False
    line = lines[0].rstrip(":")
    if len(line) > 80 or len(line) < 3 or line.endswith((".", "?", "!")):
        return False
    instruction_verbs = r"\b(add|mix|stir|heat|cook|bake|pour|place|combine|blend|whisk|serve|slice|chop|boil)\b"
    if re.search(instruction_verbs, line.lower()):
        return False
    return any(c.isupper() for c in line) and any(c.islower() for c in line)


def _line_looks_like_ingredient(line: str) -> bool:
    """Check if a single line resembles an ingredient item or section header."""
    if not line or len(line) > 150:
        return False

    # Section header like "Crust:" or "Filling:"
    if re.match(r"^[a-zA-Z\s]+:\s*$", line):
        return True

    # Numbered instruction step
    if re.match(r"^\d+\.\s+", line):
        return False

    line_lower = line.lower()
    instruction_verbs = (
        r"\b(add|mix|stir|heat|cook|bake|pour|place|combine|blend|whisk|fold|"
        r"arrange|serve|slice|cut|dice|chop|peel|boil|fry|saut[eé]|simmer|grill|"
        r"roast|baste|marinate|season|sprinkle|drizzle|layer|spread|flip|turn|"
        r"reduce|thicken|strain|drain|reserve|save|garnish|top|dust)\b"
    )
    if re.search(instruction_verbs, line_lower):
        return False

    ingredient_starters = [
        r"^(?:1/2|1/3|1/4|2/3|3/4)\s",
        r"^\d+\.\d+\s",
        r"^\d+-\d+\s",
        r"^\d+\s+(?:cup|tsp|tbsp|oz|lb|ml|l|mg|g|pkg|package)",
        r"^(?:a|an|some|few|dash|pinch|splash|handful)\s",
        r"^(?:to\s+taste|optional|fresh|dried)",
    ]
    if any(re.search(pat, line_lower) for pat in ingredient_starters):
        return True

    if len(line) < 80 and not re.search(r"[.?!]\s*$|^[A-Z][a-z]+\s+(?:is|are|was|were|can|do|did|have|has)\b", line):
        return True

    return False


def _is_ingredient_block(block: str) -> bool:
    """Determine if a text block contains ingredients."""
    lines = [l.strip() for l in block.split("\n") if l.strip()]
    if not lines:
        return False

    if re.match(r"^[a-zA-Z\s]+:\s*$", lines[0]):
        return True

    ing_count = sum(1 for l in lines if _line_looks_like_ingredient(l))
    return (ing_count / len(lines)) > 0.5


def _categorize_blocks(txt: str) -> List[Tuple[str, str]]:
    """Classify blocks into introduction, title, ingredients, or instructions."""
    raw_blocks = re.split(r"\n\s*\n+", txt.replace("\u200d", ""))
    categorized = []
    seen_title = False
    seen_ingredients = False

    for b in raw_blocks:
        block = b.strip()
        if not block:
            continue

        if not seen_title and not seen_ingredients:
            if _looks_like_introduction(block):
                categorized.append((block, "intro"))
                continue
            if _looks_like_title(block):
                categorized.append((block, "title"))
                seen_title = True
                continue

        if _is_ingredient_block(block):
            categorized.append((block, "ingredients"))
            seen_ingredients = True
            continue

        categorized.append((block, "instructions"))

    return categorized


def extract_vitt_recipes(content: str) -> List[Dict[str, Any]]:
    """Extract structured recipe dictionaries from Vitt CSV content."""
    recipes: List[Dict[str, Any]] = []
    reader = csv.DictReader(io.StringIO(content))

    for row in reader:
        name = row.get("NAME", "").strip()
        if not name:
            continue

        title = to_title_case(name)
        categories_raw = row.get("KING", "").strip()
        categories = (
            [k.strip() for k in categories_raw.split("/") if k.strip() and k.upper() != "NULL"]
            if categories_raw
            else []
        )
        source = row.get("SOURCE", "").strip()

        txt = row.get("TXT", "").strip().replace("\u200d", "")
        txt = handle_line_continuations(txt)

        blocks = _categorize_blocks(txt)
        ingredients: List[str] = []
        instructions: List[str] = []

        for block_text, b_type in blocks:
            if b_type == "ingredients":
                for line in block_text.split("\n"):
                    cleaned = re.sub(r"\s+", " ", line.strip().replace("\u200d", ""))
                    if cleaned:
                        ingredients.append(cleaned)
            elif b_type == "instructions":
                cleaned = re.sub(r"\s+", " ", block_text.strip().replace("\u200d", ""))
                if cleaned:
                    instructions.append(cleaned)

        recipes.append({
            "title": title,
            "categories": categories,
            "source": source,
            "ingredients": ingredients,
            "instructions": instructions,
        })

    return recipes


def convert_vitt_to_markdown(content: str) -> str:
    """Convert Vitt CSV content into clean Generic Markdown."""
    recipes = extract_vitt_recipes(content)
    md_sections: List[str] = []

    for r in recipes:
        sec = [f"# {r['title']}\n"]
        if r["categories"]:
            sec.append(f"Category: {', '.join(r['categories'])}\n")
        if r["source"]:
            sec.append(f"Source: {r['source']}\n")

        if r["ingredients"]:
            sec.append("## Ingredients\n")
            for ing in r["ingredients"]:
                sec.append(f"- {ing}")
            sec.append("\n")

        if r["instructions"]:
            sec.append("## Instructions\n")
            for inst in r["instructions"]:
                sec.append(f"{inst}\n")

        md_sections.append("\n".join(sec))

    body = "\n\n----------------------------------------\n\n".join(md_sections)
    return f"<!-- format: generic_md -->\n\n{body}\n"


def convert_vitt_csv_to_markdown(input_path: Path, output_path: Path) -> int:
    """Read a Vitt CSV file and write clean Generic Markdown.

    Args:
        input_path: Path to the input CSV file.
        output_path: Path to the destination Markdown file.

    Returns:
        Number of recipes converted.
    """
    raw_bytes = input_path.read_bytes()
    content = ""
    for enc in ("utf-8", "cp1252", "latin-1"):
        try:
            content = raw_bytes.decode(enc)
            break
        except UnicodeDecodeError:
            continue
    if not content:
        content = raw_bytes.decode("utf-8", errors="replace")

    recipes = extract_vitt_recipes(content)
    md_text = convert_vitt_to_markdown(content)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(md_text, encoding="utf-8")
    return len(recipes)


def main() -> None:
    """CLI entrypoint for Vitt CSV extractor."""
    parser = argparse.ArgumentParser(
        description="Extract and normalize vintage Vitt Cooking Echo CSV dumps into Generic Markdown."
    )
    parser.add_argument("input", type=Path, help="Path to input vitt.csv file")
    parser.add_argument("output", type=Path, help="Path to output markdown file (.md)")
    args = parser.parse_args()

    if not args.input.exists():
        print(f"Error: input file {args.input} not found.", file=sys.stderr)
        sys.exit(1)

    count = convert_vitt_csv_to_markdown(args.input, args.output)
    print(f"Successfully converted {count} recipes from '{args.input}' to '{args.output}'.")


if __name__ == "__main__":
    main()
