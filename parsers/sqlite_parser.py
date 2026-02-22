# SPDX-License-Identifier: MIT
"""
SQLite database recipe parser.

Supports multiple schema patterns through configuration.
"""

import sqlite3
from pathlib import Path
from typing import List, Optional

from .base import BaseRecipeParser, BaseIngredientParser
from .models import Recipe, Ingredient
from .sqlite_config import SqliteRecipeSchema, get_sqlite_schema_registry


class SqliteRecipeParser(BaseRecipeParser):
    """Parse recipes from SQLite databases."""
    
    def __init__(self, ingredient_parser: BaseIngredientParser, schema: Optional[SqliteRecipeSchema] = None):
        super().__init__(ingredient_parser)
        self.source_format = "SQLite"
        self.schema = schema
    
    def parse_file(self, filepath: str) -> List[Recipe]:
        """Parse recipes from SQLite database file."""
        db_path = Path(filepath)
        
        # Auto-detect schema if not provided
        if not self.schema:
            registry = get_sqlite_schema_registry()
            self.schema = registry.detect_schema(db_path)
            
            if not self.schema:
                print(f"Warning: Could not detect SQLite schema for {filepath}")
                return []
        
        return self.parse_content("", filepath)
    
    def parse_content(self, content: str, filepath: str) -> List[Recipe]:
        """Parse recipes from SQLite database."""
        if not self.schema:
            return []
        
        recipes = []
        try:
            connection = sqlite3.connect(filepath)
            connection.row_factory = sqlite3.Row  # Access columns by name
            
            if self.schema.ingredients_field:
                recipes = self._parse_with_ingredients_field(connection)
            elif self.schema.ingredients_table:
                recipes = self._parse_with_ingredients_table(connection)
            elif self.schema.ingredients_junction:
                recipes = self._parse_with_junction_table(connection)
            else:
                print(f"Warning: Schema {self.schema.name} has no ingredients configuration")
            
            connection.close()
        except Exception as e:
            print(f"Error parsing SQLite database {filepath}: {e}")
        
        return recipes
    
    def _parse_with_ingredients_field(self, connection: sqlite3.Connection) -> List[Recipe]:
        """Parse recipes where ingredients are in a single field (newline or delimiter separated)."""
        recipes = []
        cursor = connection.cursor()
        
        # Get all columns from recipes table
        cursor.execute(f"SELECT * FROM {self.schema.recipes_table}")
        
        for row in cursor.fetchall():
            recipe = Recipe(source_file="sqlite", source_format=self.source_format)
            
            # Extract mapped columns
            title_col = next((col.name for col in self.schema.recipe_columns if col.attribute == 'title'), None)
            if title_col:
                recipe.title = str(row[title_col] or "")
            
            # Extract ingredients from field
            if self.schema.ingredients_field in row.keys():
                ing_text = row[self.schema.ingredients_field]
                if ing_text:
                    for ing_line in ing_text.split(self.schema.ingredients_delimiter):
                        ing_line = ing_line.strip()
                        if ing_line:
                            recipe.ingredients.append(self.ingredient_parser.parse(ing_line))
            
            # Extract instructions from field
            if self.schema.instructions_field and self.schema.instructions_field in row.keys():
                inst_text = row[self.schema.instructions_field]
                if inst_text:
                    recipe.instructions = [
                        line.strip() 
                        for line in inst_text.split(self.schema.instructions_delimiter) 
                        if line.strip()
                    ]
            
            if recipe.title:
                recipes.append(recipe)
        
        return recipes
    
    def _parse_with_ingredients_table(self, connection: sqlite3.Connection) -> List[Recipe]:
        """Parse recipes where ingredients are in a separate table."""
        recipes = []
        
        if not self.schema.ingredients_table:
            return recipes
        
        cursor = connection.cursor()
        ing_schema = self.schema.ingredients_table
        
        # Get all columns from recipes table
        cursor.execute(f"SELECT * FROM {self.schema.recipes_table}")
        
        for row in cursor.fetchall():
            recipe = Recipe(source_file="sqlite", source_format=self.source_format)
            
            # Extract mapped columns
            title_col = next((col.name for col in self.schema.recipe_columns if col.attribute == 'title'), None)
            recipe_id_col = next((col.name for col in self.schema.recipe_columns if col.attribute == 'id'), None)
            
            if title_col:
                recipe.title = str(row[title_col] or "")
            
            # Get recipe ID if available
            recipe_id = None
            if recipe_id_col:
                recipe_id = row[recipe_id_col]
            
            # For now, assume junction table links recipes by ID
            # This would need to be extended for direct relationships
            if recipe_id is not None:
                # Query ingredients table - this is a placeholder
                # In reality, you'd need a junction table or foreign key
                pass
            
            # Extract instructions
            if self.schema.instructions_field and self.schema.instructions_field in row.keys():
                inst_text = row[self.schema.instructions_field]
                if inst_text:
                    recipe.instructions = [
                        line.strip()
                        for line in inst_text.split(self.schema.instructions_delimiter)
                        if line.strip()
                    ]
            
            if recipe.title:
                recipes.append(recipe)
        
        return recipes
    
    def _parse_with_junction_table(self, connection: sqlite3.Connection) -> List[Recipe]:
        """Parse recipes where ingredients are linked via junction table."""
        recipes = []
        
        if not self.schema.ingredients_junction:
            return recipes
        
        cursor = connection.cursor()
        junction = self.schema.ingredients_junction
        
        # Get all recipes
        cursor.execute(f"SELECT * FROM {self.schema.recipes_table}")
        
        for row in cursor.fetchall():
            recipe = Recipe(source_file="sqlite", source_format=self.source_format)
            
            # Extract title
            title_col = next((col.name for col in self.schema.recipe_columns if col.attribute == 'title'), None)
            if title_col:
                recipe.title = str(row[title_col] or "")
            
            # Get recipe ID
            recipe_id_col = next((col.name for col in self.schema.recipe_columns if col.attribute == 'id'), None)
            if recipe_id_col:
                recipe_id = row[recipe_id_col]
                
                # Query junction table for ingredients
                query = f"""
                    SELECT 
                        {junction.quantity_column} as qty,
                        {junction.unit_column or "''" } as unit,
                        {junction.ingredient_table.name_column} as ing_name
                    FROM {junction.junction_table}
                    JOIN {junction.ingredient_table.table_name} 
                        ON {junction.junction_table}.{junction.ingredient_id_column} = 
                           {junction.ingredient_table.table_name}.{junction.ingredient_table.id_column}
                    WHERE {junction.junction_table}.{junction.recipe_id_column} = ?
                """
                
                try:
                    ing_cursor = connection.cursor()
                    ing_cursor.execute(query, (recipe_id,))
                    
                    for ing_row in ing_cursor.fetchall():
                        qty = ing_row['qty']
                        unit = ing_row['unit']
                        name = ing_row['ing_name']
                        
                        # Build ingredient string
                        ing_str = ""
                        if qty:
                            ing_str += str(qty)
                        if unit:
                            ing_str += f" {unit}" if ing_str else unit
                        if name:
                            ing_str += f" {name}" if ing_str else name
                        
                        if ing_str:
                            recipe.ingredients.append(self.ingredient_parser.parse(ing_str))
                except Exception as e:
                    print(f"Warning: Failed to get ingredients for recipe {recipe_id}: {e}")
            
            # Extract instructions
            if self.schema.instructions_field and self.schema.instructions_field in row.keys():
                inst_text = row[self.schema.instructions_field]
                if inst_text:
                    recipe.instructions = [
                        line.strip()
                        for line in inst_text.split(self.schema.instructions_delimiter)
                        if line.strip()
                    ]
            
            if recipe.title:
                recipes.append(recipe)
        
        return recipes
