# SPDX-License-Identifier: MIT
"""Extractor for VJJE e-cookbook PDF collection.

Processes native text PDFs (using pdftotext) and scanned/image PDFs
(using pdfimages + tesseract OCR), extracting recipes formatted for
GenericMdParser in convert.py.
"""

from __future__ import annotations

import argparse
import concurrent.futures
import logging
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
from typing import Any, Dict, Iterator, List, Optional, Tuple

logger = logging.getLogger("vjje_extract")

try:
    from tqdm import tqdm
except ImportError:
    def tqdm(iterable: Any, **kwargs: Any) -> Any:
        return iterable


# Promotional and boilerplate line patterns to strip from pages
PROMO_PATTERNS = [
    re.compile(r"^FREE Cookbooks!*", re.IGNORECASE),
    re.compile(r"Stop Searching,\s*Start Cooking!", re.IGNORECASE),
    re.compile(r"https?://(?:www\.)?e[−-]cookbooks\.net\b", re.IGNORECASE),
    re.compile(r"www\.e[−-]cookbooks\.net\b", re.IGNORECASE),
    re.compile(r"^Click Here\b", re.IGNORECASE),
    re.compile(r"^Click HERE\b", re.IGNORECASE),
    re.compile(r"^Subscribe to\b.*VJJE", re.IGNORECASE),
    re.compile(r"^VJJE Publishing Co\.", re.IGNORECASE),
    re.compile(r"^Copyright\s*©?.*VJJE", re.IGNORECASE),
    re.compile(r"Personalized Cooking Aprons", re.IGNORECASE),
    re.compile(r"Make a mess\s*[-−]\s*protect the dress!", re.IGNORECASE),
]

# Section headers indicating instructions/directions
INSTRUCTION_HEADER_RE = re.compile(
    r"^(?:preparation|directions|instructions|cooking|to prepare|to make|method|procedure)\b.*:?$",
    re.IGNORECASE,
)

# Line starts strongly indicative of an instruction step
INSTRUCTION_START_RE = re.compile(
    r"^(?:"
    r"\d+\s*[\.)]\s+|"  # Numbered step: 1. or 1)
    r"(?:in\s+an?\s+|meanwhile\b|transfer\b|combine\b|place\b|pour\b|mix\b|stir\b|whisk\b|"
    r"heat\b|cook\b|bake\b|pre-?heat\b|add\b|bring\b|boil\b|simmer\b|serve\b|drain\b|remove\b|beat\b|blend\b|"
    r"cut\b|chop\b|peel\b|roll\b|spread\b|melt\b|sprinkle\b|brown\b|cover\b|toss\b|fold\b|cool\b|chill\b|"
    r"refrigerate\b|divide\b|arrange\b|season\b|garnish\b|sift\b|using\s+|with\s+a\s+|to\s+make\b|"
    r"to\s+prepare\b|soften\b|to\s+serve\b|to\s+assemble\b|dissolve\b|marinate\b|rinse\b|sauté\b|saute\b|"
    r"make\s+the\s+|assemble\s+|get\s+out\s+|soak\s+|put\s+the\s+|grease\s+|pat\s+dry\b|"
    r"line\s+a\s+|set\s+aside\b|let\s+|allow\s+|layer\s+|in\s+a\s+|wash\b|skin\b|thaw\b)"
    r")",
    re.IGNORECASE,
)

# Common units and quantity patterns for ingredient lines
QUANTITY_START_RE = re.compile(
    r"^(?:[-*•·]\s*)?(?:"
    r"\d+(?:/\d+)?(?:\s*-\s*\d+(?:/\d+)?)?\s*|"
    r"[½¼¾⅓⅔⅛⅜⅝⅞]\s*|"
    r"(?:a|an|pinch|dash|few)\s+"
    r")(?:cups?|c\.|tbsp?\.?|tablespoons?|teaspoons?|tsp?\.?|lbs?\.?|pounds?|oz\.?|ounces?|grams?|g\b|kg\b|ml\b|cloves?|slices?|cans?|pkgs?\.?|packages?|heads?|stalks?|bunches?|bottles?|jars?|sticks?|envelopes?|drops?|pieces?|large|medium|small|whole)?\b",
    re.IGNORECASE,
)

YIELD_RE = re.compile(
    r"^(?:[-*•·]\s*)?(?:yield|yields|servings?|makes|serves)\s*:\s*(.*)$|"
    r"^\((?:yield|makes|serves)\s+(.*)\)$",
    re.IGNORECASE,
)


