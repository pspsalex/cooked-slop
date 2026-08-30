---
id: SPEC-007
title: "TopSecret Recipe Collection"
tier: 2
type: html-config
priority: P1
status: done
impact: "TBD"
deliverables: []
---

# Spec: Top Secret Recipes HTML Config
## Tier: 2
## Type: html-config
## Priority: P1
## Estimated file impact: 182 files

## Description

The `Top Secret` directory contains 182 HTML files created from Todd Wilbur's *Top Secret Recipes* website (`http://www.topsecretrecipes.com`). These files are printer-friendly pages (`*pv.htm` and related files) that provide clone recipes for famous restaurant and brand-name food products (Kraft, IHOP, KFC, Outback Steakhouse, Starbucks, McDonald's, Taco Bell, etc.).

All files share a consistent Microsoft FrontPage HTML template structure with clear title tables, intro commentary, bold ingredient lists separated with line breaks, numbered instruction steps, and yield statements.

The goal is to create `configs/topsecret.yaml` to detect and parse these files into valid Schema.org JSON-LD recipes.

## Input Samples

### Sample 1: `Top Secret/1000islepv.htm`
**Location:** `/home/alex/junk/Recipes/Ingest/ToDo/HTML/Top Secret/1000islepv.htm`

```html
<html>

<head>
<meta http-equiv="Content-Type" content="text/html; charset=windows-1252">
<meta name="GENERATOR" content="Microsoft FrontPage 4.0">
<meta name="ProgId" content="FrontPage.Editor.Document">
<title>Top Secret Recipes version of Kraft Thousand Island Dressing - Printer Friendly Page</title>
</head>

<body>

        <div align="center">
          <center>
          <table border="0" cellspacing="0" width="74%">
            <tr>
              <td width="100%">
                <p align="center"><font size="5"><em><strong>Top Secret Recipes</strong></em><strong><br>
        version of <br>
                Kraft Thousand Island Dressing<br>
 </strong></font><strong><font size="1">by Todd Wilbur</font> </strong></td>
            </tr>
          </table>
          </center>
        </div>

        <p align="left"><font size="3"><b>    Here's a quick clone
        for one of the best-selling thousand island dressings
        around. Use this one on salads or on burgers (such as the In-N-Out Double-Double clone) as a home-made "special sauce."
        It's easy, it's tasty, it's cheap...and it can be made
        low fat simply by using low fat mayo. Dig it.</b></font></p>
        <p align="left"><strong>1/2 cup mayonnaise<br>
        2 tablespoons ketchup<br>
        1 tablespoon white vinegar<br>
        2 teaspoons sugar<br>
        2 teaspoons sweet pickle relish<br>
        1 teaspoon finely minced white onion<br>
        1/8 teaspoon salt<br>
        dash of black pepper</strong></p>
        <p align="left"><strong>1. Combine all of the ingredients
        in a small bowl. Stir well.<br>
        2. Place dressing in a covered container and refrigerate
        for several hours, stirring occasionally, so that the
        sugar dissolves and the flavors blend.</strong></p>
          <p align="left"><strong>From:</strong><font
        size="3"><b>  <a href="http://www.topsecretrecipes.com">http://www.topsecretrecipes.com</a><br>
          </b></font><strong><br>
        Makes about 3/4 cup.</p>
```

### Sample 2: `Top Secret/IHOP1pv.htm`
**Location:** `/home/alex/junk/Recipes/Ingest/ToDo/HTML/Top Secret/IHOP1pv.htm`

