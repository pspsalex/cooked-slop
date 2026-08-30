---
id: SPEC-005
title: "McNalley Recipe Collection"
tier: 2
type: html-config
priority: P1
status: done
impact: "TBD"
deliverables: []
---

# Spec: McNalley Recipe Archive HTML Config
## Tier: 2
## Type: html-config
## Priority: P2
## Estimated file impact: 34 files

## Description

Extract recipes from Mike McNalley's archived personal recipe collection located at `/home/alex/junk/Recipes/Ingest/ToDo/HTML/mcnalley/`.

The collection comprises 34 files across two distinct subdirectories with different HTML/CSS layouts:
1. **`Archives/`** (27 files, `.htm`): Classic 1990s table-based HTML layout with CSS styling (`Rally.css`) featuring custom CSS classes such as `recipeTitle`, `RecipeHead`, `RecipeIngred`, and `RecipeTxt`. Contains structured ingredient tables (often 2 columns) and yield info.
2. **`MomsRecipes/`** (7 files, `.html`): Handwritten family recipe transcripts styled with `Mom.css` using classes `ScripttextRed`, `Scripttext`, and `BlueText`.

The deliverable is YAML XPath configuration file(s) for the `HtmlParser` subsystem to extract standard Schema.org JSON-LD recipes from both subdirectories.

## Input Samples

### Sample 1: `mcnalley/Archives/albondigas.htm`
Path: `/home/alex/junk/Recipes/Ingest/ToDo/HTML/mcnalley/Archives/albondigas.htm`

```html
<!DOCTYPE HTML PUBLIC "-//W3C//DTD HTML 4.01 Transitional//EN">
<html>
<head>
<meta http-equiv="Content-Type" content="text/html; charset=iso-8859-10">
<meta name="resource-type" content="document">
<title>Albondigas - Meatball Soup</title>
<link rel="stylesheet" href="../Rally.css" type="text/css">
</head>
<body >
<table border="0" width="761">
  <tr> 
    <td height="28" valign="top"><img src="../images/RallyRecipe.gif" width="351" height="42" usemap="../index.htm#Map" border="0" alt=""> 
      <hr width="250" noshade size="1" align="left">
    </td>
    <td height="28" valign="top" class="recipeTitleCopy">While you're here, check 
      out my featured recipe <a href="../archive.html">Archive</a>, or my recipe 
      database on my <a href="../recipes.htm">Recipes</a> page.</td>
  </tr>
  <tr> 
    <td width="390" height="28" valign="top"><font color="#FF0000" face="Arial"><big><strong class="recipeTitle">ALBONDIGAS 
      (Meatball Soup)</strong></big></font></td>
    <td width="361" valign="top" height="28"> 
      <p align="left"><font face="Arial" color="#0000FF"><strong><span class="RecipeHead">SERVES 
        &nbsp; 10</span></strong></font> 
    </td>
  </tr>
</table>
<table border="0" width="100%">
  <tr> 
    <td width="100%"><font color="#0000FF" face="Arial, Helvetica, sans-serif"><b class="RecipeHead">Broth</b></font></td>
  </tr>
</table>
<table border="0" width="761">
  <tr> 
    <td valign="top" height="19" width="346" class="RecipeIngred"><b>1 ea Onion, 
      minced</b></td>
    <td width="405" height="19" class="RecipeIngred"><b>1 Clove Garlic, minced</b></td>
  </tr>
  <tr> 
    <td height="21" width="346" class="RecipeIngred"><b>1/4 c Oil</b></td>
    <td width="405" class="RecipeIngred"><b>1 Can Tomato Sauce</b></td>
  </tr>
  <tr> 
    <td height="21" width="346" class="RecipeIngred"><b>3 qt Beef Stock</b></td>
    <td width="405" class="RecipeIngred"><b>1 Sprig of Cilantro or Mint</b></td>
  </tr>
...
  <tr> 
    <td colspan="2" valign="top" height="203"> 
      <p><span class="RecipeTxt">Mix meat with the rest of the meatball ingredients. 
        Shape into small meatballs. Fry minced onion and garlic in oil in a large pot...</span>
```

