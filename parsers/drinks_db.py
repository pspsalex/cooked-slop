# SPDX-License-Identifier: MIT
"""Parser for Mr. Boston Drinks Database (.out, .lst, .txt) files."""
import logging
import re
from pathlib import Path
from typing import Iterator, List, Optional

from .base import BaseIngredientParser, BaseRecipeParser
from .models import Recipe
from .registry import ParserRegistry

logger = logging.getLogger(__name__)

# Regex pattern for identifying glassware entries in 42-char columns
GLASSWARE_PATTERN = re.compile(
    r'^\d*\s*(?:[A-Z0-9\.\-\/&]+\s+)*(?:GLASS|CLASS|MUG|MUGS|GOBLET|CUP|BOWL|FLUTE|TUMBLER|SNIFTER|DECANTER|JAR|JIGGER|STEIN)(?:\s*\(TO SERVE\))?$'
)


@ParserRegistry.register
class DrinksDbParser(BaseRecipeParser):
    """Parser for Mr. Boston Bartending Guide database export files."""

    def __init__(self, ingredient_parser: BaseIngredientParser):
        super().__init__(ingredient_parser)
        self.source_format = "Mr. Boston Bartending Guide"

    @classmethod
    def format_id(cls) -> str:
        """Unique lowercase identifier."""
        return "drinks_db"

    @classmethod
    def priority(cls) -> int:
        """Detection order priority (lower = tried earlier)."""
        return 8

    @classmethod
    def supported_extensions(cls) -> set[str]:
        """File extensions supported by this parser."""
        return {".out", ".lst", ".txt"}

    @classmethod
    def detect(cls, filepath: str, content_sample: str) -> float:
        """Calculate confidence score for Mr. Boston drinks database format.

        Args:
            filepath: Path to recipe file.
            content_sample: Sample of file content.

        Returns:
            Confidence score between 0.0 and 1.0.
        """
        if not content_sample:
            return 0.0

        ext = Path(filepath).suffix.lower()
        has_drink_type = "Drink type:" in content_sample
        has_seasons = "Season(s):" in content_sample

        if ext == ".out" and has_drink_type and has_seasons:
            return 0.95

        has_temp = "Temp:" in content_sample
        has_serve_at = "Serve at:" in content_sample
        if has_drink_type and has_temp and has_serve_at and has_seasons:
            return 0.85

        return 0.0

    def parse_content(self, content: str, filepath: str) -> Iterator[Recipe]:
        """Parse content of a Mr. Boston database export file.

        Args:
            content: Entire file content as string.
            filepath: Original file path for metadata.

        Yields:
            Recipe instances extracted from the database export.
        """
        records = [r.strip() for r in re.split(r"\n\s*\n", content) if r.strip()]

        for record in records:
            lines = record.splitlines()
            if len(lines) < 2:
                continue

            # Line 1: Drink Name (0..32) and Primary Spirit Category (32..)
            line0 = lines[0]
            raw_title = line0[:32].strip() if len(line0) >= 32 else line0.strip()
            title = re.sub(
                r"'[A-Z]\b",
                lambda m: m.group(0).lower(),
                raw_title.title(),
            )

            spirit = line0[32:].strip() if len(line0) > 32 else ""

            # Lines 2..5: Metadata lines
            meta: dict[str, str] = {}
            data_start_idx = len(lines)
            for idx, line in enumerate(lines[1:], start=1):
                if ":" in line:
                    prefix = line.split(":", 1)[0].strip().lower()
                    if prefix in {"drink type", "temp", "serve at", "season(s)"}:
                        k, v = line.split(":", 1)
                        meta[k.strip().lower()] = v.strip()
                        continue
                data_start_idx = idx
                break

            drink_type = meta.get("drink type", "")
            temp = meta.get("temp", "")
            serve_at = meta.get("serve at", "")
            seasons = meta.get("season(s)", "")

            categories: List[str] = []
            if spirit:
                spirit_title = re.sub(
                    r"'[A-Z]\b",
                    lambda m: m.group(0).lower(),
                    spirit.title(),
                )
                if spirit_title not in categories:
                    categories.append(spirit_title)
            if drink_type:
                dt_title = re.sub(
                    r"'[A-Z]\b",
                    lambda m: m.group(0).lower(),
                    drink_type.title(),
                )
                if dt_title not in categories:
                    categories.append(dt_title)

            # Data lines (fixed-width 42-character chunks)
            data_lines = lines[data_start_idx:]
            data_line = " ".join(data_lines)
            chunks = [
                data_line[i : i + 42].strip()
                for i in range(0, len(data_line), 42)
            ]
            chunks = [c for c in chunks if c]

            # Detect instruction boundary (first chunk containing lowercase letters)
            lower_idx: Optional[int] = None
            for i, c in enumerate(chunks):
                if re.search(r"[a-z]", c):
                    lower_idx = i
                    break

            # Identify glassware: last matching chunk before instructions
            glass_idx: Optional[int] = None
            glassware: Optional[str] = None
            search_limit = lower_idx if lower_idx is not None else len(chunks)
            for i in range(search_limit - 1, -1, -1):
                if GLASSWARE_PATTERN.match(chunks[i]):
                    glass_idx = i
                    glassware = chunks[i]
                    break

            if glass_idx is not None:
                raw_ing_chunks = chunks[:glass_idx]
                instr_start = (glass_idx + 1) * 42
                raw_instr = data_line[instr_start:].strip()
            elif lower_idx is not None:
                raw_ing_chunks = chunks[:lower_idx]
                instr_start = lower_idx * 42
                raw_instr = data_line[instr_start:].strip()
            else:
                raw_ing_chunks = chunks
                raw_instr = ""

            # Normalize instructions
            clean_instr = re.sub(r"\s+", " ", raw_instr).strip()
            if clean_instr and clean_instr[0].islower():
                clean_instr = clean_instr[0].upper() + clean_instr[1:]
            instructions = [clean_instr] if clean_instr else []

            # Merge continuation columns
            merged_ings: List[str] = []
            for c in raw_ing_chunks:
                if not merged_ings:
                    merged_ings.append(c)
                    continue
                prev = merged_ings[-1]
                is_cont = (
                    c.startswith("(")
                    or prev.endswith(",")
                    or prev.endswith("-")
                    or prev.endswith(" OR")
                    or prev.endswith(" AND")
                    or prev.endswith(" WITH")
                    or prev.endswith(" OF")
                    or prev.endswith(" FLAVORED")
                    or c.startswith("FLAVORED BRANDY")
                    or (c == "BRANDY" and "FLAVORED" in prev)
                    or (c == "SODA" and prev.endswith("CARBONATED"))
                    or (c == "WINE" and "VINEYARD" in prev)
                )
                if is_cont:
                    merged_ings[-1] = f"{prev} {c}"
                else:
                    merged_ings.append(c)

            # Build metadata description
            desc_parts: List[str] = []
            if temp:
                desc_parts.append(f"Temp: {temp}")
            if serve_at:
                desc_parts.append(f"Serve at: {serve_at}")
            if seasons:
                desc_parts.append(f"Season(s): {seasons}")
            if glassware:
                desc_parts.append(f"Glassware: {glassware}")
            description = " | ".join(desc_parts) if desc_parts else None

            # Parse ingredients with ingredient_parser
            ingredients = [self.ingredient_parser.parse(raw) for raw in merged_ings]

            yield Recipe(
                title=title,
                categories=categories,
                yield_amount="1 drink",
                ingredients=ingredients,
                instructions=instructions,
                description=description,
                source_format=self.source_format,
                source_file=filepath,
            )
