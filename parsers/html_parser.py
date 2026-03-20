# SPDX-License-Identifier: MIT
import logging
import re
from pathlib import Path
from typing import Iterator
from .models import Recipe
from .base import BaseRecipeParser, BaseIngredientParser
from .registry import ParserRegistry

logger = logging.getLogger(__name__)

try:
    from recipe_scrapers import scrape_html
    HAS_RECIPE_SCRAPERS = True
except ImportError:
    HAS_RECIPE_SCRAPERS = False

@ParserRegistry.register
class HtmlParser(BaseRecipeParser):
    """Parse recipes from HTML pages using recipe-scrapers."""

    @classmethod
    def format_id(cls) -> str:
        return "html"

    @classmethod
    def priority(cls) -> int:
        return 20

    @classmethod
    def detect(cls, filepath: str, content_sample: str) -> float:
        # Path is already imported at the top
        # re is already imported at the top
        if Path(filepath).suffix.lower() in {'.html', '.htm'}:
            return 0.99
        if re.search(r'<html|<body|<div|<p>', content_sample, re.IGNORECASE):
            return 0.8
        return 0.0

    def __init__(self, ingredient_parser: BaseIngredientParser):
        super().__init__(ingredient_parser)
        self.source_format = "HTML/URL"

    def parse_content(self, content: str, filepath: str) -> Iterator[Recipe]:
        if not HAS_RECIPE_SCRAPERS:
            logger.warning("recipe-scrapers library not installed. Skipping %s.", filepath)
            return

        try:
            scraper = scrape_html(
                content,
                org_url="https://localhost/" + Path(filepath).name,
                supported_only=False,
            )
            recipe = Recipe(source_file=filepath, source_format=self.source_format)
            try:
                recipe.title = scraper.title()
            except Exception:
                recipe.title = Path(filepath).stem
            try:
                recipe.yield_amount = str(scraper.yields())
            except Exception as e:
                logger.debug("Could not extract yield from %s: %s", filepath, e)
            try:
                for ing in scraper.ingredients():
                    recipe.ingredients.append(self.ingredient_parser.parse(ing))
            except Exception as e:
                logger.debug("Could not extract ingredients from %s: %s", filepath, e)
            try:
                instr = scraper.instructions()
                if isinstance(instr, str):
                    recipe.instructions = [i.strip() for i in instr.split('\n') if i.strip()]
                else:
                    recipe.instructions = [str(i).strip() for i in instr if str(i).strip()]
            except Exception as e:
                logger.debug("Could not extract instructions from %s: %s", filepath, e)
            try:
                recipe.categories = scraper.category().split(',') if scraper.category() else []
            except Exception as e:
                logger.debug("Could not extract categories from %s: %s", filepath, e)
            yield recipe
        except Exception as e:
            logger.warning("HTML parsing error for %s: %s", filepath, e)
            return
