# SPDX-License-Identifier: MIT
"""
20krecipes ingredient-line helpers.

The CSV layout itself is described in ``configs/twentyk.csv.yaml`` and parsed by
``ConfigurableCsvParser``; this module only provides the ``twentyk_decimal``
line transform used by that config.

CSV columns: TITLE_NO, TITLE, KEYWORD, INSTRUCT, ORIGIN, SERVES, SUBDIR, INGRED

Ingredient format per line:
  <quantity>  <ingredient>         (no unit, two spaces between qty and name)
  <quantity> <unit> <ingredient>   (with unit, one space between each)
"""

import logging
import re
from typing import List

logger = logging.getLogger(__name__)


# Category mapping
CATEGORY_MAP = {
    "app": "Appetizers",
    "bev": "Beverages",
    "bre": "Bread",
    "cak": "Cake",
    "cas": "Casserole",
    "che": "Cheese",
    "coo": "Cookies",
    "des": "Desserts",
    "kid": "Kid's Meals",
    "mea": "Main Courses",
    "pas": "Pasta",
    "pou": "Poultry",
    "sal": "Salads",
    "sau": "Sauces",
    "sea": "Fish",
    "sou": "Soups",
    "veg": "Vegetarian",
}


def decimal_to_fraction(val: float) -> str:
    """Convert a decimal to a nice fraction string."""
    fractions = {
        0.125: "1/8", 0.12: "1/8", 0.25: "1/4", 0.33: "1/3", 0.334: "1/3",
        0.333: "1/3", 0.5: "1/2", 0.667: "2/3", 0.666: "2/3", 0.67: "2/3",
        0.75: "3/4", 0.875: "7/8",
    }
    whole = int(val)
    frac = val - whole
    frac_str = fractions.get(round(frac, 3), "")
    if whole and frac_str:
        return f"{whole} {frac_str}"
    elif frac_str:
        return frac_str
    elif whole:
        return str(whole)
    return ""


def parse_ingredient_line(line: str) -> str:
    """
    Parse a single ingredient line into a human-readable string.

    Formats:
      "1.00 pk Active dry yeast"   -> "1 pk Active dry yeast"
      "0.75 c Warm water"          -> "3/4 c Warm water"
      "0.00  Salt"                 -> "Salt"   (quantity 0 = not relevant)
      "1.00  Salt"                 -> "1 Salt" (no unit, two spaces)
    """
    line = line.strip()
    if not line:
        return ""

    # Match: decimal  [unit]  ingredient
    # Two-space separator means no unit
    m_no_unit = re.match(r'^(\d+\.\d+)  (.+)$', line)
    m_with_unit = re.match(r'^(\d+\.\d+) (\S+) (.+)$', line)

    if m_no_unit:
        qty_str, ingredient = m_no_unit.group(1), m_no_unit.group(2)
        qty = float(qty_str)
        if qty == 0.0:
            return ingredient
        qty_display = decimal_to_fraction(qty) or qty_str.rstrip('0').rstrip('.')
        return f"{qty_display} {ingredient}"

    if m_with_unit:
        qty_str, unit, ingredient = m_with_unit.group(1), m_with_unit.group(2), m_with_unit.group(3)
        qty = float(qty_str)
        if qty == 0.0:
            return f"{unit} {ingredient}"
        qty_display = decimal_to_fraction(qty) or qty_str.rstrip('0').rstrip('.')
        return f"{qty_display} {unit} {ingredient}"

    # Fallback: return as-is
    return line


def parse_ingredients(ingred_field: str) -> List[str]:
    """Split ingredient block into list of ingredient strings."""
    lines = ingred_field.strip().splitlines()
    result = []
    for line in lines:
        parsed = parse_ingredient_line(line)
        if parsed:
            result.append(parsed)
    return result


