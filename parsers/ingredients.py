# SPDX-License-Identifier: MIT
import re
from typing import Optional
from .models import Ingredient
from .base import BaseIngredientParser
from .units import normalize_unit

_parse_ingredient = None
_HAS_NLP_PARSER: Optional[bool] = None


def is_nlp_available() -> bool:
    """Checks if ingredient-parser-nlp is available, loading it lazily."""
    global _parse_ingredient, _HAS_NLP_PARSER
    if _HAS_NLP_PARSER is None:
        try:
            from ingredient_parser import parse_ingredient
            _parse_ingredient = parse_ingredient
            _HAS_NLP_PARSER = True
        except ImportError:
            _parse_ingredient = None
            _HAS_NLP_PARSER = False
    return _HAS_NLP_PARSER


def __getattr__(name: str):
    if name == "HAS_NLP_PARSER":
        return is_nlp_available()
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


class RegexIngredientParser(BaseIngredientParser):
    def parse(self, raw_line: str) -> Ingredient:
        stripped = raw_line.strip()
        if not stripped or not any(c.isalnum() for c in stripped):
            return Ingredient(raw=stripped)

        qty_pattern = r"^(\d+(?:\s+\d+/\d+|\.\d+|/\d+)?(?:\s*-\s*\d+(?:\s+\d+/\d+|\.\d+|/\d+)?)?)\s+"
        match = re.match(qty_pattern, stripped)
        if match:
            quantity = match.group(1).strip()
            remaining = stripped[match.end() :].lstrip()
            unit_pattern = r"^([a-zA-Z]+\.?)\s+"
            unit_match = re.match(unit_pattern, remaining)

            if unit_match:
                unit = normalize_unit(unit_match.group(1).strip())
                name = remaining[unit_match.end() :].strip()
            else:
                unit = None
                name = remaining.strip()
            return Ingredient(raw=stripped, quantity=quantity, unit=unit, name=name)
        else:
            return Ingredient(raw=stripped, name=stripped)


class NLPIngredientParser(BaseIngredientParser):
    def __init__(self):
        self._fallback = RegexIngredientParser()

    def parse(self, raw_line: str) -> Ingredient:
        stripped = raw_line.strip()
        if not is_nlp_available() or _parse_ingredient is None:
            return self._fallback.parse(raw_line)
        try:
            parsed = _parse_ingredient(stripped)
            qty = None
            unit = None
            if parsed.amount:
                qty_val = str(parsed.amount[0].get("quantity", ""))
                if qty_val:
                    qty = qty_val
                unit_val = str(parsed.amount[0].get("unit", ""))
                if unit_val:
                    unit = normalize_unit(unit_val)

            return Ingredient(
                raw=stripped,
                quantity=qty,
                unit=unit,
                name=parsed.name.text if parsed.name else stripped,
                comment=parsed.comment.text if parsed.comment else None,
            )
        except Exception:
            return self._fallback.parse(raw_line)


def get_ingredient_parser(use_nlp: bool = True) -> BaseIngredientParser:
    if use_nlp and is_nlp_available():
        return NLPIngredientParser()
    return RegexIngredientParser()

