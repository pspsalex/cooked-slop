# SPDX-License-Identifier: MIT
from pathlib import Path
from typing import Iterator, List

from .base import BaseRecipeParser, BaseIngredientParser
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
    def detect(cls, filepath: str, content: str) -> float:
        """Return a minimal confidence score for any non-empty file.

        Always returns 0.01 so that format-specific parsers with higher
        scores take precedence.
        """
        return 0.01 if content.strip() else 0.0

    def parse_content(self, content: str, filepath: str) -> Iterator[Recipe]:
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
                        if line_str.istitle():
                            recipe.title = line_str
                            title_found = True
                            continue

                        if title_re.search(line_str):
                            recipe.title = line_str.title()
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

        if recipe.ingredients or recipe.instructions:
            yield recipe
        else:
            logger.error(f"Can't find any ingredients or instructions in {filepath}")
