# Spec: Bread-Bakers Mailing List Extract Script
## Tier: 3
## Type: script
## Priority: P0
## Estimated file impact: 11,538 files (~5,700 estimated recipes)

## Description

Create a standalone extraction and preprocessing script `extract/breadbakers.py` to process the massive Bread-Bakers mailing list archive located at `/home/alex/junk/Recipes/Ingest/ToDo/TXT/breadbakers/split/`.

With 11,538 split digest message files, this represents the single largest batch of unprocessed files in the ingest repository. Approximately 50% of the files are actual bread recipes (hand-made and automatic bread machine recipes, sourdough starters, pizza doughs, holiday loaves), while the other ~50% consist of administrative announcements, digest tables of contents, subscription instructions, and general conversational email threads.

The script preprocesses each message (stripping RFC headers, quotation blocks, and signature lines), applies heuristic filters to differentiate recipe posts from non-recipe discussions, outputs cleaned recipe text files to an output directory, and logs non-recipe files to a detailed failure/classification report (`failures.csv`). Downstream, the cleaned files are converted using `convert.py` with auto-detection (handled by `GenericTextParser` or `MixedFormatParser`).

## Input Samples

### Sample 1: Recipe Message (`v096n002.txt-split-008`)
Path: `/home/alex/junk/Recipes/Ingest/ToDo/TXT/breadbakers/split/v096n002.txt-split-008`

```
--------------- MESSAGE bread-bakers.v096.n002.8 ---------------

From: bj29@mirage.skypoint.com (bjjan)
Subject: Re: bread-bakers-digest V6 #87
Date: Sat, 30 Mar 96 07:07 CST


>From: Melissa Moore <mcm@ccstaff.cc.ukans.edu>
>Does anyone have an abm recipe for Anadama bread?
Here are 3 different Anadama Bread recipes for you!...Bev in Mn

ANADAMA BREAD  - FOR 1-1/2 LB. LOAF-
      1 pk Yeast
  3 1/2 c  Bread flour
    1/3 c  Yellow cornmeal
  1 1/2 c  Boiling water
    1/3 c  Molasses
      1 ts Salt
      2 ts Butter
Place cornmeal into a bowl. Carefully pour boiling  water into cornmeal,
stirring to make sure it is  smooth. Let stand for about 30 minutes. Stir
in molasses, salt and butter. Place yeast into the abm pan, bread flour,
then cornmeal mixture. Select white bread and push start. NOTE: An early
American recipe. Source:.......From Loafing It by DAK

ANADAMA BREAD  1 1/2 lb loaf:;   (1 lb loaf)
  2 1/4 ts Active dry yeast;     (1 1/2 tsp
  1 2/3 c  Bread flour;          (1 c+ 2 t)
  1 1/2 c  Whole-wheat flour;    (1 c)
    1/3 c  Yellow cornmeal;      (1/4 c)
  1-1/2 T     Vegetable Oil      (1 T)
    1/3 c  Molasses; unsulfured, (1/4 c
  1 1/2 ts Salt;                 (1 t)
  1 1/2 c  Water;                (1c)
 basic bread
Source: The Best Bread Machine Cookbook Ever, Madge Rosenberg


ANADAMA BREAD - 1# size
  2 1/4 c  Bread Flour
      1 tb Dry milk
      1 ts Salt
      1/4 c  Cornmeal (1/2 oz)
      1 tb Molasses
      1 tb Olive oil
  15/16 c  Water (7 1/2 fl.oz)
      1 ts Dry yeast
Timer OR Bake (Rapid) mode may be used.
Panasonic book
```

### Sample 2: Non-Recipe Discussion Message (`v096n002.txt-split-002`)
Path: `/home/alex/junk/Recipes/Ingest/ToDo/TXT/breadbakers/split/v096n002.txt-split-002`