### Sample 2: `mcnalley/MomsRecipes/CandiedSweetPotatoes.html`
Path: `/home/alex/junk/Recipes/Ingest/ToDo/HTML/mcnalley/MomsRecipes/CandiedSweetPotatoes.html`

```html
<html>
<head>
<title>CandiedSweetPotatoes</title>
<meta http-equiv="Content-Type" content="text/html; charset=iso-8859-1">
<link rel="stylesheet" href="../Rally.css" type="text/css">
<link rel="stylesheet" href="../Mom.css" type="text/css">
</head>
<body bgcolor="#FFFFFF" text="#000000" >
<table width="67%" border="0" background="../images/greengraph.gif" cellpadding="10">
  <tr> 
    <td class="RecipeHead" valign="top" height="24" width="78%"><span class="ScripttextRed"> 
      Candied Sweet Potatoes</span><br>
    </td>
    <td class="RecipeHead" valign="top" height="24" width="22%">
      <div align="right"><a href="MomsIndex.html" onClick="history.go(-1)" class="Scripttext"><font face="Marita Medium - HMK, Marita Script - HMK">Back</font></a></div>
    </td>
  </tr>
  <tr> 
    <td class="Scripttext" valign="top" height="45" colspan="2"> 
      <p>6 Medium Sweet Potatoes, boiled &amp; peeled<br>
        1 Cup Brown Sugar<br>
        1/2 Cup Melted Butter</p>
    </td>
  </tr>
  <tr> 
    <td class="BlueText" height="613" valign="top" colspan="2"> 
      <p class="Scripttext">Cut potatoes in half. Put in pan and sprinkle with 
        sugar and butter.<br>
        Bake 'till nice and brown.</p>
      <p><br>
        <span class="Scripttext">I found this in my Mom's old handwritten recipe 
        book. All o f these recipes assume a good understanding of baking techniques 
        because they mostly don't give any baking times or temps.</span></p>
      <p class="Scripttext">Copyright &copy; 2018 Mike McNalley</p>
    </td>
  </tr>
</table>
</body>
</html>
```

## Expected Behavior

### Layout 1: `Archives/` Subdirectory
- **Detection**:
  - `path_pattern`: `.*mcnalley/Archives/.*\.htm$`
  - `content_patterns`: `["recipeTitle", "RecipeIngred"]`
- **Field Mappings**:
  - `title`: `//*[@class='recipeTitle']/text() | //strong[contains(@class, 'recipeTitle')]/text()`
  - `yield_amount`: `//span[contains(@class, 'RecipeHead') and contains(text(), 'SERVES')]/text() | //*[contains(text(), 'SERVES')]/text()`
  - `ingredients`: `//td[contains(@class, 'RecipeIngred')]`
  - `instructions`: `//span[contains(@class, 'RecipeTxt')]/text() | //td[.//span[contains(@class, 'RecipeTxt')]]//p/text()`

### Layout 2: `MomsRecipes/` Subdirectory
- **Detection**:
  - `path_pattern`: `.*mcnalley/MomsRecipes/.*\.html$`
  - `content_patterns`: `["ScripttextRed", "Mom.css"]`
- **Field Mappings**:
  - `title`: `//span[contains(@class, 'ScripttextRed')]/text()`
  - `ingredients`: `//td[contains(@class, 'Scripttext') and not(contains(@class, 'BlueText'))]//p/text() | //td[contains(@class, 'Scripttext') and not(contains(@class, 'BlueText'))]/text()`
  - `instructions`: `//td[contains(@class, 'BlueText')]//p[contains(@class, 'Scripttext')][1]/text()`

### Configuration Structure Example
To copy the structure from existing configs like `configs/bbc.yaml`:

```yaml
# SPDX-License-Identifier: MIT
name: mcnalley_archives
description: "XPath configuration for McNalley Recipe Archive"
version: "1.0"

detection:
  path_pattern: ".*mcnalley/Archives/.*\\.htm$"
  content_patterns:
    - "recipeTitle"
    - "RecipeIngred"

fields:
  title:
    xpath: "//*[@class='recipeTitle']/text() | //strong[contains(@class, 'recipeTitle')]/text()"
  yield_amount:
    xpath: "//span[contains(@class, 'RecipeHead') and contains(text(), 'SERVES')]/text() | //*[contains(text(), 'SERVES')]/text()"
  ingredients:
    xpath: "//td[contains(@class, 'RecipeIngred')]"
  instructions:
    xpath: "//span[contains(@class, 'RecipeTxt')]"
```

