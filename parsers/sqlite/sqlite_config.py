# SPDX-License-Identifier: MIT
"""
SQLite database schema configuration and auto-detection.

Supports multiple patterns for storing recipes:
1. Single recipes table with newline-separated ingredients in a field
2. Separate recipes and ingredients tables
3. Junction table linking recipes to predefined ingredients with quantities
"""

from dataclasses import dataclass, field, asdict
from typing import Optional, List, Dict, Tuple, Any
from pathlib import Path
import sqlite3
import yaml
import logging

logger = logging.getLogger(__name__)


@dataclass
class ColumnMapping:
    """Maps a column to a recipe attribute."""
    name: str  # Database column name
    attribute: str  # Recipe attribute (title, yield_amount, etc.)
    required: bool = False
    parser: Optional[str] = None  # Optional parser function name


@dataclass
class IngredientTableSchema:
    """Schema for a dedicated ingredients table."""
    table_name: str
    id_column: str
    name_column: str
    quantity_column: Optional[str] = None
    unit_column: Optional[str] = None
    comment_column: Optional[str] = None


@dataclass
class RecipeTitleLookup:
    """Schema for looking up recipe title from a separate table."""
    table_name: str
    key_column: str  # Column to join on (usually recipe ID)
    title_column: str  # Column containing the title


@dataclass
class IngredientsJunctionSchema:
    """Schema for junction table linking recipes to predefined ingredients."""
    junction_table: str
    recipe_id_column: str  # Foreign key to recipes table
    ingredient_id_column: str  # Foreign key to ingredients table
    quantity_column: str
    unit_column: Optional[str] = None
    ingredient_table: IngredientTableSchema = None
    quantity_table: Optional[IngredientTableSchema] = None  # Table with quantity lookup
    order_by: Optional[str] = None  # Column to order ingredients by (e.g., contatore)


