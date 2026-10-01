# SPDX-License-Identifier: MIT
"""Extractor and normalizer for vintage printer dump recipe files (.PRN, .prn.txt).

Normalizes legacy printer report dumps (containing PCL printer escape codes,
form feeds, ASCII box-drawing borders, and running headers) into clean
Generic Markdown format tagged with <!-- format: generic_md -->.

Supports:
1. MasterCook print dumps (e.g. holiday.prn)
2. Form-feed labelled reports (e.g. cb_100.prn)
3. Recipe card box printouts (e.g. mmm150.prn.txt)
4. Classic recipe printouts (e.g. prcb.prn)
5. Asterisk banner dumps (e.g. tcs.prn)
"""

import argparse
import logging
from pathlib import Path
import re
import sys
from typing import List, Optional

logger = logging.getLogger(__name__)

__all__ = [
    "strip_pcl_escapes",
    "detect_prn_format",
    "normalize_prn",
    "normalize_mastercook_dump",
    "normalize_formfeed_dump",
    "normalize_boxed_card_dump",
    "normalize_recipe_printout_dump",
    "normalize_asterisk_banner_dump",
    "main",
]

# Regex pattern matching PCL escape codes
PCL_ESCAPE_PATTERN = re.compile(
    r"\x1b(?:"
    r"&[a-zA-Z0-9.]+"
    r"|\([a-zA-Z][0-9.]*[a-zA-Z]?"
    r"|\([0-9]+[a-zA-Z]?"
    r"|\([^\w\s]"
    r"|[a-zA-Z0-9=]"
    r")"
)


def strip_pcl_escapes(content: str) -> str:
    """Remove PCL escape sequences from raw printer dump text.

    Args:
        content: Raw text possibly containing escape sequences.

    Returns:
        Cleaned text with PCL escape codes stripped.
    """
    return PCL_ESCAPE_PATTERN.sub("", content)


def detect_prn_format(content: str) -> str:
    """Detect the specific vintage printer dump format.

    Args:
        content: Content string (raw or PCL-cleaned).

    Returns:
        One of 'boxed_card', 'recipe_printout', 'formfeed', 'mastercook',
        'asterisk_banner', or 'unknown'.
    """
    cleaned = strip_pcl_escapes(content)
    if "| CATEGORY:" in cleaned or re.search(r"\|={20,}\|={10,}\|", cleaned):
        return "boxed_card"
    if "Recipe Printout" in cleaned or (
        "Main Category--" in cleaned and re.search(r"Ingredient'?s?:", cleaned)
    ):
        return "recipe_printout"
    if "This recipe makes :" in cleaned or (
        "Ingredients :" in cleaned
        and "Instructions :" in cleaned
        and ("\x0c" in content or "See Also :" in cleaned)
    ):
        return "formfeed"
    if re.search(r"Serving Size\s*:", cleaned) and (
        re.search(r"Amount\s+Measure\s+Ingredient", cleaned)
        or "(C) Copyright" in cleaned
        or "Ingredient -- Preparation Method" in cleaned
    ):
        return "mastercook"
    if re.search(r"\*{20,}", cleaned):
        return "asterisk_banner"
    return "unknown"


def normalize_formfeed_dump(content: str) -> str:
    """Normalize form-feed delimited reports (e.g. cb_100.prn).

    Args:
        content: String content of the dump file.

    Returns:
        Generic Markdown string.
    """
    cleaned = strip_pcl_escapes(content)
    # Split by form-feed \x0c
    chunks = [c for c in cleaned.split("\x0c") if c.strip()]
    md_recipes: List[str] = []

    for chunk in chunks:
        lines = chunk.splitlines()
        title = ""
        yield_amount = ""
        ing_idx = -1
        inst_idx = -1
        see_also_idx = -1

        for i, l in enumerate(lines):
            s = l.strip()
            if (
                not title
                and s
                and not s.lower().startswith("this recipe")
                and not s.lower().startswith("estimated time")
            ):
                title = s
            if re.match(r"^This recipe makes\s*:\s*(.*)", s, re.IGNORECASE):
                m_yield = re.match(r"^This recipe makes\s*:\s*(.*)", s, re.IGNORECASE)
                if m_yield:
                    val = m_yield.group(1).strip()
                    if val:
                        yield_amount = val
                    elif i + 1 < len(lines):
                        next_s = lines[i + 1].strip()
                        if (
                            next_s
                            and not next_s.lower().startswith("estimated time")
                            and not next_s.lower().startswith("ingredients")
                        ):
                            yield_amount = next_s
            if re.match(r"^Ingredients\s*:\s*$", s, re.IGNORECASE):
                ing_idx = i
            if re.match(r"^Instructions\s*:\s*$", s, re.IGNORECASE):
                inst_idx = i
            if re.match(r"^See Also\s*:\s*$", s, re.IGNORECASE):
                see_also_idx = i

        if not title or ing_idx == -1 or inst_idx == -1:
            continue

        ing_lines = []
        for l in lines[ing_idx + 1 : inst_idx]:
            s = l.strip()
            if s and not s.lower().startswith("estimated time"):
                ing_lines.append(s)

        inst_end = see_also_idx if see_also_idx != -1 else len(lines)
        inst_raw = "\n".join(lines[inst_idx + 1 : inst_end])
        inst_paras = [
            p.strip().replace("\n", " ")
            for p in inst_raw.split("\n\n")
            if p.strip()
        ]

        md = [f"# {title}\n"]
        if yield_amount:
            md.append(f"Servings: {yield_amount}\n")
        md.append("## Ingredients\n")
        for ing in ing_lines:
            md.append(ing)
        md.append("\n## Instructions\n")
        for p in inst_paras:
            md.append(p + "\n")
        md_recipes.append("\n".join(md))

    return "<!-- format: generic_md -->\n\n" + "\n\n----------------------------------------\n\n".join(
        md_recipes
    )


