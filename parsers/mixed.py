# SPDX-License-Identifier: MIT
import logging
import re
from pathlib import Path
from typing import Iterator

from .base import BaseIngredientParser, BaseRecipeParser, get_context_window
from .compuchef import CompuChefParser
from .edna import EdnaParser
from .generic_md import GenericMdParser
from .mastercook import MasterCookParser
from .mealmaster import MealMasterParser
from .microcook import MicroCookParser
from .models import Recipe
from .nyc import NYCParser
from .registry import ParserRegistry
from .ricette import RicetteParser
from .two_col import TwoColParser

logger = logging.getLogger(__name__)

# Recipe separators: at least 12 contiguous dashes, 12 equal signs, 12 asterisks, or MasterCook end markers (15+ "- ")
SEPARATOR_RE = re.compile(
    r'^(?:-{12,}|={12,}|\*{12,}|(?:-\s){15,}-)\s*$'
)


@ParserRegistry.register
class MixedFormatParser(BaseRecipeParser):
    """
    Parser for files containing multiple recipes in DIFFERENT FORMATS, mainly .txt files.
    Extracts various recipe types using a 15-line sliding window context detection
    and recipe separator lines (12+ dashes, 12+ equals, or format markers).
    """

    @classmethod
    def format_id(cls) -> str:
        return "mixed"

    @classmethod
    def priority(cls) -> int:
        return 10

    @classmethod
    def get_candidate_parsers(cls) -> list[type[BaseRecipeParser]]:
        """Return list of recipe parser classes to evaluate for sliding window blocks."""
        return [
            MasterCookParser,
            MealMasterParser,
            CompuChefParser,
            NYCParser,
            TwoColParser,
            EdnaParser,
            RicetteParser,
            MicroCookParser,
            GenericMdParser,
        ]

    @classmethod
    def detect(cls, filepath: str, content_sample: str) -> float:
        if not content_sample or not content_sample.strip():
            return 0.0

        has_separators = bool(SEPARATOR_RE.search(content_sample))

        score = 0.0
        for parser in (MasterCookParser, MealMasterParser, CompuChefParser, NYCParser, TwoColParser):
            try:
                score += parser.detect(filepath, content_sample)
            except Exception:
                pass

        if score > 1.0 or (score > 0.5 and has_separators):
            return 1.0

        if score > 0.5:
            if Path(filepath).suffix.lower() in ('.txt', '.recipe', '.recipes'):
                return 1.0
            return score - 0.25

        return 0.0

    def __init__(self, ingredient_parser: BaseIngredientParser):
        super().__init__(ingredient_parser)
        self.source_format = "Mixed"

    def parse_file(self, filepath: str) -> Iterator[Recipe]:
        try:
            with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
            yield from self.parse_content(content, filepath)
        except Exception as e:
            logger.error("Error reading %s: %s", filepath, e)
            return

    def parse_content(self, content: str, filepath: str) -> Iterator[Recipe]:
        if not content or not content.strip():
            return

        lines = content.splitlines(keepends=True)
        num_lines = len(lines)
        idx = 0
        candidate_parsers = self.get_candidate_parsers()

        while idx < num_lines:
            line_str = lines[idx].strip()

            # Skip empty lines or separator lines at block boundaries
            if not line_str or SEPARATOR_RE.match(line_str):
                idx += 1
                continue

            # Build 15-line sliding window context
            window_sample = "".join(lines[idx:min(idx + 15, num_lines)])

            # Detect format for this sliding window
            best_parser_cls = None
            best_score = 0.0

            for p_cls in candidate_parsers:
                try:
                    score = p_cls.detect(filepath, window_sample)
                    if score > best_score:
                        best_score = score
                        best_parser_cls = p_cls
                except Exception:
                    pass

            if not best_parser_cls or best_score < 0.35:
                idx += 1
                continue

            # Found a recipe start at line `idx` with `best_parser_cls`
            parser = best_parser_cls(self.ingredient_parser)
            line_number = idx + 1
            recipe_start_idx = idx

            # Find boundary for this recipe block
            end_idx = idx + 1
            while end_idx < num_lines:
                curr_line = lines[end_idx].strip()

                if SEPARATOR_RE.match(curr_line):
                    end_idx += 1
                    break

                if hasattr(parser, 'end_re') and getattr(parser, 'end_re') and getattr(parser, 'end_re').search(curr_line):
                    end_idx += 1
                    break
                if best_parser_cls == MealMasterParser and MealMasterParser.TRAILER_RE.match(curr_line):
                    end_idx += 1
                    break
                if best_parser_cls == NYCParser and re.search(r"\*\* Exported from Now You\'re Cooking!", curr_line):
                    end_idx += 1
                    break

                # Check if a new recipe starts at end_idx
                if curr_line and end_idx > idx + 3:
                    # Check for explicit top-level START format headers at end_idx
                    if MasterCookParser.HEADER_SIG and re.search(MasterCookParser.HEADER_SIG, curr_line):
                        break
                    if MealMasterParser.HEADER_RE.search(curr_line):
                        break
                    if re.search(r'^\s*\*{3,}\s*(?!Recipe Via)[^*]+\*{3,}', curr_line, re.IGNORECASE):
                        break
                    if re.search(r"^@{5}\s+Now You\'re Cooking!", curr_line):
                        break

                    # Or check if a DIFFERENT parser returns high score on immediate lines (next 4 lines)
                    next_short_window = "".join(lines[end_idx:min(end_idx + 4, num_lines)])
                    diff_parser_found = False
                    for p_cls in candidate_parsers:
                        if p_cls == best_parser_cls:
                            continue
                        try:
                            s = p_cls.detect(filepath, next_short_window)
                            if s >= 0.60:
                                diff_parser_found = True
                                break
                        except Exception:
                            pass
                    if diff_parser_found:
                        break

                end_idx += 1

            chunk = "".join(lines[recipe_start_idx:end_idx])
            idx = end_idx

            logger.debug("Mixed format parser chunk (lines %d-%d) using %s", line_number, end_idx, parser.format_id())
            try:
                recipe_yielded = False
                for recipe in parser.parse_content(chunk, filepath):
                    if not recipe.description:
                        recipe.description = f"Imported from {self.source_format}"
                    recipe.url = f"file://{filepath}#{line_number}"
                    recipe_yielded = True
                    yield recipe

                # Fallback to parse_buffer if parse_content didn't yield anything but parser has parse_buffer
                if not recipe_yielded and hasattr(parser, 'parse_buffer'):
                    import io
                    buf = io.StringIO("".join(lines[recipe_start_idx + 1:end_idx]))
                    buf.name = filepath
                    parsed_rec, _ = parser.parse_buffer(buf, lines[recipe_start_idx], line_number)
                    if parsed_rec:
                        if not parsed_rec.description:
                            parsed_rec.description = f"Imported from {self.source_format}"
                        parsed_rec.url = f"file://{filepath}#{line_number}"
                        yield parsed_rec
            except Exception as e:
                logger.error("Error parsing block at line %d with %s: %s", line_number, parser.format_id(), e)
