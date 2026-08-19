# SPDX-License-Identifier: MIT

import re
from typing import Iterator
from .base import BaseRecipeParser, BaseIngredientParser
from .models import Recipe, Ingredient
from .registry import ParserRegistry

@ParserRegistry.register
class RicetteParser(BaseRecipeParser):
    """Parser for the Italian 'Ricette' format.

    Records begin with ``:Ricette`` and contain ``-FieldName`` markers that
    delimit metadata and content blocks.  Ingredients use ``====`` as a
    separator between amount and ingredient name.
    """

    # Compiled once; shared between detect() and parse_content()
    _SECTION_RE = re.compile(r'^:Ricette\s*', re.MULTILINE)
    _FIELD_RE = re.compile(r'^-([a-zA-Z_]+)\s*\n?', re.MULTILINE)

    def __init__(self, ingredient_parser: BaseIngredientParser):
        super().__init__(ingredient_parser)
        self.source_format = "Ricette"

    @classmethod
    def format_id(cls) -> str:
        return "ricette"

    @classmethod
    def priority(cls) -> int:
        return 5

    @classmethod
    def detect(cls, filepath: str, content_sample: str) -> float:
        if not content_sample:
            return 0.0
        if cls._SECTION_RE.search(content_sample):
            return 0.95
        return 0.0

    def parse_content(self, content: str, filepath: str) -> Iterator[Recipe]:
        """Yield one Recipe per ``:Ricette`` block found in *content*."""
        sections = self._SECTION_RE.split(content)
        
        for section in sections:
            if not section.strip():
                continue
            
            recipe = self._parse_section(section, filepath)
            if recipe.title:
                yield recipe

    def _parse_section(self, section: str, filepath: str) -> Recipe:
        recipe = Recipe(source_file=filepath, source_format=self.source_format)

        # Split by -Field entries; result is [leading, name1, content1, name2, content2, ...]
        fields = self._FIELD_RE.split(section)
        
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

    def _parse_ingredients(self, content: str, recipe: Recipe) -> None:
        """Parse a Ricette ingredients block and append to *recipe*.

        Each line uses ``====`` as a separator between the amount/unit
        on the left and the ingredient name on the right.  Lines without
        ``====`` are treated as plain ingredient strings.
        """
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
                                unit = ' '.join(amount_words[1:])
                        else:
                            unit = amount_part

                recipe.ingredients.append(Ingredient(
                    raw=line.replace('====', '').strip(),
                    quantity=quantity,
                    unit=unit,
                    name=name_part
                ))
            else:
                # Fallback if ==== is missing or it's a header
                recipe.ingredients.append(Ingredient(raw=line, name=line))
