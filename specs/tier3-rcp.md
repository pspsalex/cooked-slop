# Spec: RCP Nutritional Exchange Format Parser
## Tier: 3
## Type: parser
## Priority: P2
## Estimated file impact: 9 files (single-recipe files, ~7.5KB total)

## Description

Create a parser for Diabetic / Nutritional Exchange `.RCP` recipe files located in `/home/alex/junk/Recipes/Ingest/ToDo/TXT/`.

Each `.RCP` file contains a single recipe formatted with a title on line 1, serving count on line 2, followed by ingredient lines prefixed with 6 fixed-width floating-point numbers representing American Diabetes Association (ADA) exchange lists (Milk, Vegetable, Fruit, Bread/Starch, Meat, Fat), followed by a `RECIPE_TEXT:` section delimiter and preparation instructions.

## Input Samples

Input files (9 files in `/home/alex/junk/Recipes/Ingest/ToDo/TXT/`):
- `CHILI2.RCP` (1,399 bytes)
- `CHOWDER.RCP` (711 bytes)
- `MACARONI.RCP` (775 bytes)
- `PORKCHOP.RCP` (730 bytes)
- `PORKCHP2.RCP` (635 bytes)
- `PUMP_PIE.RCP` (906 bytes)
- `RELLANOS.RCP` (442 bytes)
- `SPAGHETI.RCP` (684 bytes)
- `SPUDS.RCP` (886 bytes)

Sample 1: `CHILI2.RCP` (complete file):

```text
Road Kill Chili
8
24.00 24.00 00.00 00.00 00.00 00.00 2 lbs ground beef, drained
00.00 00.00 00.00 00.00 00.00 00.00 2 mild red chile peppers
00.00 00.00 00.00 00.00 00.00 00.00 1 jalepeno pepper
00.00 00.00 00.00 00.00 00.00 00.00 1 tbsp cumin
00.00 00.00 00.00 00.00 00.00 00.00 1 tsp cayenne pepper
00.00 00.00 00.00 00.00 00.00 00.50 1 small onion, chopped
00.00 00.00 00.00 00.00 00.00 00.00 1 garlic clove, crushed
00.00 00.00 00.00 00.00 00.00 01.00 1 green bell pepper
01.00 00.00 00.00 00.00 00.00 00.00 4 oz can olives, chopped
00.00 03.80 03.80 00.00 00.00 00.00 15 1/2 oz can pinto beans
00.00 03.80 03.80 00.00 00.00 00.00 15 1/2 oz can kidney beans, drained
00.00 00.00 00.00 00.00 00.00 03.70 15 oz can tomato sauce
00.00 00.00 00.00 00.00 00.00 00.00 1 cup water
RECIPE_TEXT:
1. Brown the beef, and drain.
2. Blend the chile, peppers,  jalepeno peppers, tomatoe sauce, and water to make the chile sauce.  
3. Add the chile sauce to the beef, along with the onions, bell peppers, garlic, and olives.
4.  Bring to a boil, then simmer for 1 hour with the cover off the pan, stirring occasionally.  You will probably have to add water to keep it from boiling off.
5.  Add the beans and simmer for another 15 minutes.
6.  Let set in fridge overnight and reheat before serving.

For true chili hot heads, try adding a Habenero pepper or two, but stir fast to keep from losing the spoon!
```

Sample 2: `PORKCHOP.RCP` (complete file):

```text
Dick Hampton Patterson's Glazed and Onion Pork Chops
6
00.00 00.00 00.00 00.00 00.00 03.00 3 large onions, cut in half
00.00 00.00 00.00 04.00 00.00 00.00 6 medium pork chops
00.00 00.00 00.00 00.00 00.00 00.00 1/3 cup brown sugar
00.00 00.00 00.00 00.00 00.00 00.00 1 tsp sage
00.00 00.00 00.00 00.00 00.00 00.00 1 tsp salt
00.00 00.00 00.00 00.00 00.00 00.00 1 tsp dry mustard
RECIPE_TEXT:
Boil onions in salted water for 10 minutes. Drain.

Brown chops in a heavy skillet. Season with salt and pepper.

Spread sage and mustard on both sides of chops.

Cover skillet and cook over low heat for 30 minutes, turning once.

Arrange onions over chops, sprinkle with sugar.

Cover and cook over low heat for 10 to 15 minutes, or until onions are tender.
```

## Expected Behavior

### Format Structure
- **Line 1**: Recipe title (single line).
- **Line 2**: Servings count as an integer (e.g. `8`, `6`, `2`, `4`).
- **Lines 3 to N (Ingredients)**: Each ingredient line starts with 6 fixed-width numbers in `NN.NN` format separated by spaces (35-36 character prefix).
  - Regex pattern: `^\s*(?:\d{2}\.\d{2}\s+){6}(.*)$`
  - The remaining text after the 6th number is the ingredient statement (e.g. `2 lbs ground beef, drained`).
- **Section Marker**: `RECIPE_TEXT:` on its own line.
- **Lines N+2 to End**: Instructions / preparation text.

