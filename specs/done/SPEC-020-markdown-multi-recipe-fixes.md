---
id: SPEC-020
title: "Markdown Multi-Recipe Parser and Detection Fixes"
tier: 1
type: parser
priority: P0
status: done
impact: "Fixes multi-recipe extraction for converted DOCX/MD collections (~370 recipes in salads, ~680 in LowCarb)"
deliverables:
  - parsers/compuchef.py
  - parsers/generic_md.py
  - tests/test_detection.py
---

# Spec: Markdown Multi-Recipe Parser and Detection Fixes

## Description

Address issues preventing multi-recipe Markdown documents (such as DOCX files converted via Pandoc to Markdown) from being properly detected and parsed:
1. `CompuChefParser.detect()` falsely matches `.md` files starting with bold-italic headers like `***Title***` due to an over-broad asterisk regex without format marker checks.
2. `GenericMdParser` fails to extract multiple recipes when delimited by bold text (`**Recipe Title**` / `***Recipe Title***`) without horizontal rules.
3. `GenericMdParser` only checks `#{1,2}` headings, ignoring `###` (H3) recipe boundaries in structured collections (e.g. `LowCarbohydrateCooking-Recipes.docx.md`).
4. `GenericMdParser` incorrectly parses Table of Contents / Index sections as recipes due to unanchored instruction verb regex matches (e.g. `bake` matching `Baked Chocolate`) and emitting recipes that contain no ingredients.

## Input Samples

### Sample 1: Bold-Delimited Recipes (`nux/Test/DOCX/salads.docx.md`)
```markdown
***The Ultimate Salad Recipe Collection***

**24-Hour Slaw**

3/4 cup sugar

1 lg. head cabbage \-- shredded/not chopped

2 lg red onions \-- thinly sliced

Hot Dressing \-- see below

Stir sugar into cabbage. Place half of the cabbage in a large bowl.
Cover with onion slices. Top with the remaining cabbage. Pour boiling
hot dressing over slowly. Do not stir. Cover and refrigerate at once.
Chill 24 hours. Stir well before serving.

HOT DRESSING

1 teaspoon celery seeds 1 1/2 teaspoons salt

Combine celery seeds, sugar, mustard, salt, and vinegar in saucepan.
Bring to a rolling boil. Add oil, stirring, and return to rolling boil.

**Adreana\'s Greek Pasta Salad**

1 pound rotini
...
```

### Sample 2: Heading-Hierarchical Recipes (`nux/Test/DOCX/LowCarbohydrateCooking-Recipes.docx.md`)
```markdown
**[RECIPE INDEX]{.underline}**

Chapter 1 - Appetizers 1-1
Lobster Salad in Endive from Amy Kanarios 1-1
...

# Appetizers

### Lobster Salad in Endive from Amy Kanarios

Makes 24 appetizers; serves 6 to 8

3/4 pound fresh cooked lobster meat, small-diced
1/2 cup good mayonnaise
1/2 cup small-diced celery (1 stalk)

Combine the lobster, mayonnaise, celery, capers, dill, salt, and pepper.
Arrange on a platter and serve.

### Olive Garden Hot Artichoke and Spinach Dip (adapted by Janis Ross)
...
```

## Expected Behavior

### Field Mapping
- **Title**: Cleaned text from markdown headings (`#`, `##`, `###`) or standalone bold lines (`**Title**`). Discard unescaped backslashes and markdown formatting.
- **Categories**: Set from higher-level chapter headings (e.g. `# Appetizers` sets `category = ["Appetizers"]` for recipes in that section).
- **Ingredients**: Identified by quantity/bullet starts or under ingredient headers. Recipes must contain at least one ingredient to be emitted.
- **Instructions**: Paragraphs following ingredients or instructions header.
- **Table of Contents / Index**: Ignored; sections with 0 ingredients are not emitted as recipes.

### Edge Cases
1. Book/Collection titles on line 1 before the first recipe with no ingredients or instructions must not be emitted as a separate recipe.
2. Tables of Contents / Indexes with entries containing words like "Baked" or "Cooked" must not be parsed as instruction steps.
3. Sub-recipe components (e.g. `#### Cocktail Sauce` inside `### Fresh Crab Cocktail`) should stay within the current recipe rather than splitting into separate recipes with missing metadata.

### Detection Contract

| Condition | Expected Score | Rationale |
|:---|:---|:---|
| Markdown file (`.md`) with recipe quantities / cooking verbs | `>= 0.60` | Detected by `GenericMdParser` |
| Markdown file (`.md`) tested against `CompuChefParser` | `== 0.0` | CompuChef must not claim markdown files |
| CompuChef file (`.ccf` or content with `Recipe Via Compu-Chef`) | `>= 0.75` | Genuine CompuChef files match CompuChef |

## Golden Output (Canonical JSON-LD)

```json
{
  "@context": "https://schema.org",
  "@type": "Recipe",
  "name": "24-Hour Slaw",
  "recipeIngredient": [
    {
      "@type": "PropertyValue",
      "name": "sugar",
      "value": 0.75,
      "unitText": "cup"
    },
    {
      "@type": "PropertyValue",
      "name": "cabbage -- shredded/not chopped",
      "value": 1.0,
      "unitText": "large head"
    }
  ],
  "recipeInstructions": [
    {
      "@type": "HowToStep",
      "position": 1,
      "text": "Stir sugar into cabbage. Place half of the cabbage in a large bowl. Cover with onion slices. Top with the remaining cabbage. Pour boiling hot dressing over slowly. Do not stir. Cover and refrigerate at once. Chill 24 hours. Stir well before serving."
    }
  ]
}
```

## Acceptance Criteria
- [x] `CompuChefParser.detect()` excludes `.md` / `.markdown` files and requires CompuChef markers before scoring >= 0.75
- [x] `GenericMdParser` parses bold-delimited multi-recipe files like `salads.docx.md` into individual recipes
- [x] `GenericMdParser` handles H3 recipe headings under H1/H2 chapters, setting categories from chapter headings
- [x] Table of Contents / Index blocks with 0 ingredients are skipped and not emitted as recipes
- [x] Word boundaries added to instruction verb prefixes in `_looks_like_instruction_start`
- [x] Full test suite passes: `./venv/bin/python3 -m pytest tests/ -v`

## Deliverables
- `parsers/compuchef.py`
- `parsers/generic_md.py`
- `tests/test_detection.py`
