# SPDX-License-Identifier: MIT
from typing import Iterator, List
from .models import Recipe
from .base import BaseRecipeParser, BaseIngredientParser

class MealMasterParser(BaseRecipeParser):
    def __init__(self, ingredient_parser: BaseIngredientParser):
        super().__init__(ingredient_parser)
        self.source_format = "MealMaster"

    def parse_content(self, content: str, filepath: str) -> Iterator[Recipe]:
        current_recipe = None
        in_header = True
        in_instructions = False
        current_instruction_paragraph = []
        current_ingredient_raw = []

        lines = content.split('\n')

        for line in lines:
            line_str = line.rstrip()
            if (line_str.startswith('MMMMM') or line_str.startswith('-----')) and 'Recipe via' in line_str:
                yield from self._save_pending(current_recipe, current_ingredient_raw, current_instruction_paragraph)
                current_recipe = Recipe(source_file=filepath, source_format=self.source_format)
                in_header = True
                in_instructions = False
                current_instruction_paragraph = []
                current_ingredient_raw = []
                continue

            if line_str.startswith('MMMMM') and '-' in line_str and 'Recipe via' not in line_str:
                self._save_ingredient(current_recipe, current_ingredient_raw)
                in_header = True
                in_instructions = False
                continue

            if (line_str.startswith('-----') or line_str == 'MMMMM') and current_recipe:
                yield from self._save_pending(current_recipe, current_ingredient_raw, current_instruction_paragraph)
                current_recipe = None
                current_instruction_paragraph = []
                current_ingredient_raw = []
                continue

            if current_recipe is None:
                continue

            if not line_str.strip():
                if in_header and current_recipe.ingredients:
                    self._save_ingredient(current_recipe, current_ingredient_raw)
                    in_header = False
                    in_instructions = True
                elif in_instructions and current_instruction_paragraph:
                    current_recipe.instructions.append(' '.join(current_instruction_paragraph))
                    current_instruction_paragraph = []
                continue

            if line_str.strip().startswith('Title:'):
                current_recipe.title = line_str.split(':', 1)[1].strip()
                continue
            if line_str.strip().startswith('Categories:'):
                cats = line_str.split(':', 1)[1].strip()
                current_recipe.categories = [c.strip() for c in cats.split(',')]
                continue
            if line_str.strip().startswith(('Yield:', 'Servings:')):
                current_recipe.yield_amount = line_str.split(':', 1)[1].strip()
                continue

            if in_header and line_str.startswith(' '):
                stripped = line_str.strip()
                is_continuation = False
                if current_ingredient_raw:
                    if stripped.startswith('-'):
                        is_continuation = True
                    elif stripped and not stripped[0].isdigit():
                        first_word = stripped.split()[0] if stripped.split() else ''
                        if first_word and (first_word[0].islower() or stripped[0] in '(-' or first_word.lower() in ['or', 'and', 'to', 'for']):
                            is_continuation = True

                if is_continuation and current_ingredient_raw:
                    current_ingredient_raw.append(stripped.lstrip('-').strip())
                else:
                    self._save_ingredient(current_recipe, current_ingredient_raw)
                    if stripped:
                        current_ingredient_raw = [stripped]
                continue

            if in_instructions and line_str.strip():
                current_instruction_paragraph.append(line_str.strip())

        if current_recipe:
            yield from self._save_pending(current_recipe, current_ingredient_raw, current_instruction_paragraph)

    def _save_ingredient(self, recipe: Recipe, current_ingredient_raw: List[str]):
        if recipe is not None and current_ingredient_raw:
            raw = ' '.join(current_ingredient_raw)
            if raw.strip():
                recipe.ingredients.append(self.ingredient_parser.parse(raw))
            current_ingredient_raw.clear()

    def _save_pending(self, current_recipe: Recipe, current_ingredient_raw: List[str], current_instruction_paragraph: List[str]) -> Iterator[Recipe]:
        if current_recipe and current_recipe.title:
            self._save_ingredient(current_recipe, current_ingredient_raw)
            if current_instruction_paragraph:
                current_recipe.instructions.append(' '.join(current_instruction_paragraph))
                current_instruction_paragraph.clear()
            yield current_recipe
