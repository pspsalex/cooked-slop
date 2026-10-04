---
id: SPEC-032
title: "Multi-Recipe Boundary Splitting in Text and Two-Column Parsers"
tier: 1
type: parser
priority: P1
status: done
impact: "Splits 218+ monolithic multi-recipe files (up to 6,196 ingredients per file) into thousands of clean individual recipes"
deliverables:
  - parsers/two_col.py
  - parsers/generic.py
  - tests/samples/two_col_multi.txt
  - tests/expected/two_col_multi.txt.json
  - tests/unit/test_multi_recipe_splitting.py
---

# Spec: Multi-Recipe Boundary Splitting in Text and Two-Column Parsers

## Description

In `all_recipes.json`, 218 files were parsed into monolithic single-recipe objects containing between 50 and 6,196 ingredients each.

Examples:
- `Cookbook-Chocoate Treats.txt`: 6,196 ingredients, 186 instructions in 1 recipe
- `CATS_MEO.TXT`: 3,765 ingredients, 4,192 instructions in 1 recipe
- `RECIPES.1-27.txt`: 2,811 ingredients, 1,464 instructions in 1 recipe
- `restrec.txt`: 1,628 ingredients
- `cookdeluxe.txt`: 1,442 ingredients
- `lowcarb.txt`: 1,366 ingredients
- `Cheesecakes.txt`: 798 ingredients

Investigation shows that both `TwoColParser` and `GenericTextParser` currently assume single-recipe input files. When encountering multi-recipe compilations separated by dashed borders (`-----`), repeated title headers, or blank lines, they parse ingredients and instructions continuously across recipe boundaries, generating a single bloated recipe.

## Input Samples

### Sample 1: `Ingest/ToDo/TXT/RECIPES.1-27.txt` (Two-Column format with `-----` delimiters)

```text
-----
For the after-school crowd.

				Oatmeal Cookies

1 c butter				3 c rolled oats
1/4 c honey				1 3/4 c whole wheat pastry flour
1/4 c pure maple syrup			1/4 tsp nutmeg
2 eggs					1/2 c walnuts (optional)
1/2 c milk				1/2 c raisins (optional)
1 T molasses				1/2 c carob chips (optional)

Cream together butter, honey, syrup, eggs, milk and molasses.  Combine dry
ingredients; stir into wet.  Form dough into cookies and space on oiled cookie
sheets.  Bake at 350 degrees for 7-10 minutes.	Tops will be brown when done.

Makes 36

KEY WORDS:  bake sale, potluck, baked goods, cookies, kids, freezes well,
stores well, make ahead
-----
Welcome anytime, a healthy snack that's tasty too.

			      Wheat Germ Squares

1/4 c butter				1 c wheat germ
1/4 c molasses				1/2 c powdered dry milk
3/4 c honey				1/2 tsp baking powder
2 eggs					1 pinch salt
2 T vanilla				1/2 c chopped nuts

Melt butter, molasses and honey together.  Remove from heat.  Add eggs and
vanilla.  Stir in the remaining ingredients until just moistened.  Spread mix
in oiled 8-inch square pan, and bake at 350 degrees, 25-30 minutes.  Cool and
cut into 2-inch squares.

Makes 16
```

## Expected Behavior

### Two-Column Parser Multi-Recipe Splitting
1. When input contains section delimiters matching `^[-=~*]{4,}\s*$` or clear boundary headers, `TwoColParser.parse_content()` must split the content into individual recipe sections.
2. Each section must be parsed independently and yielded as an individual `Recipe`.
3. Title extraction must ignore leading intro blurbs (e.g. `For the after-school crowd.`) and correctly identify the centered title (e.g. `Oatmeal Cookies`).
4. Trailing metadata (`Makes 36`, `KEY WORDS: ...`) must populate `yield_amount` and `categories`.

### Generic Text Parser Splitting
In `GenericTextParser`, detect repeated recipe header boundaries (such as lines preceded by double blank lines with title capitalization followed by ingredient lines) or explicit divider lines, splitting into chunks before generating recipes.

## Acceptance Criteria
- [x] `TwoColParser` splits multi-recipe files on `^[-=~*]{4,}$` delimiters and yields multiple recipes
- [x] Intro text preceding centered titles in two-column recipes does not become the title
- [x] Multi-recipe test fixture `tests/samples/two_col_multi.txt` added with expected output verifying multiple yielded recipes
- [x] Unit tests in `tests/unit/test_multi_recipe_splitting.py`
- [x] Full test suite passes: `./venv/bin/python3 -m pytest tests/ -v`
