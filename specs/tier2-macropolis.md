# Spec: Macropolis/TuttoCucina HTML Config
## Tier: 2
## Type: html-config
## Priority: P1
## Estimated file impact: 67 files

## Description

The `macropolis` directory contains 67 HTML files originally archived from TuttoCucina (`macropolis.org`), an Italian culinary website. While the outer page template, titles, and site chrome are in Italian (e.g. `Cucina Afghanistan`, `TuttoCucina`, `Il sito di ricette...`), the recipe content embedded within the table cells (`<td>`) consists of standard English MealMaster-formatted recipes with `<br>` line breaks.

Crucially, **each file contains multiple recipes**, demarcated by `<b>Title: [Name]</b><br>` or `Title: [Name]`.

The goal is to create `configs/macropolis.yaml` (and ensure the HTML parser supports multi-recipe extraction / splitting) so that all recipes in these collections are extracted into individual Schema.org JSON-LD recipe records.

## Input Samples

### Sample 1: `macropolis/afghan.htm`
**Location:** `/home/alex/junk/Recipes/Ingest/ToDo/HTML/macropolis/afghan.htm`

```html
<html><!-- #BeginTemplate "/Templates/allcook.dwt" -->
<head>
<title>TuttoCucina</title>
<meta http-equiv="Content-Type" content="text/html; charset=iso-8859-1">
<link rel="SHORTCUT ICON" href="http://www.macropolis.org/fav/magcas.ico">
<meta name="tuttocucina" content="Il sito di ricette, servizi e strumenti per cucinare">
<meta name="keywords" content="ricette dal mondo, freeware, servizi, strumenti">
<meta name="description" content="Il sito che ti aiuta a cucinare">
</head>

<body bgcolor="#FFFFFF" text="#000000">
...
        <tr> 
          <td valign="top" width="47%" height="12947"><font size="2"><b>Title: 
            Spicy Eggplant Salad (Bonjan) From Afghanistan</b><br>
            Categories: Indian, Afghan, Salads<br>
            Yield: 1 servings<br>
            <br>
            3 md Eggplants<br>
            1/4 ts Pepper<br>
            2 1/2 ts Coarse (kosher salt)<br>
            1 ts Hot red chili flakes, or<br>
            Minced fresh chiles <br>
            1/4 c Corn oil <br>
            2 ts Ground cinnamon<br>
            1 1/2 c Tomato sauce<br>
            1 tb Crushed dried mint<br>
            <br>
            Slice the eggplants crosswise into 1,5 inch thick pieces. Sprinkle<br>
            them with 2 tsp. coarse salt and let stand for 15 minutes. rinse<br>
            eggplants under cold water, which removes the bitter taste, rinse,<br>
            and dry well on a towel.<br>
            <br>
            Heat the oil in a skillet and lightly brown eggplant slices over<br>
            medium-high heat. Drain on paper towels.<br>
            ...<br>
            <br>
            <b>Title: Afghan Chicken</b><br>
            Categories: Middle east, Chicken...<br>
            Yield: 6 servings<br>
            <br>
            1    Broiler-fryer chicken; cut up<br>
            1 c  Plain lowfat yogurt<br>
            ...
```

### Sample 2: `macropolis/cajun.htm`
**Location:** `/home/alex/junk/Recipes/Ingest/ToDo/HTML/macropolis/cajun.htm`

```html
<td valign="top" width="47%"><font size="2"><b>Title: 
  Alligator Sauce Piquant</b><br>
  Categories: Cajun, Game, Meats<br>
  Yield: 6 servings<br>
  <br>
  2 lb Alligator meat; cut in 1" cubes<br>
  1/2 c  Vegetable oil<br>
  1/2 c  Flour<br>
  ...<br>
  Make a dark brown roux with the oil and flour...<br>
  <br>
  <b>Title: Andouille (Smoked Cajun Pork Sausage)</b><br>
  Categories: Cajun, Pork, Sausage<br>
  Yield: 5 pounds<br>
  ...
```

### Sample 3: `macropolis/maroc.htm`
**Location:** `/home/alex/junk/Recipes/Ingest/ToDo/HTML/macropolis/maroc.htm`

```html
<td valign="top" width="47%"><font size="2"><b>Title: 
  Couscous with Seven Vegetables</b><br>
  Categories: African, Moroccan, Vegetables<br>
  Yield: 6 servings<br>
  ...
```

