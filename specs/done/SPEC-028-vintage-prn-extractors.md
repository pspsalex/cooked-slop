---
id: SPEC-028
title: "Vintage Recipe PRN Print Dump Normalizer and Extractor"
tier: 2
type: script
priority: P1
status: done
impact: "~10 printer dump files in Ingest/ToDo/TXT/ unlocking ~500 vintage recipes"
deliverables:
  - tools/extract/prn_normalizer.py
  - tests/samples/vintage_prn_sample.prn
  - tests/expected/vintage_prn_sample.prn.json
  - tests/unit/test_prn_normalizer.py
---

# Spec: Vintage Recipe PRN Print Dump Normalizer and Extractor

## Description

Create a multi-format normalizer and extractor tool in [tools/extract/prn_normalizer.py](tools/extract/prn_normalizer.py) to process legacy printer dump files (`.PRN`, `.prn.txt`) located in `/example/path/TXT/`.

Legacy DOS recipe programs frequently dumped formatted reports directly to printer ports (`LPT1:`) containing PCL printer escape codes, form feed (`\x0c`) page breaks, running headers, and ASCII box-drawing borders. Currently, these files either fail conversion completely or collapse multiple distinct recipes into a single mangled recipe.

## Target Print Dump Formats

1. **MasterCook Print Dumps (`holiday.prn`)**:
   - Contains multiple MasterCook recipes printed with running headers (e.g. `Page 1 (C) Copyright 1995 - One Command Software Inc.`).
   - Normalizer strips page headers and splits recipes at `Serving Size :` boundaries so [parsers/mastercook.py](parsers/mastercook.py) can parse each recipe cleanly without `Ingredient after instruction` errors.
2. **Form-Feed Labelled Reports (`cb_100.prn`)**:
   - Delimited by `\x0c` with labels: `This recipe makes :`, `Estimated Time :`, `Ingredients :`, `Instructions :`, `See Also :`.
   - Normalizes directly to Generic Markdown format (`# Title`, `## Ingredients`, `## Instructions`).
3. **Recipe Card Box Printouts (`mmm150.prn.txt`, `mmm151.prn.txt`)**:
   - PCL escapes (e.g. `\x1b(s1Q\x1b(s5H...`) and ASCII box tables (`| CATEGORY: ... | SERVINGS: ... |`, `|================|`).
   - Normalizer strips PCL escape sequences, unpacks tabular ingredients, and exports clean markdown.
4. **Classic Recipe Printout (`prcb.prn`)**:
   - Delimited by `Recipe Printout` and `Recipe No. NN`.
   - Contains fields `Main Category--`, `Sub-Category---`, `Recipe Name----`, `Ingredient's:`, `Recipe:`.
5. **Asterisk Banner Delimited (`tcs.prn`, `cakes-bakes.prn.txt`)**:
   - Recipes separated by `***********************************************************************`.

## Expected CLI Interface

```bash
./venv/bin/python3 tools/extract/prn_normalizer.py input.prn [-o output.md] [--in-place]
```
- When converted to `.md`, outputs are tagged with `<!-- format: generic_md -->` so they are immediately ingestible by `cook` / `convert.py`.

## Golden Output (Canonical JSON-LD for `cb_100.prn` first recipe)

```json
[
  {
    "@context": "https://schema.org",
    "@type": "Recipe",
    "name": "Chocolate Fudge Brownies",
    "recipeIngredient": [
      {
        "@type": "PropertyValue",
        "name": "butter",
        "unitText": "gram",
        "value": 125.0
      },
      {
        "@type": "PropertyValue",
        "name": "dark cooking chocolate",
        "unitText": "gram",
        "value": 185.0
      },
      {
        "@type": "PropertyValue",
        "name": "sugar",
        "unitText": "cup",
        "value": 0.75
      },
      {
        "@type": "PropertyValue",
        "name": "eggs",
        "value": 2.0
      },
      {
        "@type": "PropertyValue",
        "name": "plain flour",
        "unitText": "cup",
        "value": 1.0
      },
      {
        "@type": "PropertyValue",
        "name": "chopped walnuts",
        "unitText": "cup",
        "value": 1.0
      }
    ],
    "recipeInstructions": [
      {
        "@type": "HowToStep",
        "position": 1,
        "text": "Melt chocolate and butter together in pan over low heat, stir in sugar and eggs one at a time, beat well with wooden spoon, then stir in sifted flour and walnuts. Pour into greased 20cm square baking tin. Bake in moderate oven 30 minuts, cool in tin."
      }
    ]
  }
]
```

## Acceptance Criteria
- [ ] [tools/extract/prn_normalizer.py](tools/extract/prn_normalizer.py) correctly handles `holiday.prn`, `cb_100.prn`, `mmm150.prn.txt`, `prcb.prn`, and `tcs.prn`
- [ ] Strips PCL escape sequences (`\x1b\([a-zA-Z0-9]+` / `\x1b&[a-zA-Z0-9.]+`) and form feeds (`\x0c`)
- [ ] Successfully converts `holiday.prn` into valid MasterCook or Markdown recipes without parser exceptions
- [ ] Unit tests in `tests/unit/test_prn_normalizer.py` cover all 5 signature dump variants
- [ ] Full test suite passes: `./venv/bin/python3 -m pytest tests/ -v`

## Deliverables
- `tools/extract/prn_normalizer.py`
- `tests/samples/vintage_prn_sample.prn`
- `tests/expected/vintage_prn_sample.prn.json`
- `tests/unit/test_prn_normalizer.py`
