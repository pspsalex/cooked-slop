# SPDX-License-Identifier: MIT
"""
SQLite database schema configuration and auto-detection.

Supports multiple patterns for storing recipes:
1. Single recipes table with newline-separated ingredients in a field
2. Separate recipes and ingredients tables
3. Junction table linking recipes to predefined ingredients with quantities
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field, asdict
from typing import Optional, List, Dict, Set, Tuple, Any
from pathlib import Path
import sqlite3
import re
import yaml


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
class IngredientsJunctionSchema:
    """Schema for junction table linking recipes to predefined ingredients."""
    junction_table: str
    recipe_id_column: str  # Foreign key to recipes table
    ingredient_id_column: str  # Foreign key to ingredients table
    quantity_column: str
    unit_column: Optional[str] = None
    ingredient_table: IngredientTableSchema = None


@dataclass
class SqliteRecipeSchema:
    """Complete schema for a SQLite database containing recipes."""
    name: str  # Schema identifier
    recipes_table: str
    
    # Column mappings for recipe table
    recipe_columns: List[ColumnMapping] = field(default_factory=list)
    
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
    
    def to_dict(self) -> Dict:
        """Convert to dictionary for YAML serialization."""
        data = {
            'name': self.name,
            'recipes_table': self.recipes_table,
            'description': self.description,
            'version': self.version,
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
                'ingredient_table': {
                    'table': self.ingredients_junction.ingredient_table.table_name,
                    'id_column': self.ingredients_junction.ingredient_table.id_column,
                    'name_column': self.ingredients_junction.ingredient_table.name_column,
                } if self.ingredients_junction.ingredient_table else None,
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
                
                schema.ingredients_junction = IngredientsJunctionSchema(
                    junction_table=ing_cfg['junction_table'],
                    recipe_id_column=ing_cfg['recipe_id_column'],
                    ingredient_id_column=ing_cfg['ingredient_id_column'],
                    quantity_column=ing_cfg['quantity_column'],
                    unit_column=ing_cfg.get('unit_column'),
                    ingredient_table=ing_table,
                )
        
        # Parse instructions
        if 'instructions' in data:
            inst_cfg = data['instructions']
            schema.instructions_field = inst_cfg.get('field')
            schema.instructions_delimiter = inst_cfg.get('delimiter', '\n')
        
        return schema


class SqliteSchemaDetector(ABC):
    """Abstract base for auto-detecting SQLite recipe database schemas."""
    
    @abstractmethod
    def detect(self, connection: sqlite3.Connection) -> Optional[SqliteRecipeSchema]:
        """Detect if this database matches the schema pattern."""
        pass
    
    @abstractmethod
    def priority(self) -> int:
        """Lower numbers = higher priority."""
        pass


class SingleTableWithFieldDetector(SqliteSchemaDetector):
    """Detects: Single recipes table with newline-separated ingredients in a field."""
    
    def detect(self, connection: sqlite3.Connection) -> Optional[SqliteRecipeSchema]:
        cursor = connection.cursor()
        
        # Get all tables
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = [row[0] for row in cursor.fetchall()]
        
        # Look for a single table with recipe-like columns
        for table in tables:
            cursor.execute(f"PRAGMA table_info({table})")
            columns = {row[1]: row[2] for row in cursor.fetchall()}  # name -> type
            
            col_names_lower = {name.lower(): name for name in columns.keys()}
            
            # Check for required recipe columns
            has_title = any(k in col_names_lower for k in ['title', 'name', 'recipe_name', 'recipe'])
            has_ingredients = any(k in col_names_lower for k in ['ingredients', 'ingredient', 'ingred', 'ingredient_list'])
            
            if has_title and has_ingredients:
                # This looks like a recipes table with ingredients field
                title_col = next(k for k in col_names_lower if k in ['title', 'name', 'recipe_name', 'recipe'])
                ing_col = next(k for k in col_names_lower if k in ['ingredients', 'ingredient', 'ingred', 'ingredient_list'])
                inst_col = next((k for k in col_names_lower if k in ['instructions', 'instruction', 'directions', 'method', 'steps']), None)
                
                schema = SqliteRecipeSchema(
                    name=f"sqlite_single_table_{table}",
                    recipes_table=table,
                    recipe_columns=[
                        ColumnMapping(name=col_names_lower[title_col], attribute='title', required=True),
                    ],
                    ingredients_field=col_names_lower[ing_col],
                    instructions_field=col_names_lower[inst_col] if inst_col else None,
                )
                return schema
        
        return None
    
    def priority(self) -> int:
        return 10


class SeparateTablesDetector(SqliteSchemaDetector):
    """Detects: Recipes table + separate ingredients table."""
    
    def detect(self, connection: sqlite3.Connection) -> Optional[SqliteRecipeSchema]:
        cursor = connection.cursor()
        
        # Get all tables
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = set(row[0] for row in cursor.fetchall())
        
        # Look for recipes + ingredients pattern
        recipe_table = None
        ingredient_table = None
        
        for table in tables:
            cursor.execute(f"PRAGMA table_info({table})")
            columns = {row[1].lower(): row[1] for row in cursor.fetchall()}
            
            # Check for recipes table
            if any(k in columns for k in ['title', 'name', 'recipe']):
                has_ingredients = any(k in columns for k in ['ingredients', 'ingredient', 'ingred'])
                if not has_ingredients:
                    recipe_table = table
            
            # Check for ingredients table
            elif any(k in columns for k in ['name', 'ingredient_name', 'ingredient']):
                ingredient_table = table
        
        if recipe_table and ingredient_table:
            # Need to infer columns
            cursor.execute(f"PRAGMA table_info({recipe_table})")
            recipe_cols = {row[1].lower(): row[1] for row in cursor.fetchall()}
            title_col = next((recipe_cols[k] for k in ['title', 'name', 'recipe', 'recipe_name'] if k in recipe_cols), None)
            
            cursor.execute(f"PRAGMA table_info({ingredient_table})")
            ing_cols = {row[1].lower(): row[1] for row in cursor.fetchall()}
            name_col = next((ing_cols[k] for k in ['name', 'ingredient_name', 'ingredient'] if k in ing_cols), None)
            id_col = next((ing_cols[k] for k in ['id', 'ingredient_id'] if k in ing_cols), None)
            
            if title_col and name_col and id_col:
                schema = SqliteRecipeSchema(
                    name=f"sqlite_separate_tables",
                    recipes_table=recipe_table,
                    recipe_columns=[
                        ColumnMapping(name=title_col, attribute='title', required=True),
                    ],
                    ingredients_table=IngredientTableSchema(
                        table_name=ingredient_table,
                        id_column=id_col,
                        name_column=name_col,
                    ),
                )
                return schema
        
        return None
    
    def priority(self) -> int:
        return 20


class JunctionTableDetector(SqliteSchemaDetector):
    """Detects: Recipes + Ingredients + Junction table with quantities."""
    
    def detect(self, connection: sqlite3.Connection) -> Optional[SqliteRecipeSchema]:
        cursor = connection.cursor()
        
        # Get all tables
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = set(row[0] for row in cursor.fetchall())
        
        # Look for patterns like recipe_ingredient, recipe_ingred, etc.
        recipe_table = None
        ingredient_table = None
        junction_table = None
        
        for table in tables:
            cursor.execute(f"PRAGMA table_info({table})")
            columns = [row[1].lower() for row in cursor.fetchall()]
            
            if any(k in columns for k in ['title', 'name', 'recipe']):
                if 'ingredient' not in ' '.join(columns):
                    recipe_table = table
            
            elif any(k in columns for k in ['ingredient_name', 'ingredient', 'name']):
                if 'quantity' not in ' '.join(columns) and 'recipe' not in ' '.join(columns):
                    ingredient_table = table
            
            elif ('recipe' in ' '.join(columns) or 'recipe_id' in columns) and ('ingredient' in ' '.join(columns) or 'ingredient_id' in columns):
                if any(k in columns for k in ['quantity', 'qty', 'amount']):
                    junction_table = table
        
        if recipe_table and ingredient_table and junction_table:
            # Infer column names
            cursor.execute(f"PRAGMA table_info({recipe_table})")
            recipe_cols = {row[1].lower(): row[1] for row in cursor.fetchall()}
            title_col = next((recipe_cols[k] for k in ['title', 'name', 'recipe'] if k in recipe_cols), None)
            recipe_id_col = next((recipe_cols[k] for k in ['id', 'recipe_id'] if k in recipe_cols), None)
            
            cursor.execute(f"PRAGMA table_info({ingredient_table})")
            ing_cols = {row[1].lower(): row[1] for row in cursor.fetchall()}
            ing_id_col = next((ing_cols[k] for k in ['id', 'ingredient_id'] if k in ing_cols), None)
            ing_name_col = next((ing_cols[k] for k in ['name', 'ingredient', 'ingredient_name'] if k in ing_cols), None)
            
            cursor.execute(f"PRAGMA table_info({junction_table})")
            junc_cols = {row[1].lower(): row[1] for row in cursor.fetchall()}
            qty_col = next((junc_cols[k] for k in ['quantity', 'qty', 'amount'] if k in junc_cols), None)
            
            if title_col and recipe_id_col and ing_id_col and ing_name_col and qty_col:
                schema = SqliteRecipeSchema(
                    name="sqlite_junction_table",
                    recipes_table=recipe_table,
                    recipe_columns=[
                        ColumnMapping(name=title_col, attribute='title', required=True),
                        ColumnMapping(name=recipe_id_col, attribute='id'),
                    ],
                    ingredients_junction=IngredientsJunctionSchema(
                        junction_table=junction_table,
                        recipe_id_column=next(c for c in junc_cols if 'recipe' in c),
                        ingredient_id_column=next(c for c in junc_cols if 'ingredient' in c),
                        quantity_column=qty_col,
                        ingredient_table=IngredientTableSchema(
                            table_name=ingredient_table,
                            id_column=ing_id_col,
                            name_column=ing_name_col,
                        ),
                    ),
                )
                return schema
        
        return None
    
    def priority(self) -> int:
        return 30


class SqliteSchemaRegistry:
    """Registry for SQLite schema detection."""
    
    def __init__(self):
        self.detectors: List[SqliteSchemaDetector] = []
        self._register_default_detectors()
        self._schemas: Dict[str, SqliteRecipeSchema] = {}
    
    def _register_default_detectors(self):
        """Register standard detectors."""
        self.detectors.extend([
            SingleTableWithFieldDetector(),
            SeparateTablesDetector(),
            JunctionTableDetector(),
        ])
        self.detectors.sort(key=lambda d: d.priority())
    
    def register_detector(self, detector: SqliteSchemaDetector):
        """Register a custom detector."""
        self.detectors.append(detector)
        self.detectors.sort(key=lambda d: d.priority())
    
    def register_schema(self, schema: SqliteRecipeSchema):
        """Register a manually configured schema."""
        self._schemas[schema.name] = schema
    
    def load_schemas_from_yaml(self, config_dir: Path):
        """Load schemas from YAML files in directory."""
        if not config_dir.exists():
            return
        
        for yaml_file in config_dir.glob('*.yaml') | config_dir.glob('*.yml'):
            try:
                with open(yaml_file, 'r') as f:
                    data = yaml.safe_load(f)
                    if data:
                        schema = SqliteRecipeSchema.from_dict(data)
                        self._schemas[schema.name] = schema
            except Exception as e:
                print(f"Warning: Failed to load SQLite schema from {yaml_file}: {e}")
    
    def detect_schema(self, db_path: Path) -> Optional[SqliteRecipeSchema]:
        """Auto-detect database schema."""
        try:
            connection = sqlite3.connect(db_path)
            for detector in self.detectors:
                schema = detector.detect(connection)
                if schema:
                    connection.close()
                    return schema
            connection.close()
        except Exception:
            pass
        
        return None
    
    def get_schema(self, name: str) -> Optional[SqliteRecipeSchema]:
        """Get registered schema by name."""
        return self._schemas.get(name)


# Global registry instance
_global_sqlite_registry: Optional[SqliteSchemaRegistry] = None


def get_sqlite_schema_registry() -> SqliteSchemaRegistry:
    """Get the global SQLite schema registry."""
    global _global_sqlite_registry
    if _global_sqlite_registry is None:
        _global_sqlite_registry = SqliteSchemaRegistry()
    return _global_sqlite_registry