## Expected Behavior

### YAML Layout Schema (`configs/macropolis.yaml`)

```yaml
# SPDX-License-Identifier: MIT
name: macropolis
description: "XPath and delimiter configuration for Macropolis TuttoCucina multi-recipe archives"
version: "1.0"

detection:
  path_pattern: ".*macropolis/.*\\.htm[l]?$"
  content_patterns:
    - "TuttoCucina"
    - "macropolis.org"

recipe_delimiter: "<b>Title:"

fields:
  title:
    xpath: "//b[contains(., 'Title:')]/text()"
  categories:
    xpath: "//text()[contains(., 'Categories:')]"
    split_delimiter: ","
  yield_amount:
    xpath: "//text()[contains(., 'Yield:')]"
  body:
    xpath: "//td[@valign='top']"
```

### Field Mapping & Multi-Recipe Processing
- **Recipe Splitting**: Delimited by `<b>Title:` (or `Title:`). Each section represents one discrete recipe.
- **Title**: Extracted from the `Title:` header line. Strip leading `"Title:"` label and clean whitespace.
- **Categories**: Extracted from the `Categories:` line; comma-separated list of category tags.
- **Yield**: Extracted from `Yield: N servings` or `Yield: N pounds`.
- **Ingredients**: Extracted from lines matching MealMaster quantities and unit formats (e.g. `3 md Eggplants`, `1/4 ts Pepper`, `1 tb Crushed dried mint`).
- **Instructions**: Paragraphs following the ingredient list up to the next `Title:` header.

### Edge Cases
1. **Multi-Recipe Files**: A single HTML file can contain 20 to 50+ recipes in one large table cell. The parser must yield every recipe rather than terminating on the first one.
2. **HTML `<br>` Line Breaks**: Content is not stored as plain text newlines, but as HTML `<br>` separated text nodes inside table cells.
3. **MealMaster Unit Normalization**: Ingredients use standard MealMaster unit shorthand (`ts` -> teaspoon, `tb` -> tablespoon, `c` -> cup, `md` -> medium, `lg` -> large, `ea` -> each, `pk` -> package). Normalization must be handled by `parsers/units.py`.
4. **Italian Chrome vs English Content**: Ignore the outer navigation bar, Italian metadata (`Cucina Afghanistan`), and header banners.

## Acceptance Criteria
- [ ] `configs/macropolis.yaml` exists and conforms to the layout schema
- [ ] Multi-recipe extraction from `macropolis/afghan.htm` yields at least 2 recipes (and ideally all 7+ recipes):
  ```bash
  ./venv/bin/python3 convert.py '/home/alex/junk/Recipes/Ingest/ToDo/HTML/macropolis/afghan.htm' --html-config configs/macropolis.yaml -o /tmp/test_macro_afghan.json --no-nlp
  ```
- [ ] Multi-recipe extraction from `macropolis/maroc.htm` succeeds:
  ```bash
  ./venv/bin/python3 convert.py '/home/alex/junk/Recipes/Ingest/ToDo/HTML/macropolis/maroc.htm' --html-config configs/macropolis.yaml -o /tmp/test_macro_maroc.json --no-nlp
  ```
- [ ] Multi-recipe extraction from `macropolis/cajun.htm` succeeds:
  ```bash
  ./venv/bin/python3 convert.py '/home/alex/junk/Recipes/Ingest/ToDo/HTML/macropolis/cajun.htm' --html-config configs/macropolis.yaml -o /tmp/test_macro_cajun.json --no-nlp
  ```
- [ ] Output recipes have populated `title`, `categories`, `yield_amount`, structured `ingredients`, and `instructions`.
- [ ] Regression and detection test suites pass:
  ```bash
  ./venv/bin/python3 -m pytest tests/test_conversion.py tests/test_detection.py -v
  ```

## Deliverables
- `configs/macropolis.yaml`

## Reference
- [parsers/html_config.py](file:///home/alex/junk/Recipes/scripts/parsers/html_config.py) — HTML YAML schema registry
- [parsers/html_parser.py](file:///home/alex/junk/Recipes/scripts/parsers/html_parser.py) — HTML parser implementation
- [parsers/mealmaster.py](file:///home/alex/junk/Recipes/scripts/parsers/mealmaster.py) — MealMaster format parsing logic
- [parsers/units.py](file:///home/alex/junk/Recipes/scripts/parsers/units.py) — unit normalization mapping
