# SPDX-License-Identifier: MIT
"""Extractor and normalizer for Recipe Box printer dump files (.PRN).

Converts legacy Recipe Box print files into generic markdown format
compatible with GenericMdParser.
"""

import argparse
import logging
from pathlib import Path
import re
import sys

logger = logging.getLogger(__name__)


def convert_recipe_box_text(content: str) -> str:
    """Convert Recipe Box printer text into Generic Markdown recipe format.

    Args:
        content: Raw string content of the Recipe Box print file.

    Returns:
        Formatted markdown string containing all extracted recipes.
    """
    # 1. Remove page headers and form feed characters
    cleaned = re.sub(
        r"\x0c?[ \t]*={20,}\r?\n[ \t]*Recipe Box[^\n]*\r?\n[ \t]*={20,}\r?\n?",
        "",
        content,
    )

    # 2. Split into recipes by 'Recipe Name :'
    parts = re.split(r"^[ \t]*Recipe Name\s*:\s*", cleaned, flags=re.MULTILINE)

    md_out: list[str] = ["<!-- format: generic_md -->\n"]

    for p in parts[1:]:
        lines = p.splitlines()
        if not lines:
            continue
        title = lines[0].strip()
        if not title:
            continue

        ing_match = re.search(r"^[ \t]*Ingredients\b", p, re.MULTILINE | re.IGNORECASE)
        prep_match = re.search(r"^[ \t]*Preparation\b", p, re.MULTILINE | re.IGNORECASE)

        if not ing_match or not prep_match:
            continue

        header_block = p[: ing_match.start()]
        ing_block = p[ing_match.end() : prep_match.start()]
        prep_block = p[prep_match.end() :]

        # Metadata
        m_desc = re.search(r"Description\s*:\s*(.*)", header_block)
        desc = m_desc.group(1).strip() if m_desc else ""

        m_serv = re.search(r"Servings\s*:\s*(.*)", header_block)
        serv = m_serv.group(1).strip() if m_serv else ""

        categories: list[str] = []
        m_cat = re.search(r"Category\s*:\s*(.*)", header_block)
        if m_cat:
            cat_text = header_block[m_cat.start() :]
            first_cat = m_cat.group(1).strip()
            if first_cat:
                categories.append(first_cat)
            for l in cat_text.splitlines()[1:]:
                s = l.strip()
                if s and not s.lower().startswith("ingredients"):
                    categories.append(s)

        ingredients = [l.strip() for l in ing_block.splitlines() if l.strip()]

        # Instruction paragraphs
        prep_paragraphs = [
            re.sub(r"\s+", " ", para.strip())
            for para in re.split(r"\n\s*\n", prep_block)
            if para.strip()
        ]

        md_out.append(f"# {title}\n")
        if desc:
            md_out.append(f"Description: {desc}")
        if serv:
            md_out.append(f"Servings: {serv}")
        if categories:
            md_out.append(f"Categories: {', '.join(categories)}")
        md_out.append("\n## Ingredients\n")
        for ing in ingredients:
            md_out.append(ing)
        md_out.append("\n## Preparation\n")
        for para in prep_paragraphs:
            md_out.append(para + "\n")
        md_out.append("----------------------------------------\n")

    return "\n".join(md_out)


def main() -> None:
    """CLI entrypoint for converting Recipe Box files to markdown."""
    parser = argparse.ArgumentParser(
        description="Convert Recipe Box print files (.PRN) to Generic Markdown recipes."
    )
    parser.add_argument("input_file", type=Path, help="Path to input Recipe Box file (.PRN)")
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        default=None,
        help="Path to output markdown file (default: input file with .md extension)",
    )
    parser.add_argument(
        "--in-place",
        action="store_true",
        help="Overwrite the input file in-place with the markdown format",
    )
    args = parser.parse_args()

    input_path = args.input_file
    if not input_path.exists():
        print(f"Error: File not found: {input_path}", file=sys.stderr)
        sys.exit(1)

    output_path = input_path if args.in_place else (args.output or input_path.with_suffix(".md"))

    content = input_path.read_text(encoding="utf-8", errors="ignore")
    md_content = convert_recipe_box_text(content)

    output_path.write_text(md_content, encoding="utf-8")
    print(f"Successfully converted {input_path} -> {output_path}")


if __name__ == "__main__":
    main()
