# SPDX-License-Identifier: MIT
"""
Vitt CSV parser - converts CSV recipe format to internal Recipe model

CSV columns: RNUM, NAME, KING, SOURCE, TXT, TAG

TXT Format:
The TXT field contains logical blocks separated by blank lines:
1. INTRODUCTION block(s) - description/commentary at the beginning
2. TITLE block - optional recipe title (Title Cased)
3. INGREDIENT blocks - items and section headers like "Crust:", "Filling:"
4. INSTRUCTION blocks - steps or narrative

Strategy:
1. Handle line continuations (lines ending with _ are continued on next line)
2. Split into blocks by blank lines
3. Categorize blocks: introduction → title → ingredients → instructions
4. Section headers stay with ingredients
5. Merge all instruction blocks into single instructions list (one line per instruction)
6. Keep ingredient blocks as-is with their section headers
"""

import csv
import logging
import re
import io
import textwrap
from typing import Iterator, List, Optional, Tuple
from pathlib import Path
from enum import Enum

from .base import BaseRecipeParser, BaseIngredientParser
from .models import Recipe, Ingredient

logger = logging.getLogger(__name__)


class BlockType(Enum):
    """Block classification."""
    INTRODUCTION = "introduction"
    TITLE = "title"
    INGREDIENTS = "ingredients"
    INSTRUCTIONS = "instructions"
    UNKNOWN = "unknown"


from .registry import ParserRegistry

