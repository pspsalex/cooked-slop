# SPDX-License-Identifier: MIT
"""Unit tests for vintage PRN print dump normalizer (SPEC-028)."""

from pathlib import Path
import pytest

from parsers.generic_md import GenericMdParser
from parsers.ingredients import RegexIngredientParser
from tools.extract.prn_normalizer import (
    strip_pcl_escapes,
    detect_prn_format,
    normalize_prn,
    normalize_mastercook_dump,
    normalize_formfeed_dump,
    normalize_boxed_card_dump,
    normalize_recipe_printout_dump,
    normalize_asterisk_banner_dump,
    main as normalizer_main,
)


@pytest.fixture
def generic_parser():
    return GenericMdParser(RegexIngredientParser())


def test_strip_pcl_escapes():
    """Verify that PCL printer escape sequences are stripped completely."""
    raw = (
        "\x1b(s1Q\x1b(s5H\x1b(s3BVEGETABLE DIP\x1b(s0B\x1b(s10H\r\n"
        "\x1b(s16H\r\n"
        "\x1b&l0o6D\x1b(\x01Hello World\x1b&l5.45C\x1b(s12H\r\n"
        "\x1bEReset printer\x1b(s12\r\n"
    )
    cleaned = strip_pcl_escapes(raw)
    assert "\x1b" not in cleaned
    assert "VEGETABLE DIP" in cleaned
    assert "Hello World" in cleaned
    assert "Reset printer" in cleaned


def test_detect_prn_format():
    """Verify format sniffing across all 5 signature dump variants."""
    boxed = "|===============================================================|================|\n| CATEGORY:     APPETIZERS & DIPS                               | SERVINGS:    6 |\n"
    printout = "Recipe Printout\nRecipe No. 17\nMain Category-- BEANS\nIngredient's:\n >1 cup beans"
    formfeed = "Chocolate Brownies\nThis recipe makes :\nIngredients :\n1 cup sugar\nInstructions :\nMix well\n\x0c"
    mastercook = "Serving Size  : 12\n  Amount  Measure       Ingredient -- Preparation Method\n--------  ------------  --------------------------------\n4 pounds Chicken Gizzards\n"
    banner = "SEAFOOD BISQUE\n1 pound crabmeat\n\nCook it.\n***********************************************************************\n"

    assert detect_prn_format(boxed) == "boxed_card"
    assert detect_prn_format(printout) == "recipe_printout"
    assert detect_prn_format(formfeed) == "formfeed"
    assert detect_prn_format(mastercook) == "mastercook"
    assert detect_prn_format(banner) == "asterisk_banner"
    assert detect_prn_format("Just some plain text without any markers") == "unknown"


def test_normalize_formfeed_dump(generic_parser):
    """Verify form-feed report normalization (cb_100.prn style)."""
    raw = """Chocolate Fudge Brownies
This recipe makes :

Estimated Time : & Temperature :
Ingredients :
125g butter
185g dark cooking chocolate
3/4 cup sugar
2 eggs
1 cup plain flour
1 cup chopped walnuts

Instructions :
Melt chocolate and butter together in pan over low heat, stir in sugar and
eggs one at a time, beat well with wooden spoon, then stir in sifted flour
and walnuts. Pour into greased 20cm square baking tin. Bake in moderate oven
30 minuts, cool in tin.

See Also :

\x0cFudgy Oat-Wheat Brownies
This recipe makes :
12 slices
Estimated Time : & Temperature :
Ingredients :
185g cooking chocolate
4 tablespoons butter

Instructions :
Melt the chocolate and butter in basin over simmering water; mix well and
allow to cool.
"""
    md = normalize_formfeed_dump(raw)
    assert "<!-- format: generic_md -->" in md
    assert "# Chocolate Fudge Brownies" in md
    assert "# Fudgy Oat-Wheat Brownies" in md
    assert "Servings: 12 slices" in md
    assert "See Also :" not in md

    recipes = list(generic_parser.parse_content(md))
    assert len(recipes) == 2
    assert recipes[0].title == "Chocolate Fudge Brownies"
    assert len(recipes[0].ingredients) == 6
    assert recipes[1].title == "Fudgy Oat-Wheat Brownies"
    assert recipes[1].yield_amount == "12 slices"


