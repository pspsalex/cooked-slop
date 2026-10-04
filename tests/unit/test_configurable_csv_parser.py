# SPDX-License-Identifier: MIT
"""Unit tests for ConfigurableCsvParser."""

from pathlib import Path

import pytest

from parsers.csv_parser import ConfigurableCsvParser, decode_csv_bytes
from parsers.ingredients import RegexIngredientParser
from parsers.registry import ParserRegistry

SAMPLES = Path(__file__).parent.parent / "samples"


@pytest.fixture
def parser() -> ConfigurableCsvParser:
    return ConfigurableCsvParser(RegexIngredientParser())


def test_registered_with_priority_and_aliases():
    assert ConfigurableCsvParser in ParserRegistry._parsers
    assert ConfigurableCsvParser.priority() == 22
    names = ParserRegistry.all_format_names()
    for alias in ("csv_cookware", "csv_20krecipes"):
        assert alias in names


def test_detect_contract():
    chefs = (SAMPLES / "chefs.csv").read_text(encoding="utf-8")
    assert ConfigurableCsvParser.detect("chefs.csv", chefs) >= 0.9
    assert ConfigurableCsvParser.detect("chefs.txt", chefs) == 0.0
    assert ConfigurableCsvParser.detect("x.csv", "a,b\n1,2\n") == 0.0


def test_chefs_headerless_split(parser):
    recipes = list(parser.parse_file(str(SAMPLES / "chefs.csv")))
    assert [r.title for r in recipes] == [
        "Impossible Quiche",
        "Lime Jello Cottage Cheese Pineapple Salad",
    ]
    quiche = recipes[0]
    assert quiche.categories == ["SEAFOOD", "QUICHE"]
    raws = [i.raw for i in quiche.ingredients]
    assert "1/2 lb Crab or Shrimp" in raws and "3 Eggs" in raws  # side-by-side cell split
    assert len(raws) == 11
    assert quiche.instructions[0].startswith("Saute")
    assert len(quiche.instructions) == 3
    assert quiche.source_format == "Chef's Catalog CSV"
    assert quiche.url.endswith("#1")


def test_cookware_columns_and_dedup(parser):
    recipes = list(parser.parse_file(str(SAMPLES / "cookware.csv")))
    assert recipes
    first = recipes[0]
    assert first.title == "Almond Cheese Spread"
    assert first.source_format == "Cookware CSV"
    assert len(first.ingredients) >= 8
    assert first.instructions


def test_twentyk_value_map_and_null(parser):
    recipes = list(parser.parse_file(str(SAMPLES / "sample_20krecipes.csv")))
    assert recipes
    assert all("NULL" not in r.categories for r in recipes)
    assert all(r.source_format == "20krecipes CSV" for r in recipes)


def test_decode_fallback():
    assert decode_csv_bytes("caf\u00e9".encode("utf-8")) == "caf\u00e9"
    assert decode_csv_bytes("caf\u00e9".encode("latin-1")) == "caf\u00e9"


def test_no_schema_yields_nothing(parser):
    assert list(parser.parse_content("a,b\n1,2\n", "plain.csv")) == []