def normalize_mastercook_dump(content: str) -> str:
    """Normalize MasterCook printer dumps (e.g. holiday.prn).

    Strips running headers, copyright notices, and page breaks.
    Splits recipes at 'Serving Size :' boundaries and formats into
    clean Generic Markdown.

    Args:
        content: String content of the dump file.

    Returns:
        Generic Markdown string.
    """
    cleaned = strip_pcl_escapes(content)
    # Strip running headers and page numbers
    cleaned = re.sub(
        r"^[ \t]*.*A Mardi Gras Cookbook.*\r?\n?", "", cleaned, flags=re.MULTILINE
    )
    cleaned = re.sub(
        r"^[ \t]*Page \d+[ \t]+.*\(C\) Copyright.*\r?\n?",
        "",
        cleaned,
        flags=re.MULTILINE,
    )
    cleaned = re.sub(
        r"^[ \t]*\d{1,2}/\d{1,2}/\d{2,4}[ \t]+Upgrade to our Complete Cookbook.*\r?\n?",
        "",
        cleaned,
        flags=re.MULTILINE,
    )
    cleaned = cleaned.replace("\x0c", "")

    parts = re.split(r"^[ \t]*Serving Size\s*:\s*", cleaned, flags=re.MULTILINE)
    md_recipes: List[str] = []

    for idx in range(1, len(parts)):
        preceding_text = parts[idx - 1]
        recipe_body = parts[idx]

        # Preceding text lines from bottom up give the title
        title = ""
        for l in reversed(preceding_text.splitlines()):
            s = l.strip().strip("-").strip()
            if s and not s.startswith("NOTES :") and not s.startswith("Page"):
                title = s
                break

        body_lines = recipe_body.splitlines()
        servings = body_lines[0].strip() if body_lines else ""
        ing_lines = []
        inst_lines = []
        notes = []

        state = "SEARCH_HEADER"
        for l in body_lines[1:]:
            s = l.strip()
            if re.search(r"Amount\s+Measure\s+Ingredient", s):
                state = "HEADER_LINE"
            elif state == "HEADER_LINE" and re.match(r"^-+\s+-+\s+-+", s):
                state = "INGREDIENTS"
            elif state == "INGREDIENTS":
                if not s or re.match(r"^-{3,}", s):
                    state = "INSTRUCTIONS"
                else:
                    ing_clean = re.sub(r"[ \t]+", " ", s).strip()
                    ing_lines.append(ing_clean)
            elif state == "INSTRUCTIONS":
                if re.match(r"^NOTES\s*:\s*(.*)", s, re.IGNORECASE):
                    state = "NOTES"
                    m = re.match(r"^NOTES\s*:\s*(.*)", s, re.IGNORECASE)
                    if m and m.group(1).strip():
                        notes.append(m.group(1).strip())
                elif re.match(r"^-\s+-\s+-\s+-\s+-\s+-", s) or re.match(
                    r"^-{5,}", s
                ):
                    continue
                elif s:
                    inst_lines.append(s)
            elif state == "NOTES":
                if s and not re.match(r"^-\s+-\s+-\s+-\s+-\s+-", s):
                    notes.append(s)

        if title and ing_lines:
            md = [f"# {title}\n"]
            if servings:
                md.append(f"Servings: {servings}\n")
            md.append("## Ingredients\n")
            for ing in ing_lines:
                md.append(ing)
            md.append("\n## Instructions\n")
            if inst_lines:
                md.append(" ".join(inst_lines) + "\n")
            if notes:
                md.append("\n" + " ".join(notes) + "\n")
            md_recipes.append("\n".join(md))

    return "<!-- format: generic_md -->\n\n" + "\n\n----------------------------------------\n\n".join(
        md_recipes
    )