def clean_line_text(text: str) -> str:
    """Normalize common unicode characters and OCR artifacts in text."""
    s = text.replace("\xa0", " ")
    s = s.replace("−", "-").replace("—", "-").replace("–", "-")
    s = s.replace("“", '"').replace("”", '"').replace("‘", "'").replace("’", "'")
    return s.strip()


def is_non_recipe_page(lines: List[str]) -> bool:
    """Determine whether a page is non-recipe boilerplate (TOC, Intro, Apron promo, etc.)."""
    if len(lines) < 3:
        return True

    text_lower = " ".join(lines).lower()

    # Table of contents
    if "table of contents" in text_lower:
        return True

    # Check for dot leaders (TOC index pages)
    dots_count = sum(1 for line in lines if re.search(r"\.{3,}\s*\d+", line))
    if dots_count >= 3:
        return True

    first_line_clean = re.sub(r"[^a-z0-9 ]", "", lines[0].lower()).strip()
    if first_line_clean in {
        "introduction",
        "recipe index",
        "index",
        "welcome",
        "contents",
        "table of contents",
        "copyright",
    }:
        return True

    # Promotional / advertising pages
    if "personalized cooking aprons" in text_lower or (
        "cooking aprons" in text_lower and "click here" in text_lower
    ):
        return True

    if "the e-cookbooks library" in text_lower and len(lines) < 15:
        return True

    if "free recipes in your email" in text_lower:
        return True

    return False


def is_ingredient_line(line: str) -> bool:
    """Check if a line looks like an ingredient line."""
    s = line.strip()
    # Standalone numbers (e.g. page numbers) are not ingredients
    if re.match(r"^\d+$", s):
        return False
    # Strip bullets
    s_nobullet = re.sub(r"^[-*•·]\s*", "", s)

    # Starts with a quantity or unit
    if QUANTITY_START_RE.match(s_nobullet):
        return True

    # Common standalone ingredients without leading number (e.g. "Salt", "Pepper to taste", "Cooking oil")
    common_pantry = (
        r"^(?:salt|pepper|black pepper|white pepper|garlic powder|onion powder|"
        r"water|cooking oil|vegetable oil|olive oil|butter|sugar|flour)\b"
    )
    if re.match(common_pantry, s_nobullet, re.IGNORECASE):
        return True

    # Component subheadings like "Sauce:", "Glaze:", "Dipping Sauce:"
    if s.endswith(":") and len(s.split()) <= 4 and not INSTRUCTION_HEADER_RE.match(s):
        return True

    return False


def is_instruction_line(line: str) -> bool:
    """Check if a line looks like an instruction step."""
    s = line.strip()
    if INSTRUCTION_HEADER_RE.match(s):
        return True
    s_nobullet = re.sub(r"^[-*•·]\s*", "", s)
    if INSTRUCTION_START_RE.match(s_nobullet):
        return True
    return False


def strip_page_footer(lines: List[str], title: str) -> Tuple[List[str], Optional[str]]:
    """Strip promotional text, repeated bottom title, and page numbers from bottom of page.

    Returns:
        Tuple of (cleaned_lines, extracted_yield_or_none)
    """
    clean_lines = list(lines)
    extracted_yield = None

    norm_title = re.sub(r"[^a-z0-9]", "", title.lower())

    while clean_lines:
        last = clean_lines[-1].strip()
        if not last:
            clean_lines.pop()
            continue

        # Page number (e.g. "12", "iv")
        if re.match(r"^\d+$", last) or re.match(r"^[ivxldcm]+$", last, re.IGNORECASE):
            clean_lines.pop()
            continue

        # Promotional URL / ad lines
        if any(pat.search(last) for pat in PROMO_PATTERNS):
            clean_lines.pop()
            continue

        # Repeated title at bottom
        norm_last = re.sub(r"[^a-z0-9]", "", last.lower())
        if norm_last and (norm_last == norm_title or norm_last.startswith(norm_title[:15])):
            clean_lines.pop()
            continue

        # Yield line at bottom (e.g. "Yield: about 2 dozen")
        m_yield = YIELD_RE.match(last)
        if m_yield:
            extracted_yield = (m_yield.group(1) or m_yield.group(2)).strip()
            clean_lines.pop()
            continue

        break

    return clean_lines, extracted_yield


