# SPDX-License-Identifier: MIT

import re
from typing import Iterator
from .base import BaseRecipeParser
from .models import Recipe, Ingredient
from .units import normalize_unit

class RicetteParser(BaseRecipeParser):
    """
    Parser for the Italian 'Ricette' format.
    Characterized by :Ricette record separators and -Field markers.
    """
    
    def __init__(self, ingredient_parser=None):
        super().__init__(ingredient_parser)
        self.source_format = "Ricette"

    def parse_content(self, content: str, filepath: str) -> Iterator[Recipe]:
        # Split by :Ricette, but keep the content that follows
        sections = re.split(r'^:Ricette\s*', content, flags=re.MULTILINE)
        
        for section in sections:
            if not section.strip():
                continue
            
            recipe = self._parse_section(section, filepath)
            if recipe.title:
                yield recipe

    def _parse_section(self, section: str, filepath: str) -> Recipe:
        recipe = Recipe(source_file=filepath, source_format=self.source_format)
        
        # Split by -Field entries
        # We look for a hyphen at the start of a line followed by a word
        fields = re.split(r'^-([a-zA-Z_]+)\s*\n?', section, flags=re.MULTILINE)
        
        # fields list will be [leading_text, field_name1, field_content1, field_name2, field_content2, ...]
        i = 1
        while i < len(fields) - 1:
            field_name = fields[i].strip().lower()
            field_content = fields[i+1].strip()
            
            if field_name == 'nome':
                recipe.title = field_content
            elif field_name == 'persone':
                recipe.yield_amount = field_content
            elif field_name == 'tipo_piatto':
                recipe.categories.append(field_content)
            elif field_name == 'ing_principale':
                if field_content and field_content not in recipe.categories:
                    recipe.categories.append(field_content)
            elif field_name == 'note':
                if field_content and field_content != '-':
                    # Treat notes as part of description or instructions preamble?
                    # For now, let's keep it in a temporary place or prepend to instructions
                    pass
            elif field_name == 'ingredienti':
                self._parse_ingredients(field_content, recipe)
            elif field_name == 'preparazione':
                recipe.instructions = [p.strip() for p in field_content.split('\n') if p.strip()]
            
            i += 2
            
        return recipe

    def _parse_ingredients(self, content: str, recipe: Recipe):
        lines = content.split('\n')
        for line in lines:
            line = line.strip()
            if not line:
                continue
                
            if '====' in line:
                parts = line.split('====', 1)
                amount_part = parts[0].strip()
                name_part = parts[1].strip()
                
                # Split amount into quantity and unit
                # Heuristic: first "word" might be quantity
                quantity = ""
                unit = None
                
                if amount_part:
                    amount_words = amount_part.split()
                    if amount_words:
                        if amount_words[0][0].isdigit() or amount_words[0].startswith('/'):
                            quantity = amount_words[0]
                            if len(amount_words) > 1:
                                unit = normalize_unit(' '.join(amount_words[1:]))
                        else:
                            unit = normalize_unit(amount_part)

                recipe.ingredients.append(Ingredient(
                    raw=line.replace('====', '').strip(),
                    quantity=quantity,
                    unit=unit,
                    name=name_part
                ))
            else:
                # Fallback if ==== is missing or it's a header
                recipe.ingredients.append(Ingredient(raw=line, name=line))
