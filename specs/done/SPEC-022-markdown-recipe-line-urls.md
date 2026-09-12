---
id: SPEC-022
title: "Markdown Recipe Line Number URL Fragments"
tier: 1
type: parser
priority: P1
status: done
impact: "Enables precise deep-linking into Markdown recipe documents by tagging URL with the extraction start line number (#<line>)"
deliverables:
  - parsers/generic_md.py
  - parsers/ricette_md.py
  - tests/expected/generic_md_recipe.md.json
  - tests/expected/generic_md_multi.md.json
  - tests/expected/ricette_sample.md.json
  - tests/unit/test_markdown_url.py
---

# Spec: Markdown Recipe Line Number URL Fragments

## Description

In large recipe collections converted from Markdown documents (such as DOCX books converted to `.md` containing dozens or hundreds of recipes per file), identifying the exact location of a specific recipe within the source document is difficult when only the bare file path is stored.

Currently:
- `parsers/mealmaster.py` appends `#{start_line}` to `recipe.url` (e.g., `file://tests/samples/mealmaster_dual.mmf#1`).
- `parsers/cookware.py` appends `#{row_number}` to `recipe.url`.
- `parsers/mixed.py` appends `#{line_number}` to `recipe.url`.
- However, Markdown parsers (`GenericMdParser` and `RicetteMdParser`) do not populate `recipe.url` during extraction, causing `parsers/base.py` to fall back to the bare file URI: `file://{filepath}` without any fragment anchor.

This specification introduces start-line tracking to Markdown parsers so that every extracted recipe URL includes a `#<line_number>` fragment indicating the 1-indexed line in the source `.md` file where extraction began (e.g. `"url": "file:///path/to/input.md#134"`).

## Input Samples

### Sample 1: Multi-Recipe Markdown (`tests/samples/generic_md_multi.md`)

```markdown
1: **Chocolate Fudge Brownies**
2: 
3: Delish chocolate brownies!
4: 
5: **Ingredients:**
...
19: ----------------------------------------
20: 
21: **Simple Garlic Bread**
22: 
23: Great side for pasta!
...
```

- **Recipe 1 ("Chocolate Fudge Brownies")**: Extraction begins at line 1.
  - Expected URL: `file:///path/to/generic_md_multi.md#1`
- **Recipe 2 ("Simple Garlic Bread")**: Extraction begins at title line 21.
  - Expected URL: `file:///path/to/generic_md_multi.md#21`

### Sample 2: Italian Markdown (`tests/samples/ricette_sample.md`)

```markdown
...
15: 
16: # Alette Di Pollo Ripiene Fritte \(2\)
17: 
18: Ricetta di pollo a base di pollo
...
49: 
50: # Ali Di Pollo Alla Cinese
51: 
52: Ricetta di pollo a base di pollo 
...
```

- **Recipe 1 ("Alette Di Pollo Ripiene Fritte (2)")**: Header line starts at line 16.
  - Expected URL: `file:///path/to/ricette_sample.md#16`
- **Recipe 2 ("Ali Di Pollo Alla Cinese")**: Header line starts at line 50.
  - Expected URL: `file:///path/to/ricette_sample.md#50`

## Expected Behavior

### 1. `GenericMdParser` (`parsers/generic_md.py`)

- Maintain original 1-indexed line numbers during line scanning and table unrolling.
- When `start_new_recipe()` is triggered (by a heading `#`, bold title `**Title**`, or separator boundary), record `start_line` corresponding to the original file line number of the title / start boundary.
- When emitting or flushing the `Recipe`:
  ```python
  if filepath:
      recipe.url = f"file://{filepath}#{start_line}"
  ```
- If `filepath` is empty, leave `recipe.url` as `None`.

### 2. `RicetteMdParser` (`parsers/ricette_md.py`)

- Calculate the 1-indexed start line of each `# <Title>` section in `content` by counting preceding newlines:
  ```python
  start_line = content[:match.start()].count('\n') + 1
  ```
- Assign `recipe.url`:
  ```python
  if filepath:
      recipe.url = f"file://{filepath}#{start_line}"
  ```

### 3. URL Format Consistency

