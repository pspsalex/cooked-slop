# SPDX-License-Identifier: MIT
import re
from typing import Iterator
from .models import Recipe, Ingredient
from .base import BaseRecipeParser, BaseIngredientParser
from .registry import ParserRegistry


@ParserRegistry.register
class MicroCookParser(BaseRecipeParser):
    """Parser for MicroCook ASCII recipe files (.mca).

    Format structure:
        (preamble, ignored)
        @@@@@ ASCII Recipe from MicroCook V.x.x
        Recipe Name: Title
        Category...: Cat1, Cat2
        Servings...: N

        Ingredients:
        qty unit Ingredient name
            -continuation of ingredient line

        Description:
        Free text... with ^ as soft line-break markers.
        @@@@@ End of Recipe
    """

    RECIPE_START_RE = re.compile(
        r'@{5}\s+ASCII Recipe from MicroCook', re.IGNORECASE
    )
    RECIPE_END = '@@@@@  End of Recipe'
    RECIPE_END_RE = re.compile(r'@{5}.*End of Recipe', re.IGNORECASE)

    def __init__(self, ingredient_parser: BaseIngredientParser):
        super().__init__(ingredient_parser)
        self.source_format = "MicroCook"

    @classmethod
    def format_id(cls) -> str:
        return "microcook"

    @classmethod
    def aliases(cls) -> list:
        return ["mca"]

    @classmethod
    def priority(cls) -> int:
        return 3

    @classmethod
    def detect(cls, filepath: str, content_sample: str) -> float:
        if not content_sample:
            return 0.0
        if re.search(r'ASCII Recipe from MicroCook', content_sample, re.IGNORECASE):
            return 0.97
        import pathlib
        if pathlib.Path(filepath).suffix.lower() == '.mca':
            return 0.5
        return 0.0

    def parse_content(self, content: str, filepath: str) -> Iterator[Recipe]:
        # Split on the end-of-recipe marker, keeping blocks between start and end
        blocks = self.RECIPE_END_RE.split(content)
        for block in blocks:
            # Each block should contain a recipe start header
            if not self.RECIPE_START_RE.search(block):
                continue
            # Strip the start header line itself and everything before it
            block = self.RECIPE_START_RE.split(block, maxsplit=1)[-1]
            block = block.strip()
            if not block:
                continue
            recipe = self._parse_block(block, filepath)
            if recipe and recipe.title:
                yield recipe

    def _parse_block(self, block: str, filepath: str) -> Recipe:
        recipe = Recipe(source_file=filepath, source_format=self.source_format)
        lines = block.splitlines()

        section = None  # 'ingredients' or 'description'
        ingredient_lines: list[str] = []  # buffer for current ingredient (with continuations)
        description_parts: list[str] = []

        def flush_ingredient():
            if ingredient_lines:
                raw = ' '.join(ingredient_lines).strip()
                if raw:
                    recipe.ingredients.append(self.ingredient_parser.parse(raw))
                ingredient_lines.clear()

        for line in lines:
            # --- Header fields ---
            name_match = re.match(r'^Recipe Name\s*:\s*(.*)', line, re.IGNORECASE)
            if name_match:
                recipe.title = name_match.group(1).strip().strip('"')
                # Clean up stray non-ASCII from old BBS transfers
                recipe.title = recipe.title.encode('ascii', errors='ignore').decode()
                recipe.title = recipe.title.strip()
                section = None
                continue

            cat_match = re.match(r'^Category\.*\s*:\s*(.*)', line, re.IGNORECASE)
            if cat_match:
                cats_raw = cat_match.group(1).strip()
                recipe.categories = [c.strip() for c in cats_raw.split(',') if c.strip()]
                section = None
                continue

            srv_match = re.match(r'^Servings\.*\s*:\s*(\S+)', line, re.IGNORECASE)
            if srv_match:
                recipe.yield_amount = srv_match.group(1).strip()
                section = None
                continue

            # --- Section headers ---
            if re.match(r'^Ingredients\s*:', line, re.IGNORECASE):
                flush_ingredient()
                section = 'ingredients'
                continue

            if re.match(r'^Description\s*:', line, re.IGNORECASE):
                flush_ingredient()
                section = 'description'
                continue

            # --- Ingredient section ---
            if section == 'ingredients':
                stripped = line.rstrip()
                if not stripped.strip():
                    # Blank line ends ingredient section, switch to description if
                    # we haven't seen the Description: header yet. Just flush.
                    flush_ingredient()
                    continue

                # Continuation line: starts with whitespace followed by a dash
                if re.match(r'^\s+-', stripped) and ingredient_lines:
                    continuation = re.sub(r'^\s+-', '', stripped).strip()
                    ingredient_lines.append(continuation)
                else:
                    # New ingredient or section divider (e.g. "FROM CHEF FREDDY'S---")
                    # Treat divider-like lines (all caps + dashes) as section labels (skip)
                    flush_ingredient()
                    core = stripped.strip()
                    if not re.match(r'^[A-Z\s\'\-]+[-]{3,}$', core):
                        ingredient_lines.append(core)
                continue

            # --- Description section ---
            if section == 'description':
                # Strip the ^ soft-line-break characters by replacing with space
                cleaned = line.replace('^', ' ')
                description_parts.append(cleaned)
                continue

        # Flush any trailing ingredient
        flush_ingredient()

        # Collapse description into a single instruction string
        if description_parts:
            text = ' '.join(description_parts)
            # Collapse multiple spaces
            text = re.sub(r'  +', ' ', text).strip()
            if text:
                recipe.instructions.append(text)

        return recipe
