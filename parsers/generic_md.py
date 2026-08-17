# SPDX-License-Identifier: MIT
"""Generic Markdown recipe parser for converted DOCX/MD files."""

import logging
import re
from pathlib import Path
from typing import Iterator, Optional

from .base import BaseRecipeParser, BaseIngredientParser
from .models import Recipe, Ingredient
from .registry import ParserRegistry
from .units import normalize_unit

logger = logging.getLogger(__name__)


@ParserRegistry.register
class GenericMdParser(BaseRecipeParser):
    """Parser for generic Markdown recipes (e.g. converted from DOCX).

    Expected layout:
    - Title on first non-empty row (plain text, # heading, or **bold**).
    - Irrelevant preamble (text, images, links).
    - Section header for Ingredients (e.g. "Ingredients:", "## Ingredients").
    - Ingredients list (one per line, optional empty lines or bullet points).
    - Section header for Preparation / Directions (e.g. "Preparation:", "Directions:").
    - Preparation steps until end of file / recipe separator.
    - Multiple recipes per file separated by at least 12 dashes (--------------------).
    """

    def __init__(self, ingredient_parser: BaseIngredientParser):
        super().__init__(ingredient_parser)
        self.source_format = "Generic Markdown"

    @classmethod
    def format_id(cls) -> str:
        return "generic_md"

    @classmethod
    def aliases(cls) -> list[str]:
        return ["generic-md", "genericmd", "md_generic"]

    @classmethod
    def priority(cls) -> int:
        return 25

    @classmethod
    def detect(cls, filepath: str, content_sample: str) -> float:
        if not content_sample or not content_sample.strip():
            return 0.0

        # Check for explicit format tag anywhere in content (e.g., at the end of file)
        if re.search(
            r"(?i)(?:\[format:\s*generic[-_]?md\]|<!--\s*format:\s*generic[-_]?md\s*-->|#generic[-_]?md|\bgeneric[-_]?md\b)",
            content_sample,
        ):
            return 1.0

        has_ingredients = bool(
            re.search(
                r"(?i)^\s*(?:#+\s*)?(?:\*{1,3}|_)?ingredients:?",
                content_sample,
                re.MULTILINE,
            )
        )
        has_instructions = bool(
            re.search(
                r"(?i)^\s*(?:#+\s*)?(?:\*{1,3}|_)?(?:preparation|directions|instructions|method|steps):?",
                content_sample,
                re.MULTILINE,
            )
        )

        ext = Path(filepath).suffix.lower()
        if has_ingredients and has_instructions:
            if ext in {".md", ".markdown"}:
                return 0.85
            return 0.50
        elif has_ingredients and ext in {".md", ".markdown"}:
            return 0.40

        return 0.0

    def _clean_title(self, raw_title: str) -> str:
        """Clean markdown markers from title line."""
        title = raw_title.strip()
        # Remove leading Markdown headings (# Title, ## Title)
        title = re.sub(r"^#+\s*", "", title)
        # Remove outer bold/italic markup (**Title**, *Title*, ___Title___)
        title = re.sub(r"^(?:\*{1,3}|_{1,3})(.*?)(?:\*{1,3}|_{1,3})$", r"\1", title)
        return title.strip()

    def _clean_line(self, line: str) -> str:
        """Clean list markers and bullet formatting from line."""
        text = line.strip()
        # Remove bullet points or step numbers (- , * , + , 1. , 2) , • )
        text = re.sub(r"^(?:[-*+•]|\d+[.)])\s+", "", text)
        return text.strip(" -*")

    def _is_ingredients_header(self, line: str) -> bool:
        cleaned = re.sub(r"[^a-zA-Z:]", "", line).lower()
        return cleaned == "ingredients:" or cleaned.startswith("ingredients:")

    def _is_instructions_header(self, line: str) -> bool:
        cleaned = re.sub(r"[^a-zA-Z:]", "", line).lower()
        targets = ["preparation:", "directions:", "instructions:", "method:", "steps:"]
        return any(cleaned == t or cleaned.startswith(t) for t in targets)

    def _parse_single_recipe_block(self, block_text: str, filepath: str = "") -> Optional[Recipe]:
        lines = block_text.splitlines()

        title = "Untitled"
        start_idx = 0

        # Title on first row (or first non-empty line)
        for idx, line in enumerate(lines):
            stripped = line.strip()
            if not stripped:
                continue
            # Skip explicit format tag if present at top of block
            if re.match(
                r"(?i)^\s*(?:\[format:|<!--\s*format:|#generic[-_]?md)", stripped
            ):
                continue
            title = self._clean_title(stripped)
            start_idx = idx + 1
            break

        recipe = Recipe(
            title=title,
            source_format=self.source_format,
            source_file=filepath,
        )

        state = "PREAMBLE"  # States: PREAMBLE -> INGREDIENTS -> INSTRUCTIONS
        current_instruction_step: list[str] = []

        def flush_instruction():
            if current_instruction_step:
                step_text = " ".join(current_instruction_step).strip()
                if step_text:
                    recipe.instructions.append(step_text)
                current_instruction_step.clear()

        for i in range(start_idx, len(lines)):
            line = lines[i]
            stripped = line.strip()

            # Ignore explicit format tag lines
            if re.match(
                r"(?i)^\s*(?:\[format:|<!--\s*format:|#generic[-_]?md)", stripped
            ):
                continue

            # Check for section header transitions
            if self._is_ingredients_header(stripped):
                flush_instruction()
                state = "INGREDIENTS"
                continue
            elif self._is_instructions_header(stripped):
                flush_instruction()
                state = "INSTRUCTIONS"
                continue

            if state == "INGREDIENTS":
                if not stripped:
                    continue
                ing_text = self._clean_line(stripped.replace("--", "-"))
                if ing_text:
                    if self.ingredient_parser:
                        parsed_ing = self.ingredient_parser.parse(ing_text)
                        if parsed_ing.unit:
                            parsed_ing.unit = normalize_unit(parsed_ing.unit)
                        recipe.ingredients.append(parsed_ing)
                    else:
                        recipe.ingredients.append(
                            Ingredient(raw=ing_text, name=ing_text)
                        )
            elif state == "INSTRUCTIONS":
                if not stripped:
                    flush_instruction()
                    continue

                # If this line explicitly starts a new numbered item or bullet list item, flush previous step
                is_new_list_item = bool(re.match(r"^(?:[-*+•]|\d+[.)])\s+", stripped))
                if is_new_list_item and current_instruction_step:
                    flush_instruction()

                inst_text = self._clean_line(stripped)
                if inst_text:
                    current_instruction_step.append(inst_text)

        flush_instruction()

        if recipe.title and (recipe.ingredients or recipe.instructions):
            return recipe
        return None

    def parse_content(self, content: str, filepath: str = "") -> Iterator[Recipe]:
        # Split content into multiple recipe blocks separated by 12 or more dashes (with only whitespace around)
        blocks = re.split(r"(?:^|\n)\s*-{12,}\s*(?:\n|$)", content)
        for block in blocks:
            if not block.strip():
                continue
            recipe = self._parse_single_recipe_block(block, filepath)
            if recipe:
                yield recipe
