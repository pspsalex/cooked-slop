# SPDX-License-Identifier: MIT
"""Generic Markdown recipe parser for converted DOCX/MD files."""

import logging
import re
from pathlib import Path
from typing import Iterator, Optional

from .base import BaseRecipeParser, BaseIngredientParser
from .models import Recipe, Ingredient
from .registry import ParserRegistry

logger = logging.getLogger(__name__)


@ParserRegistry.register
class GenericMdParser(BaseRecipeParser):
    """Parser for generic Markdown recipes (e.g. converted from DOCX).

    Expected layout:
    - Title on first non-empty row (plain text, # heading, or **bold**).
    - Irrelevant preamble (text, images, links).
    - Section header for Ingredients (e.g. "Ingredients:", "## Ingredients").
    - Ingredients list (one per line, optional empty lines or bullet points).
    - Section header for Preparation / Directions (e.g. "Preparation:", "Directions:").
    - Preparation steps until end of file / recipe separator.
    - Multiple recipes per file separated by at least 12 dashes (--------------------).
    """

    def __init__(self, ingredient_parser: BaseIngredientParser):
        super().__init__(ingredient_parser)
        self.source_format = "Generic Markdown"

    @classmethod
    def format_id(cls) -> str:
        return "generic_md"

    @classmethod
    def aliases(cls) -> list[str]:
        return ["generic-md", "genericmd", "md_generic"]

    @classmethod
    def priority(cls) -> int:
        return 25

    @classmethod
    def supported_extensions(cls) -> set[str]:
        return {'.md'}

    @classmethod
    def detect(cls, filepath: str, content_sample: str) -> float:
        if not content_sample or not content_sample.strip():
            return 0.0

        # Check for explicit format tag anywhere in content (e.g., at the end of file)
        if re.search(
            r"(?i)(?:\[format:\s*generic[-_]?md\]|<!--\s*format:\s*generic[-_]?md\s*-->|#generic[-_]?md|\bgeneric[-_]?md\b)",
            content_sample,
        ):
            return 1.0

        has_ingredients = bool(
            re.search(
                r"(?i)^\s*(?:#+\s*)?(?:\*{1,3}|_)?ingredients:?",
                content_sample,
                re.MULTILINE,
            )
        )
        has_instructions = bool(
            re.search(
                r"(?i)^\s*(?:#+\s*)?(?:\*{1,3}|_)?(?:preparation|directions|instructions|method|steps):?",
                content_sample,
                re.MULTILINE,
            )
        )

        ext = Path(filepath).suffix.lower()
        if has_ingredients and has_instructions:
            if ext in {".md", ".markdown"}:
                return 0.85
            return 0.50
        elif has_ingredients and ext in {".md", ".markdown"}:
            return 0.60

        if ext in {".md", ".markdown"}:
            # Check for grid or pipe tables
            if re.search(r"^\+[-+=:]+\+$", content_sample, re.MULTILINE) or re.search(
                r"^\s*\|.*\|\s*$", content_sample, re.MULTILINE
            ):
                return 0.80

            # Check for recipe indicators: quantities, cooking verbs, or timing
            has_quantities = bool(
                re.search(
                    r"(?i)\b\d+(?:/\d+)?\s*(?:cups?|tbsp?\.?|tsp?\.?|tablespoons?|teaspoons?|lbs?\.?|pounds?|oz\.?|ounces?|grams?|g|kg|ml)\b",
                    content_sample,
                )
            )
            has_cooking_terms = bool(
                re.search(
                    r"(?i)\b(?:skillet|saucepan|preheat|bake|cook|stir|whisk|boil|simmer|servings?|makes)\b",
                    content_sample,
                )
            )
            if has_quantities and has_cooking_terms:
                return 0.75
            if has_quantities or has_cooking_terms:
                return 0.55
            return 0.30

        return 0.0

    def _clean_title(self, raw_title: str) -> str:
        """Clean markdown markers from title line."""
        title = raw_title.strip()
        # Remove leading Markdown headings (# Title, ## Title)
        title = re.sub(r"^#+\s*", "", title)
        # Unescape quotes
        title = title.replace(r"\'", "'").replace(r'\"', '"')
        # Remove trailing backslash if present (from Pandoc hard line breaks)
        title = title.rstrip("\\").strip()
        # Remove outer bold/italic markup (**Title**, *Title*, ___Title___)
        title = re.sub(r"^(?:\*{1,3}|_{1,3})(.*?)(?:\*{1,3}|_{1,3})$", r"\1", title.strip())
        return title.strip()

    def _clean_line(self, line: str) -> str:
        """Clean list markers, backslashes, and bullet formatting from line."""
        text = line.strip()
        text = text.replace(r"\'", "'").replace(r'\"', '"')
        text = text.rstrip("\\").strip()
        # Remove bullet points or step numbers (- , * , + , 1. , 2) , • , · )
        text = re.sub(r"^(?:[-*+•·]|\d+[.)])\s+", "", text)
        return text.strip(" -*")

    def _is_ingredients_header(self, line: str) -> bool:
        cleaned = re.sub(r"[^a-zA-Z:]", "", line).lower().rstrip(":")
        return cleaned in {"ingredients", "ingredient"}

    def _is_instructions_header(self, line: str) -> bool:
        cleaned = re.sub(r"[^a-zA-Z:]", "", line).lower().rstrip(":")
        targets = {"preparation", "directions", "instructions", "method", "steps", "procedure"}
        return cleaned in targets

    def _looks_like_instruction_start(self, stripped: str) -> bool:
        """Detect whether a line is likely the start of an instruction step/paragraph."""
        if re.match(r"^\d+[.)]\s+", stripped):
            return True
        instruction_verbs = (
            r"(?i)^(?:in\s+an?\s+|meanwhile|transfer|combine|place|pour|mix|stir|whisk|"
            r"heat|cook|bake|preheat|add|bring|boil|simmer|serve|drain|remove|beat|blend|"
            r"cut|chop|peel|roll|spread|melt|sprinkle|brown|cover|toss|fold|cool|chill|"
            r"refrigerate|divide|arrange|season|garnish|sift|using\s+|with\s+a\s+|to\s+make|"
            r"make\s+the\s+|assemble\s+|get\s+out\s+|soak\s+|put\s+the\s+|grease\s+|"
            r"line\s+a\s+|set\s+aside|let\s+|allow\s+|layer\s+|in\s+a\s+)"
        )
        if re.match(instruction_verbs, stripped):
            return True

        # Narrative cooking sentences without bullet or quantity start
        is_qty_start = bool(
            re.match(
                r"^(?:[-*+•·]\s+|\d+[.)]\s+|\d+(?:/\d+)?(?:\s*-\s*\d+(?:/\d+)?)?\s+(?:[a-zA-Z]|½|¼|¾|⅓|⅔|⅛|⅜|⅝|⅞)|[½¼¾⅓⅔⅛⅜⅝⅞]|(?:a|an|some|few|pinch|dash)\s+)",
                stripped,
            )
        )
        if len(stripped) > 60 and not is_qty_start:
            cooking_keywords = [
                "skillet", "saucepan", "bowl", "oven", "minutes", "hours",
                "heat", "degrees", "bake", "cook", "stir"
            ]
            if any(term in stripped.lower() for term in cooking_keywords):
                return True
        return False

    def parse_content(self, content: str, filepath: str = "") -> Iterator[Recipe]:
        # Pre-process any ASCII/Markdown grid tables into unrolled linear text
        clean_content = unroll_markdown_tables(content)
        raw_lines = clean_content.splitlines()

        lines = []
        for l in raw_lines:
            s = l.strip()
            # Ignore explicit format tag lines
            if re.match(r"(?i)^\s*(?:\[format:|<!--\s*format:|#generic[-_]?md)", s):
                continue
            lines.append(l)

        current_recipe: Optional[Recipe] = None
        state = "PREAMBLE"  # PREAMBLE -> INGREDIENTS -> INSTRUCTIONS
        current_instruction_step: list[str] = []
        last_section_header: Optional[str] = None

        def flush_instruction(rec: Optional[Recipe]):
            if current_instruction_step and rec:
                step_text = " ".join(current_instruction_step).strip()
                if step_text:
                    m_yield = re.search(
                        r"(?i)\b(?:makes|yields?|serves)\s+(\d+[^.\n]+)(?:\.|$)", step_text
                    )
                    if m_yield and not rec.yield_amount:
                        rec.yield_amount = m_yield.group(1).strip()
                    rec.instructions.append(step_text)
                current_instruction_step.clear()

        def flush_recipe() -> Optional[Recipe]:
            nonlocal current_recipe, state, last_section_header
            finished_recipe = None
            if current_recipe:
                flush_instruction(current_recipe)
                if current_recipe.title and (
                    current_recipe.ingredients or current_recipe.instructions
                ):
                    finished_recipe = current_recipe
                current_recipe = None
                state = "PREAMBLE"
                last_section_header = None
            return finished_recipe

        def start_new_recipe(title_line: str):
            nonlocal current_recipe, state, last_section_header
            current_recipe = Recipe(
                title=self._clean_title(title_line),
                source_format=self.source_format,
                source_file=filepath,
            )
            state = "PREAMBLE"
            last_section_header = None

        idx = 0
        while idx < len(lines):
            line = lines[idx]
            stripped = line.strip()

            if not stripped:
                if state == "INSTRUCTIONS":
                    flush_instruction(current_recipe)
                idx += 1
                continue

            # Check if this line is a multi-recipe separator
            is_dash_sep = bool(
                re.match(r"^-{12,}$", stripped) or re.match(r"^={12,}$", stripped)
            )
            is_md_header = bool(re.match(r"^#{1,2}\s+", stripped))

            if is_dash_sep or (
                is_md_header
                and current_recipe
                and (current_recipe.ingredients or current_recipe.instructions)
            ):
                # If we just saw a section header (e.g. boxed header in Pandoc Markdown), skip it
                if last_section_header is not None and is_dash_sep:
                    last_section_header = None
                    idx += 1
                    continue

                # Look ahead to next non-empty line
                next_idx = idx + 1
                while next_idx < len(lines) and not lines[next_idx].strip():
                    next_idx += 1

                next_line = lines[next_idx].strip() if next_idx < len(lines) else ""

                # If next line is a section header, it's NOT a recipe separator
                if (
                    self._is_ingredients_header(next_line)
                    or self._is_instructions_header(next_line)
                    or re.match(
                        r"(?i)^\*{1,3}(?:ingredients|instructions|directions|preparation|special notes|notes)",
                        next_line,
                    )
                ):
                    idx += 1
                    continue

                # If separator is followed by an instruction step while we are in instructions, skip
                if state == "INSTRUCTIONS" and is_dash_sep and not is_md_header:
                    if self._looks_like_instruction_start(next_line):
                        idx += 1
                        continue

                # Otherwise, if we have an existing recipe with content, finish it!
                if current_recipe and (
                    current_recipe.ingredients or current_recipe.instructions
                ):
                    r = flush_recipe()
                    if r:
                        yield r
                    if is_dash_sep:
                        idx = next_idx
                        if idx < len(lines):
                            start_new_recipe(lines[idx])
                            idx += 1
                        continue
                    else:
                        start_new_recipe(stripped)
                        idx += 1
                        continue

            if current_recipe is None:
                if (
                    not is_dash_sep
                    and not re.match(r"^-{3,}$", stripped)
                    and stripped not in {"--", "."}
                ):
                    start_new_recipe(stripped)
                idx += 1
                continue

            # Section header checks
            if self._is_ingredients_header(stripped):
                flush_instruction(current_recipe)
                state = "INGREDIENTS"
                last_section_header = "INGREDIENTS"
                idx += 1
                continue
            elif self._is_instructions_header(stripped):
                flush_instruction(current_recipe)
                state = "INSTRUCTIONS"
                last_section_header = "INSTRUCTIONS"
                idx += 1
                continue
            elif re.match(r"(?i)^\*{1,3}(?:special notes|notes)\*{1,3}$", stripped):
                last_section_header = "NOTES"
                idx += 1
                continue

            last_section_header = None

            if state == "PREAMBLE":
                # Metadata checks
                m_yield = re.match(
                    r"(?i)^\s*(?:\*{1,3}|_*)?(?:yield|yields|servings|serves|makes):\*?\s*(.+)$",
                    stripped,
                )
                if m_yield:
                    current_recipe.yield_amount = m_yield.group(1).rstrip("-* ").strip()
                    idx += 1
                    continue
                m_kv_serv = re.match(r"(?i)^servings\s*(?:\||:)\s*(.+)$", stripped)
                if m_kv_serv:
                    current_recipe.yield_amount = m_kv_serv.group(1).rstrip("-* ").strip()
                    idx += 1
                    continue
                m_cat = re.match(
                    r"(?i)^\s*(?:\*{1,3}|_*)?(?:categories|category|tags|keywords|course):\*?\s*(.+)$",
                    stripped,
                )
                if m_cat:
                    cats = [c.strip() for c in m_cat.group(1).split(",") if c.strip()]
                    current_recipe.categories.extend(cats)
                    idx += 1
                    continue
                m_desc = re.match(
                    r"(?i)^\s*(?:\*{1,3}|_*)?(?:description|summary):\*?\s*(.+)$", stripped
                )
                if m_desc:
                    current_recipe.description = m_desc.group(1).strip()
                    idx += 1
                    continue
                m_time = re.match(
                    r"(?i)^\s*(?:\*{1,3}|_*)?(?:prep|cook|baking|bake|total)(?:\s+time)?:\*?\s*(.+)$",
                    stripped,
                )
                if m_time:
                    idx += 1
                    continue

                # Auto-transition to INGREDIENTS or INSTRUCTIONS
                is_bullet_or_qty = bool(
                    re.match(
                        r"^(?:[-*+•·]\s+|\d+[.)]\s+|\d+(?:/\d+)?(?:\s*-\s*\d+(?:/\d+)?)?\s+(?:[a-zA-Z]|½|¼|¾|⅓|⅔|⅛|⅜|⅝|⅞)|[½¼¾⅓⅔⅛⅜⅝⅞]|(?:a|an|some|few|pinch|dash)\s+)",
                        stripped,
                    )
                )
                if is_bullet_or_qty:
                    state = "INGREDIENTS"
                    # fall through to INGREDIENTS handling below
                elif self._looks_like_instruction_start(stripped):
                    state = "INSTRUCTIONS"
                    # fall through to INSTRUCTIONS handling below
                else:
                    if not current_recipe.description:
                        clean_desc = stripped.strip("*_ \t").strip()
                        if (
                            clean_desc
                            and not clean_desc.startswith("![")
                            and not clean_desc.startswith("--")
                        ):
                            current_recipe.description = clean_desc
                    idx += 1
                    continue

            if state == "INGREDIENTS":
                m_time = re.match(
                    r"(?i)^\s*(?:\*{1,3}|_*)?(?:prep|cook|baking|bake|total)(?:\s+time)?:\*?\s*(.+)$",
                    stripped,
                )
                if m_time:
                    idx += 1
                    continue

                if current_recipe.ingredients and self._looks_like_instruction_start(stripped):
                    flush_instruction(current_recipe)
                    state = "INSTRUCTIONS"
                    # fall through to INSTRUCTIONS below
                else:
                    ing_text = self._clean_line(stripped.replace("--", "-"))
                    ing_text = re.sub(r"^#+\s*", "", ing_text)
                    if ing_text and ing_text != "." and not re.match(r"^-{3,}$", ing_text):
                        current_recipe.ingredients.append(
                            self.ingredient_parser.parse(ing_text)
                        )
                    idx += 1
                    continue

            if state == "INSTRUCTIONS":
                # Check for nutrition lines
                if re.match(
                    r"(?i)^\s*(?:\*{1,3}|_*)?(?:per serving|nutrition|nutritional information|dietary exchanges|calories):",
                    stripped,
                ):
                    idx += 1
                    continue

                is_new_list_item = bool(re.match(r"^(?:[-*+•·]|\d+[.)]|#+)\s+", stripped))
                if is_new_list_item and current_instruction_step:
                    flush_instruction(current_recipe)

                inst_text = self._clean_line(stripped)
                inst_text = re.sub(r"^#+\s*", "", inst_text)
                if inst_text and not re.match(r"^-{3,}$", inst_text):
                    current_instruction_step.append(inst_text)
                idx += 1
                continue

        r = flush_recipe()
        if r:
            yield r


