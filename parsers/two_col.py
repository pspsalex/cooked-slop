# SPDX-License-Identifier: MIT
import logging
from pathlib import Path
import re
from typing import Iterator, List

from .base import BaseRecipeParser, BaseIngredientParser, clean_recipe_title, sanitize_recipe
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
        return "two_col"

    @classmethod
    def priority(cls) -> int:
        return 15

    @classmethod
    def detect(cls, filepath: str, content_sample: str) -> float:
        if not content_sample or not content_sample.strip():
            return 0.0

        ext = Path(filepath).suffix.lower()
        if ext in {".md", ".markdown", ".csv"}:
            return 0.0

        # Exclude files that have table borders or start with pipe/table markers
        if re.search(r'^\s*[+|]', content_sample, re.MULTILINE):
            return 0.0

        # Exclude files that belong to known structured formats
        if re.search(
            r'Exported from MasterCook|\bMMMMM\b|Recipe Via Compu-Chef|Amount\s+Measure\s+Ingredient|Now You\'re Cooking!|Recipe via',
            content_sample,
            re.IGNORECASE,
        ):
            return 0.0

        lines = [l for l in content_sample.splitlines() if l.strip()][:25]

        # Check for 2-column ingredients (both sides must look like ingredients)
        two_col_lines = 0
        for line in lines:
            c1, c2 = cls._split_two_columns(line)
            if c1 and c2 and cls._looks_like_ingredient_line(c1) and cls._looks_like_ingredient_line(c2):
                two_col_lines += 1

        if two_col_lines >= 2:
            return 0.85

        return 0.0

    def parse_content(self, content: str, filepath: str) -> Iterator[Recipe]:
        chunks = re.split(r'(?m)^[-=~*]{4,}\s*$', content)
        if len(chunks) <= 1:
            recipe = self._parse_single_chunk(content, filepath)
            if recipe and (recipe.ingredients or recipe.instructions):
                sanitize_recipe(recipe)
                yield recipe
            return

        recipes: List[Recipe] = []
        for chunk in chunks:
            if not chunk.strip():
                continue
            lines = chunk.splitlines()
            if self._chunk_has_ingredients(lines):
                rec = self._parse_single_chunk(chunk, filepath)
                if rec and rec.ingredients:
                    recipes.append(rec)
            elif recipes:
                # Continuation chunk: instructions or trailing metadata for previous recipe
                self._append_continuation_chunk(recipes[-1], chunk)

        for rec in recipes:
            sanitize_recipe(rec)
            yield rec

    def _chunk_has_ingredients(self, lines: list[str]) -> bool:
        """Check if chunk contains at least one ingredient-like line or group header."""
        for line in lines:
            if self._is_group_header(line) or self._looks_like_ingredient_line(line):
                return True
        return False

    def _append_continuation_chunk(self, recipe: Recipe, chunk: str) -> None:
        """Append instructions or trailing metadata from a divider-separated continuation chunk."""
        lines = chunk.splitlines()
        current_step: List[str] = []
        in_keywords = False
        keywords_lines: List[str] = []

        def flush():
            if current_step:
                recipe.instructions.append(" ".join(current_step).strip())
                current_step.clear()

        idx = 0
        while idx < len(lines):
            line = lines[idx]
            stripped = line.strip()
            if not stripped:
                flush()
                if in_keywords:
                    in_keywords = False
                idx += 1
                continue

            if in_keywords:
                keywords_lines.append(stripped)
                idx += 1
                continue

            kw_match = re.match(r'^KEY\s*WORDS\s*:\s*(.*)$', stripped, re.IGNORECASE)
            if kw_match:
                flush()
                in_keywords = True
                kw_content = kw_match.group(1).strip()
                if kw_content:
                    keywords_lines.append(kw_content)
                idx += 1
                continue

            makes_match = re.match(r'^(?:Makes|Serves|Servings|Yield)\s*:?\s*(.+)$', stripped, re.IGNORECASE)
            if makes_match:
                flush()
                if not recipe.yield_amount:
                    recipe.yield_amount = makes_match.group(1).strip()
                idx += 1
                continue

            if line.startswith('\t') or not current_step:
                flush()
                current_step.append(stripped)
            else:
                current_step.append(stripped)
            idx += 1

        flush()
        if keywords_lines:
            raw_kw = " ".join(keywords_lines)
            for cat in [w.strip() for w in re.split(r'[,;]+', raw_kw) if w.strip()]:
                if cat not in recipe.categories:
                    recipe.categories.append(cat)

    def _parse_single_chunk(self, chunk: str, filepath: str) -> Recipe | None:
        if not chunk or not chunk.strip():
            return None

        lines = chunk.splitlines()
        recipe = Recipe(source_file=filepath, source_format=self.source_format)

        # Step 1: Parse Title, Servings, and Intro/Description
        idx = 0
        header_lines: List[str] = []
        while idx < len(lines):
            line = lines[idx]
            stripped = line.strip()
            if not stripped:
                if header_lines:
                    next_idx = idx + 1
                    while next_idx < len(lines) and not lines[next_idx].strip():
                        next_idx += 1
                    if next_idx < len(lines):
                        next_line = lines[next_idx]
                        if self._is_group_header(next_line) or self._looks_like_ingredient_line(next_line):
                            idx = next_idx
                            break
                idx += 1
                continue

            if self._is_group_header(line) or self._looks_like_ingredient_line(line):
                break

            if re.search(r'\bServings:', stripped, re.IGNORECASE):
                parts = re.split(r'\bServings:', stripped, flags=re.IGNORECASE, maxsplit=1)
                if parts[0].strip():
                    header_lines.append(parts[0].strip())
                if parts[1].strip() and not recipe.yield_amount:
                    recipe.yield_amount = parts[1].strip()
            elif re.search(r'\bMakes:', stripped, re.IGNORECASE):
                parts = re.split(r'\bMakes:', stripped, flags=re.IGNORECASE, maxsplit=1)
                if parts[0].strip():
                    header_lines.append(parts[0].strip())
                if parts[1].strip() and not recipe.yield_amount:
                    recipe.yield_amount = parts[1].strip()
            else:
                header_lines.append(line)
            idx += 1

        if not header_lines and idx >= len(lines):
            return None

        indented_lines = [l for l in header_lines if l.startswith('\t') or len(l) - len(l.lstrip(' ')) >= 3]
        unindented_lines = [l for l in header_lines if not (l.startswith('\t') or len(l) - len(l.lstrip(' ')) >= 3)]

        if indented_lines:
            raw_title = " ".join(l.strip() for l in indented_lines)
            if unindented_lines:
                recipe.description = "\n".join(l.strip() for l in unindented_lines)
        elif header_lines:
            raw_title = " ".join(l.strip() for l in header_lines)
        else:
            raw_title = "Untitled Recipe"

        c_title, ext_y = clean_recipe_title(raw_title)
        recipe.title = c_title if c_title else raw_title
        if ext_y and not recipe.yield_amount:
            recipe.yield_amount = ext_y

        # Step 2: Skip empty lines between Title/Header and Ingredients
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

        # Step 4: Parse Instructions and Trailing Metadata
        if in_instructions or idx < len(lines):
            current_step_lines: List[str] = []
            in_keywords = False
            keywords_lines: List[str] = []

            def flush_step():
                if current_step_lines:
                    recipe.instructions.append(" ".join(current_step_lines).strip())
                    current_step_lines.clear()

            while idx < len(lines):
                line = lines[idx]
                stripped = line.strip()

                if not stripped:
                    flush_step()
                    if in_keywords:
                        in_keywords = False
                    idx += 1
                    continue

                if re.match(r'^(Date Entered:|By:|Source:)', stripped, re.IGNORECASE):
                    flush_step()
                    break

                if in_keywords:
                    keywords_lines.append(stripped)
                    idx += 1
                    continue

                kw_match = re.match(r'^KEY\s*WORDS\s*:\s*(.*)$', stripped, re.IGNORECASE)
                if kw_match:
                    flush_step()
                    in_keywords = True
                    kw_content = kw_match.group(1).strip()
                    if kw_content:
                        keywords_lines.append(kw_content)
                    idx += 1
                    continue

                makes_match = re.match(r'^(?:Makes|Serves|Servings|Yield)\s*:?\s*(.+)$', stripped, re.IGNORECASE)
                if makes_match:
                    flush_step()
                    if not recipe.yield_amount:
                        recipe.yield_amount = makes_match.group(1).strip()
                    idx += 1
                    continue

                if line.startswith('\t') or not current_step_lines:
                    flush_step()
                    current_step_lines.append(stripped)
                else:
                    current_step_lines.append(stripped)

                idx += 1

            flush_step()

            if keywords_lines:
                raw_kw = " ".join(keywords_lines)
                for cat in [w.strip() for w in re.split(r'[,;]+', raw_kw) if w.strip()]:
                    if cat not in recipe.categories:
                        recipe.categories.append(cat)

        sanitize_recipe(recipe)
        if recipe.title or recipe.ingredients or recipe.instructions:
            return recipe
        return None

    def _is_group_header(self, line: str) -> bool:
        """Return True if line is an unindented group header like 'Sauce:', 'Salmon:', 'Step 1:'."""
        stripped = line.strip()
        if not stripped.endswith(':'):
            return False
        if re.match(r'^(?:KEY\s*WORDS|DATE\s*ENTERED|BY|SOURCE)\b', stripped, re.IGNORECASE):
            return False
        if not line.startswith((' ', '\t')) and len(stripped) < 30 and not re.search(r'^\d+\s+(?:c|tsp|tbsp|lb|oz)\b', stripped, re.IGNORECASE):
            return True
        return False

    _UNIT_WORDS = {
        'pinch', 'dash', 'can', 'clove', 'package', 'pkg', 'bunch', 'slice',
        'sprig', 'cup', 'tsp', 'tbsp', 't', 'tb', 'c', 'bottle', 'stick',
        'piece', 'head', 'stalk', 'strip', 'jar', 'envelope', 'handful',
        'drop', 'box', 'pt', 'qt', 'gal', 'oz', 'lb'
    }

    @classmethod
    def _looks_like_ingredient_line(cls, line: str) -> bool:
        """Check if line looks like an ingredient line."""
        stripped = line.strip()
        if not stripped:
            return False
        words = stripped.split()
        first_word = words[0]
        if any(c.isdigit() or c in '¼½¾⅓⅔⅛⅜⅝⅞' for c in first_word):
            return True
        if first_word.lower() in ['dash', 'pinch', 'few', 'some']:
            return True
        if first_word.lower() in ['a', 'an'] and len(words) > 1:
            second = words[1].lower().rstrip('s.').strip()
            if second in cls._UNIT_WORDS:
                return True
        return False

    def _is_instruction_start(self, line: str) -> bool:
        """Check if a line after a blank line starts the instructions section."""
        stripped = line.strip()
        if not stripped:
            return False
        return line.startswith('\t') or ((len(line) - len(line.lstrip(' '))) >= 2) or (':' not in line)

    @classmethod
    def _split_two_columns(cls, line: str) -> tuple[str, str]:
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
