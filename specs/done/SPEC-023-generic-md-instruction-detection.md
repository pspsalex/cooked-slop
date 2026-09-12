---
id: SPEC-023
title: "Generic Markdown Instruction Detection Fixes"
tier: 2
type: parser
priority: P1
status: done
impact: "Improves parsing of converted DOCX/MD recipe collections"
deliverables:
  - parsers/generic_md.py
---

# Spec: Generic Markdown Instruction Detection Fixes

## Description

The `GenericMdParser` fails to transition from the `INGREDIENTS` state to the `INSTRUCTIONS` state for certain recipe formats, resulting in instructions being incorrectly parsed as ingredients. The current heuristic (`_looks_like_instruction_start`) is too restrictive regarding the verbs it considers as instruction starters and the presence of `cooking_keywords`. 

## Input Samples

### Sample 1: `Grilled Salmon with Jalapeno Butter`
**Source:** `LowCarbohydrateCooking-Recipes.docx.md` (Line 8755)

```text
To prepare the butter: Combine gingerroot, garlic and jalapeno in a
blender container or food processor bowl; cover and process till finely
chopped. Add cilantro; cover and blend or process till combined. Stir
```

**Issue:** `To prepare` is not recognized as an instruction verb, and the sentence does not contain enough matching `cooking_keywords` to trigger the fallback, causing this instruction to be parsed as an ingredient.

### Sample 2: `Crab Meat Mousse`
**Source:** `LowCarbohydrateCooking-Recipes.docx.md` (Line 1587)

```text
1 T prepared mustard

Salt and pepper to taste

2 C flaked cooked crab meat

3/4 C whipping cream, whipped

Slices of lime

2 avocados, mashed

Soften gelatine in cold water and dissolve in double boiler over hot
water. Mix gelatine with mayonnaise, lime and lemon juice, parsley,
```

**Issue:** `Soften` is not recognized as an instruction verb. Additionally, no `cooking_keywords` are found, so the entire paragraph is appended to the `recipeIngredient` list.

## Expected Behavior

### Field Mapping
- **Instructions**: Lines starting with terms like `To prepare...` or `Soften...` should correctly transition the parser to the `INSTRUCTIONS` state and be appended to `recipeInstructions`.

### Edge Cases
1. **Brenna's Antipasto Platter (Line 1571)**: The format contains a list of foods (e.g., `Sliced cheeses`, `Salami`) without explicit quantities or bullets. The parser fails to enter the `INGREDIENTS` state. **This format is considered too complex/irregular and can be explicitly ignored for this implementation.**

## Acceptance Criteria
- [x] Add `to\s+prepare\b` and `soften\b` (and any other missing common preparation verbs) to `instruction_verbs` in `parsers/generic_md.py`.
- [x] Expand `cooking_keywords` if necessary to better detect narrative instructions.
- [x] Generate expected test fixtures using `--no-nlp` and verify they capture instructions correctly.
- [x] Full test suite passes: `./venv/bin/python3 -m pytest tests/ -v`

## Deliverables
- Modified `parsers/generic_md.py`
