# SPDX-License-Identifier: MIT
import re
from typing import Iterator
from .base import BaseRecipeParser, BaseIngredientParser
from .models import Recipe, Ingredient
from .registry import ParserRegistry

@ParserRegistry.register
class EdnaParser(BaseRecipeParser):
    """Parser for the Edna recipe format.

    Records are separated by a line of dashes (``------------``) followed
    immediately by a line starting with ``id:``.  Each record contains
    YAML-like ``key: value`` metadata fields plus ``ingredients:`` and
    ``instructions:`` block markers.
    """

    # Compiled once; shared between detect() and parse_content()
    _SEPARATOR_RE = re.compile(r'^------------\s*(?=[\r\n]+\s*id:)', re.MULTILINE)

    def __init__(self, ingredient_parser: BaseIngredientParser):
        super().__init__(ingredient_parser)
        self.source_format = "Edna"

    @classmethod
    def format_id(cls) -> str:
        return "edna"

    @classmethod
    def priority(cls) -> int:
        return 4

    @classmethod
    def detect(cls, filepath: str, content_sample: str) -> float:
        if not content_sample:
            return 0.0
        m = cls._SEPARATOR_RE.search(content_sample)
        if m:
            prefix = content_sample[:m.start()].strip()
            if prefix:
                before = content_sample[max(0, m.start()-4):m.start()]
                if not before.endswith('\n\n') and not before.endswith('\r\n\r\n'):
                    return 0.0
            return 0.90
        return 0.0

    def parse_content(self, content: str, filepath: str = "") -> Iterator[Recipe]:
        """Yield one Recipe per Edna record found in *content*."""
        sections = self._SEPARATOR_RE.split(content)
        
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