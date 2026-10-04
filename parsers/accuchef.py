# SPDX-License-Identifier: MIT
"""AccuChef recipe format parser."""
import logging
import re
from typing import Iterator, List, Optional, Tuple

from .base import BaseIngredientParser, BaseRecipeParser
from .models import Ingredient, Recipe
from .registry import ParserRegistry

logger = logging.getLogger(__name__)


@ParserRegistry.register
class AccuChefParser(BaseRecipeParser):
    """Parser for AccuChef v5.0 export/import format (.out, .ac, .txt)."""

    def __init__(self, ingredient_parser: BaseIngredientParser):
        super().__init__(ingredient_parser)
        self.source_format = "AccuChef"

    @classmethod
    def format_id(cls) -> str:
        """Unique lowercase identifier."""
        return "accuchef"

    @classmethod
    def priority(cls) -> int:
        """Detection order priority."""
        return 15

    @classmethod
    def supported_extensions(cls) -> set[str]:
        """Return set of lowercased file extensions handled by this parser."""
        return {".out", ".ac", ".txt"}

    @classmethod
    def detect(cls, filepath: str, content_sample: str) -> float:
        """Detect if content matches AccuChef format.

        Args:
            filepath: Path to the recipe file.
            content_sample: Sample text from the beginning of the file.

        Returns:
            Confidence score between 0.0 and 1.0.
        """
        if not content_sample:
            return 0.0
        if "*****AccuChef" in content_sample:
            return 0.99
        if re.search(r"^AA\s+.*?\n^[BDMH]\s*", content_sample, re.MULTILINE):
            return 0.85
        return 0.0

    def parse_content(self, content: str, filepath: str) -> Iterator[Recipe]:
        """Parse AccuChef content and yield Recipe instances.

        Args:
            content: Raw file content string.
            filepath: Original file path for source metadata.

        Yields:
            Recipe instances extracted from the content.
        """
        lines = content.splitlines()
        recipe: Optional[Recipe] = None
        yield_num = ""
        yield_label = ""
        j_lines: List[str] = []

        # Ingredient state
        pending_h = False
        h_qty: Optional[str] = None
        h_unit: Optional[str] = None
        curr_ing_qty: Optional[str] = None
        curr_ing_unit: Optional[str] = None
        curr_ing_name = ""
        curr_ing_comments: List[str] = []

        def flush_curr_ing() -> None:
            nonlocal curr_ing_name, curr_ing_qty, curr_ing_unit, curr_ing_comments
            if curr_ing_name and recipe:
                self._flush_ingredient(
                    curr_ing_qty,
                    curr_ing_unit,
                    curr_ing_name,
                    curr_ing_comments,
                    recipe,
                )
            curr_ing_name = ""
            curr_ing_qty = None
            curr_ing_unit = None
            curr_ing_comments = []

        def finalize_recipe() -> None:
            nonlocal yield_num, yield_label, j_lines
            if not recipe:
                return
            flush_curr_ing()
            if yield_num and yield_label:
                recipe.yield_amount = f"{yield_num} {yield_label}".strip()
            elif yield_num:
                recipe.yield_amount = yield_num
            elif yield_label:
                recipe.yield_amount = yield_label
            if j_lines:
                recipe.instructions = self._parse_instructions(j_lines)

        for line in lines:
            line_str = line.rstrip("\r\n")

            # Ignore file header comments / metadata lines starting with *****
            if line_str.startswith("*****"):
                continue

            # Recipe Title lines
            # In AccuChef, title lines start with 'AA ' or 'A'
            if line_str.startswith("AA "):
                if recipe and recipe.title:
                    finalize_recipe()
                    yield recipe
                recipe = Recipe(source_file=filepath, source_format=self.source_format)
                recipe.title = line_str[3:].strip()
                yield_num, yield_label = "", ""
                j_lines = []
                pending_h = False
                flush_curr_ing()
                continue
            elif line_str.startswith("A ") or (
                line_str.startswith("A") and not line_str.startswith("AA ")
            ):
                if recipe and recipe.title:
                    finalize_recipe()
                    yield recipe
                recipe = Recipe(source_file=filepath, source_format=self.source_format)
                recipe.title = line_str[2:].strip() if line_str.startswith("A ") else line_str[1:].strip()
                yield_num, yield_label = "", ""
                j_lines = []
                pending_h = False
                flush_curr_ing()
                continue

            if not recipe:
                continue

            # Tag dispatch
            if line_str.startswith("B"):
                cat = line_str[1:].strip()
                if cat and cat.lower() != "none":
                    for c in cat.split(","):
                        c_clean = c.strip()
                        if c_clean and c_clean not in recipe.categories:
                            recipe.categories.append(c_clean)
            elif line_str.startswith("D"):
                yield_num = line_str[1:].strip()
            elif line_str.startswith("M"):
                yield_label = line_str[1:].strip()
            elif line_str.startswith("F"):
                notes = line_str[1:].strip()
                if notes:
                    if recipe.description:
                        recipe.description += f" | {notes}"
                    else:
                        recipe.description = notes
            elif line_str.startswith("H"):
                h_val = line_str[1:]
                h_qty, h_unit = self._parse_h_line(h_val)
                pending_h = True
            elif line_str.startswith("I"):
                i_val = line_str[1:].strip()
                # Skip ingredient section headers like '------------ FOR THE FILLING -----------'
                if re.match(r"^-{3,}.*-{3,}$", i_val):
                    flush_curr_ing()
                    pending_h = False
                    continue
                # Continuation of previous ingredient name
                if i_val.startswith("-") and curr_ing_name:
                    part = i_val.lstrip("-").strip()
                    if part:
                        curr_ing_name = f"{curr_ing_name} {part}"
                else:
                    # New ingredient line
                    flush_curr_ing()
                    curr_ing_name = i_val
                    if pending_h:
                        curr_ing_qty = h_qty
                        curr_ing_unit = h_unit
                pending_h = False
            elif line_str.startswith("K"):
                k_val = line_str[1:].strip()
                if k_val:
                    curr_ing_comments.append(k_val)
            elif line_str.startswith("J"):
                flush_curr_ing()
                j_lines.append(line_str[1:])
            elif line_str.startswith("Z"):
                finalize_recipe()
                yield recipe
                recipe = None

        if recipe and recipe.title:
            finalize_recipe()
            yield recipe

    def _parse_h_line(self, h_text: str) -> Tuple[Optional[str], Optional[str]]:
        """Parse quantity and unit from an H line."""
        h_text = h_text.strip()
        if not h_text:
            return None, None
        qty_match = re.match(
            r"^(\d+(?:\s+\d+/\d+|\.\d+|/\d+)?(?:\s*-\s*\d+(?:\s+\d+/\d+|\.\d+|/\d+)?)?)\s*",
            h_text,
        )
        if qty_match:
            qty = qty_match.group(1).strip()
            unit_str = h_text[qty_match.end():].strip()
            unit = unit_str if unit_str else None
            return qty, unit
        return None, h_text

    def _flush_ingredient(
        self,
        qty: Optional[str],
        unit: Optional[str],
        name: str,
        comments: List[str],
        recipe: Recipe,
    ) -> None:
        """Create and append an Ingredient to the recipe."""
        name = name.strip()
        if not name:
            return
        comment = ", ".join(c.strip() for c in comments if c.strip()) if comments else None
        parts = []
        if qty:
            parts.append(qty)
        if unit:
            parts.append(unit)
        if name:
            parts.append(name)
        if comment:
            parts.append(f"({comment})")
        raw = " ".join(parts) if parts else name
        recipe.ingredients.append(
            Ingredient(
                raw=raw,
                quantity=qty,
                unit=unit,
                name=name,
                comment=comment,
            )
        )

    def _parse_instructions(self, j_lines: List[str]) -> List[str]:
        """Group raw J lines into paragraphs / steps."""
        raw_text = "\n".join(j_lines)
        paragraphs = re.split(r"\n\s*\n", raw_text)
        steps: List[str] = []
        for para in paragraphs:
            para = para.strip()
            if not para:
                continue
            substeps = re.split(r"(?:\s{2,}|\n\s*)(?=\d{1,2}[\s\.\)])", para)
            for s in substeps:
                cleaned = " ".join(s.split()).strip()
                if cleaned:
                    steps.append(cleaned)
        return steps