```html
<html>

<head>
<meta http-equiv="Content-Type" content="text/html; charset=windows-1252">
<meta name="GENERATOR" content="Microsoft FrontPage 4.0">
<meta name="ProgId" content="FrontPage.Editor.Document">
<title>Top Secret Recipes version of Pancakes from International House of Pancakes - Printer Friendly Page</title>
</head>

<body>

        <div align="center">
          <center>
          <table border="0" cellspacing="0" width="74%">
            <tr>
              <td width="100%">
                <p align="center"><font size="5"><em><strong>Top
91:         Secret Recipes</strong></em><strong><br>
        version of<br>
        Pancakes from<br>
        International House of Pancakes<br>
                </strong></font><strong><font size="1">by Todd Wilbur</font> </strong></td>
            </tr>
          </table>
          </center>
        </div>
        <p align="left"><b>      </b><strong>Even though the early press runs
        of </strong><em><strong>Top Secret Recipes</strong></em><strong>
        excluded buttermilk in this recipe -- a very important
        ingredient if you really want pourable batter -- many
        figured out the missing ingredient on their own and the
        error was quickly corrected in later copies. Now we just
        like to call those copies of the book the "rare collector's
        edition."</strong></p>
        <p align="left"><font size="3"><strong>Nonstick Spray<br>
        1 1/4 cups all-purpose flour<br>
        1 egg<br>
        1 1/4 cups buttermilk<br>
        1/4 cup granulated sugar<br>
        1 heaping teaspoon baking powder<br>
        1 teaspoon baking soda<br>
        1/4 cup cooking oil<br>
        pinch of salt<br>
        </strong></font></p>
        <p align="left"><font size="3"><strong>1. Preheat a
        skillet over medium heat. Use a pan with a nonstick
        surface or apply a little nonstick spray.<br>
        2. In a blender or with a mixer, combine all of the
        remaining ingredients until smooth.<br>
        3. Pour the batter by spoonfuls into the hot pan, forming
        5-inch circles.<br>
        4. When the edges appear to harden, flip the pancakes.
        They should be golden brown.<br>
        5. Cook pancakes on the other side for same amount of
        time, until golden brown.</strong></font></p>
        <p align="left"><font size="3"><strong>Makes 8 to 10 pancakes.</strong></font></p>
```

### Sample 3: `Top Secret/kfccrisppv.htm`
**Location:** `/home/alex/junk/Recipes/Ingest/ToDo/HTML/Top Secret/kfccrisppv.htm`

```html
<title>Top Secret Recipes version of KFC Extra Crispy Chicken - Printer Friendly Page</title>
...
<p align="center"><font size="5"><em><strong>Top Secret Recipes</strong></em><strong><br>
version of <br>KFC Extra Crispy Chicken<br></strong></font><strong><font size="1">by Todd Wilbur</font> </strong></p>
...
<p align="left"><strong>1 whole frying chicken, cut up<br>
6 to 8 cups shortening<br>
...</strong></p>
<p align="left"><strong>1. Combine the spice and flour mix...<br>
2. Roll chicken pieces in marinade...</strong></p>
<p align="left"><strong>Serves 4.</strong></p>
```

## Expected Behavior

### YAML Layout Schema (`configs/topsecret.yaml`)

```yaml
# SPDX-License-Identifier: MIT
name: top_secret_recipes
description: "XPath configuration for Todd Wilbur's Top Secret Recipes clone archive"
version: "1.0"

detection:
  path_pattern: ".*Top Secret/.*\\.htm[l]?$"
  content_patterns:
    - "Top Secret Recipes"
    - "Todd Wilbur"

fields:
  title:
    xpath: "//table//font[@size='5']/strong[last()]/text() | //p[@align='center']//font[@size='5']/strong[last()]/text() | //title/text()"
  description:
    xpath: "//p[@align='left'][font/b or b]/text() | //p[@align='left'][font/b or b]//text()"
  yield_amount:
    xpath: "//p[contains(translate(., 'MAKES', 'makes'), 'makes')]/strong/text() | //p[contains(translate(., 'SERVES', 'serves'), 'serves')]//text()"
  ingredients:
    xpath: "//p[@align='left'][strong and not(contains(., '1.')) and not(contains(., 'Makes')) and not(contains(., 'Serves')) and not(contains(., 'From:'))]//text()"
    split_delimiter: "\n"
  instructions:
    xpath: "//p[@align='left'][strong and contains(., '1.')]//text()"
    split_delimiter: "\n"
```

