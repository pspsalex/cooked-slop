# SPDX-License-Identifier: MIT
import re
from typing import Iterator, Optional
from .models import Recipe, Ingredient
from .base import BaseRecipeParser, BaseIngredientParser
from .units import normalize_unit


from .registry import ParserRegistry

@ParserRegistry.register
class CompuChefParser(BaseRecipeParser):
    """Parser for Compu-Chef (tm) recipe files (.ccf).
    
    Format structure:
        ***...***
        ***** Recipe Title *****
        ***...***

        Categories: Cat1  Cat2

        Calories per serving: ...   Number of Servings: N
        ...

        INGREDIENTS ---...---

           qty   unit  Ingredient name

        DIRECTIONS ---...---

        Directions text...

        *** Recipe Via Compu-Chef (tm) ***
    """

    def __init__(self, ingredient_parser: BaseIngredientParser):
        super().__init__(ingredient_parser)
        self.source_format = "CompuChef"

        self.end_re = re.compile(r'\*{3}\s*Recipe Via Compu-Chef.*\*{3}', flags=re.IGNORECASE)

    @classmethod
    def format_id(cls) -> str:
        return "compuchef"

    @classmethod
    def priority(cls) -> int:
        return 3

    @classmethod
    def detect(cls, filepath: str, content_sample: str) -> float:
        import re
        if not content_sample:
            return 0.0
        if re.search(r'Recipe Via Compu-Chef', content_sample, re.IGNORECASE):
            return 0.95
        if re.search(r'^\s*\*{3,}\s*(?![^*]*Exported from)[^*]+\s*\*{3,}', content_sample, re.MULTILINE):
            return 0.75
        return 0.0

    def parse_content(self, content: str, filepath: str) -> Iterator[Recipe]:
        # Split on the Compu-Chef recipe footer/separator
        # Each recipe ends with "*** Recipe Via Compu-Chef (tm) ***"
        sections = re.split(self.end_re, content)
        for section in sections:
            if section.strip():
                recipe = self._parse_section(section.strip(), filepath)
                if recipe and recipe.title:
                    yield recipe

    def parse_buffer(self, f, first_line: str) -> (Optional[Recipe], int):
        """
        Parse a buffer (file stream) containing CompuChef recipes.
        Reads until the next recipe header or EOF.
        """
        read_lines = 0
        recipe_text = first_line
        
        for line in f:
            read_lines += 1
            if self.end_re.match(line.strip()):
                break
            recipe_text += line

        if not recipe_text.strip():
            return (None, read_lines)
        
        print(f"Parsing recipe from {f.name} {recipe_text}")

        recipe = self._parse_section(recipe_text, f.name)
        return (recipe, read_lines)

    def _parse_section(self, section: str, filepath: str) -> Recipe:
        recipe = Recipe(source_file=filepath, source_format=self.source_format)
        lines = section.split('\n')
        in_ingredients = False
        in_directions = False
        current_para = []

        for line in lines:
            line_stripped = line.strip()

            # Extract title from the *** Title *** header
            if not recipe.title:
                title_match = re.match(r'^\*+\s*(.+?)\s*\*+$', line_stripped)
                if title_match:
                    candidate = title_match.group(1).strip().strip('*').strip()
                    # Skip the pure *** divider lines (no words)
                    if candidate and not re.match(r'^\*+$', candidate):
                        recipe.title = candidate
                continue

            # Categories line
            if re.match(r'^Categories\s*:', line_stripped, re.IGNORECASE):
                cats_raw = re.split(r':', line_stripped, maxsplit=1)[1]
                recipe.categories = [c.strip() for c in cats_raw.split() if c.strip()]
                continue

            # Servings
            if re.search(r'Number of Servings\s*:\s*(\d+)', line_stripped, re.IGNORECASE):
                m = re.search(r'Number of Servings\s*:\s*(\d+)', line_stripped, re.IGNORECASE)
                if m:
                    recipe.yield_amount = m.group(1)

            # Section header: INGREDIENTS
            if re.match(r'^INGREDIENTS\s*-+', line_stripped, re.IGNORECASE):
                in_ingredients = True
                in_directions = False
                continue

            # Section header: DIRECTIONS
            if re.match(r'^DIRECTIONS\s*-+', line_stripped, re.IGNORECASE):
                in_ingredients = False
                in_directions = True
                continue

            if in_ingredients:
                if not line_stripped:
                    continue
                # Skip section dividers like ----MARINADE----
                if re.match(r'^-{3,}.*-{3,}$', line_stripped):
                    continue

                # CompuChef ingredient columns are left-padded and split on 2+ spaces
                # Format: "   qty   unit  name"
                # The quantity is always at the start; unit is the second token
                parts = re.split(r'\s{2,}', line_stripped)
                if parts and (parts[0][0].isdigit() or parts[0].startswith('/')):
                    if len(parts) == 1:
                        # Just a quantity somehow — treat as unitless name
                        ing = Ingredient(raw=line_stripped, quantity=parts[0].strip(), name='')
                    elif len(parts) == 2:
                        # qty + ingredient name, no unit
                        ing = Ingredient(
                            raw=line_stripped,
                            quantity=parts[0].strip(),
                            unit=None,
                            name=parts[1].strip()
                        )
                    else:
                        ing = Ingredient(
                            raw=line_stripped,
                            quantity=parts[0].strip(),
                            unit=normalize_unit(parts[1].strip()),
                            name=' '.join(parts[2:]).strip()
                        )
                    recipe.ingredients.append(ing)
                else:
                    # Unitless ingredient line (e.g. "salt & pepper to taste")
                    recipe.ingredients.append(
                        Ingredient(raw=line_stripped, name=line_stripped)
                    )

            elif in_directions:
                if not line_stripped:
                    if current_para:
                        recipe.instructions.append(' '.join(current_para))
                        current_para = []
                else:
                    current_para.append(line_stripped)

        if current_para:
            recipe.instructions.append(' '.join(current_para))

        return recipe
