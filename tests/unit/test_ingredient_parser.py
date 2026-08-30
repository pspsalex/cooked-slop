# SPDX-License-Identifier: MIT
"""Unit tests for RegexIngredientParser and unit normalization."""
import pytest
from parsers.ingredients import RegexIngredientParser
from parsers.units import normalize_unit


@pytest.fixture
def parser():
    """Returns a RegexIngredientParser instance."""
    return RegexIngredientParser()


def test_parse_fractions(parser):
    """Verify parsing simple fractions like '1/2 cup flour'."""
    res = parser.parse("1/2 cup flour")
    assert res.raw == "1/2 cup flour"
    assert res.quantity == "1/2"
    assert res.unit == "cup"
    assert res.name == "flour"


def test_parse_mixed_numbers(parser):
    """Verify parsing mixed numbers like '1 1/2 tsp salt'."""
    res = parser.parse("1 1/2 tsp salt")
    assert res.raw == "1 1/2 tsp salt"
    assert res.quantity == "1 1/2"
    assert res.unit == "teaspoon"
    assert res.name == "salt"


def test_parse_decimals(parser):
    """Verify parsing decimals like '2.5 kg sugar'."""
    res = parser.parse("2.5 kg sugar")
    assert res.raw == "2.5 kg sugar"
    assert res.quantity == "2.5"
    assert res.unit == "kg"
    assert res.name == "sugar"


def test_parse_ranges(parser):
    """Verify parsing quantity ranges like '2-3 cloves garlic'."""
    res = parser.parse("2-3 cloves garlic")
    assert res.raw == "2-3 cloves garlic"
    assert res.quantity == "2-3"
    assert res.unit == "clove"
    assert res.name == "garlic"

    # Also test range with spaces
    res_spaced = parser.parse("1 - 2 tbsp olive oil")
    assert res_spaced.quantity == "1 - 2"
    assert res_spaced.unit == "tablespoon"
    assert res_spaced.name == "olive oil"


def test_parse_comments(parser):
    """Verify trailing descriptors/comments are retained in the ingredient name by regex parser."""
    res = parser.parse("1 cup butter, melted")
    assert res.raw == "1 cup butter, melted"
    assert res.quantity == "1"
    assert res.unit == "cup"
    assert res.name == "butter, melted"


def test_parse_case_sensitive_units(parser):
    """Verify case-sensitive unit distinction ('1 T' tablespoon vs '1 t' teaspoon)."""
    res_tbsp = parser.parse("1 T paprika")
    assert res_tbsp.quantity == "1"
    assert res_tbsp.unit == "tablespoon"
    assert res_tbsp.name == "paprika"

    res_tsp = parser.parse("1 t cumin")
    assert res_tsp.quantity == "1"
    assert res_tsp.unit == "teaspoon"
    assert res_tsp.name == "cumin"


def test_parse_missing_units(parser):
    """Verify ingredients with quantity but no recognized unit ('3 eggs')."""
    res = parser.parse("3 eggs")
    assert res.raw == "3 eggs"
    assert res.quantity == "3"
    assert res.unit is None
    assert res.name == "eggs"


def test_parse_missing_quantities(parser):
    """Verify ingredients without quantities ('salt and pepper to taste')."""
    res = parser.parse("salt and pepper to taste")
    assert res.raw == "salt and pepper to taste"
    assert res.quantity is None
    assert res.unit is None
    assert res.name == "salt and pepper to taste"


def test_parse_empty_or_non_alphanumeric(parser):
    """Verify empty or delimiter-only lines return raw ingredient without crash."""
    res_empty = parser.parse("")
    assert res_empty.raw == ""
    assert res_empty.quantity is None
    assert res_empty.name is None

    res_dashes = parser.parse("---")
    assert res_dashes.raw == "---"
    assert res_dashes.quantity is None
    assert res_dashes.name is None


def test_normalize_unit_case_sensitivity():
    """Verify case-sensitive exact matches in normalize_unit."""
    assert normalize_unit("T") == "tablespoon"
    assert normalize_unit("T.") == "tablespoon"
    assert normalize_unit("t") == "teaspoon"
    assert normalize_unit("t.") == "teaspoon"


def test_normalize_unit_common_abbreviations():
    """Verify common unit mappings across volume, weight, and count."""
    # Volume
    assert normalize_unit("c") == "cup"
    assert normalize_unit("c.") == "cup"
    assert normalize_unit("cups") == "cup"
    assert normalize_unit("tbsp") == "tablespoon"
    assert normalize_unit("tbsp.") == "tablespoon"
    assert normalize_unit("tbs") == "tablespoon"
    assert normalize_unit("tsp") == "teaspoon"
    assert normalize_unit("tsp.") == "teaspoon"
    assert normalize_unit("fl oz") == "fluid ounce"
    assert normalize_unit("pt") == "pint"
    assert normalize_unit("qt") == "quart"
    assert normalize_unit("gal") == "gallon"
    assert normalize_unit("ml") == "ml"
    assert normalize_unit("l") == "liter"

    # Weight
    assert normalize_unit("oz") == "ounce"
    assert normalize_unit("oz.") == "ounce"
    assert normalize_unit("lb") == "pound"
    assert normalize_unit("lbs") == "pound"
    assert normalize_unit("ib.") == "pound"
    assert normalize_unit("g") == "gr"
    assert normalize_unit("kg") == "kg"
    assert normalize_unit("kilogram") == "kg"

    # Botanical / Culinary
    assert normalize_unit("clove") == "clove"
    assert normalize_unit("cloves") == "clove"
    assert normalize_unit("pinch") == "pinch"
    assert normalize_unit("dash") == "dash"


def test_normalize_unit_case_insensitive_fallback():
    """Verify uppercase/capitalized variants resolve via case-insensitive fallback."""
    assert normalize_unit("CUP") == "cup"
    assert normalize_unit("Cups") == "cup"
    assert normalize_unit("Tablespoon") == "tablespoon"
    assert normalize_unit("POUND") == "pound"


def test_normalize_unit_unknown_and_empty():
    """Verify unknown units are returned unchanged and empty/None values are preserved."""
    assert normalize_unit("handcrafted_jar") == "handcrafted_jar"
    assert normalize_unit(None) is None
    assert normalize_unit("") == ""