### Edge Cases
1. **Two different layouts in one archive**: Either provide two targeted configs (`configs/mcnalley_archives.yaml` and `configs/mcnalley_moms.yaml`) or a unified `configs/mcnalley.yaml` with XPath union selectors (`|`) that match both variants.
2. **Two-column ingredient tables**: `Archives/` uses `<tr><td class="RecipeIngred">...</td><td class="RecipeIngred">...</td></tr>`. XPath `//td[contains(@class, 'RecipeIngred')]` retrieves all ingredient cells in DOM document order.
3. **Section headers in `Archives/`**: Intermediate headings like "Broth" and "Albondigas" are marked with `<b class="RecipeHead">Broth</b>`. Ensure ingredient XPath does not inadvertently select `RecipeHead` elements.
4. **Multline `<br>`-separated ingredients in `MomsRecipes/`**: Ingredients are often in a single `<p>` separated by `<br>`. If using lxml, check whether line breaks need splitting or if separate text nodes are extracted.
5. **Footer noise in `Archives/`**: Text such as "Please acknowledge www.mcnalley.com..." and MealMaster download links (`<a href="../zips/albondig.zip">Download</a>`) appear in `<p>` blocks near instructions. XPath should isolate recipe steps.
6. **Single recipe per file**: Each `.htm` or `.html` file contains exactly one recipe.

## Acceptance Criteria
- [ ] Config file(s) created in `configs/` adhering to `HtmlRecipeSchema` in `parsers/html_config.py`.
- [ ] Extract recipe from sample `mcnalley/Archives/albondigas.htm` with title "ALBONDIGAS (Meatball Soup)", yield "SERVES   10", 11 ingredients, and instructions.
- [ ] Extract recipe from sample `mcnalley/MomsRecipes/CandiedSweetPotatoes.html` with title "Candied Sweet Potatoes", ingredients, and instructions.
- [ ] Sample test files added to `tests/samples/` and expected JSON-LD files generated in `tests/expected/` using `--no-nlp`.
- [ ] Test command succeeds:
  ```bash
  ./venv/bin/python3 convert.py tests/samples/mcnalley_albondigas.htm -o tests/expected/mcnalley_albondigas.htm.json --no-nlp
  ./venv/bin/python3 convert.py tests/samples/mcnalley_candied_sweet_potatoes.html -o tests/expected/mcnalley_candied_sweet_potatoes.html.json --no-nlp
  ./venv/bin/python3 -m pytest tests/ -v
  ```
- [ ] All 34 files in `/home/alex/junk/Recipes/Ingest/ToDo/HTML/mcnalley/` parse without unhandled exceptions.

## Deliverables
- `/home/alex/junk/Recipes/scripts/configs/mcnalley.yaml` (or `configs/mcnalley_archives.yaml` and `configs/mcnalley_moms.yaml`)
- `/home/alex/junk/Recipes/scripts/tests/samples/mcnalley_albondigas.htm`
- `/home/alex/junk/Recipes/scripts/tests/expected/mcnalley_albondigas.htm.json`
- `/home/alex/junk/Recipes/scripts/tests/samples/mcnalley_candied_sweet_potatoes.html`
- `/home/alex/junk/Recipes/scripts/tests/expected/mcnalley_candied_sweet_potatoes.html.json`

## Reference
- [configs/bbc.yaml](file:///home/alex/junk/Recipes/scripts/configs/bbc.yaml) — reference HTML YAML configuration
- [parsers/html_config.py](file:///home/alex/junk/Recipes/scripts/parsers/html_config.py) — `HtmlRecipeSchema`, `FieldConfig`, `HtmlDetectionConfig`
- [parsers/html_parser.py](file:///home/alex/junk/Recipes/scripts/parsers/html_parser.py) — `HtmlParser` class
- [AGENTS.md](file:///home/alex/junk/Recipes/scripts/AGENTS.md) — project conventions and testing standards
