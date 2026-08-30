# SPDX-License-Identifier: MIT
import logging
from typing import Iterator
from .models import Ingredient, Recipe

logger = logging.getLogger(__name__)

def get_context_window(lines: list[str], start_idx: int, window_size: int = 15) -> str:
    """Extract a sliding window of up to window_size lines starting at start_idx."""
    end_idx = min(start_idx + window_size, len(lines))
    return "\n".join(lines[start_idx:end_idx])

class BaseIngredientParser:
    def parse(self, raw_line: str) -> Ingredient:
        raise NotImplementedError

class BaseRecipeParser:
    def __init__(self, ingredient_parser: BaseIngredientParser):
        self.ingredient_parser = ingredient_parser
        self.source_format = "Unknown"

    def get_display_name(self, filepath: str | None = None) -> str:
        """Return user-friendly display name for this parser, optionally tailored to filepath."""
        fmt = self.source_format
        if not fmt or fmt == "Unknown":
            fmt = self.__class__.__name__.replace("Parser", "")
        return f"{fmt} Parser"

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
            logger.error("Error reading %s: %s", filepath, e, exc_info=True)
            return

    def parse_content(self, content: str, filepath: str) -> Iterator[Recipe]:
        """Generator that yields recipes from content."""
        raise NotImplementedError
        yield
