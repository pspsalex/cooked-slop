# SPDX-License-Identifier: MIT
import logging
import re
from typing import Iterator, Optional
from .models import Recipe, Ingredient
from .base import BaseRecipeParser, BaseIngredientParser
from .units import normalize_unit
from .registry import ParserRegistry

logger = logging.getLogger(__name__)

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

        self.ingred_re = re.compile(r'^Amount\s+Measure\s+Ingredient\s+--\s+Preparation Method$')
        self.ingred_line_re = re.compile(r'^[-]{4,}\s+[-]{8,}\s+[-]{12,}')

        self.ingred_like_re = re.compile(r'^\s*[\d./-]+\s+[a-zA-Z.]+\s+')
        self.categories_re = re.compile(r"(?:Categories\s*:\s*)?([^\s](?:(?!\s{3,}).)*)")

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

    # Fixed-width column positions for the ingredient table
    # Format: "   1      cup           converted rice"
    _AMOUNT_COL = slice(0, 8)
    _MEASURE_COL = slice(10, 24)
    _INGREDIENT_COL = slice(24, None)

    # Fixed-width column positions for the categories table
    # Format: "                Desserts                         Apples"
    _CATEGORY_COL1 = slice(16, 48)
    _CATEGORY_COL2 = slice(49, None)

    @classmethod
    def detect(cls, filepath: str, content_sample: str) -> float:
        if not content_sample:
            return 0.0
        if re.search(cls.HEADER_SIG, content_sample):
            return 0.75

        # Also check for structural markers within a context window
        mc_markers = 0
        if re.search(r'^Recipe By\s+:', content_sample, re.MULTILINE | re.IGNORECASE):
            mc_markers += 1
        if re.search(r'^Serving Size\s+:', content_sample, re.MULTILINE | re.IGNORECASE):
            mc_markers += 1
        if re.search(r'Amount\s+Measure\s+Ingredient\s+--', content_sample, re.MULTILINE):
            mc_markers += 2
        if re.search(r'^\s*[-]{4,}\s+[-]{8,}\s+[-]{12,}', content_sample, re.MULTILINE):
            mc_markers += 2

        if mc_markers >= 2:
            return 0.85
        elif mc_markers == 1:
            return 0.60

        return 0.0

    def parse_content(self, content: str, filepath: str) -> Iterator[Recipe]:
        # Use regex to split based on the header marker
        header_sig = self.HEADER_SIG

        # Split but keep the remainder of the line in the chunk
        parts = re.split(header_sig, content)

        if len(parts) > 1:
            # The first part is usually preamble or empty
            for recipe_text in parts[1:]:
                if not recipe_text.strip():
                    continue

                recipe = self._parse_single_mastercook(recipe_text)
                if recipe:
                    recipe.source_format = self.source_format
                    recipe.source_file = filepath
                    yield recipe
        elif content.strip():
            recipe = self._parse_single_mastercook(content)
            if recipe:
                recipe.source_format = self.source_format
                recipe.source_file = filepath
                yield recipe

    def parse_buffer(self, f, first_line: str, line_number: int) -> tuple[Optional[Recipe], int]:
        """
        Parse a buffer (file stream) containing MasterCook recipes.
        Reads until the next recipe header or EOF.
        """
        read_lines = 0
        recipe_text = first_line

        for line in f:
            read_lines += 1
            if re.search(self.end_re, line):
                recipe_text += line
                break
            recipe_text += line

        if not recipe_text.strip():
            return (None, read_lines)

        recipe = self._parse_single_mastercook(recipe_text)
        if recipe:
            recipe.source_format = self.source_format
            recipe.source_file = getattr(f, 'name', '')
            return (recipe, read_lines)

        return (None, read_lines)

    def _parse_single_mastercook(self, text: str) -> Optional[Recipe]:
        """Parse a single MasterCook recipe block.

        MasterCook exports fixed-width ASCII text.  This method drives a
        state machine through five named sections: ``header``, ``categories``,
        ``ingredients``, ``instructions``, and ``notes``.  The ingredient table
        uses fixed column offsets (see ``_AMOUNT_COL`` / ``_MEASURE_COL`` /
        ``_INGREDIENT_COL``).  The categories table uses a two-column layout
        (see ``_CATEGORY_COL1`` / ``_CATEGORY_COL2``).

        Args:
                text: Raw text for one recipe (everything after the ``* Exported``
                  header up to, but not including, the next header or EOF).

        Returns:
            A populated ``Recipe`` instance, or ``None`` if the block is empty.
        """
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
        instruction_block: list[str] = []

        for i in range(start_idx + 1, len(lines)):
            line = lines[i].strip('\r') # Keep leading spaces but remove \r
            stripped = line.strip()

            if self.end_re.match(stripped):
                break

            if current_section == 'header':
                author_match = self.author_re.match(stripped)
                if author_match:
                    continue

                yield_match = self.yield_re.match(stripped)
                if yield_match:
                    recipe.yield_amount = yield_match.group(1).strip()
                    continue

            # Section detection
            if self.ingred_re.match(stripped) or self.ingred_line_re.match(stripped):
                if current_section == 'instructions':
                    raise Exception("Ingredient after instruction")
                current_section = 'ingredients_header'
                continue
            elif stripped.startswith(('Directions', 'Instructions')):
                current_section = 'instructions'
                instruction_block = []
                continue
            elif stripped.startswith('Notes:'):
                current_section = 'notes'
                note_text = stripped.replace('Notes:', '', 1).strip()
                if note_text:
                    recipe.instructions.append(note_text)
                continue
            elif stripped.startswith('Categories') or current_section == 'categories':
                current_section = 'categories'
                if not stripped:
                    current_section = 'header'
                    continue

                for category in self.categories_re.findall(stripped):
                    recipe.categories.append(category)

                continue

            # Heuristic for ingredient start even without header
            if ((current_section == 'header' and stripped) and self.ingred_like_re.match(line)) or (current_section == "ingredients_header" and stripped):
                current_section = 'ingredients'

            # Handle sections
            if current_section == 'ingredients':
                if not stripped:
                    current_section = 'instructions'
                    instruction_block = []
                    continue

                is_continuation = False

                if recipe.ingredients and stripped and stripped.startswith('-'):
                    stripped = stripped[1:].strip()
                    is_continuation = True

                parsed = self.ingredient_parser.parse(((recipe.ingredients[-1].raw + " ") if is_continuation else "") + stripped.replace(" -- ", ", "))

                if parsed.name:
                    # Normalize unit
                    parsed.unit = normalize_unit(parsed.unit)
                    if is_continuation:
                        recipe.ingredients[-1] = parsed
                    else:
                        recipe.ingredients.append(parsed)


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
                    recipe.instructions.append(stripped)

        return recipe