def normalize_boxed_card_dump(content: str) -> str:
    """Normalize recipe card box printouts (e.g. mmm150.prn.txt).

    Parses ASCII table borders, categorizations, ingredient grids,
    and instructions.

    Args:
        content: String content of the dump file.

    Returns:
        Generic Markdown string.
    """
    cleaned = strip_pcl_escapes(content)
    lines = cleaned.splitlines()
    md_recipes: List[str] = []
    i = 0

    while i < len(lines):
        line = lines[i].strip()
        if re.match(r"^\|={20,}\|={10,}\|", line):
            # Title is line above this top border
            title = ""
            for j in range(i - 1, -1, -1):
                prev = lines[j].strip().strip("\x0c").strip()
                if not prev:
                    continue
                if prev.startswith("|") or re.match(
                    r"^[A-Z]{3}\s+\d{1,2},\s*\d{4}", prev
                ):
                    break
                title = prev
                break

            category = ""
            servings = ""
            i += 1
            if i < len(lines):
                cat_match = re.search(r"CATEGORY:\s*([^|]+)", lines[i])
                serv_match = re.search(r"SERVINGS:\s*([^|]+)", lines[i])
                if cat_match:
                    category = cat_match.group(1).strip()
                if serv_match:
                    servings = serv_match.group(1).strip()

            i += 1
            if i < len(lines) and re.match(r"^\|={20,}\|={10,}\|", lines[i].strip()):
                i += 1

            ing_lines = []
            while i < len(lines):
                row = lines[i].strip()
                if re.match(r"^\|={20,}\|?$", row):
                    i += 1
                    break
                cols = [c.strip() for c in row.strip("|").split("|")]
                for col in cols:
                    c_clean = re.sub(r"\s+", " ", col).strip()
                    if c_clean:
                        ing_lines.append(c_clean)
                i += 1

            inst_lines = []
            while i < len(lines):
                row = lines[i].strip()
                if re.match(r"^\|={20,}\|?$", row):
                    i += 1
                    break
                cols = [c.strip() for c in row.strip("|").split("|")]
                for col in cols:
                    c_clean = re.sub(r"\s+", " ", col).strip()
                    if c_clean:
                        inst_lines.append(c_clean)
                i += 1

            if title and ing_lines:
                md = [f"# {title}\n"]
                if category:
                    md.append(f"Categories: {category}")
                if servings:
                    md.append(f"Servings: {servings}")
                md.append("\n## Ingredients\n")
                for ing in ing_lines:
                    md.append(ing)
                md.append("\n## Instructions\n")
                if inst_lines:
                    md.append(" ".join(inst_lines) + "\n")
                md_recipes.append("\n".join(md))
        else:
            i += 1

    return "<!-- format: generic_md -->\n\n" + "\n\n----------------------------------------\n\n".join(
        md_recipes
    )


def normalize_recipe_printout_dump(content: str) -> str:
    """Normalize classic recipe printouts (e.g. prcb.prn).

    Splits at 'Recipe Printout' and extracts Main Category, Sub-Category,
    Recipe Name, tabular ingredients, and instructions.

    Args:
        content: String content of the dump file.

    Returns:
        Generic Markdown string.
    """
    cleaned = strip_pcl_escapes(content)
    chunks = re.split(r"Recipe Printout", cleaned)
    md_recipes: List[str] = []

    for chunk in chunks[1:]:
        m_main_cat = re.search(r"Main Category--[ \t]*([^\r\n]*)", chunk)
        m_sub_cat = re.search(r"Sub-Category---[ \t]*([^\r\n]*)", chunk)
        m_name = re.search(r"Recipe Name----[ \t]*([^\r\n]*)", chunk)

        main_cat = m_main_cat.group(1).strip() if m_main_cat else ""
        sub_cat = m_sub_cat.group(1).strip() if m_sub_cat else ""
        name = m_name.group(1).strip() if m_name else ""
        title = name or sub_cat or "Untitled"

        categories = [c for c in [main_cat, sub_cat] if c]

        ing_match = re.search(r"Ingredient'?s?:", chunk, re.IGNORECASE)
        rec_match = re.search(r"Recipe\s*:", chunk, re.IGNORECASE)

        if not ing_match or not rec_match:
            continue

        ing_block = chunk[ing_match.end() : rec_match.start()]
        m_src = re.search(r"Source of recipe:", ing_block, re.IGNORECASE)
        if m_src:
            ing_block = ing_block[: m_src.start()]

        ing_lines = []
        for l in ing_block.splitlines():
            if ">" in l:
                parts = l.split(">")
                for p in parts[1:]:
                    val = re.sub(r"\s+", " ", p).strip()
                    if val:
                        ing_lines.append(val)

        inst_block = chunk[rec_match.end() :]
        m_end = re.search(r"=+", inst_block)
        if m_end:
            inst_block = inst_block[: m_end.start()]

        inst_lines = [l.strip() for l in inst_block.splitlines() if l.strip()]

        if title and ing_lines:
            md = [f"# {title}\n"]
            if categories:
                md.append(f"Categories: {', '.join(categories)}")
            md.append("\n## Ingredients\n")
            for ing in ing_lines:
                md.append(ing)
            md.append("\n## Instructions\n")
            if inst_lines:
                md.append(" ".join(inst_lines) + "\n")
            md_recipes.append("\n".join(md))

    return "<!-- format: generic_md -->\n\n" + "\n\n----------------------------------------\n\n".join(
        md_recipes
    )


