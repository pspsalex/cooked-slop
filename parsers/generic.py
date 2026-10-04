# SPDX-License-Identifier: MIT
from pathlib import Path
from typing import Iterator, List

from .base import BaseRecipeParser, BaseIngredientParser, clean_recipe_title, sanitize_recipe
from .models import Recipe
from .registry import ParserRegistry

import re
import logging
logger = logging.getLogger(__name__)

@ParserRegistry.register
class GenericTextParser(BaseRecipeParser):
    """Fallback plain-text recipe parser (priority 100).

    Attempts to extract a single recipe from unstructured text by splitting
    on blank lines and using heuristics to classify each block as title,
    description, ingredients, or instructions. Only used when no
    format-specific parser claims the file with higher confidence.
    """

    def __init__(self, ingredient_parser: BaseIngredientParser):
        super().__init__(ingredient_parser)
        self.source_format = "Raw Text"

    @classmethod
    def format_id(cls) -> str:
        return "generic_text"

    @classmethod
    def priority(cls) -> int:
        # This is a fallback parser, so it should have lowest priority
        return 100

    @classmethod
    def supported_extensions(cls) -> set[str]:
        return {'.txt', '.prn', '.out'}

    @classmethod
    def detect(cls, filepath: str, content: str) -> float:
        """Return a minimal confidence score for any non-empty file.

        Always returns 0.01 so that format-specific parsers with higher
        scores take precedence.
        """
        return 0.01 if content.strip() else 0.0

    def parse_content(self, content: str, filepath: str) -> Iterator[Recipe]:
        """Parse plain text into Recipe objects using block heuristics.

        If divider lines (e.g. 4+ dashes, equals, asterisks, tildes) separate
        multiple recipes with ingredients, splits and yields each recipe.
        Otherwise parses the content as a single recipe.
        """
        # Delegate supported PRN files to PRN normalizer if detected
        if filepath.lower().endswith(('.prn', '.prn.txt')):
            try:
                from tools.extract.prn_normalizer import detect_prn_format, normalize_prn
                if detect_prn_format(content) != "unknown":
                    from parsers.generic_md import GenericMdParser
                    md_content = normalize_prn(content)
                    yield from GenericMdParser(self.ingredient_parser).parse_content(md_content, filepath)
                    return
            except Exception as e:
                logger.debug("PRN normalization error for %s: %s", filepath, e)

        chunks = re.split(r'(?m)^\s*(?:[-=*~]\s*){4,}\s*$', content)
        if len(chunks) > 1:
            recipes: list[Recipe] = []
            for chunk in chunks:
                if not chunk.strip():
                    continue
                if self._chunk_has_ingredients(chunk):
                    rec = self._parse_single_recipe(chunk, filepath)
                    if rec and (rec.ingredients or rec.instructions):
                        recipes.append(rec)
                elif recipes:
                    # Continuation chunk: instructions or notes for the previous recipe
                    step = chunk.strip()
                    if step:
                        recipes[-1].instructions.append(step)
            if recipes:
                for rec in recipes:
                    sanitize_recipe(rec)
                    yield rec
                return

        recipe = self._parse_single_recipe(content, filepath)
        if recipe:
            yield recipe

    def _looks_like_ingredient_line(self, line: str) -> bool:
        """Check if line looks like an ingredient line."""
        s = self._clean_bullet(line)
        if not s:
            return False
        words = s.split()
        if not words:
            return False
        first = words[0]
        if any(c.isdigit() or c in '¼½¾⅓⅔⅛⅜⅝⅞' for c in first):
            if len(words) > 1 and words[1].lower().rstrip('s.,') in {
                'hour', 'hours', 'minute', 'minutes', 'second', 'seconds',
                'day', 'days', 'month', 'months', 'year', 'years', 'degree', 'degrees', 'percent'
            }:
                return False
            return True
        if first.lower().strip(':') in ['dash', 'pinch', 'few', 'some', 'a', 'an']:
            return True
        return False

    def _clean_bullet(self, line: str) -> str:
        """Strip leading bullets, list markers, and optional prefixes."""
        s = line.lstrip("•\x95-* \t").strip()
        return re.sub(r'^(?:"Optionals?"|Optionals?:?)\s*', '', s, flags=re.IGNORECASE).strip()

    def _chunk_has_ingredients(self, chunk: str) -> bool:
        """Check if chunk contains at least one ingredient-like line."""
        for line in chunk.splitlines():
            line_str = line.strip()
            if not line_str:
                continue
            if self._looks_like_ingredient_line(line_str) and len(line_str) < 80:
                return True
        return False

    def _parse_single_recipe(self, content: str, filepath: str) -> Recipe | None:
        """Parse plain text into a single Recipe using block heuristics.

        Splits the text on blank lines and classifies blocks as:
        - First block: title and description
        - Blocks where most lines start with a quantity: ingredients
        - Remaining blocks: instruction steps

        Falls back to line-by-line parsing if single block or no ingredients found.
        """
        blocks = [b for b in re.split(r'\n\s*\n', content) if b.strip()]
        if len(blocks) <= 1:
            return self._parse_line_by_line(content, filepath)

        recipe = Recipe(source_file=filepath, source_format=self.source_format)
        recipe.title = Path(filepath).stem

        title_re = re.compile(r'^[A-Z ]{5,}')
        yield_re = re.compile(r'(?:Serves|Yield|Serving).*(\d+\s*\w+)', flags=re.IGNORECASE)
        title_found = False

        is_description = True
        description = []

        for block in blocks:
            lines = block.split('\n')

            is_ingredient = False
            ingredient_lines = 0
            for line in lines:
                line_str = line.strip()
                if not line_str:
                    continue

                if self._looks_like_ingredient_line(line_str) and len(line_str) < 80:
                    ingredient_lines += 1

                if is_description:
                    if not title_found:
                        cand_title, cand_yield = clean_recipe_title(line_str)
                        if cand_title and (
                            line_str.istitle()
                            or title_re.search(line_str)
                            or re.match(r'^(?:QTitle|Recipe\s*Name|Title|Name)\s*:\s*', line_str, re.IGNORECASE)
                        ):
                            if title_re.search(line_str):
                                recipe.title = cand_title.title()
                            else:
                                recipe.title = cand_title
                            if cand_yield and not recipe.yield_amount:
                                recipe.yield_amount = cand_yield
                            title_found = True
                            continue

                    recipe_yield = yield_re.match(line_str)
                    if recipe_yield:
                        recipe.yield_amount = recipe_yield[0]
                        continue

                    description.append(line_str)

            if ingredient_lines > len(lines) / 2:
                is_ingredient = True

            if is_description:
                recipe.description = '\n'.join(description)
                is_description = False
            elif is_ingredient:
                for line in lines:
                    line_str = line.strip()
                    if not line_str:
                        continue
                    if re.match(r'^(?:Notes?|Comments?|Source)\s*:\s*', line_str, re.IGNORECASE):
                        continue
                    if re.match(r'^(?:[A-Za-z0-9\s\-_]+\s+)?Ingredients?\s*:?$', line_str, re.IGNORECASE):
                        continue
                    cleaned_ing = self._clean_bullet(line_str)
                    if cleaned_ing:
                        recipe.ingredients.append(self.ingredient_parser.parse(cleaned_ing))
            else:
                if block.strip():
                    recipe.instructions.append(block.strip())

        sanitize_recipe(recipe)
        if recipe.ingredients:
            return recipe

        # Fallback to line-by-line parsing if block parser found no ingredients
        line_recipe = self._parse_line_by_line(content, filepath)
        if line_recipe and (line_recipe.ingredients or line_recipe.instructions):
            return line_recipe

        if recipe.instructions:
            return recipe

        logger.error(f"Can't find any ingredients or instructions in {filepath}")
        return None

    def _parse_line_by_line(self, content: str, filepath: str) -> Recipe | None:
        """Fallback line-by-line recipe extraction for unstructured text."""
        recipe = Recipe(source_file=filepath, source_format=self.source_format)
        recipe.title = Path(filepath).stem

        lines = [l.strip() for l in content.splitlines() if l.strip()]
        if not lines:
            return None

        ING_HEADER_RE = re.compile(
            r'^(?:[A-Za-z0-9\s\-_]+\s+)?Ingredients?\s*:?$', re.IGNORECASE
        )
        INST_HEADER_RE = re.compile(
            r'^(?:[A-Za-z0-9\s\-_]+\s+)?(?:Instructions?|Directions?|Method|Preparation|Preparation Instructions?)\s*:?$',
            re.IGNORECASE,
        )
        YIELD_RE = re.compile(r'(?:Serves|Yield|Serving).*?(\d+[\s\w]*)', re.IGNORECASE)

        state = 'DESC'
        desc_lines: list[str] = []
        title_found = False

        for line in lines:
            if state == 'DESC' and not title_found:
                cand_title, cand_yield = clean_recipe_title(line)
                if cand_title and not ING_HEADER_RE.match(line) and not self._looks_like_ingredient_line(line):
                    if line.isupper() or line.istitle() or len(line) < 60:
                        recipe.title = cand_title
                        if cand_yield:
                            recipe.yield_amount = cand_yield
                        title_found = True
                        continue

            ym = YIELD_RE.search(line)
            if ym and not recipe.yield_amount:
                recipe.yield_amount = ym.group(1).strip()

            if ING_HEADER_RE.match(line):
                state = 'ING'
                continue

            if INST_HEADER_RE.match(line):
                state = 'INST'
                continue

            if state == 'DESC':
                if self._looks_like_ingredient_line(line):
                    state = 'ING'
                    recipe.ingredients.append(self.ingredient_parser.parse(self._clean_bullet(line)))
                else:
                    desc_lines.append(line)
            elif state == 'ING':
                if self._looks_like_ingredient_line(line):
                    recipe.ingredients.append(self.ingredient_parser.parse(self._clean_bullet(line)))
                else:
                    state = 'INST'
                    recipe.instructions.append(line)
            elif state == 'INST':
                recipe.instructions.append(line)

        if desc_lines:
            recipe.description = ' '.join(desc_lines)

        sanitize_recipe(recipe)
        if recipe.ingredients or recipe.instructions:
            return recipe

        logger.error(f"Can't find any ingredients or instructions in {filepath}")
        return None
