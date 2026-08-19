# SPDX-License-Identifier: MIT
import logging
import re
from typing import Iterator
from .base import BaseRecipeParser, BaseIngredientParser
from .models import Recipe
from .registry import ParserRegistry

logger = logging.getLogger(__name__)


@ParserRegistry.register
class IdCapsParser(BaseRecipeParser):
    """Parser for ID Caps recipe format.

    - All recipes start with an ID -- recipe name (e.g. `` 461559 -- DIABETIC DATE DAINTIES``)
    - All recipes end with a set of 13+ dashes (``------------------------``)
    - Sections within a recipe are separated by blank lines
    - First line in each section is indented by a space
    - Ingredients can contain headings (e.g. ``--GRAHAM CRACKER CRUST:--``)
    """

    def __init__(self, ingredient_parser: BaseIngredientParser):
        super().__init__(ingredient_parser)
        self.source_format = "ID Caps"

    @classmethod
    def format_id(cls) -> str:
        return "id_caps"

    @classmethod
    def aliases(cls) -> list[str]:
        return ["idcaps", "id caps"]

    @classmethod
    def priority(cls) -> int:
        return 6

    @classmethod
    def detect(cls, filepath: str, content_sample: str) -> float:
        if not content_sample:
            return 0.0
        if not re.search(r"^\s*-{13,}\s*$", content_sample, re.MULTILINE):
            return 0.0
        title_matches = re.findall(
            r"^\s*([0-9A-Za-z_-]+)\s*--\s*([A-Z0-9\s\x27-]{3,})$",
            content_sample,
            re.MULTILINE,
        )
        if not title_matches:
            return 0.0
        lines = [l for l in content_sample.splitlines() if l.strip()]
        if lines and re.match(
            r"^\s*([0-9A-Za-z_-]+)\s*--\s*([A-Z0-9\s\x27-]{3,})$", lines[0]
        ):
            return 0.95
        return 0.0

    def parse_content(self, content: str, filepath: str = "") -> Iterator[Recipe]:
        raw_blocks = re.split(r"^\s*-{13,}\s*$", content, flags=re.MULTILINE)

        for raw_block in raw_blocks:
            block = raw_block.strip()
            if not block:
                continue

            raw_sections = re.split(r"\n\s*\n+", raw_block)
            sections = []
            for s in raw_sections:
                s_lines = [l for l in s.splitlines() if l.strip()]
                if s_lines:
                    sections.append(s_lines)

            if not sections:
                continue

            title_line = sections[0][0]
            m = re.match(r"^\s*([0-9A-Za-z_-]+)\s*--\s*(.+)$", title_line)
            if not m:
                continue

            recipe_id = m.group(1).strip()
            raw_title = m.group(2).strip()
            title = re.sub(r"\s+", " ", raw_title)

            recipe = Recipe(
                title=title,
                sqlite_id=recipe_id,
                source_format=self.source_format,
                source_file=filepath,
            )

            for sec_lines in sections[1:]:
                stype = self._classify_section(sec_lines)
                if stype == "ingredients":
                    curr_ing_raw = ""
                    for l in sec_lines:
                        # Continuation line check: starts with 3+ spaces and no leading quantity
                        if (
                            curr_ing_raw
                            and l.startswith("   ")
                            and not re.match(
                                r"^(\d+|\d+/\d+|\d+\.\d+)", l.strip()
                            )
                        ):
                            curr_ing_raw += " " + l.strip()
                        else:
                            if curr_ing_raw:
                                recipe.ingredients.append(
                                    self.ingredient_parser.parse(curr_ing_raw)
                                )
                            curr_ing_raw = l.strip()
                    if curr_ing_raw:
                        recipe.ingredients.append(
                            self.ingredient_parser.parse(curr_ing_raw)
                        )
                else:
                    step_text = re.sub(r"\s+", " ", " ".join(sec_lines)).strip()
                    if step_text:
                        recipe.instructions.append(step_text)

            yield recipe

    def _classify_section(self, sec_lines: list[str]) -> str:
        first = sec_lines[0].strip()

        # Heading check: e.g. --CRUST:-- or Filling:
        if (first.startswith("--") and first.endswith("--")) or (
            first.endswith(":") and len(first) < 50
        ):
            return "ingredients"

        def _is_ing_line(line: str) -> bool:
            s = line.strip()
            if not s:
                return False
            if re.match(
                r"^(\d+|\d+/\d+|\d+\.\d+|dash|pinch|few|some|a|an)\b",
                s,
                re.IGNORECASE,
            ):
                if len(s) > 80 and re.search(
                    r"\b(bake|heat|simmer|mix|stir|combine|sift|serve|yield)\b",
                    s,
                    re.IGNORECASE,
                ):
                    return False
                return True
            return False

        ing_count = sum(1 for l in sec_lines if _is_ing_line(l))
        if len(sec_lines) > 1 and ing_count / len(sec_lines) >= 0.5:
            return "ingredients"
        if len(sec_lines) == 1 and _is_ing_line(first) and len(first) < 60:
            return "ingredients"

        return "instructions"
