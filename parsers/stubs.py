# SPDX-License-Identifier: MIT
from typing import List
import re
from .models import Recipe, Ingredient
from .base import BaseRecipeParser, BaseIngredientParser

class Colors:
    YELLOW = '\033[93m'
    ENDC = '\033[0m'

class PdfParser(BaseRecipeParser):
    """Stub for PDF recipe parsing."""
    def __init__(self, ingredient_parser: BaseIngredientParser):
        super().__init__(ingredient_parser)
        self.source_format = "PDF"

    def parse_file(self, filepath: str) -> List[Recipe]:
        print(f"{Colors.YELLOW}Note: PDF parser is a stub. Requires 'pdfminer.six' or 'pypdf' for implementation.{Colors.ENDC}")
        return []

class ImageParser(BaseRecipeParser):
    """Stub for Image/OCR recipe parsing."""
    def __init__(self, ingredient_parser: BaseIngredientParser):
        super().__init__(ingredient_parser)
        self.source_format = "Image/OCR"

    def parse_file(self, filepath: str) -> List[Recipe]:
        print(f"{Colors.YELLOW}Note: Image parser is a stub. Requires 'tesseract' or Cloud Vision API.{Colors.ENDC}")
        return []

class SqliteParser(BaseRecipeParser):
    """Stub for SQLite database recipe parsing."""
    def __init__(self, ingredient_parser: BaseIngredientParser):
        super().__init__(ingredient_parser)
        self.source_format = "SQLite"

    def parse_file(self, filepath: str) -> List[Recipe]:
        print(f"{Colors.YELLOW}Note: SQLite parser is a stub. Requires schema mapping for specific apps.{Colors.ENDC}")
        return []

class CsvParser(BaseRecipeParser):
    """Simple CSV recipe parser."""
    def __init__(self, ingredient_parser: BaseIngredientParser):
        super().__init__(ingredient_parser)
        self.source_format = "CSV"

    def parse_file(self, filepath: str) -> List[Recipe]:
        import csv
        recipes = []
        try:
            with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    # Basic mapping assuming some common headers
                    title = row.get('title') or row.get('name') or row.get('Recipe Name')
                    if not title: continue
                    
                    recipe = Recipe(source_file=filepath, source_format=self.source_format)
                    recipe.title = title
                    
                    # Try to find ingredients column
                    ings_raw = row.get('ingredients') or row.get('Ingredients')
                    if ings_raw:
                        # Assume some delimiter
                        for ing_str in re.split(r'[;|\n]', ings_raw):
                            if ing_str.strip():
                                recipe.ingredients.append(self.ingredient_parser.parse(ing_str.strip()))
                                
                    # Try to find instructions column
                    inst_raw = row.get('instructions') or row.get('Directions') or row.get('Methods')
                    if inst_raw:
                        recipe.instructions = [i.strip() for i in inst_raw.split('\n') if i.strip()]
                        
                    recipes.append(recipe)
        except Exception as e:
            print(f"{Colors.YELLOW}Error parsing CSV {filepath}: {e}{Colors.ENDC}")
        return recipes
