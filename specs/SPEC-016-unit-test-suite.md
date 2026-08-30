---
id: SPEC-016
title: "Comprehensive Unit Test Suite"
tier: 1
type: test
priority: P1
status: active
impact: "Adds isolated unit tests for core conversion, streaming writer, ingredient parsing, and registry"
deliverables:
  - tests/unit/__init__.py
  - tests/unit/test_converter.py
  - tests/unit/test_writer.py
  - tests/unit/test_ingredient_parser.py
  - tests/unit/test_registry.py
---

# Spec: Comprehensive Unit Test Suite

## Description

The current test suite consists almost entirely of end-to-end integration tests in `tests/test_conversion.py` and detection tests in `tests/test_detection.py`. While effective for catch-all regression testing, integration failures produce large, multi-hundred line JSON diffs that are difficult to debug. Furthermore, edge cases in core modules (ingredient regex parsing, schema transformation, streaming chunk rotation) are tested only through serendipity of whatever happens to be present in the 43 sample files.

This specification introduces a dedicated `tests/unit/` suite covering:
1. `converter.py`: `SchemaOrgConverter.convert()` across data shapes
2. `writer.py`: `JSONStreamWriter` streaming, empty array generation, and chunk rotation
3. `parsers/ingredients.py`: `RegexIngredientParser` handling fractions, ranges, and comments
4. `parsers/registry.py`: `ParserRegistry` priority sorting, format alias lookup, and contract validation

## Worktree & Branch Protocol

Following repository golden rules:
```bash
git worktree add -b feat/spec-016-unit-tests .worktrees/spec-016 main
cd .worktrees/spec-016
```
After verification, commit, merge to `main`, and remove worktree.

---

## Detailed Specification

### 1. `tests/unit/test_converter.py`

Create focused unit tests verifying `SchemaOrgConverter.convert(recipe)`:

- **Instruction Shape**:
  - Empty instructions -> `[]`
  - Single instruction string -> `["Mix well."]` (plain string in list)
  - Multiple instructions -> list of `{"@type": "HowToStep", "position": 1, "text": "Step 1"}` dicts
- **Ingredient PropertyValue Mapping**:
  - Quantity parsing: integer `"2"` -> `2`, float `"1.5"` -> `1.5`, fraction `"1/2"` -> `"1/2"` string
  - Unit preservation: `unitText` set when present
  - Comment preservation: `description` set when `comment` present
  - Plain string fallback: when neither quantity nor unit exists, or when `parse_ingredients=False`
- **Metadata Fields**:
  - Categories: first category becomes `recipeCategory`, all joined into `keywords`
  - URLs: plain `recipe.url`, SQLite anchor `file://path#table,id`, and fallback `file://path`
  - Yield amount: mapped to `recipeYield`
  - Optional `add_date=True` includes `datePublished` ISO timestamp

```python
# Sample test structure
def test_converter_instruction_formatting():
    from converter import SchemaOrgConverter
    from parsers.models import Recipe

    converter = SchemaOrgConverter()

    r_empty = Recipe(title="Test", instructions=[])
    assert converter.convert(r_empty)["recipeInstructions"] == []

    r_single = Recipe(title="Test", instructions=["Stir gently."])
    assert converter.convert(r_single)["recipeInstructions"] == ["Stir gently."]

    r_multi = Recipe(title="Test", instructions=["Step 1", "Step 2"])
    steps = converter.convert(r_multi)["recipeInstructions"]
    assert len(steps) == 2
    assert steps[0]["@type"] == "HowToStep"
    assert steps[0]["position"] == 1
    assert steps[0]["text"] == "Step 1"
```

### 2. `tests/unit/test_writer.py`

Test `JSONStreamWriter` with `tmp_path`:

- **Empty Flush**: `close()` on empty writer without chunking writes valid JSON `[]`.
- **Single Recipe**: Writes formatted single-item array `[{...}]`.
- **Multiple Recipes**: Emits valid JSON array with correct commas.
- **Chunking by Count**: Set `max_recipes_per_chunk=2`, write 5 recipes with `chunk=True`. Verify `part001.json`, `part002.json`, `part003.json` are created, each containing valid JSON arrays.
- **Chunking by Byte Size**: Verify file rotates when byte threshold is exceeded.
- **Unicode Integrity**: Ensure non-ASCII characters (e.g. `½`, `café`, `é`) are written cleanly without mangling (`ensure_ascii=False`).

### 3. `tests/unit/test_ingredient_parser.py`

Test `RegexIngredientParser` from `parsers/ingredients.py`:

- **Fractions**: `"1/2 cup flour"` -> qty: `"1/2"`, unit: `"cup"`, name: `"flour"`
- **Mixed Numbers**: `"1 1/2 tsp salt"` -> qty: `"1 1/2"`, unit: `"teaspoon"`, name: `"salt"`
- **Decimals**: `"2.5 kg sugar"` -> qty: `"2.5"`, unit: `"kilogram"`, name: `"sugar"`
- **Ranges**: `"2-3 cloves garlic"` -> qty: `"2-3"`, unit: `"clove"`, name: `"garlic"`
- **Trailing Comments**: `"1 cup butter, melted"` -> qty: `"1"`, unit: `"cup"`, name: `"butter"`, comment: `"melted"`
- **Case-Sensitive Units**: `"1 T paprika"` -> unit: `"tablespoon"`, `"1 t cumin"` -> unit: `"teaspoon"`
- **Missing Units**: `"3 eggs"` -> qty: `"3"`, unit: `None`, name: `"eggs"`
- **Missing Quantities**: `"salt and pepper to taste"` -> qty: `None`, unit: `None`, name: `"salt and pepper to taste"`

### 4. `tests/unit/test_registry.py`

Test `ParserRegistry` from `parsers/registry.py`:

- **Priority Ordering**: Parsers are retrieved in ascending priority order.
- **Aliases**: Resolving parser by alias or format ID works.
- **Contract Enforcement**: Registering a class missing `detect` or using non-generator `parse_content` raises `TypeError`.
- **Exception Resilience**: If a parser raises an unhandled exception inside `detect()`, `get_parser()` catches it, logs via `logger.debug()`, and continues evaluating other candidate parsers.

---

## Edge Cases

1. **Virtualenv / Subprocess Execution**: Unit tests must import modules directly in-process without relying on `convert.py` subprocess calls.
2. **Deterministic Outputs**: Ensure unit tests run without network calls or LLM dependencies.
3. **Chunk Rotation Boundary**: Writing exactly `max_recipes_per_chunk` recipes should not create an extraneous empty chunk.

---

## Acceptance Criteria

- [ ] `tests/unit/` directory created with `__init__.py`.
- [ ] `tests/unit/test_converter.py` verifies all instruction and ingredient mapping branches.
- [ ] `tests/unit/test_writer.py` verifies streaming output, empty arrays, and count/size chunking.
- [ ] `tests/unit/test_ingredient_parser.py` validates fractions, mixed numbers, ranges, and unit normalizations.
- [ ] `tests/unit/test_registry.py` validates priority resolution and contract validation errors.
- [ ] All unit tests pass deterministically: `./venv/bin/python3 -m pytest tests/unit/ -v`.
- [ ] Integration test suite remains green: `./venv/bin/python3 -m pytest tests/ -v`.

---

## Verification Plan

```bash
# Run unit tests exclusively
./venv/bin/python3 -m pytest tests/unit/ -v

# Run full test suite
./venv/bin/python3 -m pytest tests/ -v
```