def parse_vjje_page(
    page_text: str, book_title: Optional[str] = None
) -> Optional[Dict[str, Any]]:
    """Parse a single page of text into structured recipe components.

    Args:
        page_text: Plain text of a single page.
        book_title: Optional book title to detect running header lines.

    Returns:
        Dictionary with recipe components or None if not a valid recipe page.
    """
    raw_lines = [clean_line_text(l) for l in page_text.splitlines()]
    lines = [l for l in raw_lines if l]

    if is_non_recipe_page(lines):
        return None

    # Detect if top line is a running book header
    start_idx = 0
    if book_title:
        norm_book = re.sub(r"[^a-z0-9]", "", book_title.lower())
        norm_first = re.sub(r"[^a-z0-9]", "", lines[0].lower())
        if norm_first == norm_book and len(lines) > 1:
            start_idx = 1

    if start_idx >= len(lines):
        return None

    # Check if page has any ingredients at all
    has_any_ingredients = any(is_ingredient_line(l) for l in lines[start_idx:])
    if not has_any_ingredients:
        # Continuation page of instructions with no ingredients
        clean_lines = list(lines[start_idx:])
        bottom_title = ""
        while clean_lines:
            last = clean_lines[-1]
            if re.match(r"^\d+$", last) or re.match(r"^[ivxldcm]+$", last, re.IGNORECASE):
                clean_lines.pop()
                continue
            if any(pat.search(last) for pat in PROMO_PATTERNS):
                clean_lines.pop()
                continue
            # If the last line is a title (short, no sentence-ending punctuation, not an instruction)
            if (
                len(last.split()) <= 10
                and not last.endswith((".", ";", ":", ","))
                and not is_instruction_line(last)
            ):
                bottom_title = clean_lines.pop()
                continue
            break

        if clean_lines:
            return {
                "title": bottom_title,
                "is_continuation": True,
                "raw_lines": clean_lines,
            }
        return None

    title = lines[start_idx]
    # Sanity check: title shouldn't look like an ingredient or instruction
    if is_ingredient_line(title) or is_instruction_line(title):
        return {
            "title": "",
            "is_continuation": True,
            "raw_lines": lines[start_idx:],
        }

    content_lines = lines[start_idx + 1 :]
    if not content_lines:
        return None

    # Strip footer elements (bottom title repeat, page numbers, ads)
    content_lines, footer_yield = strip_page_footer(content_lines, title)

    # Process metadata, ingredients, and instructions
    yield_amount = footer_yield or ""
    description_lines: List[str] = []
    ingredients: List[str] = []
    instructions: List[str] = []

    state = "PRE_INGREDIENTS"  # PRE_INGREDIENTS -> INGREDIENTS -> INSTRUCTIONS

    for line in content_lines:
        # Check for Yield line
        m_yield = YIELD_RE.match(line)
        if m_yield and not yield_amount:
            yield_amount = (m_yield.group(1) or m_yield.group(2)).strip()
            continue

        # Check for explicit instruction header
        if INSTRUCTION_HEADER_RE.match(line):
            state = "INSTRUCTIONS"
            continue

        if state == "PRE_INGREDIENTS":
            if is_ingredient_line(line):
                state = "INGREDIENTS"
                ingredients.append(line)
            elif is_instruction_line(line):
                state = "INSTRUCTIONS"
                instructions.append(line)
            else:
                # Short introductory sentence before ingredients
                description_lines.append(line)

        elif state == "INGREDIENTS":
            # Transition to instructions if line matches instruction cues or is not an ingredient
            if is_instruction_line(line) or not is_ingredient_line(line) or re.match(r"^\d+\s*[\.)]\s+", line):
                state = "INSTRUCTIONS"
                instructions.append(line)
            else:
                ingredients.append(line)

        elif state == "INSTRUCTIONS":
            instructions.append(line)

    # Recipes must have at least one ingredient and some instructions
    if not ingredients or not instructions:
        # Check if this could be a continuation of instructions
        if instructions and not ingredients:
            return {
                "title": title,
                "is_continuation": True,
                "raw_lines": instructions,
            }
        return None

    return {
        "title": title,
        "yield_amount": yield_amount,
        "description": " ".join(description_lines).strip(),
        "ingredients": ingredients,
        "instructions": instructions,
        "is_continuation": False,
    }


def parse_book_pages(
    pages: List[str], book_title: Optional[str] = None
) -> List[Dict[str, Any]]:
    """Parse all pages in a book, merging continuation pages into their preceding recipes."""
    recipes: List[Dict[str, Any]] = []

    for page_idx, page_str in enumerate(pages):
        parsed = parse_vjje_page(page_str, book_title=book_title)
        if not parsed:
            continue

        if parsed.get("is_continuation"):
            # Append instructions to the last active recipe
            if recipes:
                more_lines = parsed.get("raw_lines") or parsed.get("instructions") or []
                recipes[-1]["instructions"].extend(more_lines)
            continue

        recipes.append(parsed)

    return recipes


