# SPDX-License-Identifier: MIT
"""Parser for From Scratch recipe format (.fs, .fsx)."""
import logging
from pathlib import Path
import re
from typing import Iterator

from .base import BaseRecipeParser, BaseIngredientParser
from .models import Recipe, Ingredient
from .registry import ParserRegistry

logger = logging.getLogger(__name__)


@ParserRegistry.register
class FromScratchParser(BaseRecipeParser):
    """Parser for the From Scratch v2.0 recipe text export format (.fs, .fsx).

    Delimited by:
    ********** FROM SCRATCH [V ...] RECIPE BEGINS ********
    ...
    ********** RECIPE ENDS ********
    """

    BEGIN_RE = re.compile(
        r"\*{10}\s*FROM\s+SCRATCH(?:\s+V\s*[\d.]+)?\s+RECIPE\s+BEGINS\s*\*{8}",
        re.IGNORECASE,
    )
    END_RE = re.compile(r"\*{5,}\s*RECIPE\s+ENDS", re.IGNORECASE)

    def __init__(self, ingredient_parser: BaseIngredientParser):
        super().__init__(ingredient_parser)
        self.source_format = "From Scratch"

    @classmethod
    def format_id(cls) -> str:
        return "fromscratch"

    @classmethod
    def priority(cls) -> int:
        return 10

    @classmethod
    def supported_extensions(cls) -> set[str]:
        return {".fs", ".fsx", ".txt"}

    @classmethod
    def detect(cls, filepath: str, content_sample: str) -> float:
        """Return confidence score for From Scratch format."""
        if not content_sample:
            return 0.0

        if cls.BEGIN_RE.search(content_sample):
            return 0.99

        ext = Path(filepath).suffix.lower()
        if ext in {".fs", ".fsx"} and re.search(r"Title\s*:", content_sample, re.IGNORECASE):
            return 0.85

        return 0.0

    def parse_content(self, content: str, filepath: str = "") -> Iterator[Recipe]:
        """Yield Recipe objects parsed from From Scratch content."""
        if self.BEGIN_RE.search(content):
            sections = self.BEGIN_RE.split(content)
        elif self.END_RE.search(content):
            sections = self.END_RE.split(content)
        elif re.search(r"(?i)^\s*Title\s*:", content, re.MULTILINE):
            sections = re.split(r"(?=(?i)^\s*Title\s*:)", content, flags=re.MULTILINE)
        else:
            sections = [content]

        for section in sections:
            section_clean = section.strip()
            if not section_clean:
                continue

            recipe = self._parse_section(section_clean, filepath)
            if recipe and recipe.title:
                yield recipe

    def _parse_section(self, section: str, filepath: str) -> Recipe:
        recipe = Recipe(source_file=filepath, source_format=self.source_format)
        lines = section.splitlines()

        state = "HEADER"
        inst_paragraphs: list[str] = []
        current_inst: list[str] = []
        notes_lines: list[str] = []
        minutes = ""
        origin = ""

        for line in lines:
            stripped = line.strip().replace("\x14", " ")

            if self.END_RE.search(stripped):
                break

            if state == "HEADER":
                m_ing = re.match(r"^Ingredients\s*:\s*(.*)$", stripped, re.IGNORECASE)
                if m_ing:
                    state = "INGREDIENTS"
                    inline_ing = m_ing.group(1).strip()
                    if inline_ing:
                        if self.ingredient_parser:
                            recipe.ingredients.append(self.ingredient_parser.parse(inline_ing))
                        else:
                            recipe.ingredients.append(Ingredient(raw=inline_ing))
                    continue

                m_inst = re.match(
                    r"^(?:Instructions|Preparation|Directions)\s*:\s*(.*)$",
                    stripped,
                    re.IGNORECASE,
                )
                if m_inst:
                    state = "INSTRUCTIONS"
                    inline_inst = m_inst.group(1).strip()
                    if inline_inst:
                        current_inst.append(inline_inst)
                    continue

                m_hdr = re.match(r"^([A-Za-z ]+)\s*:\s*(.*)$", stripped)
                if m_hdr:
                    key = m_hdr.group(1).strip().lower()
                    val = m_hdr.group(2).strip()
                    if key == "title":
                        recipe.title = val
                    elif key == "serves":
                        recipe.yield_amount = val
                    elif key in ("keywords", "keyword"):
                        if val:
                            cats: list[str] = []
                            for c in re.split(r"[, ]+", val):
                                c = c.strip()
                                if c and c not in cats:
                                    cats.append(c)
                            recipe.categories = cats
                    elif key == "minutes":
                        minutes = val
                    elif key == "origin":
                        origin = val

            elif state == "INGREDIENTS":
                m_inst = re.match(
                    r"^(?:Instructions|Preparation|Directions)\s*:\s*(.*)$",
                    stripped,
                    re.IGNORECASE,
                )
                if m_inst:
                    state = "INSTRUCTIONS"
                    inline_inst = m_inst.group(1).strip()
                    if inline_inst:
                        current_inst.append(inline_inst)
                    continue

                m_notes = re.match(r"^Notes\s*:\s*(.*)$", stripped, re.IGNORECASE)
                if m_notes:
                    state = "NOTES"
                    inline_note = m_notes.group(1).strip()
                    if inline_note and not self.END_RE.search(inline_note):
                        notes_lines.append(inline_note)
                    continue

                if stripped:
                    if self.ingredient_parser:
                        recipe.ingredients.append(self.ingredient_parser.parse(stripped))
                    else:
                        recipe.ingredients.append(Ingredient(raw=stripped))

            elif state == "INSTRUCTIONS":
                m_notes = re.match(r"^Notes\s*:\s*(.*)$", stripped, re.IGNORECASE)
                if m_notes:
                    state = "NOTES"
                    if current_inst:
                        inst_paragraphs.append(" ".join(current_inst))
                        current_inst = []
                    inline_note = m_notes.group(1).strip()
                    if inline_note and not self.END_RE.search(inline_note):
                        notes_lines.append(inline_note)
                    continue

                if stripped:
                    current_inst.append(stripped)
                else:
                    if current_inst:
                        inst_paragraphs.append(" ".join(current_inst))
                        current_inst = []

            elif state == "NOTES":
                if stripped and not self.END_RE.search(stripped):
                    notes_lines.append(stripped)

        if current_inst:
            inst_paragraphs.append(" ".join(current_inst))
        recipe.instructions = inst_paragraphs

        desc_parts: list[str] = []
        if origin:
            desc_parts.append(f"Origin: {origin}")
        if minutes:
            desc_parts.append(f"Minutes: {minutes}")
        if notes_lines:
            desc_parts.append(" ".join(notes_lines))
        if desc_parts:
            recipe.description = "\n\n".join(desc_parts)

        return recipe
