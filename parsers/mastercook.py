# SPDX-License-Identifier: MIT
import re
from typing import Iterator, Optional
from .models import Recipe, Ingredient
from .base import BaseRecipeParser, BaseIngredientParser
from .units import normalize_unit
from .registry import ParserRegistry

@ParserRegistry.register
class MasterCookParser(BaseRecipeParser):
    # PREP_VERBS = r'stemmed|washed|chopped|minced|diced|sliced|peeled|grated|shredded|cleaned|crushed|beaten|melted|sifted|mashed|halved|quartered|separated|softened|cooked|drained|thawed|frozen|chilled|warmed|sprinkled|garnished|cut'
    # PREP_REGEX = re.compile(fr'^(?:(?:well|freshly|finely|roughly|thinly)\s+)?(?:{PREP_VERBS})(?:\s+(?:and|or)\s+(?:(?:well|freshly|finely|roughly|thinly)\s+)?(?:{PREP_VERBS}))?$')

    def __init__(self, ingredient_parser: BaseIngredientParser):
        super().__init__(ingredient_parser)
        self.source_format = "MasterCook"

        self.author_re = re.compile(r'^Recipe By\s+:(.*)$', re.IGNORECASE)
        self.yield_re = re.compile(r'^Serving Size\s+:(.*?)(?:\s+Preparation Time\s+:(.*))?$', re.IGNORECASE) 
        self.end_re = re.compile(r'^(- ){16}-')

    @classmethod
    def format_id(cls) -> str:
        return "mastercook"

    @classmethod
    def aliases(cls) -> list[str]:
        return ["mxp", "mc"]

    @classmethod
    def priority(cls) -> int:
        return 10

    HEADER_SIG = r'\*\s+Exported\s+from\s+MasterCook[^*]*\*'

    @classmethod
    def detect(cls, filepath: str, content_sample: str) -> float:
        header_sig = cls.HEADER_SIG

        if re.search(header_sig, content_sample):
            return 0.75
            
        return 0.0

    def parse_content(self, content: str, filepath: str) -> Iterator[Recipe]:
        # Use regex to split based on the header marker
        header_sig = self.HEADER_SIG
        
        # Split but keep the remainder of the line in the chunk
        parts = re.split(header_sig, content)
        
        # The first part is usually preamble or empty
        for recipe_text in parts[1:]:
            if not recipe_text.strip():
                continue
            
            recipe = self._parse_single_mastercook(recipe_text)
            if recipe:
                recipe.source_format = self.source_format
                recipe.source_file = filepath
                yield recipe

    def parse_buffer(self, f, first_line: str) -> (Optional[Recipe], int):
        """
        Parse a buffer (file stream) containing MasterCook recipes.
        Reads until the next recipe header or EOF.
        """
        read_lines = 0
        recipe_text = ""
        
        for line in f:
            recipe_text += line
            read_lines += 1
            if re.search(self.end_re, line):
                break

        if not recipe_text.strip():
            return (None, read_lines)
        
        recipe = self._parse_single_mastercook(recipe_text)
        if recipe:
            recipe.source_format = self.source_format
            recipe.source_file = f.name
            return (recipe, read_lines)
        
        return (None, read_lines)

    def _parse_single_mastercook(self, text: str) -> Optional[Recipe]:
        recipe = Recipe()
        lines = text.strip().split('\n')
        
        # Basic state machine for MasterCook format
        current_section = None # None, 'header', 'ingredients', 'instructions', 'notes', 'categories'
        
        # Skip leading empty lines to find title
        start_idx = 0
        while start_idx < len(lines) and not lines[start_idx].strip():
            start_idx += 1
            
        if start_idx >= len(lines):
            return None

        # First non-empty line after header is the title
        recipe.title = lines[start_idx].strip()
        current_section = 'header'
        print("Setting header for title ", recipe.title)
        
        for i in range(start_idx + 1, len(lines)):
            line = lines[i].strip('\r') # Keep leading spaces but remove \r
            stripped = line.strip()

            if self.end_re.match(stripped):
                break

            if current_section == 'header':
                author_match = self.author_re.match(stripped)
                yield_match = self.yield_re.match(stripped)
                if author_match:
                    recipe.author = author_match.group(1).strip()
                    continue
                if yield_match:
                    recipe.yield_amount = yield_match.group(1).strip()
                    if yield_match.group(2):
                        recipe.prep_time = yield_match.group(2).strip()
                    continue

            # Section detection
            if stripped == 'Amount  Measure       Ingredient -- Preparation Method':
                current_section = 'ingredients'
                print("Setting ingredients")
                continue
            elif stripped == '--------  ------------  --------------------------------':
                current_section = 'ingredients'
                print("Setting ingredients")
                continue
            elif stripped.startswith('Directions') or stripped.startswith('Instructions'):
                current_section = 'instructions'
                print("Setting instructions")
                instruction_block = []
                continue
            elif stripped.startswith('Notes:'):
                current_section = 'notes'
                print("Setting notes")
                recipe.notes.append(stripped.replace('Notes:', '', 1).strip())
                continue
            elif stripped.startswith('Categories') or current_section == 'categories':
                current_section = 'categories'
                print("Setting categories")
                if not stripped:
                    current_section = 'header'
                    print("Setting header")
                    continue
                first_column = line[16:48].strip()
                second_column = line[49:].strip()
                if first_column:
                    recipe.categories.append(first_column)
                if second_column:
                    recipe.categories.append(second_column)
                continue
            
            # Heuristic for ingredient start even without header
            if current_section == 'header' and stripped:
                # MasterCook ingredients usually have numbers at fixed positions or start with spaces
                if re.match(r'^\s*[\d./-]+\s+[a-zA-Z.]+\s+', line) or re.match(r'^\s+\d+\s+', line):
                    current_section = 'ingredients'
                    print("Setting ingredients")
            
            # Handle sections
            if current_section == 'ingredients':
                if not stripped:
                    current_section = 'instructions'
                    print("Setting instructions")
                    instruction_block = []
                    continue
                
                # MasterCook format is fixed width: 8 spaces for Amount, 12 for Measure, then Ingredient
                amount = line[0:8].strip()
                measure = line[10:24].strip()
                ingredient_part = line[24:].strip()
                
                if ingredient_part:
                    # Check if this is a continuation
                    is_continuation = False
                    
                    if not amount and not measure:
                        if stripped and stripped[0].startswith('-'):
                            stripped = stripped[1:].strip()
                            is_continuation = True
                    
                    if is_continuation and recipe.ingredients:
                        recipe.ingredients[-1].raw += " " + stripped
                    else:
                        # Normalize unit
                        measure = normalize_unit(measure)
                        
                        # Check for preparation method at end of ingredient
                        if " -- " in ingredient_part:
                            ingredient_part = ingredient_part.replace(" -- ", ", ")
                        
                        ing = Ingredient(ingredient_part)
                        if amount: ing.quantity = amount
                        if measure: ing.unit = measure
                        # if ingredient_part: ing.name = ingredient_part
                        recipe.ingredients.append(ing)
            
            elif current_section == 'instructions' or current_section == 'header':
                if stripped:
                    if current_section == 'header' and not recipe.title:
                        recipe.title = stripped
                    else:
                        instruction_block.append(stripped)
                if current_section == 'instructions' and not stripped and len(instruction_block):
                    recipe.instructions.append(" ".join(instruction_block))
                    instruction_block = []
            
            elif current_section == 'notes':
                if stripped:
                     recipe.notes.append(stripped)
                     
        return recipe