### Field Mapping
- **Title**: Extract the recipe name from the header block or `<title>` tag. Clean prefixes (`Top Secret Recipes version of `) and suffixes (` - Printer Friendly Page`).
- **Description / Intro**: Found in the first `<p align="left">` containing bold introduction commentary.
- **Yield**: Found in `<p align="left">` containing `Makes [amount]` or `Serves [amount]`.
- **Ingredients**: Found in the `<p align="left"><strong>` block preceding the instructions. Lines are separated by `<br>` tags.
- **Instructions**: Found in subsequent `<p align="left"><strong>` blocks containing numbered steps (`1. ...`, `2. ...`).
- **Author / Source**: Always set source format / author attribution to `"Todd Wilbur (Top Secret Recipes)"`.

### Edge Cases
1. **Title Stripping**: `<title>` strings contain boilerplate wrappers like `"Top Secret Recipes version of ... - Printer Friendly Page"`. Extraction should isolate the product name (e.g. `"Kraft Thousand Island Dressing"` or `"IHOP Pancakes"`).
2. **Inline `<br>` Delimiters**: Ingredients and instructions are grouped inside single `<p><strong>` tags with `<br>` line breaks rather than `<ul><li>` lists.
3. **Intro vs Ingredient Blocks**: Both intro and ingredient blocks use `<p align="left"><strong>` or `<p align="left"><font size="3"><strong>`. Intro paragraphs can be distinguished because they do not start with quantities and do not have numbered steps.
4. **Bottom Metadata**: Trailing paragraphs contain links (`Back`, `http://www.topsecretrecipes.com`) and copyright statements which must not be parsed into ingredients or instructions.

## Acceptance Criteria
- [ ] `configs/topsecret.yaml` exists and conforms to the `HtmlRecipeSchema` schema
- [ ] Auto-detection identifies files in `/home/alex/junk/Recipes/Ingest/ToDo/HTML/Top Secret/`
- [ ] Sample 1 conversion succeeds:
  ```bash
  ./venv/bin/python3 convert.py '/home/alex/junk/Recipes/Ingest/ToDo/HTML/Top Secret/1000islepv.htm' --html-config configs/topsecret.yaml -o /tmp/test_ts_1000isle.json --no-nlp
  ```
  Produces valid JSON-LD with title containing `"Kraft Thousand Island Dressing"`, 8 ingredients, 2 instructions steps, and yield `"about 3/4 cup"`.
- [ ] Sample 2 conversion succeeds:
  ```bash
  ./venv/bin/python3 convert.py '/home/alex/junk/Recipes/Ingest/ToDo/HTML/Top Secret/IHOP1pv.htm' --html-config configs/topsecret.yaml -o /tmp/test_ts_ihop.json --no-nlp
  ```
  Produces valid JSON-LD with title containing `"Pancakes"`, ingredients, and 5 instruction steps.
- [ ] Sample 3 conversion succeeds:
  ```bash
  ./venv/bin/python3 convert.py '/home/alex/junk/Recipes/Ingest/ToDo/HTML/Top Secret/kfccrisppv.htm' --html-config configs/topsecret.yaml -o /tmp/test_ts_kfc.json --no-nlp
  ```
- [ ] All tests pass:
  ```bash
  ./venv/bin/python3 -m pytest tests/test_conversion.py tests/test_detection.py -v
  ```

## Deliverables
- `configs/topsecret.yaml`

## Reference
- [parsers/html_config.py](file:///home/alex/junk/Recipes/scripts/parsers/html_config.py) — YAML schema and field extractor
- [parsers/html_parser.py](file:///home/alex/junk/Recipes/scripts/parsers/html_parser.py) — HTML parser
- [configs/bbc.yaml](file:///home/alex/junk/Recipes/scripts/configs/bbc.yaml) — reference HTML config
