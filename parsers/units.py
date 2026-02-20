# SPDX-License-Identifier: MIT
"""
Unit normalization for recipe ingredients.

Maps the many abbreviations and inconsistent forms found in MealMaster,
MasterCook, and other recipe formats to canonical, schema.org-friendly strings.
"""

# Maps any known variant to its canonical form.
# NOTE: case-sensitive entries (like "T" vs "t") must be checked BEFORE lowercasing.
UNIT_MAP: dict[str, str] = {
    # --- Volume ---
    # Cup
    "c":         "cup",
    "c.":        "cup",
    "cup":       "cup",
    "cups":      "cup",
    # Tablespoon  (uppercase T = tablespoon is the culinary convention)
    "T":         "tablespoon",
    "tb":        "tablespoon",
    "tbs":       "tablespoon",
    "tbs.":      "tablespoon",
    "tbsp":      "tablespoon",
    "tbsp.":     "tablespoon",
    "tablespoon": "tablespoon",
    "tablespoons": "tablespoon",
    # Teaspoon  (lowercase t = teaspoon is the culinary convention)
    "t":         "teaspoon",
    "ts":        "teaspoon",
    "tsp":       "teaspoon",
    "tsp.":      "teaspoon",
    "teaspoon":  "teaspoon",
    "teaspoons": "teaspoon",
    # Fluid ounce
    "fl oz":     "fluid ounce",
    "fl. oz":    "fluid ounce",
    "fl. oz.":   "fluid ounce",
    "fluid oz":  "fluid ounce",
    "fluid ounce": "fluid ounce",
    "fluid ounces": "fluid ounce",
    # Pint / quart / gallon
    "pt":        "pint",
    "pts":       "pint",
    "pint":      "pint",
    "pints":     "pint",
    "qt":        "quart",
    "qts":       "quart",
    "quart":     "quart",
    "quarts":    "quart",
    "gal":       "gallon",
    "gallon":    "gallon",
    "gallons":   "gallon",
    # Milliliter / liter
    "ml":        "milliliter",
    "ml.":       "milliliter",
    "milliliter": "milliliter",
    "milliliters": "milliliter",
    "millilitre": "milliliter",
    "millilitres": "milliliter",
    "l":         "liter",
    "liter":     "liter",
    "liters":    "liter",
    "litre":     "liter",
    "litres":    "liter",
    # Pinch / dash / drop
    "pn":        "pinch",
    "pinch":     "pinch",
    "pinches":   "pinch",
    "dash":      "dash",
    "dashes":    "dash",
    "drop":      "drop",
    "drops":     "drop",
    # Splash / spray
    "splash":    "splash",
    "spray":     "spray",

    # --- Weight ---
    "oz":        "ounce",
    "oz.":       "ounce",
    "ounce":     "ounce",
    "ounces":    "ounce",
    "lb":        "pound",
    "lb.":       "pound",
    "lbs":       "pound",
    "lbs.":      "pound",
    "pound":     "pound",
    "pounds":    "pound",
    "g":         "gram",
    "gr":        "gram",
    "gram":      "gram",
    "grams":     "gram",
    "kg":        "kilogram",
    "kilogram":  "kilogram",
    "kilograms": "kilogram",

    # --- Count / size descriptors ---
    "sm":        "small",
    "small":     "small",
    "md":        "medium",
    "med":       "medium",
    "medium":    "medium",
    "lg":        "large",
    "lrg":       "large",
    "large":     "large",
    "whole":     "whole",
    "piece":     "piece",
    "pieces":    "piece",
    "slice":     "slice",
    "slices":    "slice",
    "strip":     "strip",
    "strips":    "strip",
    "sheet":     "sheet",
    "sheets":    "sheet",

    # --- Containers / packaging ---
    "can":       "can",
    "cans":      "can",
    "cn":        "can",
    "pkg":       "package",
    "pkg.":      "package",
    "pkgs":      "package",
    "package":   "package",
    "packages":  "package",
    "box":       "box",
    "boxes":     "box",
    "bottle":    "bottle",
    "bottles":   "bottle",
    "jar":       "jar",
    "jars":      "jar",
    "envelope":  "envelope",
    "envelopes": "envelope",

    # --- Botanical / culinary ---
    "bunch":     "bunch",
    "bunches":   "bunch",
    "head":      "head",
    "heads":     "head",
    "clove":     "clove",
    "cloves":    "clove",
    "sprig":     "sprig",
    "sprigs":    "sprig",
    "stalk":     "stalk",
    "stalks":    "stalk",
    "stick":     "stick",
    "sticks":    "stick",
    "leaf":      "leaf",
    "leaves":    "leaf",
    "ear":       "ear",
    "ears":      "ear",
    "rib":       "rib",
    "ribs":      "rib",
    "handful":   "handful",
    "dozen":     "dozen",
    "inch":      "inch",
    "inches":    "inch",
    "jumbo":     "jumbo",

    # --- Servings / recipes ---
    "serv":      "serving",
    "servings":  "serving",
    "serving":   "serving",
    "recipe":    "recipe",
}


def normalize_unit(raw: str | None) -> str | None:
    """Return the canonical unit string for *raw*, or *raw* unchanged if unknown.
    
    Case-sensitive lookup runs first to preserve distinctions like:
      'T'  (uppercase) = tablespoon
      't'  (lowercase) = teaspoon
    """
    if not raw:
        return raw
    stripped = raw.strip()
    # 1. Case-sensitive exact match (handles T vs t, etc.)
    canonical = UNIT_MAP.get(stripped)
    if canonical:
        return canonical
    # 2. Case-insensitive fallback (handles "Cup", "CUPS", "Tbs.", etc.)
    canonical = UNIT_MAP.get(stripped.lower())
    if canonical:
        return canonical
    # 3. Unknown unit — return stripped as-is
    return stripped
