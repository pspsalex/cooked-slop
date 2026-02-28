# SPDX-License-Identifier: MIT
"""
Parser factory with pluggable format detection.

This module orchestrates format detection and parser selection using:
1. The new detection registry for extensible format detection
2. MixedFormatParser only for mastercook/mealmaster/compuchef
3. Other formats applied to entire file
"""

import re
from pathlib import Path
from typing import Optional, List
from .models import Recipe, Ingredient
from .base import BaseRecipeParser, BaseIngredientParser
from .mealmaster import MealMasterParser
from .mastercook import MasterCookParser
from .compuchef import CompuChefParser
from .ricette import RicetteParser
from .ricette_md import RicetteMdParser
from .edna import EdnaParser
from .nyc import NYCParser
from .html_parser import HtmlParser
from .generic import GenericTextParser
from .stubs import PdfParser, ImageParser, CsvParser
from .recipeml import RecipeMLParser
from .twentykrecipes import TwentyKRecipesParser
from .ricette_json import RicetteJsonParser
from .vitt import VittRecipesParser



class ParserFactory:
    """
    Factory for selecting appropriate recipe parser based on file format.
    Delegates to ParserRegistry for format detection and parser instantiation.
    """

    @staticmethod
    def get_parser(filepath: Path, ingredient_parser: BaseIngredientParser,
                   format_name: Optional[str] = None, debug: bool = False,
                   use_nlp: bool = True) -> Optional[BaseRecipeParser]:
        """
        Get appropriate parser for file.

        Args:
            filepath: Path to recipe file
            ingredient_parser: Ingredient parser instance
            format_name: Optional format override (e.g., 'mastercook', 'csv_20krecipes')
            debug: Enable debug logging for SQL queries and other details
            use_nlp: Whether to use NLP-based parsing features (e.g., NLTK)
        """
        from .registry import ParserRegistry
        return ParserRegistry.get_parser(filepath, ingredient_parser, 
                                       format_name=format_name, debug=debug, 
                                       use_nlp=use_nlp)
