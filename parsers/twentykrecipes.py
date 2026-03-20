# SPDX-License-Identifier: MIT
"""
20krecipes CSV parser - converts CSV recipe format to internal Recipe model

CSV columns: TITLE_NO, TITLE, KEYWORD, INSTRUCT, ORIGIN, SERVES, SUBDIR, INGRED

Ingredient format per line:
  <quantity>  <ingredient>         (no unit, two spaces between qty and name)
  <quantity> <unit> <ingredient>   (with unit, one space between each)
"""

import csv
import logging
import re
import io
from typing import Iterator, List
from pathlib import Path

from .base import BaseRecipeParser, BaseIngredientParser
from .models import Recipe, Ingredient

logger = logging.getLogger(__name__)


# Category mapping
CATEGORY_MAP = {
    "app": "Appetizers",
    "bev": "Beverages",
    "bre": "Bread",
    "cak": "Cake",
    "cas": "Casserole",
    "che": "Cheese",
    "coo": "Cookies",
    "des": "Desserts",
    "kid": "Kid's Meals",
    "mea": "Main Courses",
    "pas": "Pasta",
    "pou": "Poultry",
    "sal": "Salads",
    "sau": "Sauces",
    "sea": "Fish",
    "sou": "Soups",
    "veg": "Vegetarian",
}


def decimal_to_fraction(val: float) -> str:
    """Convert a decimal to a nice fraction string."""
    fractions = {
        0.125: "1/8", 0.12: "1/8", 0.25: "1/4", 0.33: "1/3", 0.334: "1/3",
        0.333: "1/3", 0.5: "1/2", 0.667: "2/3", 0.666: "2/3", 0.67: "2/3",
        0.75: "3/4", 0.875: "7/8",
    }
    whole = int(val)
    frac = val - whole
    frac_str = fractions.get(round(frac, 3), "")
    if whole and frac_str:
        return f"{whole} {frac_str}"
    elif frac_str:
        return frac_str
    elif whole:
        return str(whole)
    return ""


def parse_ingredient_line(line: str) -> str:
    """
    Parse a single ingredient line into a human-readable string.

    Formats:
      "1.00 pk Active dry yeast"   -> "1 pk Active dry yeast"
      "0.75 c Warm water"          -> "3/4 c Warm water"
      "0.00  Salt"                 -> "Salt"   (quantity 0 = not relevant)
      "1.00  Salt"                 -> "1 Salt" (no unit, two spaces)
    """
    line = line.strip()
    if not line:
        return ""

    # Match: decimal  [unit]  ingredient
    # Two-space separator means no unit
    m_no_unit = re.match(r'^(\d+\.\d+)  (.+)$', line)
    m_with_unit = re.match(r'^(\d+\.\d+) (\S+) (.+)$', line)

    if m_no_unit:
        qty_str, ingredient = m_no_unit.group(1), m_no_unit.group(2)
        qty = float(qty_str)
        if qty == 0.0:
            return ingredient
        qty_display = decimal_to_fraction(qty) or qty_str.rstrip('0').rstrip('.')
        return f"{qty_display} {ingredient}"

    if m_with_unit:
        qty_str, unit, ingredient = m_with_unit.group(1), m_with_unit.group(2), m_with_unit.group(3)
        qty = float(qty_str)
        if qty == 0.0:
            return f"{unit} {ingredient}"
        qty_display = decimal_to_fraction(qty) or qty_str.rstrip('0').rstrip('.')
        return f"{qty_display} {unit} {ingredient}"

    # Fallback: return as-is
    return line


def parse_ingredients(ingred_field: str) -> List[str]:
    """Split ingredient block into list of ingredient strings."""
    lines = ingred_field.strip().splitlines()
    result = []
    for line in lines:
        parsed = parse_ingredient_line(line)
        if parsed:
            result.append(parsed)
    return result


from .registry import ParserRegistry

@ParserRegistry.register
class TwentyKRecipesParser(BaseRecipeParser):
    """Parser for 20krecipes CSV format."""

    def __init__(self, ingredient_parser: BaseIngredientParser):
        super().__init__(ingredient_parser)
        self.source_format = "20krecipes CSV"

    @classmethod
    def format_id(cls) -> str:
        return "csv_20krecipes"

    @classmethod
    def aliases(cls) -> list[str]:
        return ["20krecipes"]

    @classmethod
    def priority(cls) -> int:
        return 20

    @classmethod
    def detect(cls, filepath: str, content_sample: str) -> float:
        import csv
        import io
        if not content_sample:
            return 0.0
        try:
            reader = csv.reader(io.StringIO(content_sample))
            headers = next(reader)
            expected = ["TITLE_NO", "TITLE", "KEYWORD", "INSTRUCT", "ORIGIN", "SERVES", "SUBDIR", "INGRED"]
            if len(headers) >= 8 and headers[:8] == expected:
                return 0.95
        except Exception:
            pass
        return 0.0

    def parse_content(self, content: str, filepath: str) -> Iterator[Recipe]:
        """Parse CSV content and yield Recipe objects."""
        lines = content.strip().split('\n')
        if not lines:
            return

        # Parse as CSV
        try:
            csv_reader = csv.DictReader(io.StringIO(content))
            row_number = 2  # Start at 2 (after header)
            for row in csv_reader:
                recipe = self._parse_csv_row(row, filepath, row_number)
                if recipe.title:
                    yield recipe
                row_number += 1
        except Exception as e:
            logger.warning("Error parsing CSV: %s", e)
            return

    def _parse_csv_row(self, row: dict, filepath: str, row_number: int) -> Recipe:
        """Convert a CSV row to a Recipe object."""
        recipe = Recipe(source_file=filepath, source_format=self.source_format)

        # Title
        recipe.title = row.get("TITLE", "").strip() or "Untitled Recipe"

        # Keywords / Categories
        keyword = row.get("KEYWORD", "").strip()
        if keyword and keyword.upper() != "NULL":
            recipe.categories = [keyword]

        # Category mapping
        subdir = row.get("SUBDIR", "").strip()
        if subdir and subdir.upper() != "NULL":
            category = CATEGORY_MAP.get(subdir, subdir)
            if category and category not in recipe.categories:
                recipe.categories.append(category)

        # Instructions
        instructions_text = row.get("INSTRUCT", "").strip()
        if instructions_text and instructions_text.upper() != "NULL":
            steps = [s.strip() for s in instructions_text.split('\n') if s.strip()]
            recipe.instructions = steps

        # Yield/Servings
        serves = row.get("SERVES", "").strip()
        if serves and serves not in ("", "0", "NULL"):
            recipe.yield_amount = serves

        # Ingredients
        ingred_field = row.get("INGRED", "")
        ingredients_raw = parse_ingredients(ingred_field)
        for ing_raw in ingredients_raw:
            ing = self.ingredient_parser.parse(ing_raw) if self.ingredient_parser else Ingredient(raw=ing_raw)
            recipe.ingredients.append(ing)

        return recipe
