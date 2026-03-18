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


def _sqlite_text_factory(b: bytes) -> str:
    """Decode SQLite TEXT bytes, falling back through common encodings."""
    for enc in ('utf-8', 'latin-1', 'cp1252'):
        try:
            return b.decode(enc)
        except UnicodeDecodeError:
            continue
    return b.decode('utf-8', errors='replace')


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
            connection.row_factory = sqlite3.Row
            # Decode bytes at the SQLite layer so _safe_str fields are already str
            connection.text_factory = _sqlite_text_factory

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
        # Hoist column lookups — these never change across rows
        title_col = next((col.name for col in self.schema.recipe_columns if col.attribute == 'title'), None)
        id_col = next((col.name for col in self.schema.recipe_columns if col.attribute == 'id'), None)

        query = f"SELECT * FROM {self.schema.recipes_table}"
        self._log_query(query)
        cursor = connection.cursor()
        cursor.execute(query)

        # Pre-check field existence once from cursor metadata
        col_names = {desc[0] for desc in cursor.description} if cursor.description else set()
        has_ing_field = bool(self.schema.ingredients_field and self.schema.ingredients_field in col_names)
        has_inst_field = bool(self.schema.instructions_field and self.schema.instructions_field in col_names)

        for row in cursor:
            recipe = Recipe(source_file="sqlite", source_format=self.source_format)
            recipe.sqlite_table = self.sqlite_table
            recipe.source_file = self.sqlite_db_path

            recipe_id = None
            if id_col:
                recipe_id = self._safe_str(row[id_col])
                recipe.sqlite_id = recipe_id

            # Try to get title from lookup table if configured
            if self.schema.recipe_title_source and recipe_id is not None:
                try:
                    title_cursor = connection.cursor()
                    title_query = (
                        f"SELECT {self.schema.recipe_title_source.title_column}"
                        f" FROM {self.schema.recipe_title_source.table_name}"
                        f" WHERE {self.schema.recipe_title_source.key_column} = ?"
                    )
                    self._log_query(title_query + f"; ? = {recipe_id}")
                    title_cursor.execute(title_query, (recipe_id,))
                    title_row = title_cursor.fetchone()
                    if title_row:
                        recipe.title = self._safe_str(title_row[0])
                except Exception as e:
                    logger.warning(f"Failed to get title for recipe {recipe_id}: {e}")

            if not recipe.title and title_col:
                recipe.title = self._safe_str(row[title_col])

            if has_ing_field:
                ing_text = self._safe_str(row[self.schema.ingredients_field])
                if ing_text:
                    for ing_line in ing_text.split(self.schema.ingredients_delimiter):
                        ing_line = ing_line.strip()
                        if ing_line:
                            recipe.ingredients.append(self.ingredient_parser.parse(ing_line))

            if has_inst_field:
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
        """Parse recipes where ingredients are in a separate table.

        Fetches all ingredients in a single query and groups them by recipe ID,
        avoiding the N+1 query problem (one query per recipe).
        """
        if not self.schema.ingredients_table:
            return

        ing_schema = self.schema.ingredients_table

        # Hoist column lookups — these never change across rows
        title_col = next((col.name for col in self.schema.recipe_columns if col.attribute == 'title'), None)
        id_col = next((col.name for col in self.schema.recipe_columns if col.attribute == 'id'), None)

        # Pre-fetch ALL ingredients in one query (N+1 → 2 queries total)
        unit_expr = ing_schema.unit_column if ing_schema.unit_column else "''"
        ing_query = (
            f"SELECT {ing_schema.id_column} AS _rid,"
            f" {ing_schema.quantity_column} AS _qty,"
            f" {unit_expr} AS _unit,"
            f" {ing_schema.name_column} AS _name"
            f" FROM {ing_schema.table_name}"
        )
        self._log_query(ing_query)
        ingredients_by_id: dict[str, list[Ingredient]] = {}
        try:
            ing_cursor = connection.cursor()
            ing_cursor.execute(ing_query)
            for ing_row in ing_cursor:
                rid = self._safe_str(ing_row['_rid'])
                qty = self._safe_str(ing_row['_qty'])
                unit = self._safe_str(ing_row['_unit'])
                name = self._safe_str(ing_row['_name'])
                ing_str = " ".join(part for part in (qty, unit, name) if part)
                if ing_str:
                    ingredients_by_id.setdefault(rid, []).append(
                        self.ingredient_parser.parse(ing_str)
                    )
        except Exception as e:
            logger.warning(f"Failed to pre-fetch ingredients: {e}")

        recipe_query = f"SELECT * FROM {self.schema.recipes_table}"
        self._log_query(recipe_query)
        cursor = connection.cursor()
        cursor.execute(recipe_query)

        # Pre-check field existence once from cursor metadata
        col_names = {desc[0] for desc in cursor.description} if cursor.description else set()
        has_inst_field = bool(self.schema.instructions_field and self.schema.instructions_field in col_names)

        for row in cursor:
            recipe = Recipe(source_file="sqlite", source_format=self.source_format)
            recipe.sqlite_table = self.sqlite_table
            recipe.source_file = self.sqlite_db_path

            recipe_id = None
            if id_col:
                recipe_id = self._safe_str(row[id_col])
                recipe.sqlite_id = recipe_id

            # Try to get title from lookup table if configured
            if self.schema.recipe_title_source and recipe_id is not None:
                try:
                    title_cursor = connection.cursor()
                    title_query = (
                        f"SELECT {self.schema.recipe_title_source.title_column}"
                        f" FROM {self.schema.recipe_title_source.table_name}"
                        f" WHERE {self.schema.recipe_title_source.key_column} = ?"
                    )
                    self._log_query(title_query + f"; ? = {recipe_id}")
                    title_cursor.execute(title_query, (recipe_id,))
                    title_row = title_cursor.fetchone()
                    if title_row:
                        recipe.title = self._safe_str(title_row[0])
                except Exception as e:
                    logger.warning(f"Failed to get title for recipe {recipe_id}: {e}")

            if not recipe.title and title_col:
                recipe.title = self._safe_str(row[title_col])

            # O(1) dict lookup instead of per-recipe SQL query
            if recipe_id is not None:
                recipe.ingredients = ingredients_by_id.get(recipe_id, [])

            if has_inst_field:
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
        """Parse recipes where ingredients are linked via junction table.

        Pre-loads the quantity lookup table (if any) and pre-fetches all junction
        rows to avoid per-recipe and per-ingredient queries.
        """
        if not self.schema.ingredients_junction:
            return

        junction = self.schema.ingredients_junction

        # Hoist column lookups — these never change across rows
        title_col = next((col.name for col in self.schema.recipe_columns if col.attribute == 'title'), None)
        id_col = next((col.name for col in self.schema.recipe_columns if col.attribute == 'id'), None)

        # Pre-load quantity lookup table entirely into memory (it's typically small)
        qty_lookup: dict[str, str] = {}
        if junction.quantity_table:
            qty_query = (
                f"SELECT {junction.quantity_table.id_column},"
                f" {junction.quantity_table.name_column}"
                f" FROM {junction.quantity_table.table_name}"
            )
            self._log_query(qty_query)
            try:
                qty_cursor = connection.cursor()
                qty_cursor.execute(qty_query)
                for qty_row in qty_cursor:
                    qty_lookup[self._safe_str(qty_row[0])] = self._safe_str(qty_row[1])
            except Exception as e:
                logger.warning(f"Failed to pre-load quantity table: {e}")

        # Pre-fetch all junction rows grouped by recipe ID
        order_clause = f" ORDER BY {junction.junction_table}.{junction.order_by}" if junction.order_by else ""
        unit_expr = junction.unit_column if junction.unit_column else "''"
        junc_query = (
            f"SELECT {junction.junction_table}.{junction.recipe_id_column} AS _rid,"
            f" {junction.quantity_column} AS _qty_id,"
            f" {unit_expr} AS _unit,"
            f" {junction.ingredient_table.name_column} AS _ing_name"
            f" FROM {junction.junction_table}"
            f" JOIN {junction.ingredient_table.table_name}"
            f"   ON {junction.junction_table}.{junction.ingredient_id_column}"
            f"    = {junction.ingredient_table.table_name}.{junction.ingredient_table.id_column}"
            f"{order_clause}"
        )
        self._log_query(junc_query)
        ingredients_by_id: dict[str, list[Ingredient]] = {}
        try:
            junc_cursor = connection.cursor()
            junc_cursor.execute(junc_query)
            for junc_row in junc_cursor:
                rid = self._safe_str(junc_row['_rid'])
                qty_id = self._safe_str(junc_row['_qty_id'])
                unit = self._safe_str(junc_row['_unit'])
                name = self._safe_str(junc_row['_ing_name'])
                # Resolve quantity from pre-loaded table (O(1)) or use value directly
                qty = qty_lookup.get(qty_id, qty_id) if junction.quantity_table else qty_id
                ing_str = " ".join(part for part in (qty, unit, name) if part)
                if ing_str:
                    ingredients_by_id.setdefault(rid, []).append(
                        self.ingredient_parser.parse(ing_str)
                    )
        except Exception as e:
            logger.warning(f"Failed to pre-fetch junction ingredients: {e}")

        recipe_query = f"SELECT * FROM {self.schema.recipes_table}"
        self._log_query(recipe_query)
        cursor = connection.cursor()
        cursor.execute(recipe_query)

        col_names = {desc[0] for desc in cursor.description} if cursor.description else set()
        has_inst_field = bool(self.schema.instructions_field and self.schema.instructions_field in col_names)

        for row in cursor:
            recipe = Recipe(source_file="sqlite", source_format=self.source_format)
            recipe.sqlite_table = self.sqlite_table
            recipe.source_file = self.sqlite_db_path

            recipe_id = None
            if id_col:
                recipe.sqlite_id = self._safe_str(row[id_col])
                recipe_id = row[id_col]

            # Try to get title from lookup table if configured
            if self.schema.recipe_title_source and recipe_id is not None:
                try:
                    title_cursor = connection.cursor()
                    title_query = (
                        f"SELECT {self.schema.recipe_title_source.title_column}"
                        f" FROM {self.schema.recipe_title_source.table_name}"
                        f" WHERE {self.schema.recipe_title_source.key_column} = ?"
                    )
                    self._log_query(title_query + f"; ? = {recipe_id}")
                    title_cursor.execute(title_query, (recipe_id,))
                    title_row = title_cursor.fetchone()
                    if title_row:
                        recipe.title = self._safe_str(title_row[0])
                except Exception as e:
                    logger.warning(f"Failed to get title for recipe {recipe_id}: {e}")

            if not recipe.title and title_col:
                recipe.title = self._safe_str(row[title_col])

            # O(1) dict lookup instead of per-recipe query
            if recipe_id is not None:
                recipe.ingredients = ingredients_by_id.get(self._safe_str(recipe_id), [])

            if has_inst_field:
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
            # Fallback path — normally handled by _sqlite_text_factory at connection level
            for encoding in ['utf-8', 'latin-1', 'iso-8859-1', 'cp1252']:
                try:
                    return value.decode(encoding)
                except (UnicodeDecodeError, LookupError):
                    continue
            return value.decode('utf-8', errors='replace')

        return str(value)