def test_normalize_mastercook_dump(generic_parser):
    """Verify MasterCook printer dump normalization (holiday.prn style)."""
    raw = """
                      A Mardi Gras Cookbook (516) 569-5427

     Page 1              (C) Copyright 1995 - One Command Software Inc.
     02/05/26     Upgrade to our Complete Cookbook for only $19.95 !


                                Baked Oyster Dressing                       
                                                                            
     Serving Size  : 12                                                    
       Amount  Measure       Ingredient -- Preparation Method              
     --------  ------------  --------------------------------              
        4      pounds        Chicken Gizzards                              
        2      pounds        Chicken Livers                                
          1/2  gallon        Oyster                                        
                                                                            
     In a separate pots, boil the gizzards, livers and oysters. Bake covered
     in 350 degree oven for about 1 hour.
                        - - - - - - - - - - - - - - - - - -                

                                Bean And Macaroni Soup                      
                                                                            
     Serving Size  : 4                                                     
       Amount  Measure       Ingredient -- Preparation Method              
     --------  ------------  --------------------------------              
        3 1/2  cups          White Beans -- cooked                         
          1/4  pound         Bacon -- cut into pieces                      
                                                                            
     In a large pot, saute bacon. Simmer about 1 hour.
                        - - - - - - - - - - - - - - - - - -                
     NOTES : Serve hot with bread.
"""
    md = normalize_mastercook_dump(raw)
    assert "<!-- format: generic_md -->" in md
    assert "# Baked Oyster Dressing" in md
    assert "# Bean And Macaroni Soup" in md
    assert "Page 1" not in md
    assert "(C) Copyright" not in md

    recipes = list(generic_parser.parse_content(md))
    assert len(recipes) == 2
    assert recipes[0].title == "Baked Oyster Dressing"
    assert recipes[0].yield_amount == "12"
    assert len(recipes[0].ingredients) == 3
    assert recipes[1].title == "Bean And Macaroni Soup"
    assert recipes[1].yield_amount == "4"


def test_normalize_boxed_card_dump(generic_parser):
    """Verify boxed card dump normalization (mmm150.prn.txt style)."""
    raw = """\x1b(s1Q\x1b(s5H\x1b(s3BVEGETABLE DIP\x1b(s0B\x1b(s10H
\x1b(s16H
|===============================================================|================|
| CATEGORY:     APPETIZERS & DIPS                               | SERVINGS:    6 |
|===============================================================|================|
|       1 CUP     SALAD DRESSING        |       1 TSP     SALT                   |
|       1 CUP     COTTAGE CHEESE        |                                        |
|       1 TBSP    REAL LEMON JUICE      |                                        |
|================================================================================|
|               Mix in blender. Serve with various vegetable dippers.            |
|================================================================================|
\x1b(s6V\x1b(s16H       JAN 26,2026
\x1b(s12

CORN BREAD
|===============================================================|================|
| CATEGORY:     BISCUITS & BREADS                               | SERVINGS:    5 |
|===============================================================|================|
|       1 PKG     CORN BREAD MIX        |                                        |
|       1         EGG                   |                                        |
|================================================================================|
|      Mix egg and milk and mix. Bake at 350 for 15 minutes til light brown.     |
|================================================================================|
"""
    md = normalize_boxed_card_dump(raw)
    assert "<!-- format: generic_md -->" in md
    assert "# VEGETABLE DIP" in md
    assert "Categories: APPETIZERS & DIPS" in md
    assert "Servings: 6" in md
    assert "# CORN BREAD" in md

    recipes = list(generic_parser.parse_content(md))
    assert len(recipes) == 2
    assert recipes[0].title == "VEGETABLE DIP"
    assert len(recipes[0].ingredients) == 4
    assert recipes[1].title == "CORN BREAD"
    assert len(recipes[1].ingredients) == 2


