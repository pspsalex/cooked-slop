---
id: SPEC-009
title: "Mr. Boston Drinks Database Parser"
tier: 3
type: parser
priority: P2
status: done
impact: "1 file (~992 recipes)"
deliverables: []
---

# Spec: Mr. Boston Drinks Database Parser
## Tier: 3
## Type: parser
## Priority: P2
## Estimated file impact: 1 file (DRINKS.OUT ~445KB, 992 cocktail recipes — multi-recipe)

## Description

Create a parser for the Mr. Boston Bartending Guide database export file located at `/home/alex/junk/Recipes/Ingest/ToDo/TXT/DRINKS.OUT`.

This file contains 992 drink and cocktail recipes formatted in a legacy database dump structure: blank-line delimited records, a header line containing the drink name and primary spirit category, key-value metadata lines (`Drink type:`, `Temp:`, `Serve at:`, `Season(s):`), and a long concatenated data line with fixed-width 42-character columns containing ingredients, glassware, and instructions.

## Input Samples

Input file:
- `/home/alex/junk/Recipes/Ingest/ToDo/TXT/DRINKS.OUT` (455,483 bytes, 992 drink recipes)

Sample content (first 3 records from `DRINKS.OUT`):

```text
FROZEN PINEAPPLE DAIQUIRI       RUM            
Drink type: Blender Cocktail 
Temp: Cold Frozen 
Serve at: Lunch Cocktails Party 
Season(s): Spring Summer Fall 
1  1-1/2 OZ. MR. BOSTON RUM                  4 PINEAPPLE CHUNKS, (CANNED)              1 TBSP. LIME JUICE                        1/2 TSP. SUGAR                             1 CHAMPAGNE GLASS                         Combine all ingredients with a cup of crushed  ice in a blender. Blend at low speed and pour into champagne glass. 

ALEXANDER COCKTAIL #ONE         GIN            
Drink type: Cocktail Creme 
Temp: Cold 
Serve at: Cocktails Evening 
Season(s): Spring Summer Fall Winter 
1 OZ. MR. BOSTON GIN                      1 OZ. MR. BOSTON CREME DE CACAO,           (WHITE)                                  1 OZ. LIGHT CREAM                          NUTMEG                                   1 COCKTAIL GLASS                          shake with ice and strain into cocktail glass. Sprinkle nutmeg on top. 

BACARDI COCKTAIL                RUM            
Drink type: Cocktail 
Temp: Cold 
Serve at: Cocktails Evening 
Season(s): Spring Summer 
1-1/2 OZ. BACARDI RUM                     1/2 LIME (JUICE ONLY)                     1/2 TSP. GRENADINE                         1 COCKTAIL GLASS                          Shake with ice and strain into cocktail glass. 
```

Sample record 4 (longer multi-column ingredients + instructions):

```text
BANANA DAIQUIRI                 RUM            
Drink type: Blender Cocktail 
Temp: Cold Frozen 
Serve at: Lunch Cocktails Party 
Season(s): Spring Summer 
1-1/2 OZ. MR. BOSTON RUM                  1 TBSP. MR. BOSTON TRIPLE SEC             1-1/2 OZ. LIME JUICE                      1 TSP. SUGAR                              1 MEDIUM SIZE RIPE BANANA, SLICED         1 CUP CRUSHED ICE                         1 CHAMPAGNE GLASS                         Combine ingredients in an electric blender and blend at low speed for five seconds. Then     blend at high speed until firm. Pour into     champagne glass. Top with a cherry. 
```

## Expected Behavior

### Format Structure
- **Record Delimiters**: Blank lines (`\n\n`) separate drink records.
- **Line 1 (Header)**: Drink Name (columns 0..32, ALL CAPS, left-aligned) and Primary Spirit Category (columns 32.., e.g. `RUM`, `GIN`, `VODKA`, `WHISKEY`, `BRANDY`, `TEQUILA`, `LIQUEUR`, `NON-ALCOHOLIC`).
- **Lines 2-5 (Metadata)**:
  - `Drink type:` — e.g. `Blender Cocktail`, `Cocktail Creme`, `Cocktail`, `Highball`, `Punch`, `Hot Drink`
  - `Temp:` — e.g. `Cold Frozen`, `Cold`, `Hot`, `Room Temperature`
  - `Serve at:` — e.g. `Lunch Cocktails Party`, `Cocktails Evening`, `Party Reception`
  - `Season(s):` — e.g. `Spring Summer Fall`, `Spring Summer Fall Winter`
