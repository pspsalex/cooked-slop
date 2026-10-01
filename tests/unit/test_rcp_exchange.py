# SPDX-License-Identifier: MIT
"""Unit tests for RCP Nutritional Exchange parser."""
import glob
from pathlib import Path
import pytest

from parsers.rcp_exchange import RcpExchangeParser
from parsers.ingredients import RegexIngredientParser
from parsers.registry import ParserRegistry


@pytest.fixture
def parser():
    return RcpExchangeParser(ingredient_parser=RegexIngredientParser())


def test_registry_registration():
    """Verify RcpExchangeParser is registered with ParserRegistry."""
    format_ids = [p.format_id() for p in ParserRegistry._parsers]
    assert "rcp_exchange" in format_ids
    assert RcpExchangeParser.format_id() == "rcp_exchange"
    assert "rcp" in RcpExchangeParser.aliases()
    assert "exchange" in RcpExchangeParser.aliases()
    assert RcpExchangeParser.priority() == 6
    assert ".rcp" in RcpExchangeParser.supported_extensions()

    p = ParserRegistry.get_parser(Path("dummy.rcp"), RegexIngredientParser(), format_name="rcp_exchange")
    assert isinstance(p, RcpExchangeParser)
    p_rcp = ParserRegistry.get_parser(Path("dummy.rcp"), RegexIngredientParser(), format_name="rcp")
    assert isinstance(p_rcp, RcpExchangeParser)
    p_exch = ParserRegistry.get_parser(Path("dummy.rcp"), RegexIngredientParser(), format_name="exchange")
    assert isinstance(p_exch, RcpExchangeParser)


def test_detection_rcp_extension():
    """Verify detection score 0.95 when .rcp extension and RECIPE_TEXT: delimiter are present."""
    sample = "Test Recipe\n4\n00.00 00.00 00.00 00.00 00.00 00.00 1 cup water\nRECIPE_TEXT:\nBoil water.\n"
    assert RcpExchangeParser.detect("recipe.rcp", sample) == 0.95
    assert RcpExchangeParser.detect("recipe.RCP", sample) == 0.95


def test_detection_structural():
    """Verify detection score 0.90 when content matches structure even without .rcp extension."""
    sample = "Test Recipe\n4\n00.00 00.00 00.00 00.00 00.00 00.00 1 cup water\nRECIPE_TEXT:\nBoil water.\n"
    assert RcpExchangeParser.detect("recipe.txt", sample) == 0.90


def test_detection_negative():
    """Verify detection returns 0.0 for empty content, missing delimiter, or invalid structure."""
    assert RcpExchangeParser.detect("recipe.rcp", "") == 0.0
    assert RcpExchangeParser.detect("recipe.txt", "") == 0.0
    assert RcpExchangeParser.detect("recipe.rcp", "Just some random text\n") == 0.0
    assert RcpExchangeParser.detect("recipe.txt", "Title\nFour\n00.00 00.00 00.00 00.00 00.00 00.00 1 cup water\nRECIPE_TEXT:\nBoil.\n") == 0.0
    assert RcpExchangeParser.detect("recipe.txt", "Title\n4\n1 cup water\nRECIPE_TEXT:\nBoil.\n") == 0.0


def test_detection_all_ingest_samples():
    """Verify detection on all 9 real .RCP files in the repository if available."""
    sample_files = glob.glob("/home/alex/junk/Recipes/Ingest/ToDo/TXT/*.RCP")
    if not sample_files:
        pytest.skip("Ingest directory not available in test environment")

    for fpath in sample_files:
        with open(fpath, "r", encoding="latin-1") as f:
            content = f.read()
        score = RcpExchangeParser.detect(fpath, content)
        assert score >= 0.90, f"Detection failed for {fpath}, score: {score}"


def test_stripping_exchange_numbers(parser):
    """Verify 6 exchange numbers are stripped before ingredient parsing."""
    sample = """Simple Test
2
24.00 24.00 00.00 00.00 00.00 00.00 2 lbs ground beef, drained
00.00 03.80 03.80 00.00 00.00 00.00 15 1/2 oz can pinto beans
RECIPE_TEXT:
Cook and stir.
"""
    recipes = list(parser.parse_content(sample, "test.rcp"))
    assert len(recipes) == 1
    r = recipes[0]
    assert len(r.ingredients) == 2

    ing1 = r.ingredients[0]
    assert ing1.raw == "2 lbs ground beef, drained"
    assert ing1.quantity == "2"
    assert ing1.unit == "pound"
    assert ing1.name == "ground beef, drained"

    ing2 = r.ingredients[1]
    assert ing2.raw == "15 1/2 oz can pinto beans"
    assert ing2.quantity == "15 1/2"
    assert ing2.unit == "ounce"
    assert ing2.name == "can pinto beans"


