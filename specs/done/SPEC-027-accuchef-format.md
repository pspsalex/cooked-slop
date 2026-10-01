---
id: SPEC-027
title: "AccuChef Format Parser"
tier: 2
type: parser
priority: P1
status: done
impact: "1 large archive file (thai-converted-mmf.out), 544 recipes"
deliverables:
  - parsers/accuchef.py
  - tests/samples/accuchef_sample.out
  - tests/expected/accuchef_sample.out.json
  - tests/unit/test_accuchef.py
---

# Spec: AccuChef Format Parser

## Description

Create a parser for the AccuChef v5.0 export/import format (`.out`, `.ac`, `.txt`) located in `/example/path/TXT/thai-converted-mmf.out`.

This archive contains 544 Thai recipes formatted with single-character line tags representing metadata, ingredients, and preparation steps, delimited by signature record headers and `Z.....End of recipe definition` terminators.

## Input Samples

### Sample 1: `tests/samples/accuchef_sample.out`
```text
*****AccuChef V5.0 Import File (C)SIVART Software http://www.AccuChef.com
AA Taste Of Thailand
BVegetables
D6
MServings
P  :  
F Recipe Source
H
IVegetable cooking spray
H1.50 Cup
IChicken broth
H1.00 Cup
IRice
H0.25 Cup
Igreen onions
KChopped
H2.00 Tsp
ISoy sauce
H0.25 Tsp
IGround red pepper
H1.00
ICarrot
Kcut into thin strips
H1.00 Clove
IGarlic
Kminced
J1 Spray a nonstick skillet with cooking spray. Heat over medium-high heat.
J2 Add chicken broth, rice, green onions, soy sauce, and pepper. Bring to a boil.
J3 Reduce heat, cover, and simmer 15 minutes. Stir in carrots and garlic; cover and simmer 5 minutes longer.
Z.....End of recipe definition
```

## Expected Behavior

### Format Structure & Tag Codes
| Tag | Meaning | Mapping |
|:---|:---|:---|
| `AA` | Recipe Title | `recipe.title` |
| `B` | Category | Added to `recipe.categories` |
| `D` | Yield quantity | Combined with `M` for `recipe.yield_amount` (e.g. `"6 Servings"`) |
| `M` | Yield unit/label | Combined with `D` for `recipe.yield_amount` |
| `F` | Source / Notes | Included in `recipe.description` |
| `H` | Ingredient quantity & unit | Quantity and unit for the subsequent `I` line |
| `I` | Ingredient name | If line starts with `-`, continuation of previous ingredient name |
| `K` | Ingredient comment/prep | Associated comment (e.g. "Chopped", "minced") |
| `J` | Instruction text | Step line; grouped into paragraphs / steps for `recipe.instructions` |
| `Z` | Recipe Record Terminator | Triggers recipe flush |

### Parser Class Specification
- **Module**: [parsers/accuchef.py](parsers/accuchef.py)
- **Class**: `AccuChefParser` inheriting from [BaseRecipeParser](parsers/base.py)
- **Decorator**: `@ParserRegistry.register`
- **`format_id()`**: `"accuchef"`
- **`aliases()`**: `['accu_chef', 'sivart']`
- **`priority()`**: `15`
- **`detect(cls, filepath: str, content_sample: str) -> float`**:
  - Return `0.99` if `*****AccuChef` is present in `content_sample`.
  - Return `0.85` if `re.search(r"^AA\s+.*?\n^[BDMH]\s*", content_sample, re.M)` is found.
  - Return `0.0` otherwise.

## Detection Contract

| Condition | Expected Score | Rationale |
|:---|:---|:---|
| Content starts with `*****AccuChef` header | `>= 0.95` | Definitive AccuChef signature |
| File contains `AA ` title and tagged `H`/`I`/`J`/`Z` lines | `>= 0.85` | Signature tagged line structure |
| Plain text or other format files without AccuChef tags | `== 0.0` | Negative assertion (must not false-positive) |

## Golden Output (Canonical JSON-LD for Sample 1)

```json
[
  {
    "@context": "https://schema.org",
    "@type": "Recipe",
    "name": "Taste Of Thailand",
    "recipeCategory": "Vegetables",
    "recipeYield": "6 Servings",
    "recipeIngredient": [
      "Vegetable cooking spray",
      {
        "@type": "PropertyValue",
        "name": "Chicken broth",
        "unitText": "cup",
        "value": 1.5
      },
      {
        "@type": "PropertyValue",
        "name": "Rice",
        "unitText": "cup",
        "value": 1.0
      },
      {
        "@type": "PropertyValue",
        "name": "green onions",
        "unitText": "cup",
        "value": 0.25
      },
      {
        "@type": "PropertyValue",
        "name": "Soy sauce",
        "unitText": "teaspoon",
        "value": 2.0
      },
      {
        "@type": "PropertyValue",
        "name": "Ground red pepper",
        "unitText": "teaspoon",
        "value": 0.25
      },
      {
        "@type": "PropertyValue",
        "name": "Carrot",
        "value": 1.0
      },
      {
        "@type": "PropertyValue",
        "name": "Garlic",
        "unitText": "clove",
        "value": 1.0
      }
    ],
    "recipeInstructions": [
      {
        "@type": "HowToStep",
        "position": 1,
        "text": "1 Spray a nonstick skillet with cooking spray. Heat over medium-high heat."
      },
      {
        "@type": "HowToStep",
        "position": 2,
        "text": "2 Add chicken broth, rice, green onions, soy sauce, and pepper. Bring to a boil."
      },
      {
        "@type": "HowToStep",
        "position": 3,
        "text": "3 Reduce heat, cover, and simmer 15 minutes. Stir in carrots and garlic; cover and simmer 5 minutes longer."
      }
    ]
  }
]
```

## Acceptance Criteria
- [ ] [parsers/accuchef.py](parsers/accuchef.py) implemented with `@ParserRegistry.register`
- [ ] Registered and exported in `parsers/__init__.py`
- [ ] Auto-detection matches `thai-converted-mmf.out` with score >= 0.95
- [ ] Multi-recipe generator extracts all recipes (testing on sample and validating against full archive)
- [ ] Golden test sample and expected output added
- [ ] All unit and regression tests pass: `./venv/bin/python3 -m pytest tests/ -v`

## Deliverables
- `parsers/accuchef.py`
- `tests/samples/accuchef_sample.out`
- `tests/expected/accuchef_sample.out.json`
- `tests/unit/test_accuchef.py`