- **Line 6+ (Data Line)**: Concatenated string formatted in fixed-width 42-character chunks containing:
  - **Ingredients**: 42-character fields in ALL CAPS (e.g. `1-1/2 OZ. MR. BOSTON RUM`, `1 TBSP. LIME JUICE`).
  - **Continuation Columns**: Some ingredient names wrap into the next 42-char column (e.g. `1 OZ. MR. BOSTON CREME DE CACAO,` followed by `(WHITE)`, or `3/4 OZ. MR. BOSTON COFFEE FLAVORED` followed by `BRANDY`).
  - **Glassware Entry**: The last capitalized item before instructions (e.g. `1 CHAMPAGNE GLASS`, `1 COCKTAIL GLASS`, `1 OLD-FASHIONED GLASS`, `1 SOUR GLASS`, `1 HIGHBALL GLASS`, `1 COLLINS GLASS`, `1 WINE GLASS`, `1 MUG`, `1 PUNCH BOWL`).
  - **Instructions**: Running mixed-case text starting after the glassware entry (e.g. `Combine all ingredients with a cup of crushed ice in a blender...`).

### Parser Class Specification
- **Module**: [parsers/drinks_db.py](file:///home/alex/junk/Recipes/scripts/parsers/drinks_db.py)
- **Class**: `DrinksDbParser` inheriting from [BaseRecipeParser](file:///home/alex/junk/Recipes/scripts/parsers/base.py#L18-L66)
- **Decorator**: `@ParserRegistry.register`
- **`format_id()`**: `"drinks_db"`
- **`aliases()`**: `['mrboston', 'drinks_out']`
- **`priority()`**: `8`
- **`detect(cls, filepath: str, content_sample: str) -> float`**:
  - Return `0.95` if `Path(filepath).suffix.lower() == '.out'` AND `Drink type:` and `Season(s):` are in `content_sample`.
  - Return `0.85` if `content_sample` contains `Drink type:`, `Temp:`, `Serve at:`, and `Season(s):`.
  - Return `0.0` otherwise.

### Field Mapping
| Target Field | Source / Rule |
|:---|:---|
| `recipe.title` | Line 1 columns 0..32, stripped and converted to Title Case (e.g. `"Frozen Pineapple Daiquiri"`). |
| `recipe.categories` | Spirit category from Line 1 (columns 32..) and `Drink type:` value, title-cased and deduplicated (e.g. `["Rum", "Blender Cocktail"]`). |
| `recipe.yield_amount` | Default to `"1 drink"` (or extract from glassware e.g. `"1 glass"`). |
| `recipe.ingredients` | Parse 42-character chunks from data line up to glassware entry. Merge multi-column continuations. Parse each with `self.ingredient_parser.parse(line)`. |
| `recipe.instructions` | Running text starting after glassware entry. Split or wrap into instruction steps `list[str]`. |
| `recipe.description` | Aggregated metadata string: `f"Temp: {temp} | Serve at: {serve_at} | Season(s): {seasons} | Glassware: {glassware}"`. |
| `recipe.source_format` | `"Mr. Boston Bartending Guide"` |
| `recipe.source_file` | `filepath` |

### Edge Cases & Handling
1. **42-Character Column Chunking**: Slicing the data line into 42-character strides (`[data[i:i+42].strip() for i in range(0, len(data), 42)]`) correctly segments columns.
2. **Ingredient Continuation Columns**: If a column ends in a comma (e.g. `MR. BOSTON CREME DE CACAO,`) or the next column is a fragment like `(WHITE)`, `BRANDY`, or `3 DROPS TABASCO SAUCE`, merge them into a single ingredient line.
3. **Glassware Detection**: Match glassware entries via regex pattern: `r'^\d*\s*(?:[A-Z\-]+\s+)*(?:GLASS|MUG|GOBLET|CUP|BOWL|FLUTE|TUMBLER|SNIFTER|DECANTER|JAR)$'`
   - Glassware is excluded from ingredients and recorded in description/metadata.
4. **Instructions Boundary**: The text following the glassware column is the preparation instructions. Multiple trailing 42-char slices form continuous instruction text and should be rejoined with single spaces.
5. **Casing Normalization**: Drink titles and ingredient lines in the input file are entirely in uppercase. The parser should convert titles to title case and instructions should maintain natural sentence casing.

## Adding a New Parser Checklist

Follow this checklist from [AGENTS.md](file:///home/alex/junk/Recipes/scripts/AGENTS.md#L133-L153):
1. Create [parsers/drinks_db.py](file:///home/alex/junk/Recipes/scripts/parsers/drinks_db.py) inheriting from `BaseRecipeParser` with `@ParserRegistry.register`.
2. Add `from .drinks_db import DrinksDbParser` to [parsers/__init__.py](file:///home/alex/junk/Recipes/scripts/parsers/__init__.py).
3. Add `'DrinksDbParser'` to `__all__` in [parsers/__init__.py](file:///home/alex/junk/Recipes/scripts/parsers/__init__.py).
4. Add a sample file at `tests/samples/drinks.out` (first 10 records from `/home/alex/junk/Recipes/Ingest/ToDo/TXT/DRINKS.OUT`).
5. Generate expected output (always use `--no-nlp`):
   ```bash
   ./venv/bin/python3 convert.py tests/samples/drinks.out -o tests/expected/drinks.out.json --no-nlp
   ```
6. Run test suite:
   ```bash
   ./venv/bin/python3 -m pytest tests/ -v
   ```

## Acceptance Criteria
- [ ] [parsers/drinks_db.py](file:///home/alex/junk/Recipes/scripts/parsers/drinks_db.py) implemented and registered with `@ParserRegistry.register`
- [ ] `DrinksDbParser` imported and added to `__all__` in [parsers/__init__.py](file:///home/alex/junk/Recipes/scripts/parsers/__init__.py)
- [ ] Sample file `tests/samples/drinks.out` created with 10 representative drink records
- [ ] Expected output `tests/expected/drinks.out.json` generated with `--no-nlp`
- [ ] Format detection test passes: `DrinksDbParser.detect` returns `>= 0.85` on `DRINKS.OUT`
- [ ] Full conversion test on `/home/alex/junk/Recipes/Ingest/ToDo/TXT/DRINKS.OUT` extracts all 992 cocktail recipes:
   ```bash
   ./venv/bin/python3 convert.py /home/alex/junk/Recipes/Ingest/ToDo/TXT/DRINKS.OUT -o /tmp/drinks_out.json --no-nlp
   ```
- [ ] Glassware is properly identified and excluded from ingredients list
- [ ] Multi-column wrapped ingredients are merged correctly
- [ ] All unit and regression tests pass: `./venv/bin/python3 -m pytest tests/ -v`

## Deliverables
- `/home/alex/junk/Recipes/scripts/parsers/drinks_db.py`
- `/home/alex/junk/Recipes/scripts/parsers/__init__.py` (updated imports and `__all__`)
- `/home/alex/junk/Recipes/scripts/tests/samples/drinks.out`
- `/home/alex/junk/Recipes/scripts/tests/expected/drinks.out.json`

## Reference
- Reference implementation: [parsers/cookware.py](file:///home/alex/junk/Recipes/scripts/parsers/cookware.py)
- Base parser class: [parsers/base.py](file:///home/alex/junk/Recipes/scripts/parsers/base.py)
- Data models: [parsers/models.py](file:///home/alex/junk/Recipes/scripts/parsers/models.py)
- Project instructions: [AGENTS.md](file:///home/alex/junk/Recipes/scripts/AGENTS.md)
