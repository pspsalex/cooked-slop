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
        chunks = re.split(r'(?m)^\s*(?:[-=*~]\s*){4,}\s*$', content)
        if len(chunks) > 1:
            recipe_chunks = [c for c in chunks if c.strip() and self._chunk_has_ingredients(c)]
            if len(recipe_chunks) >= 2:
                for chunk in chunks:
                    if not chunk.strip() or not self._chunk_has_ingredients(chunk):
                        continue
                    recipe = self._parse_single_recipe(chunk, filepath)
                    if recipe:
                        yield recipe
                return

        recipe = self._parse_single_recipe(content, filepath)
        if recipe:
            yield recipe

    def _chunk_has_ingredients(self, chunk: str) -> bool:
        """Check if chunk contains at least one ingredient-like line."""
        for line in chunk.splitlines():
            line_str = line.strip()
            if not line_str:
                continue
            first_word = line_str.split()[0]
            looks_like = any(c.isdigit() for c in first_word) or first_word.lower() in ['a', 'an', 'some', 'few', 'dash', 'pinch']
            if looks_like and len(line_str) < 80:
                return True
        return False

    def _parse_single_recipe(self, content: str, filepath: str) -> Recipe | None:
        """Parse plain text into a single Recipe using block heuristics.

        Splits the text on blank lines and classifies blocks as:
        - First block: title and description
        - Blocks where most lines start with a quantity: ingredients
        - Remaining blocks: instruction steps
        """
        recipe = Recipe(source_file=filepath, source_format=self.source_format)
        recipe.title = Path(filepath).stem

        blocks = re.split(r'\n\s*\n', content)

        title_re = re.compile(r'^[A-Z ]{5,}')
        yield_re = re.compile(r'(?:Serves|Yield|Serving).*(\d+\s*\w+)', flags = re.IGNORECASE)
        title_found = False

        is_description = True
        description = []

        for block in blocks:
            lines = block.split('\n')

            is_ingredient = False
            ingredient_lines = 0
            for line in lines:
                line_str = line.strip()
                if not line_str: continue

                first_word = line_str.split()[0] if line_str.split() else ""
                looks_like_ingredient = any(c.isdigit() for c in first_word) or first_word.lower() in ['a', 'an', 'some', 'few', 'dash', 'pinch']

                if looks_like_ingredient and len(line_str) < 80:
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

            if ingredient_lines > len(lines)/2:
                is_ingredient = True

            if is_description:
                recipe.description = '\n'.join(description)
                is_description = False
            elif is_ingredient:
                for line in lines:
                    line_str = line.strip()
                    if not line_str: continue
                    recipe.ingredients.append(self.ingredient_parser.parse(line_str))
            else:
                if block.strip():
                    recipe.instructions.append(block.strip())

        sanitize_recipe(recipe)
        if recipe.ingredients or recipe.instructions:
            return recipe
        else:
            logger.error(f"Can't find any ingredients or instructions in {filepath}")
            return None