def format_recipes_markdown(recipes: List[Dict[str, Any]]) -> str:
    """Format extracted recipes into Generic Markdown format."""
    out: List[str] = ["<!-- format: generic_md -->\n"]

    for r in recipes:
        out.append(f"# {r['title']}\n")
        if r.get("description"):
            out.append(f"Description: {r['description']}\n")
        if r.get("yield_amount"):
            out.append(f"Servings: {r['yield_amount']}\n")

        out.append("## Ingredients\n")
        for ing in r["ingredients"]:
            clean_ing = re.sub(r"^[-*•·]\s*", "", ing).strip()
            if clean_ing.endswith(":") and len(clean_ing.split()) <= 4:
                out.append(f"\n{clean_ing}")
            else:
                out.append(f"- {clean_ing}")

        out.append("\n## Preparation\n")
        # Group instruction lines into coherent steps or paragraphs
        current_step: List[str] = []
        for line in r["instructions"]:
            m_step = re.match(r"^(\d+)\s*[\.)]\s+(.*)$", line)
            if m_step:
                if current_step:
                    out.append(" ".join(current_step) + "\n")
                    current_step.clear()
                out.append(f"{m_step.group(1)}. {m_step.group(2)}")
            elif line.endswith(":") and len(line.split()) <= 4:
                if current_step:
                    out.append(" ".join(current_step) + "\n")
                    current_step.clear()
                out.append(f"\n{line}\n")
            else:
                current_step.append(line)

        if current_step:
            out.append(" ".join(current_step) + "\n")

        out.append("----------------------------------------\n")

    return "\n".join(out)


_TESS_ENV = os.environ.copy()
_TESS_ENV["OMP_NUM_THREADS"] = "1"
_TESS_ENV["OMP_THREAD_LIMIT"] = "1"


def _ocr_single_image(img_path: str) -> str:
    """Run tesseract OCR on a single image file."""
    try:
        cmd = ["tesseract", img_path, "stdout", "--oem", "1", "-l", "eng"]
        res = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            check=True,
            text=True,
            env=_TESS_ENV,
        )
        return res.stdout
    except Exception as e:
        logger.warning("OCR failed on %s: %s", img_path, e)
        return ""


def extract_pdf_pages(
    pdf_path: Path, jobs: int = 4, no_ocr: bool = False, limit: Optional[int] = None
) -> List[str]:
    """Extract pages from a PDF.

    First tries pdftotext. If the PDF lacks a text stream (scanned/image PDF),
    extracts embedded page images using pdfimages and processes with tesseract.
    """
    # 1. Try pdftotext
    cmd = ["pdftotext", "-layout"]
    if limit and limit > 0:
        cmd.extend(["-f", "1", "-l", str(limit)])
    cmd.extend([str(pdf_path), "-"])

    try:
        res = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            check=True,
            text=True,
        )
        raw_text = res.stdout
    except Exception as e:
        logger.debug("pdftotext failed for %s: %s", pdf_path, e)
        raw_text = ""

    pages = [p for p in raw_text.split("\x0c")]
    non_empty_chars = sum(len(p.strip()) for p in pages)

    # If pdftotext extracted meaningful content (> 500 chars), treat as text PDF
    if non_empty_chars > 500:
        return pages

    if no_ocr:
        logger.info("Skipping image PDF (no-ocr flag set): %s", pdf_path.name)
        return []

    # 2. Scanned / image PDF: Extract images and OCR
    logger.info("Extracting images and running OCR for %s...", pdf_path.name)
    with tempfile.TemporaryDirectory() as td:
        img_prefix = os.path.join(td, "page")
        img_cmd = ["pdfimages"]
        if limit and limit > 0:
            img_cmd.extend(["-f", "1", "-l", str(limit)])
        img_cmd.extend(["-png", str(pdf_path), img_prefix])

        try:
            subprocess.run(
                img_cmd,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=True,
            )
        except Exception as e:
            logger.error("pdfimages failed for %s: %s", pdf_path, e)
            return []

        images = sorted(Path(td).glob("*.png"))
        if not images:
            logger.warning("No images found in PDF: %s", pdf_path)
            return []

        # Run OCR with ThreadPoolExecutor (I/O & subprocess bound)
        ocr_results: List[str] = []
        with concurrent.futures.ThreadPoolExecutor(max_workers=jobs) as executor:
            future_to_idx = {
                executor.submit(_ocr_single_image, str(img)): idx
                for idx, img in enumerate(images)
            }
            results_by_idx: Dict[int, str] = {}
            for future in concurrent.futures.as_completed(future_to_idx):
                idx = future_to_idx[future]
                results_by_idx[idx] = future.result()

            for idx in range(len(images)):
                ocr_results.append(results_by_idx.get(idx, ""))

        return ocr_results


