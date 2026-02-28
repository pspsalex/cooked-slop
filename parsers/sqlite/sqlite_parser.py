# SPDX-License-Identifier: MIT
"""
SQLite database recipe parser.

Supports multiple schema patterns through configuration.
"""

import logging
import sqlite3
from pathlib import Path
from typing import Iterator, Optional

from ..base import BaseRecipeParser, BaseIngredientParser
from ..models import Recipe, Ingredient
from .sqlite_config import SqliteRecipeSchema, get_sqlite_schema_registry
from ..registry import ParserRegistry

# Set up logger for this module
logger = logging.getLogger(__name__)


@ParserRegistry.register
class SqliteRecipeParser(BaseRecipeParser):
    """Parse recipes from SQLite databases."""

    @classmethod
    def format_id(cls) -> str:
        return "sqlite"

    @classmethod
    def priority(cls) -> int:
        return 25

    @classmethod
    def detect(cls, filepath: str, content_sample: str) -> float:
        from pathlib import Path
        path = Path(filepath)
        if path.suffix.lower() not in {'.sqlite', '.db', '.sqlite3'}:
            return 0.0

        try:
            with open(path, 'rb') as f:
                magic = f.read(16)
                if magic.startswith(b'SQLite format 3\x00'):
                    return 0.99
        except Exception:
            pass

        return 0.0

    def __init__(self, ingredient_parser: BaseIngredientParser, schema: Optional[SqliteRecipeSchema] = None, debug: bool = True):
        super().__init__(ingredient_parser)
        self.source_format = "SQLite"
        self.schema = schema
        self.sqlite_db_path = None
        self.sqlite_table = None
        self.debug = debug  # Set to False to suppress SQL query logging

    def parse_file(self, filepath: str) -> Iterator[Recipe]:
        """Parse recipes from SQLite database file."""
        db_path = Path(filepath)

        # Auto-detect schema if not provided
        if not self.schema:
            registry = get_sqlite_schema_registry()
            self.schema = registry.detect_schema(db_path)

            if not self.schema:
                logger.warning(f"Could not detect SQLite schema for {filepath}")
                return

        self.sqlite_db_path = str(db_path.resolve())
        self.sqlite_table = self.schema.recipes_table
        yield from self.parse_content("", filepath)

    def parse_content(self, content: str, filepath: str) -> Iterator[Recipe]:
        """Parse recipes from SQLite database, yielding each recipe as it's completed."""
        if not self.schema:
            return

        try:
            connection = sqlite3.connect(filepath)
            connection.row_factory = sqlite3.Row  # Access columns by name
            connection.text_factory = bytes  # Return bytes instead of trying UTF-8 decode

            if self.schema.ingredients_field:
                yield from self._parse_with_ingredients_field(connection)
            elif self.schema.ingredients_table:
                yield from self._parse_with_ingredients_table(connection)
            elif self.schema.ingredients_junction:
                yield from self._parse_with_junction_table(connection)
            else:
                logger.warning(f"Schema {self.schema.name} has no ingredients configuration")

            connection.close()
        except KeyboardInterrupt:
            logger.info("Interrupted by user (Ctrl+C)")
            return
        except Exception as e:
            logger.error(f"Error parsing SQLite database {filepath}: {e}")

    def _log_query(self, query: str):
        """Log SQL query at TRACE level if debug mode is enabled."""
        if self.debug:
            logger.log(5, f"[SQL] {query}")

    def _parse_with_ingredients_field(self, connection: sqlite3.Connection) -> Iterator[Recipe]:
        """Parse recipes where ingredients are in a single field (newline or delimiter separated)."""
        cursor = connection.cursor()

        # Get all columns from recipes table
        query = f"SELECT * FROM {self.schema.recipes_table}"
        self._log_query(query)
        cursor.execute(query)

        for row in cursor:
            recipe = Recipe(source_file="sqlite", source_format=self.source_format)
            recipe.sqlite_table = self.sqlite_table
            recipe.source_file = self.sqlite_db_path

            # Extract mapped columns
            title_col = next((col.name for col in self.schema.recipe_columns if col.attribute == 'title'), None)
            id_col = next((col.name for col in self.schema.recipe_columns if col.attribute == 'id'), None)

            recipe_id = None
            if id_col:
                recipe_id = self._safe_str(row[id_col])
                recipe.sqlite_id = recipe_id

            # Try to get title from lookup table if configured
            if self.schema.recipe_title_source and recipe_id is not None:
                try:
                    title_cursor = connection.cursor()
                    title_query = f"""
                        SELECT {self.schema.recipe_title_source.title_column}
                        FROM {self.schema.recipe_title_source.table_name}
                        WHERE {self.schema.recipe_title_source.key_column} = ?
                        """
                    self._log_query(title_query.strip() + f"; ? = {recipe_id}")
                    title_cursor.execute(title_query, (recipe_id,))
                    title_row = title_cursor.fetchone()
                    if title_row:
                        recipe.title = self._safe_str(title_row[0])
                except Exception as e:
                    logger.warning(f"Failed to get title for recipe {recipe_id}: {e}")

            # If no title from lookup, try direct column
            if not recipe.title and title_col:
                recipe.title = self._safe_str(row[title_col])

            # Extract ingredients from field
            if self.schema.ingredients_field in row.keys():
                ing_text = self._safe_str(row[self.schema.ingredients_field])
                if ing_text:
                    for ing_line in ing_text.split(self.schema.ingredients_delimiter):
                        ing_line = ing_line.strip()
                        if ing_line:
                            recipe.ingredients.append(self.ingredient_parser.parse(ing_line))

            # Extract instructions from field
            if self.schema.instructions_field and self.schema.instructions_field in row.keys():
                inst_text = self._safe_str(row[self.schema.instructions_field])
                if inst_text:
                    recipe.instructions = [
                        line.strip()
                        for line in inst_text.split(self.schema.instructions_delimiter)
                        if line.strip()
                    ]

            if recipe.title:
                yield recipe

    def _parse_with_ingredients_table(self, connection: sqlite3.Connection) -> Iterator[Recipe]:
        """Parse recipes where ingredients are in a separate table."""
        if not self.schema.ingredients_table:
            return

        cursor = connection.cursor()
        ing_schema = self.schema.ingredients_table

        # Get all columns from recipes table
        query = f"SELECT * FROM {self.schema.recipes_table}"
        self._log_query(query)
        cursor.execute(query)

        for row in cursor:
            recipe = Recipe(source_file="sqlite", source_format=self.source_format)
            recipe.sqlite_table = self.sqlite_table
            recipe.source_file = self.sqlite_db_path

            # Extract mapped columns
            title_col = next((col.name for col in self.schema.recipe_columns if col.attribute == 'title'), None)
            id_col = next((col.name for col in self.schema.recipe_columns if col.attribute == 'id'), None)
            recipe_id_col = next((col.name for col in self.schema.recipe_columns if col.attribute == 'id'), None)

            recipe_id = None
            if recipe_id_col:
                recipe_id = self._safe_str(row[recipe_id_col])
                recipe.sqlite_id = recipe_id

            # Try to get title from lookup table if configured
            if self.schema.recipe_title_source and recipe_id is not None:
                try:
                    title_cursor = connection.cursor()
                    title_query = f"""
                        SELECT {self.schema.recipe_title_source.title_column}
                        FROM {self.schema.recipe_title_source.table_name}
                        WHERE {self.schema.recipe_title_source.key_column} = ?
                    """
                    self._log_query(title_query.strip() + f"; ? = {recipe_id}")
                    title_cursor.execute(title_query, (recipe_id,))
                    title_row = title_cursor.fetchone()
                    if title_row:
                        recipe.title = self._safe_str(title_row[0])
                except Exception as e:
                    logger.warning(f"Failed to get title for recipe {recipe_id}: {e}")

            # If no title from lookup, try direct column
            if not recipe.title and title_col:
                recipe.title = self._safe_str(row[title_col])

            # Query ingredients table using recipe ID
            if recipe_id is not None:
                ing_query = f"""
                    SELECT
                        {ing_schema.quantity_column} as qty,
                        {ing_schema.unit_column or "''" } as unit,
                        {ing_schema.name_column} as ing_name
                    FROM {ing_schema.table_name}
                    WHERE {ing_schema.id_column} = ?
                """
                self._log_query(ing_query.strip() + f"; ? = {recipe_id}")

                try:
                    ing_cursor = connection.cursor()
                    ing_cursor.execute(ing_query, (recipe_id,))

                    for ing_row in ing_cursor:
                        qty = self._safe_str(ing_row['qty'])
                        unit = self._safe_str(ing_row['unit'])
                        name = self._safe_str(ing_row['ing_name'])

                        # Build ingredient string
                        ing_str = ""
                        if qty:
                            ing_str += qty
                        if unit:
                            ing_str += f" {unit}" if ing_str else unit
                        if name:
                            ing_str += f" {name}" if ing_str else name

                        if ing_str:
                            recipe.ingredients.append(self.ingredient_parser.parse(ing_str))
                except Exception as e:
                    logger.warning(f"Failed to get ingredients for recipe {recipe_id}: {e}")

            # Extract instructions
            if self.schema.instructions_field and self.schema.instructions_field in row.keys():
                inst_text = self._safe_str(row[self.schema.instructions_field])
                if inst_text:
                    recipe.instructions = [
                        line.strip()
                        for line in inst_text.split(self.schema.instructions_delimiter)
                        if line.strip()
                    ]

            if recipe.title:
                yield recipe

    def _parse_with_junction_table(self, connection: sqlite3.Connection) -> Iterator[Recipe]:
        """Parse recipes where ingredients are linked via junction table."""
        if not self.schema.ingredients_junction:
            return

        cursor = connection.cursor()
        junction = self.schema.ingredients_junction

        # Get all recipes
        query = f"SELECT * FROM {self.schema.recipes_table}"
        self._log_query(query)
        cursor.execute(query)

        for row in cursor:
            recipe = Recipe(source_file="sqlite", source_format=self.source_format)
            recipe.sqlite_table = self.sqlite_table
            recipe.source_file = self.sqlite_db_path

            # Extract title - either directly or from lookup table
            title_col = next((col.name for col in self.schema.recipe_columns if col.attribute == 'title'), None)
            recipe_id_col = next((col.name for col in self.schema.recipe_columns if col.attribute == 'id'), None)

            if recipe_id_col:
                recipe.sqlite_id = self._safe_str(row[recipe_id_col])
                recipe_id = row[recipe_id_col]

                # Try to get title from lookup table if configured
                if self.schema.recipe_title_source and recipe_id is not None:
                    try:
                        title_cursor = connection.cursor()
                        title_query = f"""
                            SELECT {self.schema.recipe_title_source.title_column}
                            FROM {self.schema.recipe_title_source.table_name}
                            WHERE {self.schema.recipe_title_source.key_column} = ?
                        """
                        self._log_query(title_query.strip() + f"; ? = {recipe_id}")
                        title_cursor.execute(title_query, (recipe_id,))
                        title_row = title_cursor.fetchone()
                        if title_row:
                            recipe.title = self._safe_str(title_row[0])
                    except Exception as e:
                        logger.warning(f"Failed to get title for recipe {recipe_id}: {e}")

            # If no title from lookup, try direct column
            if not recipe.title and title_col:
                recipe.title = self._safe_str(row[title_col])

            # Get ingredients from junction table
            if recipe_id is not None:
                # Build order by clause if specified
                order_clause = ""
                if junction.order_by:
                    order_clause = f" ORDER BY {junction.junction_table}.{junction.order_by}"

                # Query junction table for ingredients
                query = f"""
                    SELECT
                        {junction.quantity_column} as qty_id,
                        {junction.unit_column or "''" } as unit,
                        {junction.ingredient_table.name_column} as ing_name
                    FROM {junction.junction_table}
                    JOIN {junction.ingredient_table.table_name}
                        ON {junction.junction_table}.{junction.ingredient_id_column} =
                           {junction.ingredient_table.table_name}.{junction.ingredient_table.id_column}
                    WHERE {junction.junction_table}.{junction.recipe_id_column} = ?
                    {order_clause}
                """
                self._log_query(query.strip() + f"; ? = {recipe_id}")

                try:
                    ing_cursor = connection.cursor()
                    ing_cursor.execute(query, (recipe_id,))

                    for ing_row in ing_cursor:
                        qty_id = ing_row['qty_id']
                        unit = self._safe_str(ing_row['unit'])
                        name = self._safe_str(ing_row['ing_name'])

                        # Lookup quantity from quantita table if configured
                        qty = ""
                        if junction.quantity_table and qty_id is not None:
                            try:
                                qty_cursor = connection.cursor()
                                qty_query = f"""
                                    SELECT {junction.quantity_table.name_column}
                                    FROM {junction.quantity_table.table_name}
                                    WHERE {junction.quantity_table.id_column} = ?
                                """
                                self._log_query(qty_query.strip() + f"; ? = {qty_id}")
                                qty_cursor.execute(qty_query, (qty_id,))
                                qty_row = qty_cursor.fetchone()
                                if qty_row:
                                    qty = self._safe_str(qty_row[0])
                            except Exception as e:
                                logger.warning(f"Failed to get quantity for id {qty_id}: {e}")
                        else:
                            qty = self._safe_str(qty_id)

                        # Build ingredient string
                        ing_str = ""
                        if qty:
                            ing_str += qty
                        if unit:
                            ing_str += f" {unit}" if ing_str else unit
                        if name:
                            ing_str += f" {name}" if ing_str else name

                        if ing_str:
                            recipe.ingredients.append(self.ingredient_parser.parse(ing_str))
                except Exception as e:
                    logger.warning(f"Failed to get ingredients for recipe {recipe_id}: {e}")

            # Extract instructions
            if self.schema.instructions_field and self.schema.instructions_field in row.keys():
                inst_text = self._safe_str(row[self.schema.instructions_field])
                if inst_text:
                    recipe.instructions = [
                        line.strip()
                        for line in inst_text.split(self.schema.instructions_delimiter)
                        if line.strip()
                    ]

            if recipe.title:
                yield recipe

    def _safe_str(self, value) -> str:
        """Safely convert value to string, handling encoding errors and None values."""
        if value is None:
            return ""

        if isinstance(value, bytes):
            # Try UTF-8 first, then latin-1, then replace invalid chars
            for encoding in ['utf-8', 'latin-1', 'iso-8859-1', 'cp1252']:
                try:
                    return value.decode(encoding)
                except (UnicodeDecodeError, LookupError):
                    continue
            # Last resort: replace invalid bytes
            return value.decode('utf-8', errors='replace')

        return str(value)
