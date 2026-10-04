# SPDX-License-Identifier: MIT
"""Parser for Diabetic / Nutritional Exchange (.RCP) recipe files."""

import logging
from pathlib import Path
import re
from typing import Iterator

from .base import BaseIngredientParser, BaseRecipeParser
from .models import Recipe
from .registry import ParserRegistry

logger = logging.getLogger(__name__)

EXCHANGE_PREFIX_RE = re.compile(r"^\s*(?:\d{2}\.\d{2}\s+){6}(.*)$")
EXCHANGE_DETECT_RE = re.compile(r"^(?:\d{2}\.\d{2}\s+){6}")


@ParserRegistry.register
class RcpExchangeParser(BaseRecipeParser):
    """Parser for Diabetic / Nutritional Exchange (.RCP) format."""

    def __init__(self, ingredient_parser: BaseIngredientParser):
        super().__init__(ingredient_parser)
        self.source_format = "RCP Exchange"

    @classmethod
    def format_id(cls) -> str:
        """Unique identifier for this format."""
        return "rcp_exchange"

    @classmethod
    def priority(cls) -> int:
        """Detection order priority. Lower is tried earlier."""
        return 6

    @classmethod
    def supported_extensions(cls) -> set[str]:
        """Supported file extensions."""
        return {".rcp"}

    @classmethod
    def detect(cls, filepath: str, content_sample: str) -> float:
        """Detect whether the content or file matches RCP Nutritional Exchange format."""
        if not content_sample:
            return 0.0
        if "RECIPE_TEXT:" not in content_sample:
            return 0.0

        if Path(filepath).suffix.lower() == ".rcp":
            return 0.95

        # Check structural layout: Line 1 title, Line 2 integer, Line 3+ exchange floats
        lines = [line.strip() for line in content_sample.splitlines() if line.strip()]
        if len(lines) >= 3:
            try:
                int(lines[1])
                if EXCHANGE_DETECT_RE.match(lines[2]):
                    return 0.90
            except ValueError:
                pass

        return 0.0

    def parse_content(self, content: str, filepath: str) -> Iterator[Recipe]:
        """Parse RCP content and yield Recipe objects.

        Args:
            content: Raw recipe file content.
            filepath: Path of the source file.

        Yields:
            Parsed Recipe instances.
        """
        if not content or not content.strip():
            return

        lines = content.splitlines()
        idx = 0
        while idx < len(lines) and not lines[idx].strip():
            idx += 1

        if idx >= len(lines):
            return

        # Line 1: Title
        title = lines[idx].strip()
        idx += 1

        # Line 2: Servings / Yield
        yield_amount = ""
        if idx < len(lines):
            servings = lines[idx].strip()
            if servings.isdigit():
                yield_amount = f"{servings} servings"
            elif servings:
                yield_amount = servings
            idx += 1

        # Lines 3 up to RECIPE_TEXT:
        ingredients = []
        while idx < len(lines):
            line = lines[idx]
            stripped = line.strip()
            if stripped == "RECIPE_TEXT:":
                idx += 1
                break
            if stripped.startswith("RECIPE_TEXT:"):
                remainder = stripped[len("RECIPE_TEXT:"):].strip()
                idx += 1
                if remainder:
                    lines.insert(idx, remainder)
                break
            if stripped:
                match = EXCHANGE_PREFIX_RE.match(stripped)
                if match:
                    ing_text = match.group(1).strip()
                else:
                    ing_text = stripped
                if ing_text:
                    ing = self.ingredient_parser.parse(ing_text)
                    ingredients.append(ing)
            idx += 1

        # Lines after RECIPE_TEXT:
        instructions = []
        while idx < len(lines):
            line = lines[idx]
            stripped = line.strip()
            if stripped:
                instructions.append(stripped)
            idx += 1

        recipe = Recipe(
            title=title,
            yield_amount=yield_amount,
            ingredients=ingredients,
            instructions=instructions,
            source_file=filepath,
            source_format=self.source_format,
        )
        yield recipe
