# SPDX-License-Identifier: MIT
import logging
import re
from typing import Iterator, Optional
from .models import Ingredient, Recipe

logger = logging.getLogger(__name__)

_TITLE_PREFIX_RE = re.compile(
    r"^(?:QTitle|Recipe\s*Name|Title|Name)\s*:\s*",
    re.IGNORECASE,
)

_PANDOC_ATTR_RE = re.compile(r"\[(.*?)\]\{.*?\}")

_TRAILING_YIELD_RE = re.compile(
    r"[\s(;,|-]+(?:Yield|Servings?|Serves|Makes)\s*:\s*([^)]+?)\)?$",
    re.IGNORECASE,
)

_EMAIL_HEADER_RE = re.compile(
    r"^(?:Date|From|Subject|To|Message-ID|Received|Return-Path)\s*:\s*",
    re.IGNORECASE,
)

_NUTRITION_LINE_RE = re.compile(
    r"calories\s+from\s+fat|g\s+(?:protein|carbohydrate|fat|dietary\s+fiber)",
    re.IGNORECASE,
)

_DIVIDER_LINE_RE = re.compile(
    r"^[-=~*_#+]{3,}$|^[-=~*_]{2,}\s*RECIPE(?:\s+SEPARATOR|\s+DIVIDER)?\s*[-=~*_]{2,}$",
    re.IGNORECASE,
)

_EMPTY_AUTHOR_RE = re.compile(
    r"^(?:Recipe\s*By|Author)\s*:\s*$",
    re.IGNORECASE,
)


def clean_recipe_title(title: str) -> tuple[str, Optional[str]]:
    """Clean and sanitize a recipe title, extracting trailing yield if present.

    Args:
        title: Raw title string candidate.

    Returns:
        A tuple of (clean_title, extracted_yield). If the candidate title is invalid
        (e.g., empty author line, email header, nutrition line, divider), clean_title
        will be an empty string.
    """
    if not title:
        return ("", None)

    s = title.strip()
    if not s:
        return ("", None)

    # 4. Check for rejected title lines
    if _EMPTY_AUTHOR_RE.match(s):
        return ("", None)
    if _EMAIL_HEADER_RE.match(s):
        return ("", None)
    if _NUTRITION_LINE_RE.search(s):
        return ("", None)
    if _DIVIDER_LINE_RE.match(s):
        return ("", None)

    # 1. Strip leading prefixes matching ^(?:QTitle|Recipe Name|Title|Name)\s*:\s*
    while True:
        stripped = _TITLE_PREFIX_RE.sub("", s).strip()
        if stripped == s:
            break
        s = stripped

    # 2. Strip Markdown Pandoc attributes [(.*?)]\{.*?\}
    s = _PANDOC_ATTR_RE.sub(r"\1", s).strip()

    # Unescape escaped punctuation if present in title
    s = re.sub(r"\\([.-])", r"\1", s).strip()

    # 3. Detect and strip trailing yield
    extracted_yield: Optional[str] = None
    m_yield = _TRAILING_YIELD_RE.search(s)
    if m_yield:
        extracted_yield = m_yield.group(1).strip()
        s = s[: m_yield.start()].rstrip(" -–—;,|(")

    # Post-check: ensure stripped title is not empty or pure punctuation
    s = s.strip()
    if not s or not any(c.isalnum() for c in s):
        return ("", extracted_yield)

    return (s, extracted_yield)


def is_divider_step(step: str) -> bool:
    """Check if an instruction step is purely a decorative divider line."""
    s = step.strip()
    if not s:
        return True
    if _DIVIDER_LINE_RE.match(s):
        return True
    if re.match(r"^[-=~*_+]{4,}(?:\s*[-=~*_+]{4,})*$", s):
        return True
    return False


def clean_instructions(instructions: list[str]) -> list[str]:
    """Filter out pure divider lines and blank lines from instructions."""
    cleaned = []
    for step in instructions:
        s = step.strip()
        if not s or is_divider_step(s):
            continue
        cleaned.append(s)
    return cleaned


def sanitize_recipe(recipe: Recipe) -> Recipe:
    """Sanitize title, yield, instructions, and ingredients on a Recipe instance."""
    if recipe.title:
        c_title, ext_y = clean_recipe_title(recipe.title)
        if c_title:
            recipe.title = c_title
        if ext_y and not recipe.yield_amount:
            recipe.yield_amount = ext_y

    if recipe.instructions:
        recipe.instructions = clean_instructions(recipe.instructions)

    for ing in recipe.ingredients:
        if ing.raw:
            ing.raw = re.sub(r"\\([.-])", r"\1", ing.raw)
        if ing.name:
            ing.name = re.sub(r"\\([.-])", r"\1", ing.name)

    return recipe


def get_context_window(lines: list[str], start_idx: int, window_size: int = 15) -> str:
    """Extract a sliding window of up to window_size lines starting at start_idx."""
    end_idx = min(start_idx + window_size, len(lines))
    return "\n".join(lines[start_idx:end_idx])


class BaseIngredientParser:
    def parse(self, raw_line: str) -> Ingredient:
        raise NotImplementedError

class BaseRecipeParser:
    def __init__(self, ingredient_parser: BaseIngredientParser):
        self.ingredient_parser = ingredient_parser
        self.source_format = "Unknown"

    def get_display_name(self, filepath: str | None = None) -> str:
        """Return user-friendly display name for this parser, optionally tailored to filepath."""
        fmt = self.source_format
        if not fmt or fmt == "Unknown":
            fmt = self.__class__.__name__.replace("Parser", "")
        return f"{fmt} Parser"

    @classmethod
    def format_id(cls) -> str:
        """Unique identifier for this format."""
        return "unknown"

    @classmethod
    def aliases(cls) -> list[str]:
        """List of alternate names for this format."""
        return []

    @classmethod
    def priority(cls) -> int:
        """Detection priority. Lower is higher priority."""
        return 100

    @classmethod
    def detect(cls, filepath: str, content_sample: str) -> float:
        """
        Return a confidence score (0.0 to 1.0) that this parser can handle the file.
        Uses pathlib.Path internally if string is passed.
        """
        return 0.0

    @classmethod
    def supported_extensions(cls) -> set[str]:
        """Return set of lowercased file extensions (with leading dot) handled by this parser."""
        return set()

    def parse_file(self, filepath: str) -> Iterator[Recipe]:
        """Generator that yields recipes from file."""
        from pathlib import Path
        try:
            with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
            for recipe in self.parse_content(content, filepath):
                sanitize_recipe(recipe)
                if not recipe.description:
                    recipe.description = f"Imported from {self.source_format}"
                if not recipe.url:
                    recipe.url = f"file://{filepath}"
                yield recipe
        except Exception as e:
            logger.error("Error reading %s: %s", filepath, e, exc_info=True)
            return

    def parse_content(self, content: str, filepath: str) -> Iterator[Recipe]:
        """Generator that yields recipes from content."""
        raise NotImplementedError
        yield