def normalize_asterisk_banner_dump(content: str) -> str:
    """Normalize asterisk banner dumps (e.g. tcs.prn, cakes-bakes.prn.txt).

    Args:
        content: String content of the dump file.

    Returns:
        Generic Markdown string.
    """
    cleaned = strip_pcl_escapes(content)
    chunks = re.split(r"\*{20,}", cleaned)
    md_recipes: List[str] = []

    for c in chunks:
        text = c.strip()
        if not text:
            continue
        lines = text.splitlines()
        title_lines = []
        rest_lines = []

        for i, l in enumerate(lines):
            s = l.strip()
            if not s:
                if title_lines:
                    rest_lines = lines[i + 1 :]
                    break
            else:
                title_lines.append(s)

        full_title = " ".join(title_lines)
        m_title = re.match(r"^(.*?)\s*-\s*compliments of", full_title, re.IGNORECASE)
        title = m_title.group(1).strip() if m_title else full_title

        ing_lines = []
        inst_lines = []
        state = "ING"

        for l in rest_lines:
            s = l.strip()
            if state == "ING":
                if not s:
                    if ing_lines:
                        state = "INST"
                else:
                    ing_lines.append(s)
            elif state == "INST":
                if s:
                    inst_lines.append(s)

        servings = ""
        clean_inst = []
        for l in inst_lines:
            m_s = re.match(r"^(?:Serves|Yields?)\s+(.*)", l, re.IGNORECASE)
            if m_s:
                servings = m_s.group(1).strip().rstrip(".")
            else:
                clean_inst.append(l)

        if title and ing_lines:
            md = [f"# {title}\n"]
            if servings:
                md.append(f"Servings: {servings}\n")
            md.append("## Ingredients\n")
            for ing in ing_lines:
                md.append(ing)
            md.append("\n## Instructions\n")
            if clean_inst:
                md.append(" ".join(clean_inst) + "\n")
            md_recipes.append("\n".join(md))

    return "<!-- format: generic_md -->\n\n" + "\n\n----------------------------------------\n\n".join(
        md_recipes
    )


def normalize_prn(content: str) -> str:
    """Normalize any supported PRN print dump text into Generic Markdown.

    Args:
        content: Raw PRN file content.

    Returns:
        Formatted markdown string starting with <!-- format: generic_md -->.
    """
    fmt = detect_prn_format(content)
    if fmt == "formfeed":
        return normalize_formfeed_dump(content)
    elif fmt == "mastercook":
        return normalize_mastercook_dump(content)
    elif fmt == "boxed_card":
        return normalize_boxed_card_dump(content)
    elif fmt == "recipe_printout":
        return normalize_recipe_printout_dump(content)
    elif fmt == "asterisk_banner":
        return normalize_asterisk_banner_dump(content)
    else:
        # Fallback to formfeed or PCL-stripped content
        cleaned = strip_pcl_escapes(content)
        if "\x0c" in content:
            return normalize_formfeed_dump(content)
        return "<!-- format: generic_md -->\n\n" + cleaned


def main(argv: Optional[List[str]] = None) -> None:
    """CLI entrypoint for PRN normalizer tool."""
    parser = argparse.ArgumentParser(
        description="Normalize vintage printer dump recipe files (.PRN, .prn.txt) to Generic Markdown."
    )
    parser.add_argument(
        "input_file",
        type=Path,
        help="Path to input PRN dump file (.PRN, .prn.txt)",
    )
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
    args = parser.parse_args(argv)

    input_path = args.input_file
    if not input_path.exists():
        print(f"Error: File not found: {input_path}", file=sys.stderr)
        sys.exit(1)

    output_path = (
        input_path
        if args.in_place
        else (args.output or input_path.with_suffix(".md"))
    )

    content = input_path.read_text(encoding="utf-8", errors="ignore")
    md_content = normalize_prn(content)

    output_path.write_text(md_content, encoding="utf-8")
    print(f"Successfully normalized {input_path} -> {output_path}")


if __name__ == "__main__":
    main()
