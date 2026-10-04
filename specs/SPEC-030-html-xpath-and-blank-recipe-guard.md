---
id: SPEC-030
title: "HTML XPath Schema Refinements and Blank Recipe Guard"
tier: 1
type: html-config
priority: P0
status: active
impact: "Fixes 293 empty recipes (0 ing, 0 inst) and ~1,926 zero-ingredient HTML recipes in Ingest/ToDo/HTML"
deliverables:
  - parsers/html_parser.py
  - configs/bbq.yaml
  - configs/cscmu.yaml
  - tests/samples/bbq_netrelief_sample.shtml
  - tests/expected/bbq_netrelief_sample.shtml.json
  - tests/unit/test_html_guard.py
---

# Spec: HTML XPath Schema Refinements and Blank Recipe Guard

## Description

During large-scale batch conversion of `Ingest/ToDo/HTML`, 293 recipes were emitted with completely empty bodies (0 ingredients and 0 instructions), and an additional 1,926 recipes were emitted with zero ingredients.

Investigation revealed two root causes:
1. **Overly Restrictive XPath in `configs/bbq.yaml`**: The XPath requires `//table//...` (e.g. `//table//p[b and not(contains(b, 'Recipe By'))]/b//text()`). Many netRelief and BBQ recipes (e.g. `artichoke_dip_appetizer_recipe.shtml`) do not use `<table>` layouts, but rather `<blockquote><p><b>...</b></p></blockquote>`. As a result, title extraction matched (`//title/text()`), but ingredients and instructions completely failed to extract.
2. **Missing Quality Guard in `HtmlParser`**: `HtmlParser.parse_content` yielded any recipe where `recipe.title or recipe.ingredients` was truthy. Because almost all HTML pages have a `<title>`, index pages and pages where XPath failed to extract ingredients/steps were yielded as valid recipes with 0 ingredients and 0 instructions, preventing fallback to subsequent candidate schemas or generic fallback.

## Input Samples

### Sample 1: `Ingest/ToDo/HTML/netrelief/artichoke_dip_appetizer_recipe.shtml`

```html
<html>
<head>
<title> Artichoke Dip Appetizer </title>
</head>
<body bgcolor="#FFFFFF" text="#000000">
<p align="center"><font size="5"><b>Artichoke Dip Appetizer </b></font></p>
<hr size="8">
<blockquote>
  <p>I downloaded this recipe off the internet years ago and I have made it numerous times.</p>
  <p><i>Garry</i> </p>
  <p><b>Recipe By : </b>jbilos@labs-n.bbn.com (John Bilos)<br>
  <b>Serving Size : </b>10 </p>
  <p><b>8 ounces cream cheese<br>
  12 ounces mozzarella cheese -- shredded<br>
  1 cup mayonnaise<br>
  1 cup grated parmesan cheese<br>
  2 jars (6 oz. each) artichoke hearts -- drained and chopped<br>
  1 can (4 oz.) chopped green chilies -- drained<br>
  1 dash garlic powder</b></p>
  <p>Preheat oven to 350. Mix all ingredients together. Bake for 30 minutes in a 9 x 13 baking dish.</p>
</blockquote>
</body>
</html>
```

## Expected Behavior

### Field Mapping
- **Title**: `<font size="5"><b>...</b></font>` or `<title>` (`Artichoke Dip Appetizer`)
- **Yield**: Serving Size / Makes field (`10`)
- **Ingredients**: Extracted from both `//table//p[b]/b//text()` and `//blockquote//p[b]/b//text()` or `//p[b]/b//text()`
- **Instructions**: Extracted from paragraphs following ingredients (`Preheat oven to 350...`)

### Recipe Guard in `HtmlParser`
- A recipe extracted by an XPath schema must have at least one ingredient OR non-empty instructions.
- If an XPath schema only extracts a title (0 ingredients and 0 instructions), do NOT yield it. Treat it as a schema mismatch and allow subsequent candidate schemas or fallbacks to evaluate.

## Detection Contract

| Condition | Expected Score | Rationale |
|:---|:---|:---|
| Path contains `bbq` or `netrelief` + content has `bbq.netrelief.com` or `Garry's Home Cookin'` | `>= 0.90` | Definitive netRelief BBQ layout |
| HTML file with only title and no ingredients/instructions | Yields 0 recipes (skips or falls back) | Blank recipe guard |

## Acceptance Criteria
- [ ] `configs/bbq.yaml` updated to extract ingredients and instructions from `<blockquote>` and tableless layouts
- [ ] `parsers/html_parser.py` updated with a guard rejecting recipes that have 0 ingredients and 0 instructions
- [ ] Sample test fixture `tests/samples/bbq_netrelief_sample.shtml` added with expected JSON output
- [ ] Unit tests in `tests/unit/test_html_guard.py` verifying empty title-only HTML pages do not yield blank recipes
- [ ] Full test suite passes: `./venv/bin/python3 -m pytest tests/ -v`