```
--------------- MESSAGE bread-bakers.v096.n002.2 ---------------

From: RobLK6@aol.com
Subject: broken paddle
Date: Sat, 30 Mar 1996 21:09:18 -0500


My kids broke the paddle on my round Welbuilt breadmachine.  How to replace?
I know this has been posted mucho before.  OTOH, I thought it'll never
happen to me.

  [Editor's Note:  I asked Rob how they broke it...]

They gave it to the dog to chew on.  They prefer store bought white bread -
it's what their friends eat.

Rob
```

### Sample 3: Non-Recipe Table of Contents (`v096n002.txt-split-000`)
Path: `/home/alex/junk/Recipes/Ingest/ToDo/TXT/breadbakers/split/v096n002.txt-split-000`

```
Date: Sat, 6 Apr 1996 19:21:33 -0800

-------------- BEGIN bread-bakers.v096.n002 --------------

    001 - Reggie Dwork <reggie@regg - spring break
    002 - RobLK6@aol.com            - broken paddle
    003 - Gerard_Mcmahon@ftdetrck-c - re: baguette pan / malt syrup
    004 - Doug Weller <eat@ramtops. - Re: rec.food.* CFV
    005 - bj29@mirage.skypoint.com  - Re: bread-bakers-digest V6 #86
    006 - bj29@mirage.skypoint.com  - Re: bread-bakers-digest V6 #87
    007 - bj29@mirage.skypoint.com  - Re: bread-bakers-digest V6 #87
    008 - bj29@mirage.skypoint.com  - Re: bread-bakers-digest V6 #87
```

## Expected Behavior

### Script Invocation & CLI Interface
```bash
./venv/bin/python3 extract/breadbakers.py <input_dir> <output_dir> [--report failures.csv] [--workers N]
```

### Per-File Processing Pipeline
1. **Header Stripping**:
   - Strip message delimiters: `--------------- MESSAGE ... ---------------`, `-------------- BEGIN ... --------------`, and `-------------- END ... --------------`.
   - Strip RFC 822 email headers: `From:`, `Subject:`, `Date:`, `To:`, `Reply-To:`, `Message-ID:`, `X-.*:`.
2. **Quote & Annotation Removal**:
   - Strip lines starting with `>` (quoted email replies).
   - Strip inline editorial notes like `[Editor's Note: ...]` blocks.
3. **Signature & Footer Stripping**:
   - Cut off text starting at standard signature line `-- ` (or `--\n`).
   - Strip common BBS and email footers (e.g., `Rainbow V 1.19.1`, `CHRONIX`, `Bestserv`, subscription help text).
4. **Table of Contents & Admin Detection**:
   - Identify index/TOC files composed primarily of numbered subject lines (e.g. `^\s*\d{3}\s*-\s*.*`). Classify as `toc_only`.
   - Identify administrative/help messages (e.g., `BEGIN INFO bread-bakers`, `Command: info`, `To unsubscribe...`). Classify as `admin_only`.
5. **Recipe vs. Non-Recipe Classification Heuristics**:
   - **Line Count Threshold**: Must have > 10 non-blank lines remaining after stripping. If <= 10 lines, classify as `too_short`.
   - **Ingredient Pattern Matching**:
     - Check for standard ingredient words: `cup|cups|tablespoon|tablespoons|teaspoon|teaspoons|tbsp|tsp|ounce|ounces|oz|pound|pounds|lb|lbs|package|pkg|can|stick|sticks|clove|cloves|bunch|head|slice|slices|pinch|dash|quart|gallon|pint`
     - Check for MealMaster abbreviations (respecting case sensitivity where needed):
       - `t\.` / `ts` (teaspoon)
       - `T\.` / `T ` / `tb` (tablespoon)
       - `c ` / `c\.` (cup)
       - `ea` (each), `pk` (package), `sm` (small), `md` (medium), `lg` (large), `bn` (bunch), `ds` (dash), `pn` (pinch), `dr` (drop)
     - Regex expressions:
       - `\b\d+[\s/.-]*(cup|cups|tbsp|tsp|oz|lb|lbs|package|pkg|can|stick|sticks|clove|cloves|pinch|dash|quart|gallon|pint)s?\b`
       - `\b\d+(?:[/-]\d+)?\s+(?:t\.|T\.|T|c\.|c|ea|pk|sm|md|lg|ts|tb)\s+\w+`
     - A valid recipe candidate **must contain at least 2 distinct ingredient pattern matches**. If fewer than 2 matches, classify as `no_ingredients`.
