# SPDX-License-Identifier: MIT
import logging
from typing import Iterator
from .models import Ingredient, Recipe

logger = logging.getLogger(__name__)

class BaseIngredientParser:
    def parse(self, raw_line: str) -> Ingredient:
        raise NotImplementedError

class BaseRecipeParser:
    def __init__(self, ingredient_parser: BaseIngredientParser):
        self.ingredient_parser = ingredient_parser
        self.source_format = "Unknown"

    @classmethod
    def format_id(cls) -> str:
        """Unique identifier for this format."""
        return "unknown"

    @classmethod
    def aliases(cls) -> list[str]:
        """List of alternate names for this format."""
        return []

    @classmethod
    def priority(cls) -> int:
        """Detection priority. Lower is higher priority."""
        return 100

    @classmethod
    def detect(cls, filepath: str, content_sample: str) -> float:
        """
        Return a confidence score (0.0 to 1.0) that this parser can handle the file.
        Uses pathlib.Path internally if string is passed.
        """
        return 0.0

    def parse_file(self, filepath: str) -> Iterator[Recipe]:
        """Generator that yields recipes from file."""
        from pathlib import Path
        try:
            with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
            for recipe in self.parse_content(content, filepath):
                if not recipe.description:
                    recipe.description = f"Imported from {self.source_format}"
                if not recipe.url:
                    recipe.url = f"file://{filepath}"
                yield recipe
        except Exception as e:
            logger.error("Error reading %s: %s", filepath, e)
            return

    def parse_content(self, content: str, filepath: str) -> Iterator[Recipe]:
        """Generator that yields recipes from content."""
        raise NotImplementedError
