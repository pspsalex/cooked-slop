# SPDX-License-Identifier: MIT
from typing import List
import re
import csv
from pathlib import Path
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
    """SQLite database recipe parsing using schema configuration."""
    def __init__(self, ingredient_parser: BaseIngredientParser):
        super().__init__(ingredient_parser)
        self.source_format = "SQLite"

    def parse_file(self, filepath: str) -> List[Recipe]:
        # Import here to avoid circular imports
        from .sqlite_parser import SqliteRecipeParser
        parser = SqliteRecipeParser(self.ingredient_parser)
        return parser.parse_file(filepath)

class CsvParser(BaseRecipeParser):
    """CSV recipe parser with format detection."""
    def __init__(self, ingredient_parser: BaseIngredientParser, format_hint: str = None):
        super().__init__(ingredient_parser)
        self.source_format = "CSV"
        self.format_hint = format_hint

    def parse_file(self, filepath: str) -> List[Recipe]:
        from .detection import get_detection_registry, Format
        from .twentykrecipes import TwentyKRecipesParser
        
        recipes = []
        db_path = Path(filepath)
        
        # Try to detect CSV format
        registry = get_detection_registry()
        result = registry.detect(db_path)
        
        if result.format == Format.CSV_20KRECIPES:
            parser = TwentyKRecipesParser(self.ingredient_parser)
            return parser.parse_file(filepath)
        elif result.format == Format.CSV_GENERIC:
            return self._parse_generic_csv(filepath)
        
        # Fallback to generic
        return self._parse_generic_csv(filepath)
    
    def _parse_generic_csv(self, filepath: str) -> List[Recipe]:
        """Generic CSV parser for common recipe layouts."""
        recipes = []
        try:
            with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
                # Detect delimiter
                sample = f.readline()
                f.seek(0)
                delimiter = self._detect_delimiter(sample)
                
                reader = csv.DictReader(f, delimiter=delimiter)
                for row in reader:
                    # Find title column (case-insensitive)
                    title = None
                    for key in ['title', 'name', 'recipe_name', 'recipe name']:
                        if key in [k.lower() for k in row.keys()]:
                            title = row[next(k for k in row.keys() if k.lower() == key)]
                            break
                    
                    if not title:
                        continue
                    
                    recipe = Recipe(source_file=filepath, source_format=self.source_format)
                    recipe.title = title
                    
                    # Find ingredients column
                    for key in ['ingredients', 'ingredient', 'ingred', 'ingredient_list']:
                        ing_key = next((k for k in row.keys() if k.lower() == key), None)
                        if ing_key and row[ing_key]:
                            for ing_str in re.split(r'[;|\n]', row[ing_key]):
                                if ing_str.strip():
                                    recipe.ingredients.append(self.ingredient_parser.parse(ing_str.strip()))
                            break
                    
                    # Find instructions column
                    for key in ['instructions', 'instruction', 'directions', 'method', 'instruct', 'steps']:
                        inst_key = next((k for k in row.keys() if k.lower() == key), None)
                        if inst_key and row[inst_key]:
                            recipe.instructions = [i.strip() for i in row[inst_key].split('\n') if i.strip()]
                            break
                    
                    recipes.append(recipe)
        except Exception as e:
            print(f"{Colors.YELLOW}Error parsing CSV {filepath}: {e}{Colors.ENDC}")
        return recipes
    
    def _detect_delimiter(self, sample: str) -> str:
        """Detect CSV delimiter from sample line."""
        delimiters = [',', ';', '\t', '|']
        max_splits = 0
        best_delim = ','
        for delim in delimiters:
            splits = sample.count(delim)
            if splits > max_splits:
                max_splits = splits
                best_delim = delim
        return best_delim
