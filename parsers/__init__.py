# SPDX-License-Identifier: MIT
import importlib
import pkgutil
from pathlib import Path

# Explicit core exports
from .models import Recipe, Ingredient
from .base import BaseIngredientParser, BaseRecipeParser
from .ingredients import get_ingredient_parser
from .registry import ParserRegistry

# Auto-discover and import all modules in parsers/ so @ParserRegistry.register fires
_package_dir = str(Path(__file__).parent)
for _, module_name, is_pkg in pkgutil.iter_modules([_package_dir]):
    # Skip private modules or subpackages that handle their own initialization
    if not module_name.startswith('_'):
        importlib.import_module(f'.{module_name}', __package__)

# Explicitly discover sqlite parser subpackage
try:
    importlib.import_module('.sqlite', __package__)
except ImportError:
    pass

__all__ = [
    'Recipe',
    'Ingredient',
    'BaseIngredientParser',
    'BaseRecipeParser',
    'get_ingredient_parser',
    'ParserRegistry',
]