@ParserRegistry.register
class VittRecipesParser(BaseRecipeParser):
    """Parser for vitt CSV format."""

    def __init__(self, ingredient_parser: BaseIngredientParser):
        super().__init__(ingredient_parser)
        self.source_format = "vitt CSV"

    @classmethod
    def format_id(cls) -> str:
        return "csv_vitt"

    @classmethod
    def aliases(cls) -> list[str]:
        return ["vitt"]

    @classmethod
    def priority(cls) -> int:
        return 19

    @classmethod
    def detect(cls, filepath: str, content_sample: str) -> float:
        if not content_sample:
            return 0.0
        try:
            reader = csv.reader(io.StringIO(content_sample))
            headers = next(reader)
            expected = ["RNUM", "NAME", "KING", "SOURCE", "TXT", "TAG"]
            if len(headers) >= 6 and headers[:6] == expected:
                return 0.95
        except Exception:
            pass
        return 0.0

    def parse_content(self, content: str, filepath: str) -> Iterator[Recipe]:
        """Parse CSV content and yield Recipe objects."""
        if not content.strip():
            return

        # Parse as CSV
        try:
            csv_reader = csv.DictReader(io.StringIO(content))
            row_number = 2  # Start at 2 (after header)
            for row in csv_reader:
                recipe = self._parse_csv_row(row, filepath, row_number)
                if recipe.title:
                    yield recipe
                row_number += 1
        except Exception as e:
            logger.warning("Error parsing CSV: %s", e)
            return

    def _parse_csv_row(self, row: dict, filepath: str, row_number: int) -> Recipe:
        """Convert a CSV row to a Recipe object."""
        recipe = Recipe(source_file=filepath, source_format=self.source_format)

        # Get raw TXT field
        txt = row.get("TXT", "").strip()

        # Remove problematic Unicode characters (ZWJ: U+200D encoded as 0xC2 0x8D in UTF-8)
        # These are artifacts from formatting and should be removed entirely
        txt = txt.replace('\u200d', '')  # Remove Zero Width Joiner

        # Handle line continuations (lines ending with _)
        txt = self._handle_line_continuations(txt)

        # Categorize blocks
        blocks_with_types = self._categorize_blocks(txt)

        # Extract title from NAME column or title block
        name = row.get("NAME", "").strip()
        title_block = next((b for b, t in blocks_with_types if t == BlockType.TITLE), None)

        recipe.title = self._to_title_case(name)

        # Keywords / Categories
        keyword = row.get("KING", "").strip()
        if keyword and keyword.upper() != "NULL":
            recipe.categories = [k.strip() for k in keyword.split('/') if k.strip()]

        # Process categorized blocks
        self._process_blocks(blocks_with_types, recipe)

        return recipe

    def _handle_line_continuations(self, txt: str) -> str:
        """
        Handle lines ending with underscore (_) as line continuations.
        These lines should be merged with the next line.
        """
        lines = txt.split('\n')
        result = []
        i = 0

        while i < len(lines):
            line = lines[i]

            # Check if line ends with underscore (continuation)
            while i < len(lines) and line.rstrip().endswith('_'):
                # Remove the trailing underscore and merge with next line
                line = line.rstrip()[:-1]  # Remove the _
                if i + 1 < len(lines):
                    line = line + lines[i + 1]
                    i += 1
                else:
                    break

            result.append(line)
            i += 1

        return '\n'.join(result)

    def _categorize_blocks(self, txt: str) -> List[Tuple[str, BlockType]]:
        """
        Categorize blocks into: introduction → title → ingredients → instructions

        Key insight: Ingredients can appear in multiple blocks, separated by instructions.
        For example: "Crust: [ingredients] [instructions] Filling: [ingredients] [instructions]"

        Returns list of (block_content, block_type) tuples.
        """
        blocks = self._split_blocks(txt)
        categorized = []
        seen_title = False
        seen_ingredients = False

        for block in blocks:
            block = block.strip()
            if not block:
                continue

            # Stage 1: Introduction blocks (before title or ingredients)
            if not seen_title and not seen_ingredients:
                if self._looks_like_introduction(block):
                    categorized.append((block, BlockType.INTRODUCTION))
                    continue

            # Stage 2: Title block (single line, properly Title Cased)
            if not seen_title and not seen_ingredients:
                if self._looks_like_title(block):
                    categorized.append((block, BlockType.TITLE))
                    seen_title = True
                    continue

            # Stage 3 & 4: Check if block is ingredients
            # Key: Even after we've seen instructions, we can see more ingredient blocks
            # (identified by starting with section header or >50% ingredient-like lines)
            if self._is_ingredient_block(block):
                categorized.append((block, BlockType.INGREDIENTS))
                seen_ingredients = True
                continue

            # Stage 4: Everything else after title is instructions
            if seen_ingredients or seen_title:
                categorized.append((block, BlockType.INSTRUCTIONS))
                continue

            # Fallback: if we haven't classified yet, default to instructions
            categorized.append((block, BlockType.INSTRUCTIONS))

        return categorized

    def _process_blocks(self, blocks_with_types: List[Tuple[str, BlockType]], recipe: Recipe) -> None:
        """Process categorized blocks and populate recipe."""
        # Collect all ingredient blocks
        ingredient_blocks = []
        instruction_blocks = []

        for block, block_type in blocks_with_types:
            if block_type == BlockType.INGREDIENTS:
                ingredient_blocks.append(block)
            elif block_type == BlockType.INSTRUCTIONS:
                instruction_blocks.append(block)

        # Extract ingredients from all ingredient blocks
        for block in ingredient_blocks:
            self._extract_ingredients(block, recipe)

        # Extract instructions from all instruction blocks (merged)
        for block in instruction_blocks:
            self._extract_instructions(block, recipe)

    def _looks_like_introduction(self, block: str) -> bool:
        """Check if a block looks like introductory commentary."""
        lines = block.split('\n')

        # Single-line blocks that look like titles don't count as introduction
        if len(lines) == 1:
            line = lines[0].strip()
            # Section headers like "Crust:" are not introduction
            if re.match(r'^[A-Za-z\s]+:\s*$', line):
                return False

        # Check for introduction patterns
        introduction_patterns = [
            r'^contributed',
            r'^(i |you |he |she |we |they |my |your |his |her |our |their )',
            r'(thank|appreciate|enjoyed|wonderful|delicious|great)',
            r'^CC>',
            r'^(.*?ph\.?s\.?.*?)$',  # P.S. patterns
        ]

        for line in lines:
            line_lower = line.strip().lower()
            if not line_lower:
                continue

            for pattern in introduction_patterns:
                if re.search(pattern, line_lower):
                    return True

        return False

    def _looks_like_title(self, block: str) -> bool:
        """Check if a single block is a recipe title."""
        lines = [line.strip() for line in block.split('\n') if line.strip()]

        # Title must be a single line
        if len(lines) != 1:
            return False

        line = lines[0].rstrip(':')

        # Check if line looks like a title (not instruction, not commentary)
        return self._line_looks_like_title(line)

    def _line_looks_like_title(self, line: str) -> bool:
        """Check if a line looks like a recipe title."""
        if len(line) > 80 or len(line) < 3:
            return False

        # Reject obvious instruction lines
        instruction_patterns = [
            r'\b(add|mix|stir|heat|cook|bake|pour|place|combine|blend|whisk|fold|'
            r'arrange|serve|slice|cut|dice|chop|peel|boil|fry|sauté|simmer|grill|'
            r'roast|baste|marinate|season|sprinkle|drizzle|layer|spread|flip|turn|'
            r'reduce|thicken|strain|drain|reserve|save|garnish|top|dust)\b'
        ]

        line_lower = line.lower()
        for pattern in instruction_patterns:
            if re.search(pattern, line_lower):
                return False

        # Reject personal commentary patterns
        commentary_patterns = [
            r'^(contributed|i |you |he |she |we |they |my |your |his |her |our |their )',
            r'(thank|appreciate|enjoyed|wonderful)',
            r'^CC>',
        ]

        for pattern in commentary_patterns:
            if re.search(pattern, line_lower):
                return False

        # Check if it has proper Title Case (at least one capital, mix of cases)
        has_cap = any(c.isupper() for c in line)
        has_lower = any(c.islower() for c in line)

        if not (has_cap and has_lower):
            return False

        # Titles don't end with periods or question marks
        if line.endswith(('.', '?', '!')):
            return False

        return True

    def _to_title_case(self, text: str) -> str:
        """Convert ALL CAPS text to Title Case intelligently."""
        if not text:
            return text

        # If it's already mixed case, return as-is
        if any(c.islower() for c in text):
            return text

        words = text.split()
        small_words = {'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of', 'the', 'with', 'by', 'w'}

        result = []
        for i, word in enumerate(words):
            if i == 0:
                result.append(word.capitalize())
            elif i == len(words) - 1:
                result.append(word.capitalize())
            elif word.lower() in small_words and not result[-1].endswith('('):
                result.append(word.lower())
            else:
                result.append(word.capitalize())

        return ' '.join(result)

    def _split_blocks(self, text: str) -> List[str]:
        """Split text into blocks separated by blank lines.

        First removes any Zero Width Joiner characters that might interfere with parsing.
        """
        # Remove Zero Width Joiner (U+200D) which can appear as formatting artifact
        text = text.replace('\u200d', '')

        # Split by blank lines (one or more newlines with optional whitespace)
        blocks = re.split(r'\n\s*\n+', text)
        return blocks

    def _is_ingredient_block(self, block: str) -> bool:
        """
        Heuristic to determine if a block contains ingredients.

        A block is an ingredient block if:
        1. It starts with a section header (Crust:, Filling:, etc.), OR
        2. >50% of its lines look like ingredients
        """
        lines = block.split('\n')
        if not lines:
            return False

        # Check if first non-empty line is a section header
        for line in lines:
            line = line.strip()
            if line:
                if re.match(r'^[a-zA-Z\s]+:\s*$', line):
                    # Starts with section header - this is definitely an ingredient block
                    return True
                break  # Stop after checking first non-empty line

        # Otherwise, check if >50% of lines look like ingredients
        ingredient_like_count = 0
        total_lines = 0

        for line in lines:
            line = line.strip()
            if not line:
                continue

            total_lines += 1
            if self._line_looks_like_ingredient(line):
                ingredient_like_count += 1

        if total_lines == 0:
            return False

        return ingredient_like_count / total_lines > 0.5

    def _line_looks_like_ingredient(self, line: str) -> bool:
        """Check if a single line looks like an ingredient."""
        if not line or len(line) > 150:
            return False

        line_lower = line.lower()

        # Section headers like "Crust:" or "Filling:" are ingredient markers
        if re.match(r'^[a-zA-Z\s]+:\s*$', line):
            return True

        # Numbered instruction lines (1., 2., 3., etc.) are NOT ingredients
        if re.match(r'^\d+\.\s+', line):
            return False

        # Reject obvious instruction patterns
        instruction_verbs = [
            r'\b(add|mix|stir|heat|cook|bake|pour|place|combine|blend|whisk|fold|'
            r'arrange|serve|slice|cut|dice|chop|peel|boil|fry|sauté|simmer|grill|'
            r'roast|baste|marinate|season|sprinkle|drizzle|layer|spread|flip|turn|'
            r'reduce|thicken|strain|drain|reserve|save|garnish|top|dust)\b'
        ]

        instruction_phrases = [
            r'(until|then|after|before|while|for\s+\d+|during)',
            r'(cool|chill|refrigerate|freeze|let|allow)',
        ]

        for pattern in instruction_verbs + instruction_phrases:
            if re.search(pattern, line_lower):
                return False

        # Strong indicators that this IS an ingredient
        ingredient_starters = [
            # Fractions: 1/2, 1/3, 2/3, 3/4, etc.
            r'^(1/2|1/3|1/4|2/3|3/4)\s',
            # Decimal quantities: 1.5, 2.0, etc.
            r'^\d+\.\d+\s',
            # Ranges: 1-2, 3-4, etc.
            r'^\d+-\d+\s',
            # Quantities with measure words: "2 cups", "3 tablespoons"
            r'^\d+\s+(cup|tsp|tbsp|oz|lb|ml|l|mg|g|pkg|package)',
            # Measure words at start: "a cup", "some salt", "dash of"
            r'^(a|an|some|few|dash|pinch|splash|handful)\s',
            # Ingredient qualifiers
            r'^(to\s+taste|optional|fresh|dried)',
        ]

        for pattern in ingredient_starters:
            if re.search(pattern, line_lower):
                return True

        # Short lines without obvious instruction markers are likely ingredients
        if len(line) < 80:
            sentence_indicators = r'[.?!]\s*$|^[A-Z][a-z]+\s+(is|are|was|were|can|do|did|have|has)\b'
            if not re.search(sentence_indicators, line):
                return True

        return False

    def _extract_ingredients(self, block: str, recipe: Recipe) -> None:
        """Extract individual ingredients from a block and add to recipe."""
        lines = block.split('\n')
        for line in lines:
            line = line.strip()
            if not line:
                continue
            # Remove Zero Width Joiner (U+200D) characters
            line = line.replace('\u200d', '')
            # Normalize whitespace (replace multiple spaces with single space)
            line = re.sub(r'\s+', ' ', line)
            line = line.strip()
            if line and self.ingredient_parser:
                ingredient = self.ingredient_parser.parse(line)
                if ingredient.raw:
                    recipe.ingredients.append(ingredient)

    def _extract_instructions(self, block: str, recipe: Recipe) -> None:
        """Extract instructions from a block and add as a single instruction step.

        Each instruction BLOCK (separated by blank lines) becomes ONE instruction step.
        Removes Zero Width Joiner characters and normalizes whitespace.
        """
        block = block.strip()
        if block:
            # Remove Zero Width Joiner (U+200D) characters
            block = block.replace('\u200d', '')
            # Replace newlines and multiple spaces with single space
            block = re.sub(r'\s+', ' ', block)
            # Clean up any trailing/leading whitespace again
            block = block.strip()
            if block:
                recipe.instructions.append(block)