def _clean_cell_line(cl: str) -> tuple[str, bool]:
    s = cl.strip()
    had_break = s.endswith("\\")
    if had_break:
        s = s.rstrip("\\").strip()
    return s, had_break


def _is_item_boundary(prev_had_break: bool, prev_empty: bool, cl: str) -> bool:
    if prev_had_break or prev_empty:
        return True
    if re.match(r"^(?:\*{1,3}|_{1,3})", cl):
        return True
    if re.match(r"^(?:[-*+•·]|\d+[.)])\s+", cl):
        return True
    return False


def _extract_col_items(cell_lines: list[str]) -> list[str]:
    items = []
    current = []
    prev_had_break = False
    prev_empty = False
    for cl_raw in cell_lines:
        cl, had_break = _clean_cell_line(cl_raw)
        if not cl or cl == "." or cl == "\xa0":
            if current:
                items.append(" ".join(current).strip())
                current = []
            prev_had_break = False
            prev_empty = True
            continue
        if current and _is_item_boundary(prev_had_break, prev_empty, cl):
            items.append(" ".join(current).strip())
            current = []
        current.append(cl)
        prev_had_break = had_break
        prev_empty = False
    if current:
        items.append(" ".join(current).strip())
    cleaned = []
    for it in items:
        unbold = re.sub(r"^(?:\*{1,3}|_{1,3})(.*?)(?:\*{1,3}|_{1,3})$", r"\1", it).strip()
        unbold = re.sub(r"\s*-{4,}\s*$", "", unbold).strip()
        if unbold and not re.match(r"^-{3,}$", unbold) and unbold not in {"--", "."}:
            cleaned.append(unbold)
    return cleaned