def process_book(
    pdf_path: Path,
    output_dir: Path,
    jobs: int = 4,
    skip_existing: bool = False,
    no_ocr: bool = False,
    limit: Optional[int] = None,
) -> int:
    """Process a single PDF book and write its extracted markdown file.

    Returns:
        Number of recipes extracted.
    """
    output_filename = f"{pdf_path.stem}.md"
    out_file = output_dir / output_filename

    if skip_existing and out_file.exists():
        logger.info("Skipping existing output: %s", out_file.name)
        return 0

    pages = extract_pdf_pages(pdf_path, jobs=jobs, no_ocr=no_ocr, limit=limit)

    recipes = parse_book_pages(pages, book_title=pdf_path.stem)
    if not recipes:
        logger.warning("No recipes extracted from %s", pdf_path.name)
        return 0

    md_content = format_recipes_markdown(recipes)
    output_dir.mkdir(parents=True, exist_ok=True)
    out_file.write_text(md_content, encoding="utf-8")

    logger.info("Extracted %d recipes -> %s", len(recipes), out_file.name)
    return len(recipes)


def main() -> None:
    """CLI entry point for VJJE recipe extraction."""
    parser = argparse.ArgumentParser(
        description="Extract recipes from VJJE e-cookbook PDFs into Generic Markdown."
    )
    parser.add_argument(
        "-i",
        "--input",
        type=Path,
        default=Path("/home/alex/junk/Recipes/Dedupe/VJJE"),
        help="Input PDF file or directory containing VJJE PDFs (default: ~/junk/Recipes/Dedupe/VJJE).",
    )
    parser.add_argument(
        "-o",
        "--output-dir",
        type=Path,
        default=Path("./extracted_vjje"),
        help="Output directory for generated .md files (default: ./extracted_vjje).",
    )
    parser.add_argument(
        "-j",
        "--jobs",
        type=int,
        default=min(8, os.cpu_count() or 1),
        help="Number of worker threads for parallel OCR (default: CPU cores).",
    )
    parser.add_argument(
        "--skip-existing",
        action="store_true",
        help="Skip books that have already been extracted to output-dir.",
    )
    parser.add_argument(
        "--no-ocr",
        action="store_true",
        help="Skip OCR for scanned/image PDFs (only extract native text PDFs).",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Limit number of pages processed per book (useful for testing).",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Enable detailed logging.",
    )

    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%H:%M:%S",
    )

    # Check dependencies
    for tool in ("pdftotext", "pdfimages", "tesseract"):
        if not shutil.which(tool):
            if tool == "tesseract" and args.no_ocr:
                continue
            logger.error("Required tool '%s' is not found in PATH.", tool)
            sys.exit(1)

    input_path = args.input.expanduser().resolve()
    if not input_path.exists():
        logger.error("Input path does not exist: %s", input_path)
        sys.exit(1)

    if input_path.is_file():
        pdf_files = [input_path]
    else:
        pdf_files = sorted(input_path.rglob("*.pdf"))

    if not pdf_files:
        logger.error("No PDF files found in %s", input_path)
        sys.exit(1)

    print(f"Found {len(pdf_files)} PDF file(s) to process.")
    print(f"Output directory: {args.output_dir.resolve()}")
    print(f"Parallel OCR threads: {args.jobs}\n")

    total_recipes = 0
    total_books = 0

    for pdf in tqdm(pdf_files, desc="Extracting books"):
        count = process_book(
            pdf_path=pdf,
            output_dir=args.output_dir,
            jobs=args.jobs,
            skip_existing=args.skip_existing,
            no_ocr=args.no_ocr,
            limit=args.limit,
        )
        if count > 0:
            total_recipes += count
            total_books += 1

    print("\n" + "=" * 50)
    print(f"Extraction complete!")
    print(f"Successfully processed {total_books} books.")
    print(f"Total recipes extracted: {total_recipes}")
    print(f"Files written to: {args.output_dir.resolve()}")
    print("=" * 50)
    print("\nTo convert extracted recipes to Schema.org JSON-LD, run:")
    print(f"./venv/bin/cook {args.output_dir} -o converted_vjje/ -r\n")


if __name__ == "__main__":
    main()
