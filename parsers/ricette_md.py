# SPDX-License-Identifier: MIT
import re
from typing import List, Optional
from .base import BaseRecipeParser
from .models import Recipe, Ingredient

class RicetteMdParser(BaseRecipeParser):
    def __init__(self, ingredient_parser=None):
        super().__init__(ingredient_parser)
        self.source_format = "RicetteMD"

    def _unescape(self, text: str) -> str:
        r"""Unescape common Markdown escapes like \( or \)."""
        return text.replace(r'\(', '(').replace(r'\)', ')')

    def parse_content(self, content: str, filepath: str = "") -> List[Recipe]:
        recipes = []
        # Split by level 1 headings
        sections = re.split(r'^#\s+', content, flags=re.MULTILINE)
        
        for section in sections:
            section = section.strip()
            if not section:
                continue
                
            lines = section.splitlines()
            title = self._unescape(lines[0].strip()) if lines else "Untitled"
            
            recipe = Recipe(
                title=title,
                source_format=self.source_format,
                source_file=filepath
            )
            
            current_header = None
            i = 1
            while i < len(lines):
                line = lines[i]
                
                # Any header level resets or changes the block
                if line.startswith('#'):
                    header_match = re.match(r'^#+\s+(.*)$', line)
                    if header_match:
                        header_text = header_match.group(1).strip()
                        if "Ingredienti" in header_text:
                            current_header = "ingredients"
                            # Extract yield: per X persone
                            yield_match = re.search(r'per\s+(\d+)\s+persone', header_text, re.IGNORECASE)
                            if yield_match:
                                recipe.yield_amount = yield_match.group(1).strip()
                        elif header_text == "Ricetta":
                            current_header = "instructions"
                        else:
                            current_header = "other"
                    else:
                        current_header = "other"
                    
                    i += 1
                    continue
                
                if current_header == "ingredients":
                    if line.startswith('+ '):
                        ing_text = self._unescape(line[2:].strip())
                        if self.ingredient_parser:
                            recipe.ingredients.append(self.ingredient_parser.parse(ing_text))
                        else:
                            recipe.ingredients.append(Ingredient(raw=ing_text, name=ing_text))
                elif current_header == "instructions":
                    if line.strip():
                        recipe.instructions.append(self._unescape(line.strip()))
                    elif recipe.instructions:
                        # Allow single empty lines in instructions
                        recipe.instructions.append('')
                
                i += 1
                
            # Post-process instructions
            while recipe.instructions and not recipe.instructions[-1]:
                recipe.instructions.pop()
                
            # If we have title and either ingredients or instructions, it's a valid recipe
            if recipe.title and (recipe.ingredients or recipe.instructions):
                # Group instructions into blocks separated by empty strings if desired, 
                # but Recipe.instructions expects a list of strings (steps).
                # The User said: "Steps can be separated by one empty line."
                # I will join lines until an empty string is found.
                grouped_instructions = []
                current_step = []
                for inst in recipe.instructions:
                    if inst == '':
                        if current_step:
                            grouped_instructions.append(" ".join(current_step))
                            current_step = []
                    else:
                        current_step.append(inst)
                if current_step:
                    grouped_instructions.append(" ".join(current_step))
                recipe.instructions = grouped_instructions
                
                recipes.append(recipe)
                
        return recipes
