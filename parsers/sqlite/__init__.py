# SPDX-License-Identifier: MIT
"""SQLite parser subsystem for recipe databases with configurable schemas."""

from .sqlite_config import (
    ColumnMapping,
    IngredientTableSchema,
    IngredientsJunctionSchema,
    RecipeTitleLookup,
    SqliteRecipeSchema,
    SqliteSchemaRegistry,
    SchemaValidator,
    get_sqlite_schema_registry,
)
from .sqlite_parser import SqliteRecipeParser

__all__ = [
    'ColumnMapping',
    'IngredientTableSchema',
    'IngredientsJunctionSchema',
    'RecipeTitleLookup',
    'SqliteRecipeSchema',
    'SqliteSchemaRegistry',
    'SchemaValidator',
    'get_sqlite_schema_registry',
    'SqliteRecipeParser',
]