def test_parse_content_chili2_sample(parser):
    """Verify complete parsing of chili2.rcp fixture."""
    sample_path = Path(__file__).parent.parent / "samples" / "chili2.rcp"
    if not sample_path.exists():
        pytest.fail(f"Fixture not found at {sample_path}")

    with open(sample_path, "r", encoding="utf-8") as f:
        content = f.read()

    recipes = list(parser.parse_content(content, str(sample_path)))
    assert len(recipes) == 1
    r = recipes[0]

    assert r.title == "Road Kill Chili"
    assert r.yield_amount == "8 servings"
    assert r.source_format == "RCP Exchange"
    assert r.source_file == str(sample_path)
    assert len(r.ingredients) == 13

    # Check first and last ingredients
    assert r.ingredients[0].raw == "2 lbs ground beef, drained"
    assert r.ingredients[-1].raw == "1 cup water"

    # Check instructions
    assert len(r.instructions) == 7
    assert r.instructions[0] == "1. Brown the beef, and drain."
    assert r.instructions[5] == "6.  Let set in fridge overnight and reheat before serving."
    assert r.instructions[6] == "For true chili hot heads, try adding a Habenero pepper or two, but stir fast to keep from losing the spoon!"


def test_parse_content_porkchop_sample(parser):
    """Verify parsing of Sample 2 (PORKCHOP.RCP)."""
    sample = """Dick Hampton Patterson's Glazed and Onion Pork Chops
6
00.00 00.00 00.00 00.00 00.00 03.00 3 large onions, cut in half
00.00 00.00 00.00 04.00 00.00 00.00 6 medium pork chops
00.00 00.00 00.00 00.00 00.00 00.00 1/3 cup brown sugar
00.00 00.00 00.00 00.00 00.00 00.00 1 tsp sage
00.00 00.00 00.00 00.00 00.00 00.00 1 tsp salt
00.00 00.00 00.00 00.00 00.00 00.00 1 tsp paprika
00.00 00.00 00.00 00.00 00.00 00.00 1 tsp mustard
00.00 00.00 00.00 00.00 00.00 00.00 1/4 tsp pepper
13.50 27.00 00.00 00.00 00.00 00.00 1 tbsp water
RECIPE_TEXT:
Boil onions in salted water for 10 minutes.  Drain.

Put onions, cut side up, with chops in baking pan.

Mix other ingrediants and spoon over chops.  Bake and base for 1 hour at 325 degrees.
"""
    recipes = list(parser.parse_content(sample, "porkchop.rcp"))
    assert len(recipes) == 1
    r = recipes[0]
    assert r.title == "Dick Hampton Patterson's Glazed and Onion Pork Chops"
    assert r.yield_amount == "6 servings"
    assert len(r.ingredients) == 9
    assert len(r.instructions) == 3
    assert r.instructions[0] == "Boil onions in salted water for 10 minutes.  Drain."
    assert r.instructions[1] == "Put onions, cut side up, with chops in baking pan."
    assert r.instructions[2] == "Mix other ingrediants and spoon over chops.  Bake and base for 1 hour at 325 degrees."


def test_edge_cases(parser):
    """Verify edge cases such as leading empty lines, empty input, and plain ingredients."""
    # Empty content
    assert list(parser.parse_content("", "test.rcp")) == []
    assert list(parser.parse_content("   \n\n  ", "test.rcp")) == []

    # Leading whitespace and un-prefixed ingredient line
    sample = """

Pecan Pie
1
00.00 00.00 00.00 00.00 00.00 00.00 1 cup pecans
Pinch of salt
RECIPE_TEXT:
Bake at 350.
"""
    recipes = list(parser.parse_content(sample, "test.rcp"))
    assert len(recipes) == 1
    r = recipes[0]
    assert r.title == "Pecan Pie"
    assert r.yield_amount == "1 servings"
    assert len(r.ingredients) == 2
    assert r.ingredients[0].raw == "1 cup pecans"
    assert r.ingredients[1].raw == "Pinch of salt"
    assert r.instructions == ["Bake at 350."]
