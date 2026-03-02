# SPDX-License-Identifier: MIT
"""
RecipeML (XML) parser - converts RecipeML format to internal Recipe model
"""

import logging
from pathlib import Path
from typing import Iterator
from xml.etree import ElementTree as ET

from .base import BaseRecipeParser, BaseIngredientParser
from .models import Recipe, Ingredient
from .registry import ParserRegistry

logger = logging.getLogger(__name__)


# ── helpers ──────────────────────────────────────────────────────────────────

def _text(el, tag, default=None):
    """Return stripped text of first child with given tag, or default."""
    if el is None:
        return default
    child = el.find(tag)
    if child is not None and child.text:
        return child.text.strip()
    return default


def _all_text(el, tag):
    """Return list of stripped text for all children with given tag."""
    return [c.text.strip() for c in el.findall(tag) if c is not None and c.text]


def _inner_text(el):
    """Concatenate all text content inside an element (including tail text of children)."""
    if el is None:
        return ""
    parts = []
    if el.text:
        parts.append(el.text.strip())
    for child in el:
        if child.text:
            parts.append(child.text.strip())
        if child.tail:
            parts.append(child.tail.strip())
    return " ".join(p for p in parts if p)


# ── ingredient parsing ────────────────────────────────────────────────────────

def parse_ingredient_element(ing_el):
    """
    Convert a RecipeML <ing> element to a human-readable string.
    <ing> may contain <amt>, <item>, <prep>, <alt-ing> etc.
    """
    parts = []

    amt_el = ing_el.find("amt")
    if amt_el is not None:
        qty_el = amt_el.find("qty")
        unit_el = amt_el.find("unit")
        qty = _inner_text(qty_el) if qty_el is not None else ""
        unit = _inner_text(unit_el) if unit_el is not None else ""
        if qty:
            parts.append(qty)
        if unit:
            parts.append(unit)

    item_el = ing_el.find("item")
    if item_el is not None:
        parts.append(_inner_text(item_el))

    prep_el = ing_el.find("prep")
    if prep_el is not None:
        prep = _inner_text(prep_el)
        if prep:
            parts.append(f"({prep})")

    return " ".join(parts).strip() or _inner_text(ing_el)


def collect_ingredients(recipe_el):
    """Walk <ingredients> / <ing-div> trees and collect all <ing> elements."""
    results = []
    ing_section = recipe_el.find("ingredients")
    if ing_section is None:
        return results

    def walk(el):
        for child in el:
            if child.tag == "ing":
                text = parse_ingredient_element(child)
                if text:
                    results.append(text)
            elif child.tag in ("ing-div", "ingredients"):
                walk(child)

    walk(ing_section)
    return results


# ── step parsing ──────────────────────────────────────────────────────────────

def collect_steps(recipe_el):
    """
    Parse <directions> → list of step strings.
    RecipeML uses <step> elements, optionally grouped in <dir-div>.
    """
    results = []
    directions = recipe_el.find("directions")
    if directions is None:
        return results

    def walk(el):
        for child in el:
            if child.tag == "step":
                text = _inner_text(child)
                if text:
                    results.append(text)
            elif child.tag == "dir-div":
                walk(child)

    walk(directions)
    return results


# ── time parsing ──────────────────────────────────────────────────────────────

def parse_time(time_el):
    """
    Convert RecipeML <time> to a readable string (e.g., "1 hour 30 minutes").
    <time qty="30" unit="minutes" /> or <time><qty>1</qty><unit>hour</unit></time>
    """
    if time_el is None:
        return None
    qty_attr = time_el.get("qty") or _text(time_el, "qty")
    unit_attr = (time_el.get("unit") or _text(time_el, "unit") or "").lower()
    try:
        qty = float(qty_attr) if qty_attr else None
    except (ValueError, TypeError):
        qty = None
    if qty is None:
        return None

    minutes = qty
    if "hour" in unit_attr:
        minutes = qty * 60
    elif "day" in unit_attr:
        minutes = qty * 60 * 24

    total = int(round(minutes))
    hours, mins = divmod(total, 60)
    if hours and mins:
        return f"{hours} hour{'s' if hours > 1 else ''} {mins} minute{'s' if mins > 1 else ''}"
    elif hours:
        return f"{hours} hour{'s' if hours > 1 else ''}"
    else:
        return f"{mins} minute{'s' if mins > 1 else ''}"


def get_times(recipe_el):
    """Extract prep, cook, and total times from recipe."""
    prep_time = None
    cook_time = None
    total_time = None

    head = recipe_el.find("head")
    if head is None:
        return prep_time, cook_time, total_time

    for t in head.findall("time"):
        kind = (t.get("type") or "").lower()
        time_str = parse_time(t)
        if not time_str:
            continue
        if "prep" in kind:
            prep_time = time_str
        elif "cook" in kind or "bake" in kind or "total" not in kind:
            if cook_time is None:
                cook_time = time_str
        if "total" in kind:
            total_time = time_str

    return prep_time, cook_time, total_time


# ── main recipe converter ─────────────────────────────────────────────────────

@ParserRegistry.register
class RecipeMLParser(BaseRecipeParser):
    """Parser for RecipeML (XML) format."""

    def __init__(self, ingredient_parser: BaseIngredientParser):
        super().__init__(ingredient_parser)
        self.source_format = "RecipeML"

    @classmethod
    def format_id(cls) -> str:
        return "recipeml"

    @classmethod
    def priority(cls) -> int:
        return 7

    @classmethod
    def detect(cls, filepath: str, content_sample: str) -> float:
        import re
        if not content_sample:
            return 0.0
        if re.search(r'<recipeml|<recipe[^a-zA-Z]', content_sample, re.IGNORECASE):
            return 0.95
        return 0.0

    def parse_content(self, content: str, filepath: str) -> Iterator[Recipe]:
        """Parse RecipeML content (XML string) and return list of Recipe objects."""
        try:
            root = ET.fromstring(content)
        except ET.ParseError as e:
            logger.error("Failed to parse XML in %s: %s", filepath, e)
            return

        # Collect recipe elements
        if root.tag == "recipe":
            recipe_els = [root]
        elif root.tag == "recipeml":
            recipe_els = root.findall(".//recipe")
        else:
            recipe_els = root.findall(".//recipe")

        for recipe_el in recipe_els:
            recipe = self._parse_recipe_element(recipe_el, filepath)
            if recipe.title:
                yield recipe

    def _parse_recipe_element(self, recipe_el, filepath: str) -> Recipe:
        """Convert an XML <recipe> element to a Recipe object."""
        recipe = Recipe(source_file=filepath, source_format=self.source_format)

        head = recipe_el.find("head")
        if head is not None:
            recipe.title = _text(head, "title") or "Untitled Recipe"
            # categories
            cats = _all_text(head, "categories/cat")
            recipe.categories = cats if cats else []
            # yield / servings
            yield_el = head.find("yield")
            if yield_el is not None:
                qty = yield_el.get("qty") or _inner_text(yield_el)
                unit = yield_el.get("unit") or ""
                recipe.yield_amount = f"{qty} {unit}".strip() if qty else ""
        else:
            recipe.title = _text(recipe_el, "title") or "Untitled Recipe"

        # ingredients
        ingredients_raw = collect_ingredients(recipe_el)
        for ing_raw in ingredients_raw:
            ing = self.ingredient_parser.parse(ing_raw) if self.ingredient_parser else Ingredient(raw=ing_raw)
            recipe.ingredients.append(ing)

        # instructions
        recipe.instructions = collect_steps(recipe_el)

        return recipe
