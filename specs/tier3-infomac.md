# Spec: Info-Mac / BBS .INF Recipe Parser
## Tier: 3
## Type: parser
## Priority: P1
## Estimated file impact: 5 files (CORNBRE.INF, DUCK.INF, SALAD.INF, SAVORY.INF, STEAK.INF — ~120KB total, 120 recipes)

## Description

Create a parser for vintage Macintosh Info-Mac archive / BBS recipe collections stored in `.INF` files located in `/home/alex/junk/Recipes/Ingest/ToDo/TXT/`.

These files are multi-recipe digests distributed on early Macintosh bulletin board systems (BBS). They use `%` as a file-level marker, backticks (`` ` ``) for recipe titles, `-` (dash) to separate ingredients from instructions, and `~` (tilde) as recipe record terminators.

## Input Samples

Input files:
- `/home/alex/junk/Recipes/Ingest/ToDo/TXT/CORNBRE.INF` (23,570 bytes, 27 recipes)
- `/home/alex/junk/Recipes/Ingest/ToDo/TXT/DUCK.INF` (13,169 bytes, 9 recipes)
- `/home/alex/junk/Recipes/Ingest/ToDo/TXT/SALAD.INF` (46,672 bytes, 55 recipes)
- `/home/alex/junk/Recipes/Ingest/ToDo/TXT/SAVORY.INF` (25,184 bytes, 17 recipes)
- `/home/alex/junk/Recipes/Ingest/ToDo/TXT/STEAK.INF` (13,960 bytes, 12 recipes)

Sample content from `/home/alex/junk/Recipes/Ingest/ToDo/TXT/CORNBRE.INF`:

```text
%
`AMANDA COCKERELL'S CORN PONE

Corn meal
buttermilk
sugar
-
mix buttermilk with corn meal and about a teaspoon of sugar till the
consistancy of good sandcastle building sand (neither one of us could find a
better description) and fry on medium heat in grease/oil about 5-10 min a
side, depending on thickness  Serve with lots of butter melted on the top.
went really well with breakfast.

From Trude Duckworth to John Hartman                  27-Nov-89
~
`BUTTERMILK CORN BREAD

Preheat the oven to 400 degrees F.  Grease a 9 X 12-inch baking dish.  Sift
together the following:

2       Cups    Unbleached All Purpose Flour
2       t       Baking Powder
1       t       Baking Soda
3/4     t       Salt

Beat together in a large bowl, in the order given,

2       Large   Eggs
3/4     Cup     Sugar
2       Cups    Butter or Sour Milk
1/4     Cup     Melted Butter, Slightly Cooled
1       Cup     Stone or Coarsely Ground Corn Meal

Makes 12 Servings
-

Stir dry ingredients into the buttermilk mixture.  Turn into prepared pan.
Bake at 400 degrees for 25 to 30 minutes or until a wooden pick inserted in
the center comes out clean.  Serve warm.


I found this recipe in a cookbook called The Wooden Spoon Bread Book by
Marilyn M Moore.  And I really do like it.  I have made it with sour milk
and also with the dried Buttermilk powder that is available at the grocery
stores here.  I much prefer the buttermilk in it.  One place to get true
stone ground corn meal, unless you grind it yourself, is at Walnut Acres
Penns Creek PA 17862.  And they did have a free catalog that they would
send you that gives the prices.  It is a little expensive, but they have
many things that you do not find in the shopping mall supermarkets.

From:    Rich Harper 
~
`BACONY CORN BREAD
 
  1 8oz package of bacon slices        2 C all purpose flour
  1 1/2 C cornmeal                     1/4 sugar
  2 Tbsp double acting baking powder   1 tsp salt
  2 eggs                               1 1/2  C milk
  1/4 C salad oil
-
Preheat oven to 400.  Cook bacon crisp, and crumble; set aside.
Reserve 1/4 C bacon drippings.
Grease 13x9 baking pan.  In a large bowl, with fork, mix flour, cornmeal,
sugar, baking powder, and salt. In medium bowl, with fork, beat together eggs,
milk, salad oil and reserved bacon drippings.
...
From:    Sandy Colby
~
```

## Expected Behavior

### Format Structure
- **File Header**: First non-blank line of file is `%` (standard Info-Mac digest header).
- **Recipe Start**: Line begins with a backtick (`` ` ``) followed by recipe title (e.g. `` `AMANDA COCKERELL'S CORN PONE ``).
- **Ingredient Block**: Lines between recipe title and `-` separator line.
- **Section Separator**: A line containing a single `-` (dash) character (optionally surrounded by whitespace) separates ingredients from directions.
- **Instructions Block**: Lines following `-` separator up to `~` delimiter.
- **Attribution / Metadata**: Near the bottom of instructions before `~`, lines often contain attribution such as:
  - `From <Author> to <Recipient> <Date>`
  - `From:    <Author>`
  - Optional formatting codes such as `\fm` preceding the author line.
- **Recipe Terminator**: A line containing `~` terminates the recipe.

### Parser Class Specification
- **Module**: [parsers/infomac.py](file:///home/alex/junk/Recipes/scripts/parsers/infomac.py)
- **Class**: `InfoMacParser` inheriting from [BaseRecipeParser](file:///home/alex/junk/Recipes/scripts/parsers/base.py#L18-L66)
- **Decorator**: `@ParserRegistry.register`
- **`format_id()`**: `"infomac"`
- **`aliases()`**: `['inf', 'bbs_inf']`
- **`priority()`**: `6`
- **`detect(cls, filepath: str, content_sample: str) -> float`**:
  - Return `0.99` if first non-blank line is `%` AND `content_sample` contains backtick title lines (``^`[A-Za-z]``) and `~` delimiters.
  - Return `0.85` if `Path(filepath).suffix.lower() == '.inf'` AND `%` and `~` are in `content_sample`.
  - Return `0.0` otherwise.

### Field Mapping
| Target Field | Source / Rule |
|:---|:---|
| `recipe.title` | Text on the backtick line after `` ` ``, stripped. |
| `recipe.yield_amount` | Extract pattern `(?:Makes|Servings:?|Serves:?)\s*(\d+(?:-\d+)?\s*(?:Servings|servings|slices|pies|gallons)?)` from ingredients, preamble, or instructions if present. |
| `recipe.categories` | Extract from `Categories:\s*(.*)` line if present. |
| `recipe.ingredients` | Parse lines between title and `-`. Handle both single-column and two-column layouts. Parse each ingredient line using `self.ingredient_parser.parse(raw)`. |
| `recipe.instructions` | Lines between `-` and `~`, excluding trailing attribution lines. Join paragraphs into `list[str]`. |
| `recipe.description` | Attribution / source note if extracted from `From: ...` line; otherwise default description from base class. |
| `recipe.source_format` | `"Info-Mac BBS"` |
| `recipe.source_file` | `filepath` |

### Edge Cases & Handling
1. **Two-Column Ingredient Layout**: Some recipes format ingredients in two columns separated by 3+ spaces or tabs (e.g. `1 8oz package of bacon slices        2 C all purpose flour`). The parser must detect two-column lines (see [parsers/two_col.py](file:///home/alex/junk/Recipes/scripts/parsers/two_col.py)) and split them into separate ingredients.
2. **Preamble Text in Ingredient Section**: Some recipes contain preheating notes or subheadings before or between ingredients (e.g. `Preheat the oven to 400 degrees F...`, `Beat together in a large bowl...`). Non-ingredient preamble lines should either be prepended to instructions or parsed cleanly as ingredient notes.
3. **MealMaster Unit Abbreviations**: Common MealMaster-style unit abbreviations appear throughout (`t`, `T`, `c`, `C`, `Tbsp`, `tsp`, `oz`, `lb`). These are normalized via [parsers/units.py](file:///home/alex/junk/Recipes/scripts/parsers/units.py).
4. **Attribution Lines and `\fm` Formatting Codes**:
   - Lines like `From:    Rich Harper`, `From Trude Duckworth to John Hartman  27-Nov-89`, `\fm` before attribution must be stripped from `recipe.instructions` and optionally saved to `recipe.description`.
5. **Stray Artifact Lines**: Occasional OCR/formatting artifacts such as an `a` on a line by itself immediately following the title line should be skipped.

## Adding a New Parser Checklist

Follow this checklist from [AGENTS.md](file:///home/alex/junk/Recipes/scripts/AGENTS.md#L133-L153):
1. Create [parsers/infomac.py](file:///home/alex/junk/Recipes/scripts/parsers/infomac.py) inheriting from `BaseRecipeParser` with `@ParserRegistry.register`.
2. Add `from .infomac import InfoMacParser` to [parsers/__init__.py](file:///home/alex/junk/Recipes/scripts/parsers/__init__.py).
3. Add `'InfoMacParser'` to `__all__` in [parsers/__init__.py](file:///home/alex/junk/Recipes/scripts/parsers/__init__.py).
4. Add a sample file at `tests/samples/cornbre.inf` (trimmed to first 5 representative recipes from `/home/alex/junk/Recipes/Ingest/ToDo/TXT/CORNBRE.INF`).
5. Generate expected output (always use `--no-nlp`):
   ```bash
   ./venv/bin/python3 convert.py tests/samples/cornbre.inf -o tests/expected/cornbre.inf.json --no-nlp
   ```
6. Run test suite:
   ```bash
   ./venv/bin/python3 -m pytest tests/ -v
   ```

## Acceptance Criteria
- [ ] [parsers/infomac.py](file:///home/alex/junk/Recipes/scripts/parsers/infomac.py) implemented and registered with `@ParserRegistry.register`
- [ ] `InfoMacParser` imported and added to `__all__` in [parsers/__init__.py](file:///home/alex/junk/Recipes/scripts/parsers/__init__.py)
- [ ] Sample file `tests/samples/cornbre.inf` created with 5 representative recipes (including single-col, two-col, and preamble cases)
- [ ] Expected output `tests/expected/cornbre.inf.json` generated using `./venv/bin/python3 convert.py tests/samples/cornbre.inf -o tests/expected/cornbre.inf.json --no-nlp`
- [ ] Detection test passes: `InfoMacParser.detect` returns `0.99` on `.INF` files starting with `%`
- [ ] All 5 `.INF` files convert successfully without unhandled exceptions:
  - `CORNBRE.INF` (27 recipes)
  - `DUCK.INF` (9 recipes)
  - `SALAD.INF` (55 recipes)
  - `SAVORY.INF` (17 recipes)
  - `STEAK.INF` (12 recipes)
- [ ] All unit and regression tests pass: `./venv/bin/python3 -m pytest tests/ -v`

## Deliverables
- `/home/alex/junk/Recipes/scripts/parsers/infomac.py`
- `/home/alex/junk/Recipes/scripts/parsers/__init__.py` (updated imports and `__all__`)
- `/home/alex/junk/Recipes/scripts/tests/samples/cornbre.inf`
- `/home/alex/junk/Recipes/scripts/tests/expected/cornbre.inf.json`

## Reference
- Reference implementation: [parsers/cookware.py](file:///home/alex/junk/Recipes/scripts/parsers/cookware.py)
- Two-column layout splitting reference: [parsers/two_col.py](file:///home/alex/junk/Recipes/scripts/parsers/two_col.py)
- Base parser class: [parsers/base.py](file:///home/alex/junk/Recipes/scripts/parsers/base.py)
- Data models: [parsers/models.py](file:///home/alex/junk/Recipes/scripts/parsers/models.py)
- Project instructions: [AGENTS.md](file:///home/alex/junk/Recipes/scripts/AGENTS.md)