@dataclass
class SqliteRecipeSchema:
    """Complete schema for a SQLite database containing recipes."""
    name: str  # Schema identifier
    recipes_table: str

    # Column mappings for recipe table
    recipe_columns: List[ColumnMapping] = field(default_factory=list)

    # Optional: lookup recipe title from separate table
    recipe_title_source: Optional[RecipeTitleLookup] = None

    # One of these three must be defined:

    # 1. Ingredients in a field (newline or delimiter separated)
    ingredients_field: Optional[str] = None
    ingredients_delimiter: str = "\n"

    # 2. Separate ingredients table
    ingredients_table: Optional[IngredientTableSchema] = None

    # 3. Junction table with predefined ingredients
    ingredients_junction: Optional[IngredientsJunctionSchema] = None

    # Instructions
    instructions_field: Optional[str] = None
    instructions_delimiter: str = "\n"

    # Metadata
    description: str = ""
    version: str = "1.0"
    config_file: Optional[str] = None

    def to_dict(self) -> Dict:
        """Convert to dictionary for YAML serialization."""
        data = {
            'name': self.name,
            'recipes_table': self.recipes_table,
            'description': self.description,
            'version': self.version,
        }

        # Add recipe title source if present
        if self.recipe_title_source:
            data['recipe_title_source'] = {
                'type': 'join',
                'table': self.recipe_title_source.table_name,
                'key_column': self.recipe_title_source.key_column,
                'title_column': self.recipe_title_source.title_column,
            }

        if self.recipe_columns:
            data['recipe_columns'] = [
                {
                    'name': col.name,
                    'attribute': col.attribute,
                    'required': col.required,
                    'parser': col.parser,
                }
                for col in self.recipe_columns if col.parser or col.required
            ]

        if self.ingredients_field:
            data['ingredients'] = {
                'type': 'field',
                'field': self.ingredients_field,
                'delimiter': self.ingredients_delimiter,
            }
        elif self.ingredients_table:
            data['ingredients'] = {
                'type': 'table',
                'table': self.ingredients_table.table_name,
                'id_column': self.ingredients_table.id_column,
                'name_column': self.ingredients_table.name_column,
                'quantity_column': self.ingredients_table.quantity_column,
                'unit_column': self.ingredients_table.unit_column,
                'comment_column': self.ingredients_table.comment_column,
            }
        elif self.ingredients_junction:
            data['ingredients'] = {
                'type': 'junction',
                'junction_table': self.ingredients_junction.junction_table,
                'recipe_id_column': self.ingredients_junction.recipe_id_column,
                'ingredient_id_column': self.ingredients_junction.ingredient_id_column,
                'quantity_column': self.ingredients_junction.quantity_column,
                'unit_column': self.ingredients_junction.unit_column,
                'order_by': self.ingredients_junction.order_by,
                'ingredient_table': {
                    'table': self.ingredients_junction.ingredient_table.table_name,
                    'id_column': self.ingredients_junction.ingredient_table.id_column,
                    'name_column': self.ingredients_junction.ingredient_table.name_column,
                } if self.ingredients_junction.ingredient_table else None,
                'quantity_table': {
                    'table': self.ingredients_junction.quantity_table.table_name,
                    'id_column': self.ingredients_junction.quantity_table.id_column,
                    'quantity_column': self.ingredients_junction.quantity_table.quantity_column,
                } if self.ingredients_junction.quantity_table else None,
            }

        if self.instructions_field:
            data['instructions'] = {
                'field': self.instructions_field,
                'delimiter': self.instructions_delimiter,
            }

        return data

    @classmethod
    def from_dict(cls, data: Dict) -> 'SqliteRecipeSchema':
        """Create schema from dictionary (parsed from YAML)."""
        schema = cls(
            name=data.get('name', 'custom'),
            recipes_table=data['recipes_table'],
            description=data.get('description', ''),
            version=data.get('version', '1.0'),
        )

        # Parse recipe title source lookup
        if 'recipe_title_source' in data:
            title_src = data['recipe_title_source']
            schema.recipe_title_source = RecipeTitleLookup(
                table_name=title_src['table'],
                key_column=title_src['key_column'],
                title_column=title_src['title_column'],
            )

        # Parse recipe columns
        if 'recipe_columns' in data:
            schema.recipe_columns = [
                ColumnMapping(
                    name=col['name'],
                    attribute=col['attribute'],
                    required=col.get('required', False),
                    parser=col.get('parser'),
                )
                for col in data['recipe_columns']
            ]

        # Parse ingredients configuration
        if 'ingredients' in data:
            ing_cfg = data['ingredients']
            ing_type = ing_cfg.get('type', 'field')

            if ing_type == 'field':
                schema.ingredients_field = ing_cfg.get('field')
                schema.ingredients_delimiter = ing_cfg.get('delimiter', '\n')

            elif ing_type == 'table':
                schema.ingredients_table = IngredientTableSchema(
                    table_name=ing_cfg['table'],
                    id_column=ing_cfg['id_column'],
                    name_column=ing_cfg['name_column'],
                    quantity_column=ing_cfg.get('quantity_column'),
                    unit_column=ing_cfg.get('unit_column'),
                    comment_column=ing_cfg.get('comment_column'),
                )

            elif ing_type == 'junction':
                ing_table_cfg = ing_cfg.get('ingredient_table')
                ing_table = None
                if ing_table_cfg:
                    ing_table = IngredientTableSchema(
                        table_name=ing_table_cfg['table'],
                        id_column=ing_table_cfg['id_column'],
                        name_column=ing_table_cfg['name_column'],
                    )

                qty_table_cfg = ing_cfg.get('quantity_table')
                qty_table = None
                if qty_table_cfg:
                    qty_table = IngredientTableSchema(
                        table_name=qty_table_cfg['table'],
                        id_column=qty_table_cfg['id_column'],
                        name_column=qty_table_cfg.get('quantity_column'),
                    )

                schema.ingredients_junction = IngredientsJunctionSchema(
                    junction_table=ing_cfg['junction_table'],
                    recipe_id_column=ing_cfg['recipe_id_column'],
                    ingredient_id_column=ing_cfg['ingredient_id_column'],
                    quantity_column=ing_cfg['quantity_column'],
                    unit_column=ing_cfg.get('unit_column'),
                    ingredient_table=ing_table,
                    quantity_table=qty_table,
                    order_by=ing_cfg.get('order_by'),
                )

        # Parse instructions
        if 'instructions' in data:
            inst_cfg = data['instructions']
            schema.instructions_field = inst_cfg.get('field')
            schema.instructions_delimiter = inst_cfg.get('delimiter', '\n')

        return schema

