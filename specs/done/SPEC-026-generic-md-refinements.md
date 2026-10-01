---
id: SPEC-026
title: "Generic Markdown Parser Refinements"
tier: 1
type: parser
priority: P0
status: done
impact: "~180 missed DOCX files; unlocks 550 CROCKPOT RECIPES (+549 recipes)"
deliverables:
  - parsers/generic_md.py
  - tests/samples/generic_md_edge_cases.md
  - tests/expected/generic_md_edge_cases.md.json
  - tests/unit/test_generic_md_edge_cases.py
---

# Spec: Generic Markdown Parser Refinements

## Description

Refine `GenericMdParser` in [parsers/generic_md.py](parsers/generic_md.py) to resolve key failure modes observed during batch conversion of Word/DOCX documents converted to Markdown via Pandoc.

These failure modes currently cause ~186 converted files in `Ingest/ToDo/DOCX/` to yield 0 recipes, and cause `550 CROCKPOT RECIPES.docx.md` (22,000 lines) to collapse into a single truncated recipe rather than extracting 550 distinct recipes.

## Identified Failure Modes & Edge Cases

1. **Pandoc Escaped List Numbering (`1\.`, `2\.`)**:
   - Pandoc escapes periods after numbers in Markdown output (e.g. `1\. cup peanut butter`, `2\. 1/2 cup sugar`).
   - `_looks_like_qty_or_ing()` only matches `\d+[.)]`, failing on `\d+\\?[.)]`.
2. **All-Bold Recipe Documents**:
   - In Word documents where the entire text was bolded (`**Title**`, `**1 lb ground beef**`, `**Cook until done.**`), `is_bold_title` flags the first line as a title candidate, but because `nxt_line` is also bold, `nxt_is_bold` prevents `is_recipe_boundary` from triggering.
   - Fix: Check if line matches `_looks_like_qty_or_ing()` before considering it a title candidate, and allow bold boundaries when the previous bold block was an ingredient or instruction.
3. **Multi-Recipe Tilde Delimiters (`\~\~\~...` / `~~~~...`) and Plain Numbered Titles**:
   - Compilations like `550 CROCKPOT RECIPES.docx.md` separate recipes with `\~\~\~\~\~\~\~\~\~\~\~\~\~\~\~\~\~\~\~\~\~\~\~\~\~\~\~\~\~\~\~\~\~\~\~\~\~\~\~\~\~\~\~\~\~\~\~\~\~\~\~\~\~\~` and label titles with plain numbers without `#` or `**` (e.g. `1\. ALDILLA`, `2\. ALL DAY BEEF`).
   - Fix: Expand `is_dash_sep` to detect `(?:\\?~){12,}`. Recognize plain numbered titles immediately following separators as recipe titles.
4. **Pandoc Markdown Blockquotes (`> `)**:
   - Recipes indented with `> ` (e.g. `CRAB NOODLES.docx.md`, `CHICKEN TORTILLA CASSEROLE.docx.md`).
   - Fix: In `_clean_line()`, strip leading `>\s*` along with other bullet markers so ingredient quantities and instruction text are detected cleanly.
5. **Image Tags in Heading Titles**:
   - Headings with Pandoc image embeds (e.g. `# ![](media/image1.png){width="1.6in"} Eggplant Timbale`).
   - Fix: In `_clean_title()`, strip Markdown/Pandoc image syntax `!\[.*?\](?:\(.*?\))?(?:\{.*?\})?`.
6. **Hyphenated Cooking Verbs**:
   - Words like `Pre-heat` or `pre-heating`.
   - Fix: Expand instruction regex to match `pre-?heat\b`.

## Input Samples

### Sample 1: Pandoc Numbering & Hyphenated Verb (`1-2-3 Peanut Butter Cookies.docx.md`)
```markdown
**1-2-3 Peanut Butter Cookies**

1\. cup peanut butter

2\. 1/2 cup sugar

3\. 1 large or 2 small. egg/s  

Pre-heat oven to 325 degrees. Mix egg and sugar until creamy Add peanut
butter to the mix and mix well Drop dough by teaspoon on to the
non-stick or greased cookie sheet. Dip fork in water and criss-cross to
flatten the cookies Bake for 12 minutes.
```

