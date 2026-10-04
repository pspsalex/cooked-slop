# SPDX-License-Identifier: MIT
"""Parser for vintage Macintosh Info-Mac BBS recipe collections (.INF files)."""

import logging
from pathlib import Path
import re
from typing import Iterator, List, Optional, Tuple

from .base import BaseRecipeParser, BaseIngredientParser
from .models import Recipe, Ingredient
from .registry import ParserRegistry

logger = logging.getLogger(__name__)


@ParserRegistry.register
class InfoMacParser(BaseRecipeParser):
    """Parser for vintage Macintosh Info-Mac BBS recipe collections (.INF files)."""

    def __init__(self, ingredient_parser: BaseIngredientParser):
        super().__init__(ingredient_parser)
        self.source_format = "Info-Mac"

    @classmethod
    def format_id(cls) -> str:
        return "infomac"

    @classmethod
    def priority(cls) -> int:
        return 10

    @classmethod
    def supported_extensions(cls) -> set[str]:
        return {".inf", ".txt"}

    @classmethod
    def detect(cls, filepath: str, content_sample: str) -> float:
        """Sniff content and file path to determine confidence score for Info-Mac format.

        Returns:
            0.95 if content starts with '%' and contains a newline followed by '`' title line.
            0.85 if file extension is '.inf' and content contains '`' title line.
            0.0 otherwise.
        """
        if not content_sample or not content_sample.strip():
            return 0.0

        ext = Path(filepath).suffix.lower()
        starts_with_pct = content_sample.lstrip().startswith("%")
        has_backtick_title = bool(re.search(r"\r?\n\s*`[^\r\n]+", content_sample))

        if starts_with_pct and has_backtick_title:
            return 0.95
        if ext == ".inf" and (has_backtick_title or bool(re.search(r"^[ \t]*`[^\r\n]+", content_sample, re.MULTILINE))):
            return 0.85
        return 0.0

    def parse_content(self, content: str, filepath: str) -> Iterator[Recipe]:
        """Parse Info-Mac BBS multi-recipe file content and yield Recipe instances.

        Recipes are delimited by tilde ('~') lines or leading backticks ('`').
        Within each recipe, ingredients and instructions are separated by a dash divider line.
        """
        raw_chunks = re.split(r"^[ \t]*~[ \t]*$", content, flags=re.MULTILINE)
        for chunk in raw_chunks:
            recipe_blocks = re.split(r"(?=^[ \t]*\`[^\r\n]+)", chunk, flags=re.MULTILINE)
            for block in recipe_blocks:
                block_stripped = block.strip()
                if not block_stripped:
                    continue
                if not re.search(r"^[ \t]*\`", block, re.MULTILINE):
                    continue
                recipe = self._parse_single_recipe(block, filepath)
                if recipe and (recipe.title or recipe.ingredients or recipe.instructions):
                    yield recipe

    def _parse_single_recipe(self, block: str, filepath: str) -> Optional[Recipe]:
        """Parse an individual recipe block."""
        recipe = Recipe(source_file=filepath, source_format=self.source_format)
        lines = block.splitlines()

        # Step 1: Find recipe title line
        start_idx = 0
        for i, line in enumerate(lines):
            stripped = line.strip()
            if stripped.startswith("`"):
                recipe.title = stripped.lstrip("`").strip()
                start_idx = i + 1
                break

        if not recipe.title:
            return None

        # Step 2: Skip empty lines and OCR / formatting artifacts right after title
        while start_idx < len(lines):
            stripped = lines[start_idx].strip()
            if not stripped or stripped in {"a", "A", "%"}:
                start_idx += 1
            else:
                break

        # Step 3: Find divider separating ingredients from instructions
        dash_idx = -1
        extra_ing = None

        for i in range(start_idx, len(lines)):
            line = lines[i]
            if re.match(r"^[ \t]*-+[ \t]*$", line):
                dash_idx = i
                break
            # Handle dash with trailing text like: "-                Cornmeal"
            m = re.match(r"^[ \t]*-+\s{3,}(.*)$", line)
            if m:
                dash_idx = i
                extra_ing = m.group(1).strip()
                break

        # Fallback if no dash divider was found: look for section headers like DIRECTIONS, INSTRUCTIONS, METHOD
        if dash_idx == -1:
            for i in range(start_idx, len(lines)):
                if re.match(r"^[ \t]*(?:directions?|instructions?|method|preparation):?[ \t]*$", lines[i], re.IGNORECASE):
                    dash_idx = i
                    break

        if dash_idx != -1:
            raw_ing_lines = lines[start_idx:dash_idx]
            raw_inst_lines = lines[dash_idx + 1:]
            if extra_ing:
                raw_ing_lines.append(extra_ing)
        else:
            first_non_empty = ""
            for l in lines[start_idx:]:
                if l.strip():
                    first_non_empty = l.strip()
                    break

            instruction_verb_pattern = (
                r"^(?:Preheat|Heat|Rub|Place|Mix|Combine|Cook|Peel|Cut|Brown|Stir|Bake|"
                r"In a|Dissolve|Melt|Beat|Boil|Wash|Scald|Drain|Sift|Cover|After)\b"
            )
            if re.match(instruction_verb_pattern, first_non_empty, re.IGNORECASE) and not re.match(r"^\d", first_non_empty):
                raw_ing_lines = []
                raw_inst_lines = lines[start_idx:]
            else:
                split_at = len(lines)
                for i in range(start_idx, len(lines)):
                    l_str = lines[i].strip()
                    if re.match(instruction_verb_pattern, l_str, re.IGNORECASE) and not re.match(r"^\d", l_str):
                        split_at = i
                        break
                raw_ing_lines = lines[start_idx:split_at]
                raw_inst_lines = lines[split_at:]

        # Step 4: Parse Ingredients
        for line in raw_ing_lines:
            stripped = line.strip()
            if not stripped:
                continue

            # Check for Categories:
            cat_match = re.match(r"^Categories:\s*(.*)", stripped, re.IGNORECASE)
            if cat_match:
                cats_val = cat_match.group(1).strip()
                if "," in cats_val:
                    cats = [c.strip() for c in cats_val.split(",") if c.strip()]
                else:
                    cats = [cats_val] if cats_val else []
                recipe.categories.extend(cats)
                continue

            # Check for standalone Servings / Makes line
            yield_match = re.match(r"^(?:Makes|Servings?|Serves):\s*(.*)", stripped, re.IGNORECASE)
            if yield_match:
                recipe.yield_amount = yield_match.group(1).strip()
                continue

            # Check for "Makes 12 Servings"
            yield_match2 = re.match(
                r"^(?:Makes|Serves)\s+(\d+(?:\s*(?:to|-)\s*\d+)?\s*(?:Servings|servings|slices|pies|gallons|people|loaf|loaves)?)\.?$",
                stripped,
                re.IGNORECASE,
            )
            if yield_match2:
                recipe.yield_amount = yield_match2.group(1).strip()
                continue

            # Skip section headers
            if re.match(r"^(?:ingredients?|amounts?):?$", stripped, re.IGNORECASE):
                continue

            # Check for two-column ingredient layout
            c1, c2 = self._split_two_columns(line)
            if c1:
                recipe.ingredients.append(self.ingredient_parser.parse(c1))
            if c2:
                recipe.ingredients.append(self.ingredient_parser.parse(c2))

        # Step 5: Parse Instructions & Attribution
        cleaned_inst_lines = []
        for line in raw_inst_lines:
            stripped = line.strip()
            if re.match(r"^(?:directions?|instructions?|method|preparation):?$", stripped, re.IGNORECASE):
                continue
            cleaned_inst_lines.append(line)

        # Extract attribution lines from the end of instructions
        while cleaned_inst_lines:
            last = cleaned_inst_lines[-1].strip()
            if not last:
                cleaned_inst_lines.pop()
                continue
            if last.startswith("\\fm"):
                cleaned_inst_lines.pop()
                continue
            from_match = re.match(r"^(?:From:?\s+.*|From\s+[A-Z].*)", last)
            if from_match:
                if not recipe.description:
                    recipe.description = last
                cleaned_inst_lines.pop()
                continue
            break

        # Group non-empty lines into paragraphs
        current_step: List[str] = []
        for line in cleaned_inst_lines:
            stripped = line.strip()
            if stripped:
                if stripped.startswith("\\fm"):
                    continue
                current_step.append(stripped)
            else:
                if current_step:
                    recipe.instructions.append(" ".join(current_step))
                    current_step = []

        if current_step:
            recipe.instructions.append(" ".join(current_step))

        # Step 6: If yield was not found in ingredients, extract from instructions
        if not recipe.yield_amount:
            for step in recipe.instructions:
                ym = re.search(
                    r"\b(?:Makes|Servings?:?|Serves:?)\s*(?:about\s*)?(\d+(?:\s*(?:to|-)\s*\d+)?\s*(?:servings?|slices|pies|gallons|sticks|cups|bars|cookies|muffins|biscuits|rolls|loaves|loaf|people|portions|doz(?:en)?)?)",
                    step,
                    re.IGNORECASE,
                )
                if ym:
                    recipe.yield_amount = ym.group(1).strip()
                    break

        return recipe

    def _split_two_columns(self, line: str) -> Tuple[str, str]:
        """Split a line into two column strings (col1, col2) if formatted as two columns.

        Uses tab separation or 3+ spaces after column 25, while ensuring single-column
        tab-spaced ingredients (quantity, unit, name) are not improperly split.
        """
        if "\t" in line:
            if line.startswith("\t"):
                parts = [p.strip() for p in line.split("\t") if p.strip()]
                if len(parts) >= 2 and any(p[0].isdigit() for p in parts[1:] if p):
                    return parts[0], " ".join(parts[1:])
                return line.strip(), ""
            parts = line.split("\t", 1)
            c1 = parts[0].strip()
            c2 = parts[1].strip() if len(parts) > 1 else ""
            if c1 and c2 and re.search(r"[a-zA-Z]", c1):
                return c1, c2
            return line.strip(), ""

        expanded = line.expandtabs(8)
        if len(expanded) > 25:
            match = re.search(r" {3,}", expanded[25:])
            if match:
                split_pos = 25 + match.start()
                c1 = expanded[:split_pos].strip()
                c2 = expanded[25 + match.end():].strip()
                if c1 and c2 and re.search(r"[a-zA-Z]", c1):
                    return c1, c2
        return line.strip(), ""
