---
id: SPEC-035
title: "YAML-Configurable Unified CSV Recipe Parser"
tier: 1
type: parser
priority: P1
status: done
impact: "Unifies existing CSV parsers (cookware, twentykrecipes) and enables YAML configuration for future CSV layouts (e.g. chefs.csv)"
deliverables:
  - parsers/csv_config.py
  - parsers/csv_parser.py
  - configs/cookware.csv.yaml
  - configs/twentyk.csv.yaml
  - configs/chefs.csv.yaml
  - tests/samples/chefs.csv
  - tests/expected/chefs.csv.json
  - tests/unit/test_csv_config.py
  - tests/unit/test_configurable_csv_parser.py
---

# Spec: YAML-Configurable Unified CSV Recipe Parser

## Description

Currently, the codebase handles CSV recipe files through bespoke, hardcoded parser classes:
- [parsers/cookware.py](parsers/cookware.py) (`CookwareCSVParser`)
- [parsers/twentykrecipes.py](parsers/twentykrecipes.py) (`TwentyKRecipesParser`)
- [parsers/stubs.py](parsers/stubs.py) (`CsvParser` stub)

Whenever a new CSV recipe format is encountered (such as `chefs.csv` from Chef's Catalog / QuickBook), the system either misdetects it or requires authoring custom python parsing code from scratch.

Following the design pattern established by the **SQLite** subsystem ([parsers/sqlite/sqlite_config.py](parsers/sqlite/sqlite_config.py)) and **HTML** subsystem ([parsers/html_config.py](parsers/html_config.py)), this specification defines a **YAML-configurable CSV parser subsystem**. A single `ConfigurableCsvParser` auto-discovers CSV schema definitions from `configs/*.yaml` and extracts recipes dynamically based on column names or positional column indices.

## Configuration Schema (`type: csv`)

Each CSV schema definition is stored in `configs/` (e.g. `configs/csv_*.yaml`) with the following structure:

```yaml
name: chefs_catalog
description: "Chef's Catalog / QuickBook comma-delimited export"
type: csv
version: "1.0"

csv_options:
  delimiter: ","
  has_header: false
  encoding: "latin-1"           # optional encoding hint (default utf-8 with fallback)

detection:
  filename_patterns:
    - "*chef*.csv"
  min_columns: 8
  content_patterns:
    - "^\\s*\\d{3,4}\\s*,\\s*1\\s*,"

fields:
  title:
    column_index: 5
  source:
    column_index: 6
  categories:
    column_indices: [2, 3, 4]
  ingredients:
    start_column_index: 7
    stop_marker: ""             # empty column delimiter precedes instructions
    cell_split_pattern: "\\s{3,}" # split side-by-side ingredients in single cell
  instructions:
    after_marker: ""            # instructions start after empty column delimiter
```

### Header-Based Schema Example (`configs/csv_cookware.yaml`)

```yaml
name: cookware
description: "Cookware Recipe Manager CSV export"
type: csv
version: "1.0"

csv_options:
  delimiter: ","
  has_header: true

detection:
  header_columns:
    - "Recipe"
    - "Course"
    - "Ingredients"
    - "Instructions"

fields:
  title:
    column_name: "Recipe"
  categories:
    column_name: "Course"
  yield_amount:
    column_name: "Servings"
  description:
    column_name: "Description"
  ingredients:
    column_name: "Ingredients"
    split_delimiter: "\n"
  instructions:
    column_name: "Instructions"
    split_delimiter: "\n"
```

## Input Samples

### Sample 1: Headerless, Multi-Column Recipe Dump (`chefs.csv`)
```csv
 1001 ,1,SEAFOOD,QUICHE,,Impossible Quiche,Cuisinart,1/2 lb Crab or Shrimp          3 Eggs,1/2 cup Bisquick               1 1/2 cups Milk,1/4 tsp Salt                   2 cups grated cheese,Dash of tabasco                1/2 cup melted butter,green or red peppers-onions-mushrooms-celery,(quantity suited to taste),10 1/2" pie pan,,Saute peppers-onions-mushrooms-celery in butter.,Bake 350 deg. for 45 min. (add 15 min. if made up,ahead of time),
 1002 ,1,JELLO,MOLDED,SALAD,Lime Jello Cottage Cheese Pineapple Salad,Jo Lynn Kruse,1 small can crushed pineapple,juice from 1 lemon,1/2 cup sugar,3/4 cup cottage cheese,1 cup whipping cream-whipped,1 small pkg lime jello,,Dissolve jello in 1 cup hot water,Mix above-except for cottage cheese and,whipped cream-put in refrigerator.,When thick add cottage cheese and whipped cream,Put in refrigerator to set
```

### Sample 2: Header-Based CSV (`cookware.csv`)
```csv
Recipe,Course,Servings,Prep Time,Cook Time,Ingredients,Instructions,Source
"Classic Guacamole","Appetizer","4","15 mins","0 mins","3 ripe avocados\n1 lime, juiced\n1/2 cup diced onion\n1/4 cup chopped cilantro","1. Cut avocados in half and remove pit.\n2. Mash avocados with a fork.\n3. Stir in remaining ingredients.","Chef John"
```

## Architecture & Subsystem Components

1. **`parsers/csv_config.py`**:
   - `CsvSchema`: Dataclass containing schema rules (options, detection, fields mapping).
   - `CsvConfigRegistry`: Loads and caches all `type: csv` YAML configs from `configs/`.
   - `detect_schema(filepath, sample_text)`: Evaluates candidate schemas by filename pattern, required header columns, and content regex, returning the highest-confidence `CsvSchema`.

2. **`parsers/csv_parser.py`**:
   - `ConfigurableCsvParser(BaseRecipeParser)` registered in `ParserRegistry` with priority 22.
   - Uses `CsvConfigRegistry` to find the matching schema for a `.csv` file.
   - Handles robust encoding fallbacks (`utf-8`, `cp1252`, `latin-1`).
   - Extracts title, categories, yield, description, ingredients, and instructions based on the schema's column names or indices.
   - Backward compatibility: Exports aliases `csv_cookware`, `csv_20krecipes`, and `csv_generic` to avoid breaking existing CLI options or test suites.

## Detection Contract

| Condition | Expected Score | Rationale |
|:---|:---|:---|
| Path has `.csv` + matches schema `header_columns` or `filename_patterns` | `>= 0.90` | Definitive schema match |
| Path has `.csv` + recognized generic recipe headers | `>= 0.60` | Generic CSV fallback |
| Path has `.csv` without recipe indicators or non-CSV extension | `== 0.0` | Negative assertion |

## Acceptance Criteria
- [x] `parsers/csv_config.py` implements `CsvSchema` and `CsvConfigRegistry` with auto-discovery from `configs/`
- [x] `parsers/csv_parser.py` implements `ConfigurableCsvParser` registered in `ParserRegistry`
- [x] Create YAML configuration files `configs/cookware.csv.yaml`, `configs/twentyk.csv.yaml`, and `configs/chefs.csv.yaml` (dual-identification naming)
- [x] Existing Cookware and 20krecipes CSV tests pass without regressions
- [x] Sample fixture `tests/samples/chefs.csv` added and converts cleanly with `--no-nlp`
- [x] Unit tests in `tests/unit/test_csv_config.py` and `tests/unit/test_configurable_csv_parser.py`
- [x] Full test suite passes: `./venv/bin/python3 -m pytest tests/ -v`