class SchemaValidator:
    """Validates if a database matches a schema configuration."""

    @staticmethod
    def validate_schema(connection: sqlite3.Connection, schema: SqliteRecipeSchema) -> Tuple[bool, float]:
        """
        Validate if a database matches the given schema.

        Returns:
            Tuple of (is_valid, confidence_score)
            - is_valid: True if all required tables and columns exist
            - confidence_score: 0.0-1.0 indicating how well the db matches the schema
        """
        try:
            cursor = connection.cursor()

            # Check if recipes table exists
            cursor.execute(f"SELECT name FROM sqlite_master WHERE type='table' AND name=?", (schema.recipes_table,))
            if not cursor.fetchone():
                return False, 0.0

            # Get columns in recipes table
            cursor.execute(f"PRAGMA table_info({schema.recipes_table})")
            recipe_cols = {row[1]: row[2] for row in cursor.fetchall()}  # name -> type
            recipe_cols_lower = {name.lower(): name for name in recipe_cols.keys()}

            # Check required recipe columns
            required_cols = [col for col in schema.recipe_columns if col.required]
            for col in required_cols:
                if col.name.lower() not in recipe_cols_lower and col.name not in recipe_cols:
                    return False, 0.0

            score = 0.0
            total_checks = 0

            # Check ingredients field if specified
            if schema.ingredients_field:
                total_checks += 1

                if schema.ingredients_field.lower() in recipe_cols_lower or schema.ingredients_field in recipe_cols:
                    score += 1.0

            # Check ingredients table if specified
            if schema.ingredients_table:
                total_checks += 3  # table + id_col + name_col

                ing_table = schema.ingredients_table

                cursor.execute(f"SELECT name FROM sqlite_master WHERE type='table' AND lower(name)=lower(?)", (ing_table.table_name,))
                if cursor.fetchone():
                    score += 1.0

                    cursor.execute(f"PRAGMA table_info({ing_table.table_name})")
                    ing_cols = {row[1] for row in cursor.fetchall()}
                    ing_cols_lower = {name.lower(): name for name in ing_cols}

                    if ing_table.id_column.lower() in ing_cols_lower or ing_table.id_column in ing_cols:
                        score += 1.0
                    if ing_table.name_column.lower() in ing_cols_lower or ing_table.name_column in ing_cols:
                        score += 1.0

            # Check junction table if specified
            if schema.ingredients_junction:
                total_checks += 4  # junction_table + recipe_id + ing_id + qty
                junction = schema.ingredients_junction

                cursor.execute(f"SELECT name FROM sqlite_master WHERE type='table' AND name=?", (junction.junction_table,))
                if cursor.fetchone():
                    score += 1.0

                    cursor.execute(f"PRAGMA table_info({junction.junction_table})")
                    junc_cols = {row[1] for row in cursor.fetchall()}
                    junc_cols_lower = {name.lower(): name for name in junc_cols}

                    if junction.recipe_id_column.lower() in junc_cols_lower or junction.recipe_id_column in junc_cols:
                        score += 1.0
                    if junction.ingredient_id_column.lower() in junc_cols_lower or junction.ingredient_id_column in junc_cols:
                        score += 1.0
                    if junction.quantity_column.lower() in junc_cols_lower or junction.quantity_column in junc_cols:
                        score += 1.0

                    # Check ingredient table
                    if junction.ingredient_table:
                        cursor.execute(f"SELECT name FROM sqlite_master WHERE type='table' AND name=?", (junction.ingredient_table.table_name,))
                        if cursor.fetchone():
                            cursor.execute(f"PRAGMA table_info({junction.ingredient_table.table_name})")
                            ing_cols = {row[1] for row in cursor.fetchall()}
                            ing_cols_lower = {name.lower(): name for name in ing_cols}

                            if junction.ingredient_table.id_column.lower() in ing_cols_lower or junction.ingredient_table.id_column in ing_cols:
                                total_checks += 1
                                score += 1.0
                            if junction.ingredient_table.name_column.lower() in ing_cols_lower or junction.ingredient_table.name_column in ing_cols:
                                total_checks += 1
                                score += 1.0

                    # Check quantity table if specified
                    if junction.quantity_table:
                        cursor.execute(f"SELECT name FROM sqlite_master WHERE type='table' AND name=?", (junction.quantity_table.table_name,))
                        if cursor.fetchone():
                            cursor.execute(f"PRAGMA table_info({junction.quantity_table.table_name})")
                            qty_cols = {row[1] for row in cursor.fetchall()}
                            qty_cols_lower = {name.lower(): name for name in qty_cols}

                            if junction.quantity_table.id_column.lower() in qty_cols_lower or junction.quantity_table.id_column in qty_cols:
                                total_checks += 1
                                score += 1.0
                            if junction.quantity_table.name_column and (junction.quantity_table.name_column.lower() in qty_cols_lower or junction.quantity_table.name_column in qty_cols):
                                total_checks += 1
                                score += 1.0

            # Check instructions field if specified
            if schema.instructions_field:
                total_checks += 1
                if schema.instructions_field.lower() in recipe_cols_lower or schema.instructions_field in recipe_cols:
                    score += 1.0

            # Minimum score must have all required components
            if total_checks > 0:
                confidence = score / total_checks
                return confidence > 0.5, confidence  # Valid if at least 50% match

            return True, 1.0  # Schema with no optional fields matches by default

        except Exception as e:
            logger.warning("Error validating schema: %s", e)
            return False, 0.0


