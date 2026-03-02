# SPDX-License-Identifier: MIT
from .models import Recipe, Ingredient
from .base import BaseIngredientParser, BaseRecipeParser
from .ingredients import get_ingredient_parser
from .registry import ParserRegistry
from .generic import GenericTextParser
from .mixed import MixedFormatParser
from .compuchef import CompuChefParser
from .recipeml import RecipeMLParser
from .twentykrecipes import TwentyKRecipesParser
from .ricette_json import RicetteJsonParser
from .sqlite.sqlite_config import get_sqlite_schema_registry, SqliteRecipeSchema, SqliteSchemaRegistry
from .ricette import RicetteParser
from .edna import EdnaParser
from .ricette_md import RicetteMdParser
from .vitt import VittRecipesParser
from .nyc import NYCParser
from .sqlite.sqlite_parser import SqliteRecipeParser
from .html_parser import HtmlParser
from .llm_parser import LLMRecipeParser
from .microcook import MicroCookParser
from .cookware import CookwareCSVParser
# Explicit imports ensure @ParserRegistry.register fires; mixed.py transitively
# imports mealmaster/mastercook but they must be listed here for clarity and __all__.
from .mealmaster import MealMasterParser
from .mastercook import MasterCookParser
from .stubs import PdfParser, ImageParser, CsvParser

__all__ = [
    'Recipe',
    'Ingredient',
    'BaseIngredientParser',
    'BaseRecipeParser',
    'get_ingredient_parser',
    'ParserRegistry',
    'GenericTextParser',
    'MixedFormatParser',
    'CompuChefParser',
    'RicetteMdParser',
    'RecipeMLParser',
    'EdnaParser',
    'TwentyKRecipesParser',
    'RicetteJsonParser',
    'get_sqlite_schema_registry',
    'SqliteRecipeSchema',
    'SqliteSchemaRegistry',
    'RicetteParser',
    'VittRecipesParser',
    'NYCParser',
    'SqliteRecipeParser',
    'HtmlParser',
    'LLMRecipeParser',
    'MicroCookParser',
    'CookwareCSVParser',
    'MealMasterParser',
    'MasterCookParser',
    'PdfParser',
    'ImageParser',
    'CsvParser',
]
