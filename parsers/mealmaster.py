# SPDX-License-Identifier: MIT
import logging
import re
from collections.abc import Iterator
from enum import Enum
from pathlib import Path

from .base import BaseIngredientParser, BaseRecipeParser
from .models import Ingredient, Recipe
from .registry import ParserRegistry

logger = logging.getLogger(__name__)

@ParserRegistry.register
class MealMasterParser(BaseRecipeParser):
    HEADER_RE = re.compile(
        r"^.*(?:MMMMM|-----).*(?:Meal-Master|Recipe via)", re.IGNORECASE
    )
    TRAILER_RE = re.compile(r"^\s*(?:MMMMM|-----*)\s*$", re.IGNORECASE)
    TITLE_RE = re.compile(r"^.{0,6}Title: ", re.IGNORECASE)
    SECTION_RE = re.compile(r"[ -]{3}", re.IGNORECASE)

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
        if Path(filepath).suffix.lower() == ".mmf":
            return 1.0
        if not content_sample:
            return 0.0
        if cls.HEADER_RE.search(content_sample):
            return 0.90
        if cls.TITLE_RE.search(content_sample):
            return 0.70
        return 0.0

    def parse_content(self, content: str, filepath: str) -> Iterator[Recipe]:
        lines = content.splitlines()
        current: list[str] = []
        in_recipe = False

        line_number = 0
        recipe_start = 0

        for line in lines:
            line_number = line_number + 1
            if self.HEADER_RE.match(line):
                if in_recipe and current:
                    logger.warning(
                        "MealMaster parser: Missing recipe trailer line before next recipe header in %s at %d",
                        filepath,
                        line_number,
                    )
                    yield self._parse_single_mealmaster(current, filepath, recipe_start)
                    current = []
                in_recipe = True
                recipe_start = line_number
            elif self.TITLE_RE.match(line) and not in_recipe:
                if current and "\n".join(current).strip():
                    logger.warning(
                        "MealMaster parser: Found Title: line without preceding recipe header in %s at %d. Dropping lines before title",
                        filepath,
                        recipe_start,
                    )
                    current = []
                in_recipe = True
                recipe_start = line_number
                current.append(line)
            elif self.TRAILER_RE.match(line):
                if in_recipe:
                    yield self._parse_single_mealmaster(current, filepath, recipe_start)
                    current = []
                    in_recipe = False
            else:
                if in_recipe:
                    current.append(line)

        if current and "\n".join(current).strip():
            yield self._parse_single_mealmaster(current, filepath, recipe_start)

    def parse_buffer(
        self, f, first_line: str, start_line
    ) -> tuple[Recipe|None, int]:
        """
        Parse a buffer (file stream) containing MealMaster recipes.
        Reads until the next recipe trailer or header EOF.
        """
        read_lines = 1
        lines = [first_line]

        for line in f:
            read_lines += 1
            lines.append(line)
            if self.TRAILER_RE.match(line):
                break
            if len(lines) > 1 and self.HEADER_RE.match(line):
                break

        recipe_text = "".join(lines)
        if not recipe_text.strip():
            return (None, read_lines)

        recipe = self._parse_single_mealmaster(
            lines, getattr(f, "name", "buffer"), start_line
        )
        return (recipe, read_lines)

    def _parse_column_stream(self, stream: list[str], recipe: Recipe, filepath: str):
        """Parse a single column stream of ingredient lines (top to bottom)."""

    def _is_ingredient_separator(self, line: str) -> bool:
        return (
            (len(line) >= 40)
            and ((line[0:5] == "-----") or (line[0:5].lower() == "mmmmm"))
            and not self.SECTION_RE.search(
                line[int(len(line) / 2) - 1 : int(len(line) / 2) + 2]
            )
        )

    def _parse_single_mealmaster(
        self, lines: list[str], filepath: str, start_line: int
    ) -> Recipe|None:
        recipe = Recipe(source_file=filepath, source_format=self.source_format)

        class RecipeSection(Enum):
            BEFORE_HEADER = (1,)
            IN_HEADER = 2
            IN_INGREDIENTS = 3
            IN_INSTRUCTIONS = 4

        class Section:
            Title: str
            Ingredients: list[str]

            def __init__(self) -> None:
                self.Ingredients = []
                self.Title = ""

            def _is_dual_column(self) -> bool:
                """Check if ingredient lines contain a second column (pos 40+). This must be true for first line at least."""

                return len(self.Ingredients) and len(self.Ingredients[0]) and (self.Ingredients[0][39:].strip())

            def _flush_ingredient(self, recipe: Recipe, current_raw: list[str], parser):
                if not current_raw:
                    return
                raw_text = " ".join(current_raw).strip()
                current_raw.clear()
                if not raw_text:
                    return

                parsed = parser.parse(raw_text)
                recipe.ingredients.append(parsed)

            def parse(self, parser, recipe):
                if self._is_dual_column():
                    self.Ingredients = [line[:39] for line in self.Ingredients] + [
                        line[39:] for line in self.Ingredients
                    ]

                current_raw: list[str] = []

                if len(self.Title):
                    recipe.ingredients.append(Ingredient(f"----- {self.Title} -----"))

                for line in self.Ingredients:
                    stripped = line.strip()
                    if not stripped:
                        self._flush_ingredient(recipe, current_raw, parser)

                    if not re.search(r"[a-zA-Z0-9]", stripped):
                        continue

                    is_continuation = False
                    if current_raw:
                        if stripped.startswith("-"):
                            is_continuation = True
                        elif not stripped[0].isdigit():
                            first_word = stripped.split()[0] if stripped.split() else ""
                            if first_word and (
                                first_word[0].islower()
                                or stripped[0] in "(-"
                                or first_word.lower()
                                in ["or", "and", "to", "for", "with"]
                            ):
                                is_continuation = True

                    if is_continuation and current_raw:
                        # TODO: Continuation with "-" is not really used properly in the sample files.
                        # raise Exception(f"is continuation: {recipe.title} in {recipe.source_file}")
                        current_raw.append(stripped.lstrip("-").strip())
                    else:
                        self._flush_ingredient(recipe, current_raw, parser)
                        current_raw = [stripped]

                self._flush_ingredient(recipe, current_raw, parser)

        state: RecipeSection = RecipeSection.BEFORE_HEADER

        instruction_lines: list[str] = []
        ingredient_section: Section = Section()
        for line in lines:
            line_str = line.rstrip()
            stripped = line_str.strip()

            if self.HEADER_RE.match(line_str) or self.TRAILER_RE.match(line_str):
                state = RecipeSection.BEFORE_HEADER
                continue

            if state == RecipeSection.BEFORE_HEADER and not stripped:
                state = RecipeSection.IN_HEADER
                continue

            if state == RecipeSection.IN_HEADER or state == RecipeSection.BEFORE_HEADER:
                if stripped.startswith("Title:"):
                    recipe.title = line_str.split(":", 1)[1].strip()
                    continue

                if stripped.startswith("Categories:"):
                    cats = line_str.split(":", 1)[1].strip()
                    recipe.categories = [
                        c.strip() for c in cats.split(",") if c.strip()
                    ]
                    continue

                if stripped.startswith(("Yield:", "Servings:")):
                    recipe.yield_amount = line_str.split(":", 1)[1].strip()
                    continue

                if not stripped:
                    state = RecipeSection.IN_INGREDIENTS
                    continue

            if state == RecipeSection.IN_INSTRUCTIONS:
                if (
                    not len(instruction_lines)
                    and not len(recipe.instructions)
                    and self._is_ingredient_separator(line)
                ):
                    state = RecipeSection.IN_INGREDIENTS
                else:
                    if not stripped:
                        instruction_para = " ".join(instruction_lines).strip()
                        if len(instruction_para):
                            recipe.instructions.append(instruction_para)
                        instruction_lines = []
                        continue
                    else:
                        instruction_lines.append(stripped)
                        continue

            if state == RecipeSection.IN_INGREDIENTS:
                if self._is_ingredient_separator(line):
                    if len(ingredient_section.Ingredients):
                        ingredient_section.parse(self.ingredient_parser, recipe)
                        ingredient_section = Section()

                    ingredient_section.Title = line[5:].strip("- =M\t")
                    continue

                if not stripped:
                    ingredient_section.parse(self.ingredient_parser, recipe)
                    ingredient_section = Section()
                    state = RecipeSection.IN_INSTRUCTIONS
                    continue

                ingredient_section.Ingredients.append(line)

        if not recipe.title:
            logger.warning(
                "MealMaster parser: Recipe missing title in %s at %d",
                filepath,
                start_line,
            )
            return None

        if len(recipe.ingredients) == 0:
            logger.warning(
                "MealMaster parser: Recipe '%s' (%s at %d) has no ingredients",
                recipe.title,
                filepath,
                start_line,
            )

        if len(recipe.instructions) == 0:
            logger.warning(
                "MealMaster parser: Recipe '%s' (%s at %d) has no instructions",
                recipe.title,
                filepath,
                start_line,
            )

        recipe.url = f"file://{filepath}#{start_line}"
        return recipe
