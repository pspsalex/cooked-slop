---
id: SPEC-031
title: "Centralized Title Sanitization and Recipe Metadata Cleanup"
tier: 2
type: parser
priority: P1
status: active
impact: "Cleans malformed titles across 13,824 recipes (~35.6% of dataset) and fixes instruction divider artifacts"
deliverables:
  - parsers/base.py
  - parsers/models.py
  - parsers/mastercook.py
  - parsers/two_col.py
  - tests/samples/title_cleanup_sample.txt
  - tests/expected/title_cleanup_sample.txt.json
  - tests/unit/test_title_sanitization.py
---

# Spec: Centralized Title Sanitization and Recipe Metadata Cleanup

## Description

Inspection of `all_recipes.json` revealed that 13,824 recipes (35.6% of the dataset) suffer from malformed titles, leaked metadata prefixes, markdown syntax artifacts, and delimiter lines appearing in instruction steps.

Common patterns identified:
1. **Unstripped Title Prefixes**:
   - `QTitle: Rice Pilaf Yield: 2 servings` (Two-Column format)
   - `Recipe Name : Apple Grape Salad` (Generic text / PRN exports)
   - `Title: Classic Chili`
2. **Embedded Yield in Title Lines**:
   - Titles containing `Yield: 4 servings`, `Serves 6`, or `Makes 12` where yield should be parsed into `Recipe.yield_amount` and stripped from `Recipe.title`.
3. **Markdown / Pandoc Attribute Artifacts**:
   - Titles formatted as `[Black Death]{.underline}` or `[Title]{#anchor}`.
   - Ingredient names with escaped punctuation: `whites \- whipped` instead of `whites - whipped`.
4. **Nutrition & Author Lines Misidentified as Titles**:
   - MasterCook headers where an empty author line was selected: `Recipe By     :`.
   - Nutrition summary lines parsed as titles: `calories from fat); 4g Protein; 28g Carbohydrate; 4g Dietary Fiber;`.
   - Email header lines selected as titles: `Date: Sun, 27 Feb 2011 08:53:48 GMT`.
5. **Instruction Steps Containing Section Dividers**:
   - Steps consisting solely of divider lines: `"---- RECIPE ----"`, `"==================="`, `"----------------"`.

## Expected Behavior

### Title Sanitization Helper
Provide a centralized helper `clean_recipe_title(title: str) -> Tuple[str, Optional[str]]`:
1. Strips leading prefixes matching `^(?:QTitle|Recipe Name|Title|Name)\s*:\s*` (case-insensitive).
2. Strips Markdown Pandoc attributes `\[(.*?)\]\{.*?\}`, unwrapping the clean title text.
3. Detects trailing yield substrings matching `(?:Yield|Servings?|Makes)\s*:\s*(.+)$`, strips them from the title, and returns the extracted yield if `recipe.yield_amount` is unset.
4. Returns empty string / fallback if the candidate title is an empty author field (`Recipe By :`), an email header (`Date:`, `From:`, `Subject:`), or a nutrition breakdown line (`calories from fat`, `g protein`).

### Step Sanitization Helper
Filter instruction steps so that pure separator lines (e.g. `^[-=~*_]{3,}$` or `^----\s*RECIPE\s*----$`) are excluded from `recipeInstructions`.

### Ingredient Text Cleaning
Unescape escaped hyphens and periods (e.g. `\-` -> `-`, `\.` -> `.`) produced by pandoc docx-to-markdown conversion.

## Acceptance Criteria
- [ ] Centralized title sanitization helper integrated into `Recipe` post-processing or `BaseRecipeParser`
- [ ] TwoColParser and GenericTextParser strip `QTitle:`, `Recipe Name :`, and trailing yields
- [ ] MasterCookParser rejects empty author lines and nutrition summary lines as title candidates
- [ ] Instruction step parser excludes raw delimiter lines like `---- RECIPE ----`
- [ ] Sample test fixture `tests/samples/title_cleanup_sample.txt` added with expected output
- [ ] Unit tests in `tests/unit/test_title_sanitization.py` validating all edge cases
- [ ] Full test suite passes: `./venv/bin/python3 -m pytest tests/ -v`
