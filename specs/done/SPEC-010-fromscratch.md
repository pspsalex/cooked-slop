---
id: SPEC-010
title: "FromScratch Recipe Collection"
tier: 3
type: parser
priority: P1
status: done
impact: "TBD"
deliverables: []
---

# Spec: From Scratch v2.0 Parser
## Tier: 3
## Type: parser
## Priority: P1
## Estimated file impact: 2 files (BONUSREC.FS ~107KB / 95 recipes, BONUSREC.FSX ~107KB / 95 recipes — multi-recipe)

## Description

Create a parser for the From Scratch v2.0 recipe text export format (`.FS` and `.FSX` files) located in `/home/alex/junk/Recipes/Ingest/ToDo/TXT/`.

> [!NOTE]
> [configs/fscratch.yaml](file:///home/alex/junk/Recipes/scripts/configs/fscratch.yaml) is an SQLite database schema configuration for `.sqlite`/`.db` files exported from From Scratch. This new parser ([parsers/fromscratch.py](file:///home/alex/junk/Recipes/scripts/parsers/fromscratch.py)) handles the plaintext `.FS` and `.FSX` multi-recipe export format directly.

## Input Samples

Input files:
- `/home/alex/junk/Recipes/Ingest/ToDo/TXT/BONUSREC.FS` (105,446 bytes, 95 recipes)
- `/home/alex/junk/Recipes/Ingest/ToDo/TXT/BONUSREC.FSX` (105,270 bytes, 95 recipes)

Sample content (first 2 recipes from `BONUSREC.FS`):

```text
********** FROM SCRATCH V 2.0  RECIPE BEGINS ********

Title    :Amy's Cornbread                                             
Serves   :4  
KeyWords :Breads                                                      
Minutes  :
Origin   :                                                            
Calories :
Protein  :
Fat      :
Carb     :
Fiber    :
Chol     :
Iron     :
Sodium   :
Calcium  :
Sat      :
Poly     :
Mono     :
Oven Temp:    
Ingredients:
  1.00     pkg.         Frozen broccoli
  2.00     cup          Grated cheddar sharp cheese
  1.00     ea.         Med. onion
  1.00     ea.         Box jiffy cornbread mix

Instructions:
Bake in glass pan for 25-30 minutes at 400 degree.


Notes:
********** RECIPE ENDS ********
********** FROM SCRATCH V 2.0  RECIPE BEGINS ********

Title    :Apple Cobbler                                               
Serves   :8  
KeyWords :Desserts                                                    
Minutes  :
Origin   :                                                            
Calories :
Protein  :
Fat      :
Carb     :
Fiber    :
Chol     :
Iron     :
Sodium   :
Calcium  :
Sat      :
Poly     :
Mono     :
Oven Temp:    
Ingredients:
  1.00     ea.         20 oz. Apple Pie Filling
  1.00     T          Butter
  1.00     t          Lemon juice
  1.00     ea.         Dash of cinnamon
  1.00     c          Prepared biscuit mix
  0.33     c          Milk

Instructions:
Preheat oven to 375.
Place pie filling in an 8 inch square baking dish. Dot with butter and
sprinkle with lemon juice and cinnamon.
Combine biscuit mix and milk, blending well.
Spoon dough on top of fruit. Bake for 20 to 25 minutes or until lightly
browned. Serve warm or cold with cream or ice cream.

Notes:
********** RECIPE ENDS ********
```

## Expected Behavior

### Format Structure
- **Record Delimiters**: Each recipe begins with `********** FROM SCRATCH V 2.0  RECIPE BEGINS ********` (or `FROM SCRATCH V`) and ends with `********** RECIPE ENDS ********`.
- **Field Labels**: Colon-separated fixed-width field labels (e.g. `Title    :`, `Serves   :`, `KeyWords :`, `Minutes  :`, `Origin   :`, `Oven Temp:`, `Calories :`, `Protein  :`, etc.).
- **Ingredients Section**: Begins with `Ingredients:` line. Followed by ingredient lines with decimal quantities, unit abbreviations, and ingredient names formatted in columns:
  - Format: `  <qty>     <unit>         <name>` (e.g. `  1.00     pkg.         Frozen broccoli`, `  0.33     c          Milk`)
- **Instructions Section**: Begins with `Instructions:` line up to `Notes:` or `********** RECIPE ENDS ********`.
- **Notes Section**: Begins with `Notes:` up to `********** RECIPE ENDS ********`.

### Parser Class Specification
- **Module**: [parsers/fromscratch.py](file:///home/alex/junk/Recipes/scripts/parsers/fromscratch.py)
- **Class**: `FromScratchParser` inheriting from [BaseRecipeParser](file:///home/alex/junk/Recipes/scripts/parsers/base.py#L18-L66)
- **Decorator**: `@ParserRegistry.register`
- **`format_id()`**: `"fromscratch"`
- **`aliases()`**: `['from_scratch', 'fs']`
- **`priority()`**: `5`
- **`detect(cls, filepath: str, content_sample: str) -> float`**:
  - Return `0.99` if `FROM SCRATCH V 2.0  RECIPE BEGINS` or `FROM SCRATCH V` is found in `content_sample` (case-insensitive).
  - Return `0.85` if `Path(filepath).suffix.lower() in ('.fs', '.fsx')` and `RECIPE BEGINS` is in `content_sample`.
  - Return `0.0` otherwise.

### Field Mapping
| Target Field | Source / Rule |
|:---|:---|
| `recipe.title` | Value of `Title    :` line, stripped. |
| `recipe.yield_amount` | Value of `Serves   :` line, stripped. |
| `recipe.categories` | Value of `KeyWords :` line, split on commas and stripped (e.g. `['Breads']`). |
| `recipe.ingredients` | Parse lines between `Ingredients:` and `Instructions:`. Strip leading whitespace, parse quantity (decimal), unit (normalized via [parsers/units.py](file:///home/alex/junk/Recipes/scripts/parsers/units.py)), and ingredient name. Construct `Ingredient(raw=line, quantity=..., unit=..., name=...)` or use `self.ingredient_parser.parse(line)`. |
| `recipe.instructions` | Lines between `Instructions:` and `Notes:` (or end marker). Join non-empty lines / paragraphs into `list[str]`. |
| `recipe.description` | Text from `Notes:` section if non-empty; otherwise default description from base class. |
| `recipe.source_format` | `"From Scratch v2.0"` |
| `recipe.source_file` | `filepath` |

### Edge Cases
- **Empty Nutrition Fields**: Labels such as `Calories :`, `Protein  :`, `Fat      :`, `Carb     :`, `Fiber    :`, `Chol     :`, `Iron     :`, `Sodium   :`, `Calcium  :`, `Sat      :`, `Poly     :`, `Mono     :` are almost always empty in export files and must be safely skipped without creating empty fields.
- **Empty or Missing Notes**: When `Notes:` is empty (followed immediately by `********** RECIPE ENDS ********`), do not store empty string into description.
- **Multi-Recipe Parsing**: Files contain dozens of recipes (`BONUSREC.FS` has 95 recipes). `parse_content` must yield each [Recipe](file:///home/alex/junk/Recipes/scripts/parsers/models.py#L20-L34) generator-style using `yield`.
- **Unit Normalization**: Standard abbreviations like `pkg.`, `ea.`, `c`, `T`, `t`, `cup`, `tbsp`, `tsp` should map cleanly through `Ingredient.__post_init__` / `normalize_unit`.
- **File Extensions**: Both `.FS` and `.FSX` extensions are used.

## Adding a New Parser Checklist

Follow this checklist from [AGENTS.md](file:///home/alex/junk/Recipes/scripts/AGENTS.md#L133-L153):
1. Create [parsers/fromscratch.py](file:///home/alex/junk/Recipes/scripts/parsers/fromscratch.py) inheriting from `BaseRecipeParser` with `@ParserRegistry.register`.
2. Add `from .fromscratch import FromScratchParser` to [parsers/__init__.py](file:///home/alex/junk/Recipes/scripts/parsers/__init__.py).
3. Add `'FromScratchParser'` to `__all__` in [parsers/__init__.py](file:///home/alex/junk/Recipes/scripts/parsers/__init__.py).
4. Add a sample file at `tests/samples/bonusrec.fs` (copy first 3-5 recipes from `/home/alex/junk/Recipes/Ingest/ToDo/TXT/BONUSREC.FS`).
5. Generate expected output (always use `--no-nlp`):
   ```bash
   ./venv/bin/python3 convert.py tests/samples/bonusrec.fs -o tests/expected/bonusrec.fs.json --no-nlp
   ```
6. Run test suite:
   ```bash
   ./venv/bin/python3 -m pytest tests/ -v
   ```

## Acceptance Criteria
- [ ] [parsers/fromscratch.py](file:///home/alex/junk/Recipes/scripts/parsers/fromscratch.py) implemented and decorated with `@ParserRegistry.register`
- [ ] `FromScratchParser` imported and added to `__all__` in [parsers/__init__.py](file:///home/alex/junk/Recipes/scripts/parsers/__init__.py)
- [ ] Sample file `tests/samples/bonusrec.fs` created with 3-5 recipes
- [ ] Expected output `tests/expected/bonusrec.fs.json` generated using `./venv/bin/python3 convert.py tests/samples/bonusrec.fs -o tests/expected/bonusrec.fs.json --no-nlp`
- [ ] Format detection test passes: `FromScratchParser.detect` returns `0.99` for `BONUSREC.FS` and `BONUSREC.FSX`
- [ ] Full conversion test on `/home/alex/junk/Recipes/Ingest/ToDo/TXT/BONUSREC.FS` extracts all 95 recipes:
  ```bash
  ./venv/bin/python3 convert.py /home/alex/junk/Recipes/Ingest/ToDo/TXT/BONUSREC.FS -o /tmp/bonusrec_out.json --no-nlp
  ```
- [ ] All unit and regression tests pass: `./venv/bin/python3 -m pytest tests/ -v`

## Deliverables
- `/home/alex/junk/Recipes/scripts/parsers/fromscratch.py`
- `/home/alex/junk/Recipes/scripts/parsers/__init__.py` (updated imports and `__all__`)
- `/home/alex/junk/Recipes/scripts/tests/samples/bonusrec.fs`
- `/home/alex/junk/Recipes/scripts/tests/expected/bonusrec.fs.json`

## Reference
- Reference implementation: [parsers/cookware.py](file:///home/alex/junk/Recipes/scripts/parsers/cookware.py)
- Base parser class: [parsers/base.py](file:///home/alex/junk/Recipes/scripts/parsers/base.py)
- Data models: [parsers/models.py](file:///home/alex/junk/Recipes/scripts/parsers/models.py)
- Existing text parsers: [parsers/edna.py](file:///home/alex/junk/Recipes/scripts/parsers/edna.py), [parsers/compuchef.py](file:///home/alex/junk/Recipes/scripts/parsers/compuchef.py)
- Project instructions: [AGENTS.md](file:///home/alex/junk/Recipes/scripts/AGENTS.md)