6. **Cleaned Output Generation**:
   - If classified as a valid recipe, write the stripped text to `<output_dir>/<original_filename>`.
7. **Report Logging**:
   - If classified as non-recipe, log an entry to `failures.csv` with fields:
     - `file`: Relative or original file path
     - `reason`: One of `too_short`, `no_ingredients`, `toc_only`, `admin_only`
     - `line_count`: Count of non-blank lines remaining
     - `sample_line`: First non-blank line of remaining text for easy triage

### Downstream Post-Processing
- Output files are standard plain-text recipes that can be converted by running:
  ```bash
  ./venv/bin/python3 convert.py <output_dir> -o recipes.json --no-nlp
  ```
- Multi-recipe messages (e.g. messages containing 2 or 3 recipe variants) are parsed by `MixedFormatParser` or `GenericTextParser`.

### Edge Cases
1. **Multi-recipe messages in a single email**: Several posts include 2 or 3 bread variations in one message (e.g. Sample 1 with 3 Anadama recipes). The extract script preserves all recipe text so downstream parsers can split or extract them.
2. **Tabular vs. freeform ingredients**: Bread machine recipes frequently use column-aligned quantities (e.g., `  1 1/2 c  Bread flour`). Pattern matching must accommodate leading whitespace and fractional numbers (`1 1/2`, `1-1/2`, `1/3`, `15/16`).
3. **Character encoding**: Old BBS files may contain non-UTF-8 characters (CP1252, ISO-8859-1). Use resilient file reading with fallback encodings (`errors="replace"` or `errors="ignore"`).
4. **Signature markers without hyphens**: Some users sign off with just their name ("Rob", "Bev in Mn") or BBS tagline without a `-- ` delimiter. The line-count and ingredient-frequency heuristics ensure conversational snippets are rejected even if signature stripping doesn't trigger.

## Acceptance Criteria
- [ ] Script processes all 11,538 files in `/home/alex/junk/Recipes/Ingest/ToDo/TXT/breadbakers/split/` without crashing or throwing unhandled exceptions.
- [ ] Correctly identifies and skips TOC/index files (e.g., `v096n001.txt-split-000`, `v096n002.txt-split-000`) with reason `toc_only`.
- [ ] Correctly identifies and skips short conversational messages (e.g., `v096n002.txt-split-002`) with reason `too_short` or `no_ingredients`.
- [ ] Correctly extracts recipe posts (e.g., `v096n002.txt-split-008`).
- [ ] Cleaned output files can be successfully processed by `convert.py` using auto-detection.
- [ ] `failures.csv` report is well-formed CSV with valid headers and data.
- [ ] No `print()` statements in library functions; uses Python's standard `logging` module.
- [ ] First line of `extract/breadbakers.py` is `# SPDX-License-Identifier: MIT`.
- [ ] All functions have complete type annotations.
- [ ] Unit tests for `breadbakers.py` added to test suite and pass `./venv/bin/python3 -m pytest tests/ -v`.

## Deliverables
- `/home/alex/junk/Recipes/scripts/extract/breadbakers.py`
- `/home/alex/junk/Recipes/scripts/tests/test_breadbakers_extract.py`

## Reference
- [extract/fareshare.py](file:///home/alex/junk/Recipes/scripts/extract/fareshare.py) — extraction script conventions
- [parsers/units.py](file:///home/alex/junk/Recipes/scripts/parsers/units.py) — `UNIT_MAP` dictionary for MealMaster abbreviations
- [parsers/generic.py](file:///home/alex/junk/Recipes/scripts/parsers/generic.py) — `GenericTextParser` plain-text handling
- [AGENTS.md](file:///home/alex/junk/Recipes/scripts/AGENTS.md) — project coding standards and virtual environment rules
