# SPDX-License-Identifier: MIT
import logging
import re
from pathlib import Path
from typing import Iterator, Optional
from .models import Recipe
from .base import BaseRecipeParser, BaseIngredientParser
from .registry import ParserRegistry
from .html_config import (
    get_html_schema_registry,
    parse_html_with_schema,
    HAS_LXML,
)

logger = logging.getLogger(__name__)

_scrape_html = None
_HAS_RECIPE_SCRAPERS = None


def _get_scrape_html():
    global _scrape_html, _HAS_RECIPE_SCRAPERS
    if _HAS_RECIPE_SCRAPERS is None:
        try:
            from recipe_scrapers import scrape_html
            _scrape_html = scrape_html
            _HAS_RECIPE_SCRAPERS = True
        except ImportError:
            _scrape_html = None
            _HAS_RECIPE_SCRAPERS = False
    return _scrape_html


@ParserRegistry.register
class HtmlParser(BaseRecipeParser):
    """Parse recipes from HTML pages using configurable XPath YAML schemas or recipe-scrapers."""

    @classmethod
    def format_id(cls) -> str:
        return "html"

    @classmethod
    def priority(cls) -> int:
        return 20

    @classmethod
    def detect(cls, filepath: str, content_sample: str) -> float:
        if Path(filepath).suffix.lower() in {'.html', '.htm'}:
            return 0.99
        if re.search(r'<html|<body|<div|<p>', content_sample, re.IGNORECASE):
            return 0.8
        return 0.0

    def __init__(
        self,
        ingredient_parser: BaseIngredientParser,
        config_path: Optional[str] = None,
    ):
        super().__init__(ingredient_parser)
        self.source_format = "HTML/URL"
        self.config_path = config_path

    def parse_content(self, content: str, filepath: str) -> Iterator[Recipe]:
        registry = get_html_schema_registry()
        schema = None

        if self.config_path:
            schema = registry.load_schema_from_file(Path(self.config_path))
        if not schema:
            schema = registry.detect_schema(content[:5000], filepath)

        if schema and HAS_LXML:
            try:
                recipe = parse_html_with_schema(
                    content, schema, self.ingredient_parser, filepath
                )
                if recipe.title or recipe.ingredients:
                    yield recipe
                    return
            except Exception as e:
                logger.debug("XPath HTML schema parsing failed for %s: %s", filepath, e)

        scraper_fn = _get_scrape_html()
        if not scraper_fn:
            logger.warning(
                "recipe-scrapers library not installed and no valid XPath schema matched. Skipping %s.",
                filepath,
            )
            return

        try:
            scraper = scraper_fn(
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