def test_normalize_recipe_printout_dump(generic_parser):
    """Verify classic recipe printout normalization (prcb.prn style)."""
    raw = """
===============================================================================
                          Recipe Printout
Recipe No.     17  Abbr.-- Misc      Page 1 of 1
Main Category-- BEANS                                             
Sub-Category--- BAKED BEANS                                       
Recipe Name----                                                   
Ingredient's:                                                                 
 >2 cans Bush baked beans                   >1/2 cup brown sugar               
 >1/2 cup Molasses                          >                                  
 Source of recipe: Family secret                                          
Recipe: 
1) Bake at 300 Degrees (covered) for 1 hour. and 1 hour uncoverd               
===============================================================================

===============================================================================
                          Recipe Printout
Recipe No.     13  Abbr.-- BREAD     Page 1 of 1
Main Category-- BREAD                                             
Sub-Category--- PUMPKIN BREAD                                     
Recipe Name---- PUMPKIN BREAD                                     
Ingredient's:                                                                 
 >2 2/3 CUPS SUGAR                          >1/2 TSP SALT                      
 >2/3 CUP SHORTENING                        >1 TSP. CIMMANON                   
Recipe: 
1) MIX ABOVE INGREDIENTS. BAKE AT 350 DEGREES FOR 1hour.
===============================================================================
"""
    md = normalize_recipe_printout_dump(raw)
    assert "<!-- format: generic_md -->" in md
    assert "# BAKED BEANS" in md
    assert "# PUMPKIN BREAD" in md

    recipes = list(generic_parser.parse_content(md))
    assert len(recipes) == 2
    assert recipes[0].title == "BAKED BEANS"
    assert len(recipes[0].ingredients) == 3
    assert recipes[1].title == "PUMPKIN BREAD"
    assert len(recipes[1].ingredients) == 4


def test_normalize_asterisk_banner_dump(generic_parser):
    """Verify asterisk banner delimited dump normalization (tcs.prn style)."""
    raw = """
SEAFOOD BISQUE - compliments of "The Chef's Source"

1 pound crabmeat
1 pound scallops
1/4 cup onion; finely chopped

1) In a large saucepan saute the onion.
2) Add the scallops and crabmeat; simmer 10 minutes.
Serves 8 as a first course.
***********************************************************************

BERRY DELICIOUS LEMONADE

1 1/2 cups strawberries; sliced
1 cup fresh lemon juice

1) Process ingredients in blender.
Yields 4 cups.
***********************************************************************
"""
    md = normalize_asterisk_banner_dump(raw)
    assert "<!-- format: generic_md -->" in md
    assert "# SEAFOOD BISQUE" in md
    assert "# BERRY DELICIOUS LEMONADE" in md
    assert "Servings: 8 as a first course" in md

    recipes = list(generic_parser.parse_content(md))
    assert len(recipes) == 2
    assert recipes[0].title == "SEAFOOD BISQUE"
    assert len(recipes[0].ingredients) == 3
    assert recipes[1].title == "BERRY DELICIOUS LEMONADE"
    assert len(recipes[1].ingredients) == 2


def test_prn_normalizer_cli(tmp_path: Path):
    """Verify CLI interface for prn_normalizer with -o and --in-place."""
    input_file = tmp_path / "test_report.prn"
    input_file.write_text(
        "Fudge Brownies\nThis recipe makes :\nIngredients :\n1 cup sugar\nInstructions :\nBake 30 min.\n\x0c",
        encoding="utf-8",
    )

    out_file = tmp_path / "custom_out.md"
    normalizer_main([str(input_file), "-o", str(out_file)])
    assert out_file.exists()
    content = out_file.read_text(encoding="utf-8")
    assert "<!-- format: generic_md -->" in content
    assert "# Fudge Brownies" in content

    # Test in-place
    normalizer_main([str(input_file), "--in-place"])
    in_place_content = input_file.read_text(encoding="utf-8")
    assert "<!-- format: generic_md -->" in in_place_content
    assert "# Fudge Brownies" in in_place_content
