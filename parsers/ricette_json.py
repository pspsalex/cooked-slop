# SPDX-License-Identifier: MIT
"""
Ricette JSON parser - converts custom Ricette JSON format to internal Recipe model

Input format: newline-delimited JSON objects (one per recipe) or JSON array.

Expected JSON structure:
{
    "Nome": "Recipe Name",
    "Tipo_Piatto": "Category",
    "Ing_Principale": "Main Ingredient",
    "Persone": "Servings",
    "Ingredienti": "ing1;ing2;ing3",
    "Preparazione": "Instructions",
    "Id": 1,
    "Annotazioni": "Notes"
}
"""

import json
import logging
import re
from typing import List, Iterator

from .base import BaseRecipeParser, BaseIngredientParser
from .models import Recipe, Ingredient

logger = logging.getLogger(__name__)


def load_recipes_from_content(content: str) -> List[dict]:
    """
    Load recipes from a string containing newline-delimited JSON objects or JSON array.
    Handles:
    - Newline-delimited JSON (one object per line)
    - Multiple concatenated JSON objects (no separator)
    - A JSON array
    """
    content = content.strip()
    if not content:
        return []

    # Try as a JSON array first
    try:
        data = json.loads(content)
        if isinstance(data, list):
            return data
        elif isinstance(data, dict):
            return [data]
    except json.JSONDecodeError:
        pass

    # Try parsing as concatenated JSON objects using a decoder
    recipes = []
    decoder = json.JSONDecoder()
    pos = 0
    while pos < len(content):
        # Skip whitespace
        while pos < len(content) and content[pos] in " \t\n\r":
            pos += 1
        if pos >= len(content):
            break

        try:
            obj, end_pos = decoder.raw_decode(content, pos)
            recipes.append(obj)
            pos = end_pos
        except json.JSONDecodeError as e:
            logger.warning("Failed to parse JSON at position %d: %s", pos, e)
            break

    return recipes


def parse_ingredients(ingredients_str: str) -> List[str]:
    """Split ingredients string by semicolon and clean up each ingredient."""
    if not ingredients_str:
        return []
    return [ing.strip() for ing in ingredients_str.split(";") if ing.strip()]


from .registry import ParserRegistry

@ParserRegistry.register
class RicetteJsonParser(BaseRecipeParser):
    """Parser for Ricette JSON format."""

    def __init__(self, ingredient_parser: BaseIngredientParser):
        super().__init__(ingredient_parser)
        self.source_format = "Ricette JSON"

    @classmethod
    def format_id(cls) -> str:
        return "ricette_json"

    @classmethod
    def aliases(cls) -> list[str]:
        return ["json"]

    @classmethod
    def priority(cls) -> int:
        return 11

    @classmethod
    def detect(cls, filepath: str, content_sample: str) -> float:
        if not content_sample:
            return 0.0
        if re.match(r'^\s*[\{\[]', content_sample):
            if '"Nome"' in content_sample or '"Ingredienti"' in content_sample:
                return 0.95
            return 0.4
        return 0.0

    def parse_content(self, content: str, filepath: str) -> Iterator[Recipe]:
        """Parse JSON content and yield Recipe objects."""
        json_recipes = load_recipes_from_content(content)

        for row_index, json_recipe in enumerate(json_recipes):
            recipe = self._parse_json_recipe(json_recipe, filepath, row_index)
            if recipe.title:
                yield recipe

    def _parse_json_recipe(self, json_recipe: dict, filepath: str, row_index: int) -> Recipe:
        """Convert a JSON recipe object to a Recipe."""
        recipe = Recipe(source_file=filepath, source_format=self.source_format)

        # Name (title)
        recipe.title = json_recipe.get("Nome", "").strip() or "Untitled Recipe"

        # Categories
        categories = []
        tipo_piatto = json_recipe.get("Tipo_Piatto", "").strip()
        if tipo_piatto:
            categories.append(tipo_piatto)

        ing_principale = json_recipe.get("Ing_Principale", "").strip()
        if ing_principale and ing_principale not in categories:
            categories.append(ing_principale)

        recipe.categories = categories

        # Servings
        servings = str(json_recipe.get("Persone", "")).strip()
        if servings and servings not in ("", "None", "null", "-"):
            recipe.yield_amount = servings

        # Ingredients
        ingredienti_str = json_recipe.get("Ingredienti", "")
        ingredients_raw = parse_ingredients(ingredienti_str)
        for ing_raw in ingredients_raw:
            ing = self.ingredient_parser.parse(ing_raw) if self.ingredient_parser else Ingredient(raw=ing_raw)
            recipe.ingredients.append(ing)

        # Instructions
        preparazione = json_recipe.get("Preparazione", "").strip()
        if preparazione:
            recipe.instructions = [preparazione]

        return recipe
