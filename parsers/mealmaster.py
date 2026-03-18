# SPDX-License-Identifier: MIT
import logging
import re
from typing import Iterator, List, Optional
from pathlib import Path
from .models import Recipe
from .base import BaseRecipeParser, BaseIngredientParser
from .registry import ParserRegistry

logger = logging.getLogger(__name__)

@ParserRegistry.register
class MealMasterParser(BaseRecipeParser):
    def __init__(self, ingredient_parser: BaseIngredientParser):
        super().__init__(ingredient_parser)
        self.source_format = "MealMaster"

    @classmethod
    def format_id(cls) -> str:
        return "mealmaster"

    @classmethod
    def priority(cls) -> int:
        return 2

    @classmethod
    def detect(cls, filepath: str, content_sample: str) -> float:
        if Path(filepath).suffix.lower() == '.mmf':
            return 1.0
        if not content_sample:
            return 0.0
        if re.search(r'^(?:MMMMM|-----).*[A-Z0-9]', content_sample, re.MULTILINE):
            return 0.90
        return 0.0

    def parse_content(self, content: str, filepath: str) -> Iterator[Recipe]:
        # Use regex to split based on the header marker
        header_sig = r'^(?:MMMMM|-----).*Recipe via.*$'

        # Split but keep the remainder of the line in the chunk
        parts = re.split(header_sig, content, flags=re.IGNORECASE|re.MULTILINE)

        # The first part is usually preamble or empty
        for recipe_text in parts[1:]:
            if not recipe_text.strip():
                continue

            yield self._parse_single_mealmaster(recipe_text, filepath)

    def parse_buffer(self, f, first_line: str) -> tuple[Optional[Recipe], int]:
        """
        Parse a buffer (file stream) containing MealMaster recipes.
        Reads until the next recipe header or EOF.
        """
        read_lines = 0
        recipe_text = ""

        for line in f:
            recipe_text += line
            read_lines += 1
            if line.strip() == 'MMMMM' or line.strip() == '-----':
                break

        if not recipe_text.strip():
            return (None, read_lines)

        recipe = self._parse_single_mealmaster(recipe_text, f.name)
        return (recipe, read_lines)

    def _parse_single_mealmaster(self, content: str, filepath: str) -> Optional[Recipe]:
        """Parse a single MealMaster recipe block.

        MealMaster files contain one or more recipes delimited by
        ``MMMMM`` / ``-----`` header lines.  Each block begins with
        ``Title:``, ``Categories:``, and ``Yield:``/``Servings:`` metadata
        fields, followed by space-indented ingredient lines and then free-form
        instruction paragraphs.

        Args:
            content: Text of one recipe block, excluding the leading header.
            filepath: Source file path (used to populate ``Recipe.source_file``).

        Returns:
            A populated ``Recipe``, or ``None`` if the block lacks a title.
        """
        current_recipe = Recipe(source_file=filepath, source_format=self.source_format)
        in_header = True
        in_instructions = False
        current_instruction_paragraph = []
        current_ingredient_raw = []

        lines = content.split('\n')

        for line in lines:
            line_str = line.rstrip()
            if (line_str.startswith('MMMMM') or line_str.startswith('-----')) and 'Recipe via' in line_str:
                break

            if line_str.startswith('MMMMM') and '-' in line_str and 'Recipe via' not in line_str:
                self._save_ingredient(current_recipe, current_ingredient_raw)
                in_header = True
                in_instructions = False
                continue

            if (line_str.startswith('-----') or line_str == 'MMMMM') and current_recipe:
                break

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
            return self._save_pending(current_recipe, current_ingredient_raw, current_instruction_paragraph)

        return None

    def _save_ingredient(self, recipe: Recipe, current_ingredient_raw: List[str]):
        if recipe is not None and current_ingredient_raw:
            raw = ' '.join(current_ingredient_raw)
            if raw.strip():
                recipe.ingredients.append(self.ingredient_parser.parse(raw))
            current_ingredient_raw.clear()

    def _save_pending(self, current_recipe: Recipe, current_ingredient_raw: List[str], current_instruction_paragraph: List[str]) -> Optional[Recipe]:
        if current_recipe and current_recipe.title:
            self._save_ingredient(current_recipe, current_ingredient_raw)
            if current_instruction_paragraph:
                current_recipe.instructions.append(' '.join(current_instruction_paragraph))
                current_instruction_paragraph.clear()
            return current_recipe
        return None
