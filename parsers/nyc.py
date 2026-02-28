import re
from typing import Iterator, Optional
from .base import BaseRecipeParser
from .models import Recipe, Ingredient

from .registry import ParserRegistry

@ParserRegistry.register
class NYCParser(BaseRecipeParser):
    """Parser for Now You're Cooking! (NYC) export format."""

    def __init__(self, ingredient_parser=None):
        super().__init__(ingredient_parser)
        self.source_format = "NYC"

    @classmethod
    def format_id(cls) -> str:
        return "nyc"

    @classmethod
    def priority(cls) -> int:
        return 6

    @classmethod
    def detect(cls, filepath: str, content_sample: str) -> float:
        import re
        if not content_sample:
            return 0.0
        if re.search(r'^@{5}\s+Now You\'re Cooking!', content_sample, re.MULTILINE):
            return 0.95
        return 0.0

    def parse_content(self, content: str, filepath: str = "") -> Iterator[Recipe]:
        # Split by the NYC header
        sections = re.split(r'@{5}\s+Now You\'re Cooking! Export Format', content)
        
        for section in sections:
            section = section.strip()
            if not section:
                continue

            # Split into lines and find title, category, ingredients, instructions
            lines = section.splitlines()
            
            # Remove the footer if present
            footer_regex = r'\*\* Exported from Now You\'re Cooking!.* \*\*'
            filtered_lines = []
            for line in lines:
                if not re.search(footer_regex, line):
                    filtered_lines.append(line)
            lines = filtered_lines

            if not lines:
                continue

            # NYC structure:
            # Title
            # (blank)
            # Category
            # (blank)
            # Ingredients
            # (blank)
            # Instructions
            # (blank)
            # Yield: ...

            title = "Untitled"
            categories = []
            ingredients_raw = []
            instructions_raw = []
            yield_str = ""

            # Phase 0: Find title
            idx = 0
            while idx < len(lines) and not lines[idx].strip():
                idx += 1
            if idx < len(lines):
                title = lines[idx].strip()
                idx += 1

            # Phase 1: Find categories
            while idx < len(lines) and not lines[idx].strip():
                idx += 1
            if idx < len(lines):
                cat_line = lines[idx].strip()
                categories = [c.strip() for c in cat_line.split(',')]
                idx += 1

            # Phase 2: Ingredients vs Instructions
            # This is the hardest part. Usually, ingredients are lines starting with 
            # a number, a fraction, or a measurement.
            # Instructions are paragraphs of text.
            
            in_ingredients = True
            
            # Skip initial blank lines
            while idx < len(lines) and not lines[idx].strip():
                idx += 1
                
            temp_instructions = []
            
            while idx < len(lines):
                line = lines[idx].strip()
                
                # Check for yield at any point near the end
                yield_match = re.match(r'^Yield:\s*(.*)$', line, re.IGNORECASE)
                if yield_match:
                    yield_str = yield_match.group(1).strip()
                    idx += 1
                    continue
                
                if in_ingredients:
                    if not line:
                        # Empty line might signify transition to instructions
                        # Peek ahead to see if the next non-empty line looks like an ingredient
                        peek_idx = idx + 1
                        found_next = False
                        while peek_idx < len(lines):
                            peek_line = lines[peek_idx].strip()
                            if peek_line:
                                # Heuristic: if it starts with a digit or Fraction-like string
                                if re.match(r'^[\d½⅓⅔¼¾⅛⅜⅝⅞\*\-]', peek_line) or \
                                   re.match(r'^(?:[Aa] [Ff]ew|[Aa] [Dd]ash|[Aa] [Pp]inch|[Ss]alt|[Pp]epper)', peek_line):
                                    # Still in ingredients
                                    pass
                                else:
                                    in_ingredients = False
                                found_next = True
                                break
                            peek_idx += 1
                        
                        if not found_next:
                            in_ingredients = False
                        
                        if in_ingredients:
                            # Just a blank line in ingredients, maybe skip or preserve?
                            # Usually NYC doesn't have blank lines IN ingredients
                            pass
                    else:
                        # Check if this line looks like an instruction instead
                        # If a line is long and doesn't start with quantities, it's likely instructions
                        if len(line) > 50 and not re.match(r'^[\d½⅓⅔¼¾⅛⅜⅝⅞]', line):
                            in_ingredients = False
                            temp_instructions.append(line)
                        else:
                            # It's an ingredient
                            # Clean up -- comments if they were accidentally left in raw form
                            # (BaseIngredientParser will handle most of it)
                            ingredients_raw.append(line)
                else:
                    if line:
                        temp_instructions.append(line)
                        
                idx += 1

            # Group instructions into paragraphs
            recipe_instructions = []
            current_paragraph = []
            for line in temp_instructions:
                if not line:
                    if current_paragraph:
                        recipe_instructions.append(" ".join(current_paragraph))
                        current_paragraph = []
                else:
                    current_paragraph.append(line)
            if current_paragraph:
                recipe_instructions.append(" ".join(current_paragraph))

            # Create Recipe object
            recipe = Recipe(
                title=title,
                categories=categories,
                source_format=self.source_format,
                source_file=filepath,
                yield_amount=yield_str
            )

            # Parse ingredients
            for ing_line in ingredients_raw:
                # NYC sometimes uses "--" for comments
                if " -- " in ing_line:
                    ing_line = ing_line.replace(" -- ", " ")
                
                if self.ingredient_parser:
                    recipe.ingredients.append(self.ingredient_parser.parse(ing_line))
                else:
                    recipe.ingredients.append(Ingredient(raw=ing_line, name=ing_line))

            recipe.instructions = recipe_instructions
            yield recipe
