# SPDX-License-Identifier: MIT
"""Unit tests for Vitt CSV recipe extractor (tools/extract/vitt.py)."""

from pathlib import Path
import pytest

from parsers.generic_md import GenericMdParser
from parsers.ingredients import RegexIngredientParser
from tools.extract.vitt import (
    to_title_case,
    handle_line_continuations,
    extract_vitt_recipes,
    convert_vitt_to_markdown,
    convert_vitt_csv_to_markdown,
)

SAMPLE_CSV = """RNUM,NAME,KING,SOURCE,TXT,TAG
3,"FROZEN PEANUT BUTTER DESSERT","peanut butter/chocolate/nuts","Natl Cooking Echo 17 Jul 90","Contributed to the echo by: Janice Norman

Steve, my husband, also a peanut butter addict, had a peanut 
butter/chocolate dessert this week at a meeting. He enjoyed it so much.

Frosty Peanut Butter Dessert

Crust:

1 cup flour (all purpose)
2 tablespoons sugar
1 stick butter or margarine, melted
1/2 cup chopped walnuts

Mix and press into 13 x 9 pan. Bake at 350 for 15 minutes.

Filling:

1 pkg. (8 oz.) cream cheese softened
1/2 c. sugar
1/4 c. peanut butter

Beat cream cheese with sugar and peanut butter. Cover & freeze.
",
4,"LAMB BURGERS W/RASPBERRY-MINT SAUCE",lamb/chevre,"Natl Cooking Echo 18 Jul 90","Contributed to the echo by: Vincent Mcguire

I am getting ready for supper.

Lamb Burgers with Raspberry-Mint Sauce

2 pounds of ground lean lamb
salt and ground pepper
8 ounces of soft mild chevre

Mix lamb with seasonings. Grill burgers.
",
"""


@pytest.fixture
def generic_parser():
    return GenericMdParser(RegexIngredientParser())


def test_to_title_case():
    assert to_title_case("FROZEN PEANUT BUTTER DESSERT") == "Frozen Peanut Butter Dessert"
    assert to_title_case("LAMB BURGERS W/RASPBERRY-MINT SAUCE") == "Lamb Burgers W/raspberry-mint Sauce"
    assert to_title_case("Already Mixed Case") == "Already Mixed Case"
    assert to_title_case("") == ""


def test_handle_line_continuations():
    raw = "Line one ends with _\ncontinuation text\nLine two is separate"
    merged = handle_line_continuations(raw)
    assert "Line one ends with continuation text" in merged
    assert "Line two is separate" in merged


def test_extract_vitt_recipes():
    recipes = extract_vitt_recipes(SAMPLE_CSV)
    assert len(recipes) == 2

    r1 = recipes[0]
    assert r1["title"] == "Frozen Peanut Butter Dessert"
    assert r1["categories"] == ["peanut butter", "chocolate", "nuts"]
    assert r1["source"] == "Natl Cooking Echo 17 Jul 90"
    assert "Crust:" in r1["ingredients"]
    assert "1 cup flour (all purpose)" in r1["ingredients"]
    assert "Filling:" in r1["ingredients"]
    assert any("Mix and press into 13 x 9 pan" in step for step in r1["instructions"])

    r2 = recipes[1]
    assert r2["title"] == "Lamb Burgers W/raspberry-mint Sauce"
    assert r2["categories"] == ["lamb", "chevre"]
    assert "2 pounds of ground lean lamb" in r2["ingredients"]
    assert any("Grill burgers" in step for step in r2["instructions"])


def test_convert_vitt_to_markdown_and_parse(generic_parser, tmp_path):
    in_file = tmp_path / "vitt.csv"
    out_file = tmp_path / "vitt.md"
    in_file.write_text(SAMPLE_CSV, encoding="utf-8")

    count = convert_vitt_csv_to_markdown(in_file, out_file)
    assert count == 2
    assert out_file.exists()

    md_content = out_file.read_text(encoding="utf-8")
    assert "<!-- format: generic_md -->" in md_content
    assert "# Frozen Peanut Butter Dessert" in md_content

    # Verify standard GenericMdParser can parse the generated markdown
    recipes = list(generic_parser.parse_content(md_content, str(out_file)))
    assert len(recipes) == 2
    assert recipes[0].title == "Frozen Peanut Butter Dessert"
    assert "peanut butter" in recipes[0].categories
    assert len(recipes[0].ingredients) >= 7
    assert len(recipes[0].instructions) >= 1