def _process_grid_table_rows(table_rows: list[list[str]]) -> list[str]:
    res = []
    for row in table_rows:
        col_cells: dict[int, list[str]] = {}
        for line in row:
            parts = line.split("|")
            if len(parts) >= 3:
                cols = parts[1:-1]
                for c_idx, cell in enumerate(cols):
                    col_cells.setdefault(c_idx, []).append(cell)

        col_items = {
            c_idx: _extract_col_items(col_cells[c_idx]) for c_idx in sorted(col_cells.keys())
        }
        non_empty_cols = [c_idx for c_idx in sorted(col_items.keys()) if col_items[c_idx]]

        # Check if 2-column layout with Qty | Ingredient Name (e.g. Emeril)
        if len(non_empty_cols) == 2:
            c0_items = col_items[non_empty_cols[0]]
            c1_items = col_items[non_empty_cols[1]]
            if len(c0_items) == 1 and len(c1_items) == 1:
                t0 = c0_items[0]
                t1 = c1_items[0]
                if re.match(r"^(?:\d|[½¼¾⅓⅔⅛⅜⅝⅞]|one|two)", t0, re.IGNORECASE) and not re.match(
                    r"^(?:\d|[½¼¾⅓⅔⅛⅜⅝⅞])", t1
                ):
                    if len(t0.split()) <= 7 and not any(
                        v in t0.lower() for v in ["cook", "bake", "heat", "skillet"]
                    ):
                        res.append(f"{t0} {t1}")
                        res.append("")
                        continue

        for c_idx in sorted(col_items.keys()):
            for it in col_items[c_idx]:
                res.append(it)
                res.append("")
    return res


def unroll_markdown_tables(text: str) -> str:
    """Pre-processes text to unroll ASCII grid tables (+---+, +===+) and pipe tables into linear text."""
    lines = text.splitlines()
    out = []
    table_border_re = re.compile(r"^\+[-+=:]+\+$")
    in_grid_table = False
    table_rows = []
    current_row = []
    i = 0
    while i < len(lines):
        line = lines[i]
        stripped = line.strip()
        if table_border_re.match(stripped):
            if not in_grid_table:
                in_grid_table = True
                current_row = []
            else:
                if current_row:
                    table_rows.append(current_row)
                    current_row = []
            i += 1
            continue
        if in_grid_table:
            if stripped.startswith("|"):
                current_row.append(line)
                i += 1
                continue
            else:
                if current_row:
                    table_rows.append(current_row)
                    current_row = []
                out.extend(_process_grid_table_rows(table_rows))
                table_rows = []
                in_grid_table = False
                out.append(line)
                i += 1
                continue
        else:
            out.append(line)
            i += 1
    if in_grid_table and (table_rows or current_row):
        if current_row:
            table_rows.append(current_row)
        out.extend(_process_grid_table_rows(table_rows))
    return "\n".join(out)
