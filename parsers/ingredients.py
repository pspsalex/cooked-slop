# SPDX-License-Identifier: MIT
import re
from .models import Ingredient
from .base import BaseIngredientParser

HAS_NLP_PARSER = None

class RegexIngredientParser(BaseIngredientParser):
    def parse(self, raw_line: str) -> Ingredient:
        stripped = raw_line.strip()
        ingredient = Ingredient(raw=stripped)
        if not stripped or not any(c.isalnum() for c in stripped):
            return ingredient
        
        qty_pattern = r'^(\d+(?:\s+\d+/\d+|\.\d+|/\d+)?(?:\s*-\s*\d+(?:\s+\d+/\d+|\.\d+|/\d+)?)?)\s+'
        match = re.match(qty_pattern, stripped)
        if match:
            ingredient.quantity = match.group(1).strip()
            remaining = stripped[match.end():].lstrip()
            unit_pattern = r'^([a-zA-Z]+\.?)\s+'
            unit_match = re.match(unit_pattern, remaining)
            
            if unit_match:
                ingredient.unit = unit_match.group(1).strip()
                ingredient.name = remaining[unit_match.end():].strip()
            else:
                ingredient.name = remaining.strip()
        else:
            ingredient.name = stripped
        return ingredient

class NLPIngredientParser(BaseIngredientParser):
    def __init__(self):
        self._fallback = RegexIngredientParser()

    def parse(self, raw_line: str) -> Ingredient:
        stripped = raw_line.strip()
        if not HAS_NLP_PARSER:
            return self._fallback.parse(raw_line)
        try:
            parsed = parse_ingredient(stripped)
            qty = None
            unit = None
            if parsed.amount:
                qty_val = str(parsed.amount[0].get('quantity', ''))
                if qty_val: qty = qty_val
                unit_val = str(parsed.amount[0].get('unit', ''))
                if unit_val: unit = unit_val
                
            return Ingredient(
                raw=stripped,
                quantity=qty,
                unit=unit,
                name=parsed.name.text if parsed.name else stripped,
                comment=parsed.comment.text if parsed.comment else None
            )
        except Exception:
            return self._fallback.parse(raw_line)

def get_ingredient_parser(use_nlp: bool = True) -> BaseIngredientParser:
    global HAS_NLP_PARSER
    if use_nlp:
        if HAS_NLP_PARSER is None:
            try:
                from ingredient_parser import parse_ingredient
                HAS_NLP_PARSER = True
            except ImportError:
                HAS_NLP_PARSER = False
        
        if HAS_NLP_PARSER:
            return NLPIngredientParser()

    return RegexIngredientParser()
