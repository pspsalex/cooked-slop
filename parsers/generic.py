# SPDX-License-Identifier: MIT
from pathlib import Path
from typing import Iterator, List

from .base import BaseRecipeParser, BaseIngredientParser
from .models import Recipe
from .registry import ParserRegistry

@ParserRegistry.register
class GenericTextParser(BaseRecipeParser):
    def __init__(self, ingredient_parser: BaseIngredientParser):
        super().__init__(ingredient_parser)
        self.source_format = "Raw Text"

    @classmethod
    def format_id(cls) -> str:
        return "generic_text"

    @classmethod
    def priority(cls) -> int:
        # This is a fallback parser, so it should have lowest priority
        return 100

    @classmethod
    def detect(cls, filepath: str, content: str) -> float:
        # This parser is a generic fallback and should always be able to
        # attempt parsing, as long as the file is not empty.
        # More specific parsers should have higher priority and detect
        # their formats first.
        return 0.01 if content.strip() else 0.0

    def parse_content(self, content: str, filepath: str) -> Iterator[Recipe]:
        recipe = Recipe(source_file=filepath, source_format=self.source_format)
        recipe.title = Path(filepath).stem
        
        lines = content.split('\n')
            
        in_instructions = False
        for line in lines:
            line_str = line.strip()
            if not line_str: continue
            
            # Heuristic: If it's a long sentence or doesn't start with a number, it's an instruction
            first_word = line_str.split()[0] if line_str.split() else ""
            looks_like_ingredient = any(c.isdigit() for c in first_word) or first_word.lower() in ['a', 'an', 'some', 'few', 'dash', 'pinch']
            
            if not in_instructions and looks_like_ingredient and len(line_str) < 80:
                recipe.ingredients.append(self.ingredient_parser.parse(line_str))
            else:
                in_instructions = True # Once we hit instructions, everything else is instructions
                recipe.instructions.append(line_str)
                
        if recipe.ingredients or recipe.instructions:
            yield recipe
