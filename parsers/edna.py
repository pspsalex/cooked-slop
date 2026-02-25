# SPDX-License-Identifier: MIT
import re
from typing import Iterator
from .base import BaseRecipeParser
from .models import Recipe, Ingredient

class EdnaParser(BaseRecipeParser):
    def __init__(self, ingredient_parser=None):
        super().__init__(ingredient_parser)
        self.source_format = "Edna"

    def parse_content(self, content: str, filepath: str = "") -> Iterator[Recipe]:
        # Split by the record separator (refined to include positive lookahead for id:)
        sections = re.split(r'^------------\s*(?=[\r\n]+\s*id:)', content, flags=re.MULTILINE)
        
        for section in sections:
            section = section.strip()
            if not section:
                continue
                
            # Initialize Recipe object
            recipe = Recipe(
                source_format=self.source_format,
                source_file=filepath
            )
            
            lines = section.splitlines()
            current_block = None
            
            i = 0
            while i < len(lines):
                line = lines[i]
                
                # If we are in instructions, everything until the end of section is instructions
                if current_block == 'instructions':
                    instruction_lines = lines[i:]
                    current_step = []
                    for iline in instruction_lines:
                        stripped = iline.strip()
                        if stripped:
                            current_step.append(stripped)
                        else:
                            if current_step:
                                recipe.instructions.append(" ".join(current_step))
                                current_step = []
                    if current_step:
                        recipe.instructions.append(" ".join(current_step))
                    break

                # Check for metadata fields
                meta_match = re.match(r'^\s*(\w+):\s*(.*)$', line)
                if meta_match:
                    key = meta_match.group(1).lower()
                    value = meta_match.group(2).strip()
                    
                    if key == 'title':
                        recipe.title = value
                    elif key == 'category':
                        if value:
                            recipe.categories.append(value)
                    elif key == 'subcategory':
                        if value:
                            recipe.categories.append(value)
                    elif key == 'source':
                        pass
                    elif key == 'ingredients':
                        current_block = 'ingredients'
                    elif key == 'instructions':
                        current_block = 'instructions'
                    
                    i += 1
                    continue
                
                # Handle blocks
                if current_block == 'ingredients':
                    # Ingredient lines start with "  - "
                    if line.startswith('  - '):
                        ingredient_text = line[4:].strip()
                        # Headers in ingredients end in ":"
                        if ingredient_text.endswith(':'):
                            recipe.ingredients.append(Ingredient(raw=ingredient_text, name=ingredient_text))
                        elif ingredient_text:
                            # Handle continuations if any (lines with extra indent)
                            while i + 1 < len(lines) and lines[i+1].startswith('  -   '):
                                i += 1
                                ingredient_text += " " + lines[i][6:].strip()
                            
                            if self.ingredient_parser:
                                recipe.ingredients.append(self.ingredient_parser.parse(ingredient_text))
                            else:
                                recipe.ingredients.append(Ingredient(raw=ingredient_text, name=ingredient_text))
                    elif line.strip() == '':
                        pass # allow empty lines in ingredients
                    else:
                        if line.strip():
                            current_block = None
                
                i += 1
            
            # Post-process instructions
            while recipe.instructions and not recipe.instructions[-1]:
                recipe.instructions.pop()
                
            if recipe.title:
                yield recipe