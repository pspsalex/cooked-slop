# SPDX-License-Identifier: MIT
import csv
import io
from typing import Iterator, List
from pathlib import Path

from .base import BaseRecipeParser
from .models import Recipe, Ingredient
from .registry import ParserRegistry


@ParserRegistry.register
class CookwareCSVParser(BaseRecipeParser):
    """Parser for Cookware CSV format."""

    def __init__(self, ingredient_parser=None):
        super().__init__(ingredient_parser)
        self.source_format = "Cookware CSV"

    @classmethod
    def format_id(cls) -> str:
        return "csv_cookware"

    @classmethod
    def priority(cls) -> int:
        return 20

    @classmethod
    def detect(cls, filepath: str, content_sample: str) -> float:
        if not content_sample:
            return 0.0
        try:
            # Re-read with StringIO to use csv.reader
            reader = csv.reader(io.StringIO(content_sample))
            headers = next(reader)
            expected = ["Recipe Title", "Main Ingredient", "Course", "Region", "Ingredients (col.1)", "Ingredients (col.2)", "Ingredients (col.3)", "Directions"]
            # Check if all expected headers are present in the first few columns
            if len(headers) >= 8 and all(h in headers for h in expected):
                return 0.95
        except Exception:
            pass
        return 0.0

    def parse_content(self, content: str, filepath: str) -> Iterator[Recipe]:
        """Parse CSV content and yield Recipe objects."""
        try:
            csv_reader = csv.DictReader(io.StringIO(content))
            for row_number, row in enumerate(csv_reader, start=1):
                recipe = self._parse_csv_row(row, filepath)
                if recipe.title:
                    recipe.url = f"file://{Path(filepath).absolute()}#{row_number}"
                    yield recipe
        except Exception as e:
            import logging
            logging.getLogger(__name__).warning(f"Error parsing Cookware CSV: {e}")
            return

    def _parse_csv_row(self, row: dict, filepath: str) -> Recipe:
        """Convert a CSV row to a Recipe object."""
        recipe = Recipe(source_file=filepath, source_format=self.source_format)

        # Title
        recipe.title = row.get("Recipe Title", "").strip() or "Untitled Recipe"

        # Categories / Course / Region
        categories = []
        course = row.get("Course", "").strip()
        if course:
            categories.append(course.rstrip('.'))

        region = row.get("Region", "").strip()
        if region:
            categories.append(region.rstrip('.'))

        main_ingredient = row.get("Main Ingredient", "").strip()
        if main_ingredient:
            categories.append(main_ingredient.rstrip('.'))

        recipe.categories = list(dict.fromkeys(categories))  # Remove duplicates while preserving order

        # Yield/Servings
        serves = row.get("Servings?", "").strip()
        if serves and serves not in ("", "0", "?"):
            recipe.yield_amount = serves

        # Ingredients (3 columns)
        for col in ["Ingredients (col.1)", "Ingredients (col.2)", "Ingredients (col.3)"]:
            ingred_field = row.get(col, "")
            if ingred_field:
                lines = [line.strip() for line in ingred_field.split('\n') if line.strip()]
                for line in lines:
                    ing = self.ingredient_parser.parse(line) if self.ingredient_parser else Ingredient(raw=line)
                    recipe.ingredients.append(ing)

        # Directions
        directions_text = row.get("Directions", "").strip()
        if directions_text:
            # Directions are usually in a single block, split by sentences or paragraphs if needed
            # For now, let's treat it as a single step or split on double newlines
            steps = [s.strip() for s in directions_text.split('\n') if s.strip()]
            recipe.instructions = steps

        return recipe
