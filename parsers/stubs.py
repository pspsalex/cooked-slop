# SPDX-License-Identifier: MIT
import csv
import logging
import re
from pathlib import Path
from typing import Iterator
from .models import Recipe
from .base import BaseRecipeParser, BaseIngredientParser
from .registry import ParserRegistry

logger = logging.getLogger(__name__)

@ParserRegistry.register
class PdfParser(BaseRecipeParser):
    """Stub for PDF recipe parsing."""
    
    @classmethod
    def format_id(cls) -> str: return "pdf"
    @classmethod
    def priority(cls) -> int: return 35
    @classmethod
    def detect(cls, filepath: str, content_sample: str) -> float:
        if Path(filepath).suffix.lower() == '.pdf': return 0.99
        return 0.0
    def __init__(self, ingredient_parser: BaseIngredientParser):
        super().__init__(ingredient_parser)
        self.source_format = "PDF"

    def parse_file(self, filepath: str) -> Iterator[Recipe]:
        logger.warning("PDF parser is a stub. Requires 'pdfminer.six' or 'pypdf' for implementation.")
        yield from ()

@ParserRegistry.register
class ImageParser(BaseRecipeParser):
    """Stub for Image/OCR recipe parsing."""
    
    @classmethod
    def format_id(cls) -> str: return "image"
    @classmethod
    def priority(cls) -> int: return 36
    @classmethod
    def detect(cls, filepath: str, content_sample: str) -> float:
        if Path(filepath).suffix.lower() in {'.jpg', '.jpeg', '.png', '.gif', '.bmp'}: return 0.99
        return 0.0
    def __init__(self, ingredient_parser: BaseIngredientParser):
        super().__init__(ingredient_parser)
        self.source_format = "Image/OCR"

    def parse_file(self, filepath: str) -> Iterator[Recipe]:
        logger.warning("Image parser is a stub. Requires 'tesseract' or Cloud Vision API.")
        yield from ()

@ParserRegistry.register
class CsvParser(BaseRecipeParser):
    """CSV recipe parser with format detection."""
    
    @classmethod
    def format_id(cls) -> str: return "csv_generic"
    @classmethod
    def priority(cls) -> int: return 21
    @classmethod
    def detect(cls, filepath: str, content_sample: str) -> float:
        if Path(filepath).suffix.lower() != '.csv': return 0.0
        try:
            with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
                f.readline()
                f.seek(0)
                for delimiter in [',', ';', '\t', '|']:
                    reader = csv.DictReader(f, delimiter=delimiter)
                    if reader.fieldnames and len(reader.fieldnames) > 1:
                        headers = [h.strip().lower() for h in reader.fieldnames if h]
                        has_title = any(h in headers for h in ['title', 'name', 'recipe_name', 'recipe name'])
                        has_ing = any(h in headers for h in ['ingredients', 'ingredient', 'ingred', 'ingredient_list'])
                        has_inst = any(h in headers for h in ['instructions', 'instruction', 'directions', 'method', 'instruct', 'steps'])
                        if has_title and has_ing and has_inst: return 0.80
        except Exception: pass
        return 0.1 # Generic CSV fallback

    def __init__(self, ingredient_parser: BaseIngredientParser, format_hint: str | None = None):
        super().__init__(ingredient_parser)
        self.source_format = "CSV"
        self.format_hint = format_hint

    def parse_file(self, filepath: str) -> Iterator[Recipe]:
        for recipe in self._parse_generic_csv(filepath):
            if not recipe.description:
                recipe.description = f"Imported from {self.source_format}"
            if not recipe.url:
                recipe.url = f"file://{Path(filepath).absolute()}"
            yield recipe

    def _parse_generic_csv(self, filepath: str) -> Iterator[Recipe]:
        """Generic CSV parser for common recipe layouts."""
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

                    yield recipe
        except Exception as e:
            logger.error("Error parsing CSV %s: %s", filepath, e)

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