class SqliteSchemaRegistry:
    """Registry for SQLite schema detection based on YAML configurations."""

    def __init__(self):
        self._schemas: Dict[str, SqliteRecipeSchema] = {}
        self._loaded = False

    def register_schema(self, schema: SqliteRecipeSchema):
        """Register a manually configured schema."""
        self._schemas[schema.name] = schema

    def load_schemas_from_yaml(self, config_dir: Path):
        """Load schemas from YAML files in directory."""
        if not config_dir.exists():
            return

        for yaml_file in config_dir.glob('*.y[am]*l'):
            try:
                with open(yaml_file, 'r') as f:
                    data = yaml.safe_load(f)
                    if data and isinstance(data, dict) and 'recipes_table' in data:
                        schema = SqliteRecipeSchema.from_dict(data)
                        schema.config_file = yaml_file.name
                        self._schemas[schema.name] = schema
            except Exception as e:
                logger.warning("Failed to load SQLite schema from %s: %s", yaml_file, e)

    def detect_schema(self, db_path: Path) -> Optional[SqliteRecipeSchema]:
        """
        Match database schema against all loaded YAML configurations.
        Returns the best matching configuration, or None if no good match found.
        """
        try:
            connection = sqlite3.connect(db_path)

            # Score all available schemas
            best_schema = None
            best_score = 0.0

            for schema_name, schema in self._schemas.items():
                is_valid, confidence = SchemaValidator.validate_schema(connection, schema)

                if is_valid and confidence > best_score:
                    best_score = confidence
                    best_schema = schema

            connection.close()

            if best_schema:
                logger.debug(f"Detected schema: {best_schema.name} (confidence: {best_score:.1%})")

            return best_schema

        except Exception as e:
            logger.warning("Error detecting schema for %s: %s", db_path, e)
            return None

    def get_schema(self, name: str) -> Optional[SqliteRecipeSchema]:
        """Get registered schema by name."""
        return self._schemas.get(name)

    def get_all_schemas(self) -> Dict[str, SqliteRecipeSchema]:
        """Get all registered schemas."""
        return dict(self._schemas)


# Global registry instance
_global_sqlite_registry: Optional[SqliteSchemaRegistry] = None


def get_sqlite_schema_registry() -> SqliteSchemaRegistry:
    """Get the global SQLite schema registry and auto-load YAML configs."""
    global _global_sqlite_registry
    if _global_sqlite_registry is None:
        _global_sqlite_registry = SqliteSchemaRegistry()

        # Auto-load YAML configurations from configs directory
        # Look for configs in multiple possible locations
        config_paths = [
            Path(__file__).parent.parent.parent / "configs",  # Relative to parsers module
            Path.cwd() / "configs",                      # In current working directory
        ]

        for config_dir in config_paths:
            if config_dir.exists():
                _global_sqlite_registry.load_schemas_from_yaml(config_dir)
                break  # Use first found configs directory

    return _global_sqlite_registry
