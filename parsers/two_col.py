# SPDX-License-Identifier: MIT
import logging
from pathlib import Path
import re
from typing import Iterator, List

from .base import BaseRecipeParser, BaseIngredientParser
from .models import Recipe, Ingredient
from .registry import ParserRegistry

logger = logging.getLogger(__name__)


@ParserRegistry.register
class TwoColParser(BaseRecipeParser):
    """Parser for two-column text recipe format."""

    def __init__(self, ingredient_parser: BaseIngredientParser):
        super().__init__(ingredient_parser)
        self.source_format = "Two-Column Text"

    @classmethod
    def format_id(cls) -> str:
        return "two-col"

    @classmethod
    def aliases(cls) -> list[str]:
        return ["two_col", "twocolumn", "two_column"]

    @classmethod
    def priority(cls) -> int:
        return 15

    @classmethod
    def detect(cls, filepath: str, content_sample: str) -> float:
        if not content_sample or not content_sample.strip():
            return 0.0

        ext = Path(filepath).suffix.lower()
        if ext in {".md", ".markdown"}:
            return 0.0

        # Exclude files that have table borders or start with pipe/table markers
        if re.search(r'^\s*[+|]', content_sample, re.MULTILINE):
            return 0.0

        # Exclude files that belong to known structured formats
        if re.search(
            r'Exported from MasterCook|MMMMM|Recipe Via Compu-Chef|Amount\s+Measure\s+Ingredient|Now You\'re Cooking!|Recipe via',
            content_sample,
            re.IGNORECASE,
        ):
            return 0.0

        lines = content_sample.splitlines()[:15]
        # Check for exact "Servings:" header on title line
        for line in lines:
            if re.search(r'\bServings:\s*\d*', line):
                return 0.85

        # Check for 2-column ingredients (tabs or 3+ spaces after col 30)
        tab_cols = 0
        space_cols = 0
        for line in lines:
            if '\t' in line and not line.startswith('\t'):
                tab_cols += 1
            else:
                expanded = line.expandtabs(8)
                if len(expanded) > 30 and re.search(r' {3,}', expanded[30:]):
                    space_cols += 1

        if tab_cols >= 2 or space_cols >= 2:
            return 0.80

        return 0.0

    def parse_content(self, content: str, filepath: str) -> Iterator[Recipe]:
        recipe = Recipe(source_file=filepath, source_format=self.source_format)
        lines = content.splitlines()

        # Step 1: Parse Title & Servings (Header)
        idx = 0
        while idx < len(lines) and not lines[idx].strip():
            idx += 1

        if idx >= len(lines):
            return

        title_parts = []
        while idx < len(lines) and lines[idx].strip():
            line_raw = lines[idx]
            line_str = line_raw.strip()

            if self._is_group_header(line_raw) or self._looks_like_ingredient_line(line_raw):
                break

            if re.search(r'\bServings:', line_str, re.IGNORECASE):
                parts = re.split(r'\bServings:', line_str, flags=re.IGNORECASE, maxsplit=1)
                if parts[0].strip():
                    title_parts.append(parts[0].strip())
                if parts[1].strip():
                    recipe.yield_amount = parts[1].strip()
            else:
                title_parts.append(line_str)
            idx += 1

        recipe.title = " ".join(title_parts).strip() if title_parts else "Untitled Recipe"

        # Step 2: Skip empty lines between Title and Ingredients
        while idx < len(lines) and not lines[idx].strip():
            idx += 1

        # Step 3: Parse Ingredient Groups
        col1_list: List[str] = []
        col2_list: List[str] = []

        def flush_current_group():
            nonlocal col1_list, col2_list
            for text in col1_list:
                recipe.ingredients.append(self.ingredient_parser.parse(text))
            for text in col2_list:
                recipe.ingredients.append(self.ingredient_parser.parse(text))
            col1_list = []
            col2_list = []

        in_instructions = False

        while idx < len(lines):
            line = lines[idx]
            stripped = line.strip()

            if not stripped:
                next_idx = idx + 1
                while next_idx < len(lines) and not lines[next_idx].strip():
                    next_idx += 1
                if next_idx < len(lines):
                    next_line = lines[next_idx]
                    if self._is_instruction_start(next_line):
                        idx = next_idx
                        in_instructions = True
                        break
                idx += 1
                continue

            if self._is_group_header(line):
                flush_current_group()
                header_ing = Ingredient(raw=stripped, name=stripped)
                recipe.ingredients.append(header_ing)
                idx += 1
                continue

            c1, c2 = self._split_two_columns(line)
            if c1:
                col1_list.append(c1)
            if c2:
                col2_list.append(c2)

            idx += 1

        flush_current_group()

        # Step 4: Parse Instructions
        if in_instructions or idx < len(lines):
            current_step_lines = []

            def flush_step():
                if current_step_lines:
                    recipe.instructions.append(" ".join(current_step_lines).strip())
                    current_step_lines.clear()

            while idx < len(lines):
                line = lines[idx]
                stripped = line.strip()

                if not stripped:
                    flush_step()
                    idx += 1
                    continue

                if re.match(r'^(Date Entered:|By:|Source:)', stripped, re.IGNORECASE):
                    flush_step()
                    break

                if line.startswith('\t') or not current_step_lines:
                    flush_step()
                    current_step_lines.append(stripped)
                else:
                    current_step_lines.append(stripped)

                idx += 1

            flush_step()

        if recipe.title or recipe.ingredients or recipe.instructions:
            yield recipe

    def _is_group_header(self, line: str) -> bool:
        """Return True if line is an unindented group header like 'Sauce:', 'Salmon:', 'Step 1:'."""
        stripped = line.strip()
        if not stripped.endswith(':'):
            return False
        if not line.startswith((' ', '\t')) and len(stripped) < 30 and not re.search(r'^\d+\s+(?:c|tsp|tbsp|lb|oz)\b', stripped, re.IGNORECASE):
            return True
        return False

    def _looks_like_ingredient_line(self, line: str) -> bool:
        """Check if line looks like an ingredient line."""
        stripped = line.strip()
        if not stripped:
            return False
        if '\t' in line and not line.startswith('\t'):
            return True
        first_word = stripped.split()[0] if stripped.split() else ""
        return any(c.isdigit() for c in first_word) or first_word.lower() in ['a', 'an', 'some', 'few', 'dash', 'pinch']

    def _is_instruction_start(self, line: str) -> bool:
        """Check if a line after a blank line starts the instructions section."""
        stripped = line.strip()
        if not stripped:
            return False
        return line.startswith('\t') or ((len(line) - len(line.lstrip(' '))) >= 2) or (':' not in line)

    def _split_two_columns(self, line: str) -> tuple[str, str]:
        """Split a line into two column strings (col1, col2)."""
        if '\t' in line:
            if line.startswith('\t'):
                return "", line.strip()
            parts = line.split('\t', 1)
            c1 = parts[0].strip()
            c2 = parts[1].strip() if len(parts) > 1 else ""
            return c1, c2

        expanded = line.expandtabs(8)
        if len(expanded) > 30:
            match = re.search(r' {3,}', expanded[30:])
            if match:
                split_pos = 30 + match.start()
                c1 = expanded[:split_pos].strip()
                c2 = expanded[30 + match.end():].strip()

                qty_match = re.search(
                    r'\s+(\d+(?:\s+\d+/\d+|\.\d+|/\d+)?\s*(?:tsp\.?|tbsp\.?|t\.?|T\.?|c\.?|oz\.?|lb\.?|g|kg|ml|sprigs?|cloves?|halves?)?)$',
                    c1,
                    re.IGNORECASE,
                )
                if qty_match:
                    qty_str = qty_match.group(1).strip()
                    c1 = c1[:qty_match.start()].strip()
                    c2 = f"{qty_str} {c2}".strip()

                return c1, c2

        return expanded.strip(), ""
