# SPDX-License-Identifier: MIT
"""Schema.org JSON-LD pass-through parser.

Detects files containing Schema.org Recipe objects and passes them through
with minimal transformation, extracting fields into the internal Recipe model.
"""

import json
import logging
from typing import Iterator, Optional

from .base import BaseRecipeParser, BaseIngredientParser
from .models import Recipe, Ingredient
from .registry import ParserRegistry

logger = logging.getLogger(__name__)


@ParserRegistry.register
class SchemaOrgParser(BaseRecipeParser):
    """Pass-through parser for Schema.org Recipe JSON-LD files."""

    def __init__(self, ingredient_parser: BaseIngredientParser):
        super().__init__(ingredient_parser)
        self.source_format = "Schema.org JSON-LD"

    @classmethod
    def format_id(cls) -> str:
        return "schemaorg"

    @classmethod
    def aliases(cls) -> list[str]:
        return ["schema", "jsonld"]

    @classmethod
    def priority(cls) -> int:
        return 5

    @classmethod
    def detect(cls, filepath: str, content_sample: str) -> float:
        if not content_sample:
            return 0.0
        # Must look like JSON
        stripped = content_sample.strip()
        if not stripped or stripped[0] not in ('{', '['):
            return 0.0
        # Check for Schema.org Recipe markers
        if '"@type"' in content_sample and '"Recipe"' in content_sample:
            if '"recipeIngredient"' in content_sample or '"recipeInstructions"' in content_sample:
                return 0.98
            if '"https://schema.org"' in content_sample or '"schema.org"' in content_sample:
                return 0.95
        return 0.0

    def parse_content(self, content: str, filepath: str) -> Iterator[Recipe]:
        """Parse Schema.org Recipe JSON-LD and yield Recipe objects."""
        try:
            data = json.loads(content)
        except json.JSONDecodeError as e:
            logger.warning("Failed to parse JSON from %s: %s", filepath, e)
            return

        recipes = []
        if isinstance(data, list):
            recipes = data
        elif isinstance(data, dict):
            recipes = [data]

        for item in recipes:
            if not isinstance(item, dict):
                continue
            if item.get("@type") != "Recipe":
                continue

            recipe = Recipe(source_file=filepath, source_format=self.source_format)
            recipe.title = item.get("name", "Untitled")

            # Yield
            yield_val = item.get("recipeYield")
            if yield_val:
                recipe.yield_amount = str(yield_val) if not isinstance(yield_val, str) else yield_val

            # Categories
            cat = item.get("recipeCategory")
            if isinstance(cat, str):
                recipe.categories = [c.strip() for c in cat.split(",") if c.strip()]
            elif isinstance(cat, list):
                recipe.categories = cat

            # Description
            recipe.description = item.get("description")

            # URL
            recipe.url = item.get("url")

            # Ingredients — pass through as raw strings
            for ing in item.get("recipeIngredient", []):
                if isinstance(ing, str):
                    recipe.ingredients.append(self.ingredient_parser.parse(ing))
                elif isinstance(ing, dict):
                    raw = ing.get("name", str(ing))
                    recipe.ingredients.append(self.ingredient_parser.parse(raw))

            # Instructions
            instructions = item.get("recipeInstructions", [])
            if isinstance(instructions, str):
                recipe.instructions = [s.strip() for s in instructions.split("\n") if s.strip()]
            elif isinstance(instructions, list):
                for step in instructions:
                    if isinstance(step, str):
                        if step.strip():
                            recipe.instructions.append(step.strip())
                    elif isinstance(step, dict):
                        text = step.get("text", "")
                        if text.strip():
                            recipe.instructions.append(text.strip())

            if recipe.title:
                yield recipe