- Format: `file://{filepath}#{start_line}`.
- For absolute paths (such as `/example/path/recipe.md`), string formatting produces `file:///example/path/recipe.md#134`.
- For relative paths (such as `tests/samples/generic_md_recipe.md`), string formatting produces `file://tests/samples/generic_md_recipe.md#1`.
- This matches the convention in `parsers/mealmaster.py` and `parsers/mixed.py`.

### Edge Cases

1. **In-memory content (empty `filepath`)**: When `filepath=""`, `recipe.url` should not produce `file://#<line>`. It should either remain `None` or not crash.
2. **Preamble and blank lines**: If a file begins with blank lines, metadata, or Pandoc format tags (`[format: generic_md]`), `start_line` must point to the actual recipe title line, not line 1.
3. **Multi-recipe files with separators**: In files where recipes are separated by `---` or `===`, `start_line` corresponds to the recipe title line immediately following the separator.
4. **Unrolled grid tables**: If markdown tables are unrolled into linear text, the line numbers of subsequent recipes must remain anchored to the original source line positions.

## Detection Contract

| Condition | Expected Score | Rationale |
|:---|:---|:---|
| Path `.md` + Italian keywords (`## Ingredienti`, `## Ricetta`) | `>= 0.85` | `RicetteMdParser` match |
| Path `.md` + quantities & cooking terms | `>= 0.75` | `GenericMdParser` match |
| Non-matching format or generic text | `== 0.0` | Negative assertion (no collision) |

## Golden Output (Canonical JSON-LD)

```json
{
  "@context": "https://schema.org",
  "@type": "Recipe",
  "name": "Simple Garlic Bread",
  "recipeIngredient": [
    {
      "@type": "PropertyValue",
      "name": "French bread",
      "value": 1,
      "unitText": "loaf"
    },
    {
      "@type": "PropertyValue",
      "name": "butter",
      "value": 4,
      "unitText": "tablespoon"
    },
    {
      "@type": "PropertyValue",
      "name": "garlic, minced",
      "value": 2,
      "unitText": "clove"
    }
  ],
  "recipeInstructions": [
    {
      "@type": "HowToStep",
      "position": 1,
      "text": "Slice bread in half."
    },
    {
      "@type": "HowToStep",
      "position": 2,
      "text": "Spread garlic butter over bread."
    },
    {
      "@type": "HowToStep",
      "position": 3,
      "text": "Broil for 5 minutes until golden."
    }
  ],
  "comment": "Imported from tests/samples/generic_md_multi.md",
  "url": "file:///path/to/input.md#21",
  "description": "Recipe converted from Generic Markdown format"
}
```

## Worktree & Branch Protocol

Following repository golden rules:
```bash
git worktree add -b feat/spec-022-md-line-urls .worktrees/spec-022 main
cd .worktrees/spec-022
```
After implementation and verification:
```bash
./venv/bin/python3 -m pytest tests/ -v
git add <files>
git commit -m "feat(parser): add start line number fragment to markdown recipe urls"
git checkout main
git merge --ff-only feat/spec-022-md-line-urls
git worktree remove .worktrees/spec-022
git branch -d feat/spec-022-md-line-urls
```

## Acceptance Criteria

- [x] `GenericMdParser` sets `recipe.url = f"file://{filepath}#{start_line}"` with 1-indexed source line numbers.
- [x] `RicetteMdParser` sets `recipe.url = f"file://{filepath}#{start_line}"` with 1-indexed source line numbers.
- [x] Multi-recipe markdown files correctly assign distinct `#<line>` numbers to each recipe.
- [x] Unit tests in `tests/unit/test_markdown_url.py` verify line number extraction across headings, bold titles, and Italian markdown.
- [x] Expected fixture outputs for `tests/expected/generic_md_recipe.md.json`, `tests/expected/generic_md_multi.md.json`, and `tests/expected/ricette_sample.md.json` are regenerated and match with line numbers.
- [x] Full test suite passes: `./venv/bin/python3 -m pytest tests/ -v`.

## Deliverables

- `parsers/generic_md.py`
- `parsers/ricette_md.py`
- `tests/expected/generic_md_recipe.md.json`
- `tests/expected/generic_md_multi.md.json`
- `tests/expected/ricette_sample.md.json`
- `tests/unit/test_markdown_url.py`
