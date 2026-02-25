# SPDX-License-Identifier: MIT
from typing import Iterator
from .models import Ingredient, Recipe

class BaseIngredientParser:
    def parse(self, raw_line: str) -> Ingredient:
        raise NotImplementedError

class BaseRecipeParser:
    def __init__(self, ingredient_parser: BaseIngredientParser):
        self.ingredient_parser = ingredient_parser
        self.source_format = "Unknown"

    def parse_file(self, filepath: str) -> Iterator[Recipe]:
        """Generator that yields recipes from file."""
        try:
            with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
            yield from self.parse_content(content, filepath)
        except Exception as e:
            print(f"Error reading {filepath}: {e}")
            return

    def parse_content(self, content: str, filepath: str) -> Iterator[Recipe]:
        """Generator that yields recipes from content."""
        raise NotImplementedError
