# SPDX-License-Identifier: MIT
import re
from typing import Iterator
from pathlib import Path
from .models import Recipe
from .base import BaseRecipeParser, BaseIngredientParser
from .registry import ParserRegistry

from .mastercook import MasterCookParser
from .mealmaster import MealMasterParser
from .compuchef import CompuChefParser
from .nyc import NYCParser

@ParserRegistry.register
class MixedFormatParser(BaseRecipeParser):
    """
    Parser for files containing multiple recipes in DIFFERENT FORMATS, mainly .txt files.
    Extracts various recipe types (mealmaster, nyc, mastercook, compuchef) from the same text file.
    """

    @classmethod
    def format_id(cls) -> str:
        return "mixed"

    @classmethod
    def priority(cls) -> int:
        return 10

    @classmethod
    def detect(cls, filepath: str, content_sample: str) -> float:
        score = 0.0
        for parser in (MasterCookParser, MealMasterParser, CompuChefParser, NYCParser):
            score += parser.detect(filepath, content_sample)
            print(f"Mix parser score: {score} due to {parser.format_id()}, {len(content_sample)}")

        if score > 1.0:
            return 1.0

        if score > 0.5:
            if Path(filepath).suffix.lower() == '.txt':
                return 1.0
            return score - 0.25

        return 0.0

    def __init__(self, ingredient_parser: BaseIngredientParser):
        super().__init__(ingredient_parser)
        self.source_format = "Mixed"
        
    def parse_file(self, filepath: str) -> Iterator[Recipe]:
        try:
            line_number = 0
            with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
                for line in f:
                    line_number += 1

                    if not line.strip():
                        continue

                    if MasterCookParser.detect(filepath, line) > 0.5:
                        print(f"Detected at line {line_number}: MasterCook")
                        parser = MasterCookParser(self.ingredient_parser)
                    elif MealMasterParser.detect(filepath, line) > 0.5:
                        print(f"Detected at line {line_number}: MealMaster")
                        parser = MealMasterParser(self.ingredient_parser)
                    elif CompuChefParser.detect(filepath, line) > 0.5:
                        print(f"Detected at line {line_number}: CompuChef")
                        parser = CompuChefParser(self.ingredient_parser)
                    elif NYCParser.detect(filepath, line) > 0.5:
                        print(f"Detected at line {line_number}: NYC")
                        parser = NYCParser(self.ingredient_parser)
                    else:
                        print(f"Not detected at line {line_number}: {line}")
                        continue

                    recipe, lines_read = parser.parse_buffer(f, line)
                    if recipe:
                        if not recipe.description:
                            recipe.description = f"Imported from {self.source_format}"
                        # if not recipe.url:
                        recipe.url = f"file://{filepath}#{line_number}"

                        print(f"recipe: {recipe.title}")
                        yield recipe

                    line_number += lines_read

        except Exception as e:
            print(f"Error reading {filepath}: {e}")
            return

    def parse_content(self, content: str, filepath: str) -> Iterator[Recipe]:
        raise NotImplementedError("Mixed format parser does not support parsing content directly. Use parse_file instead.")