### Sample 2: All-Bold Formatting (`Beef Stroganoff2.docx.md`)
```markdown
**Beef Stroganoff**

**1 lb. ground beef**

**1 onion (size does not matter but not too small)**

**1 cup sliced mushrooms (optional)**

**1 can Campbells Cream of Chicken Soup**

**1/2 cup sour cream**

**Egg Noodles**

**Cook ground beef and onion. Add soup and mushrooms.**

**Heat through. Add sour cream. Salt and pepper to taste.**

**Serve over cooked egg noodles.**

Yummy!
```

### Sample 3: Tilde Delimiters & Plain Numbered Titles (`550 CROCKPOT RECIPES.docx.md`)
```markdown
\~\~\~\~\~\~\~\~\~\~\~\~\~\~\~\~\~\~\~\~\~\~\~\~\~\~\~\~\~\~\~\~\~\~\~\~\~\~\~\~\~\~\~\~\~\~\~\~\~\~\~\~\~\~

1\. ALDILLA

1 large onion \-- chopped

1 1/2 pound flank steak

Score steak and rub with chili powder; coat with flour. Cook on low for 8 hours.

\~\~\~\~\~\~\~\~\~\~\~\~\~\~\~\~\~\~\~\~\~\~\~\~\~\~\~\~\~\~\~\~\~\~\~\~\~\~\~\~\~\~\~\~\~\~\~\~\~\~\~\~\~\~

2\. ALL DAY BEEF

1 1/2 lb. Beef roast \-- \*any cut desired

1/2 tsp. Black pepper

Brown meat and cook in slow cooker for 8 hours.
```

## Detection Contract

Detection behavior remains consistent with existing `GenericMdParser.detect()`:

| Condition | Expected Score | Rationale |
|:---|:---|:---|
| File has `.md` or `.markdown` extension with ingredients/instructions | `>= 0.85` | Definitive markdown recipe match |
| Markdown content without explicit headers but with quantities & instructions | `>= 0.50` | Fallback markdown matching |
| Non-markdown extensions or plain text files | `<= 0.10` | Prevents false positives over other formats |

## Golden Output (Canonical JSON-LD for Sample 1)

```json
[
  {
    "@context": "https://schema.org",
    "@type": "Recipe",
    "name": "1-2-3 Peanut Butter Cookies",
    "recipeIngredient": [
      {
        "@type": "PropertyValue",
        "name": "peanut butter",
        "unitText": "cup",
        "value": 1.0
      },
      {
        "@type": "PropertyValue",
        "name": "sugar",
        "unitText": "cup",
        "value": 0.5
      },
      {
        "@type": "PropertyValue",
        "name": "egg/s",
        "value": 1.0
      }
    ],
    "recipeInstructions": [
      {
        "@type": "HowToStep",
        "position": 1,
        "text": "Pre-heat oven to 325 degrees. Mix egg and sugar until creamy Add peanut butter to the mix and mix well Drop dough by teaspoon on to the non-stick or greased cookie sheet. Dip fork in water and criss-cross to flatten the cookies Bake for 12 minutes."
      }
    ]
  }
]
```

## Acceptance Criteria
- [ ] Escaped numbering `\d+\\?[.)]` matches `_looks_like_qty_or_ing()`
- [ ] Leading blockquote markers `>\s*` stripped from lines in `_clean_line()`
- [ ] Pandoc image syntax `!\[.*?\](?:\(.*?\))?(?:\{.*?\})?` stripped from titles in `_clean_title()`
- [ ] Hyphenated `pre-?heat` matched in `_looks_like_instruction_start()`
- [ ] All-bold documents successfully extract recipe title, ingredients, and instructions
- [ ] Tilde-delimited files (`\~\~\~` / `~~~~`) split into separate recipes and extract plain numbered titles
- [ ] New regression test fixture `tests/samples/generic_md_edge_cases.md` and expected output added
- [ ] All unit and regression tests pass: `./venv/bin/python3 -m pytest tests/ -v`

## Deliverables
- `parsers/generic_md.py`
- `tests/samples/generic_md_edge_cases.md`
- `tests/expected/generic_md_edge_cases.md.json`
- `tests/unit/test_generic_md_edge_cases.py`