### Parser Class Specification
- **Module**: [parsers/rcp_exchange.py](file:///home/alex/junk/Recipes/scripts/parsers/rcp_exchange.py)
- **Class**: `RcpExchangeParser` inheriting from [BaseRecipeParser](file:///home/alex/junk/Recipes/scripts/parsers/base.py#L18-L66)
- **Decorator**: `@ParserRegistry.register`
- **`format_id()`**: `"rcp_exchange"`
- **`aliases()`**: `['rcp', 'exchange']`
- **`priority()`**: `6`
- **`detect(cls, filepath: str, content_sample: str) -> float`**:
  - Return `0.95` if `Path(filepath).suffix.lower() == '.rcp'` AND `RECIPE_TEXT:` in `content_sample`.
  - Return `0.90` if `content_sample` contains `RECIPE_TEXT:` AND line 2 is an integer AND ingredient lines match `^(?:\d{2}\.\d{2}\s+){6}`.
  - Return `0.0` otherwise.

### Field Mapping
| Target Field | Source / Rule |
|:---|:---|
| `recipe.title` | Line 1, stripped. |
| `recipe.yield_amount` | Line 2 value, formatted as `"<N> servings"` (or `"<N>"`). |
| `recipe.ingredients` | Lines between line 2 and `RECIPE_TEXT:`. Strip the initial 6 exchange floats (`^\s*(?:\d{2}\.\d{2}\s+){6}`), parse remainder with `self.ingredient_parser.parse(ing_text)`. |
| `recipe.instructions` | All lines after `RECIPE_TEXT:`. Group non-empty lines / numbered steps into `list[str]`. |
| `recipe.source_format` | `"RCP Exchange"` |
| `recipe.source_file` | `filepath` |

### Edge Cases
- **Strip Exchange Numbers**: The 6 exchange numbers (e.g. `24.00 24.00 00.00 00.00 00.00 00.00`) must be stripped before passing ingredient text to the ingredient parser, otherwise `24.00` will be incorrectly interpreted as quantity.
- **Numbered vs Paragraph Steps**: Instructions may be numbered (e.g. `1. Brown the beef...`) or formatted as blank-line-separated paragraphs. Preserve step structure.
- **Single Recipe Per File**: Each `.RCP` file contains exactly one recipe.
- **Trailing Commentary**: Text at the end of instructions (such as tips or notes) should be included as part of instructions or captured cleanly without truncation.

## Adding a New Parser Checklist

Follow this checklist from [AGENTS.md](file:///home/alex/junk/Recipes/scripts/AGENTS.md#L133-L153):
1. Create [parsers/rcp_exchange.py](file:///home/alex/junk/Recipes/scripts/parsers/rcp_exchange.py) inheriting from `BaseRecipeParser` with `@ParserRegistry.register`.
2. Add `from .rcp_exchange import RcpExchangeParser` to [parsers/__init__.py](file:///home/alex/junk/Recipes/scripts/parsers/__init__.py).
3. Add `'RcpExchangeParser'` to `__all__` in [parsers/__init__.py](file:///home/alex/junk/Recipes/scripts/parsers/__init__.py).
4. Add a sample file at `tests/samples/chili2.rcp` (copy `/home/alex/junk/Recipes/Ingest/ToDo/TXT/CHILI2.RCP`).
5. Generate expected output (always use `--no-nlp`):
   ```bash
   ./venv/bin/python3 convert.py tests/samples/chili2.rcp -o tests/expected/chili2.rcp.json --no-nlp
   ```
6. Run test suite:
   ```bash
   ./venv/bin/python3 -m pytest tests/ -v
   ```

## Acceptance Criteria
- [ ] [parsers/rcp_exchange.py](file:///home/alex/junk/Recipes/scripts/parsers/rcp_exchange.py) implemented and registered with `@ParserRegistry.register`
- [ ] `RcpExchangeParser` imported and added to `__all__` in [parsers/__init__.py](file:///home/alex/junk/Recipes/scripts/parsers/__init__.py)
- [ ] Sample file `tests/samples/chili2.rcp` added to `tests/samples/`
- [ ] Expected output `tests/expected/chili2.rcp.json` generated with `--no-nlp`
- [ ] Format detection test passes: `RcpExchangeParser.detect` returns `>= 0.90` on all 9 `.RCP` files
- [ ] All 9 `.RCP` files convert cleanly without errors:
  ```bash
  for f in /home/alex/junk/Recipes/Ingest/ToDo/TXT/*.RCP; do
    ./venv/bin/python3 convert.py "$f" -o "/tmp/$(basename "$f").json" --no-nlp
  done
  ```
- [ ] All unit and regression tests pass: `./venv/bin/python3 -m pytest tests/ -v`

## Deliverables
- `/home/alex/junk/Recipes/scripts/parsers/rcp_exchange.py`
- `/home/alex/junk/Recipes/scripts/parsers/__init__.py` (updated imports and `__all__`)
- `/home/alex/junk/Recipes/scripts/tests/samples/chili2.rcp`
- `/home/alex/junk/Recipes/scripts/tests/expected/chili2.rcp.json`

## Reference
- Reference implementation: [parsers/cookware.py](file:///home/alex/junk/Recipes/scripts/parsers/cookware.py)
- Base parser class: [parsers/base.py](file:///home/alex/junk/Recipes/scripts/parsers/base.py)
- Data models: [parsers/models.py](file:///home/alex/junk/Recipes/scripts/parsers/models.py)
- Project instructions: [AGENTS.md](file:///home/alex/junk/Recipes/scripts/AGENTS.md)
