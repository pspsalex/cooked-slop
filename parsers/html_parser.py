# SPDX-License-Identifier: MIT
import sys
from pathlib import Path
from typing import Iterator
from .models import Recipe
from .base import BaseRecipeParser, BaseIngredientParser
import logging

logger = logging.getLogger(__name__)

# ANSI colors - imported inline or redefined
class Colors:
    YELLOW = '\033[93m'
    ENDC = '\033[0m'

try:
    from recipe_scrapers import scrape_html
    HAS_RECIPE_SCRAPERS = True
except ImportError:
    HAS_RECIPE_SCRAPERS = False

class HtmlParser(BaseRecipeParser):
    def __init__(self, ingredient_parser: BaseIngredientParser):
        super().__init__(ingredient_parser)
        self.source_format = "HTML/URL"

    def parse_content(self, content: str, filepath: str) -> Iterator[Recipe]:
        if not HAS_RECIPE_SCRAPERS:
            logger.warning(f"recipe-scrapers library not installed. Skipping {filepath}.")
            return

        try:
            # Passing it strictly to scrapers (some scrapers also accept raw html if host is provided)
            # This is a naive implementation, a better one would scrape local HTML via specific extractors.
            scraper = scrape_html(content, org_url="file://" + str(Path(filepath).absolute()))
            recipe = Recipe(source_file=filepath, source_format=self.source_format)
            try: recipe.title = scraper.title()
            except: recipe.title = Path(filepath).stem
            try: recipe.yield_amount = str(scraper.yields())
            except: pass
            try:
                for ing in scraper.ingredients():
                    recipe.ingredients.append(self.ingredient_parser.parse(ing))
            except: pass
            try:
                instr = scraper.instructions()
                # Ensure it's a list since scraper might return a string depending on version
                if isinstance(instr, str):
                    recipe.instructions = [i.strip() for i in instr.split('\n') if i.strip()]
                else:
                    recipe.instructions = [str(i).strip() for i in instr if str(i).strip()]
            except: pass
            try:
                recipe.categories = scraper.category().split(',') if scraper.category() else []
            except: pass
            yield recipe
        except Exception as e:
            logger.warning(f"HTML parsing error for {filepath}: {e}")
            return
