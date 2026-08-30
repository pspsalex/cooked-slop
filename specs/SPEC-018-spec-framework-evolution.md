---
id: SPEC-018
title: "Spec Framework Standards and Validation"
tier: 0
type: review
priority: P2
status: active
impact: "Formalizes Golden Output fixtures and Detection Contracts in specs; adds automated pytest validation for all specs"
deliverables:
  - specs/_template.md
  - specs/README.md
  - tests/test_specs.py
---

# Spec: Spec Framework Standards and Validation

## Description

The project uses a spec-driven development model where specifications in `specs/` serve as self-contained prompts and design artifacts for AI agents and human developers. However, review analysis identified three areas of improvement:
1. **Missing Golden Output Fixtures**: Specs describe field mapping rules in prose, but lack canonical expected JSON-LD output blocks. Without an exact golden output fixture, test fixtures must be reverse-engineered or manually guessed by lesser models.
2. **Missing Detection Contracts**: Specs rarely document the expected detection scoring behavior (e.g. extension weight, keyword triggers, and negative assertions that non-matching samples must return `0.0`). This has caused score inflation and format collisions.
3. **No Schema Validation for Specs**: Spec frontmatter (`id`, `title`, `tier`, `type`, `priority`, `status`, `deliverables`) and structure are enforced only by convention, not automated tests.

This specification:
1. Updates `specs/_template.md` with standard `## Detection Contract` and `## Golden Output` sections.
2. Updates `specs/README.md` to document the golden fixture expectations.
3. Adds `tests/test_specs.py` to validate frontmatter and formatting across all active and archived specs.

## Worktree & Branch Protocol

Following repository golden rules:
```bash
git worktree add -b feat/spec-018-spec-standards .worktrees/spec-018 main
cd .worktrees/spec-018
```
After verification, commit, merge to `main`, and remove worktree.

---

## Detailed Specification

### 1. `specs/_template.md` Enhancements

Add two standard sections to `_template.md`:

```markdown
## Detection Contract

| Condition | Expected Score | Rationale |
|:---|:---|:---|
| Path matches format pattern + content matches signature | `>= 0.85` | Definitive format match |
| Content matches signature without distinctive filename | `>= 0.60` | Content-only match |
| Generic text or HTML without signature markers | `== 0.0` | Negative assertion (must not false-positive) |

## Golden Output (Canonical JSON-LD)

```json
{
  "@context": "https://schema.org",
  "@type": "Recipe",
  "name": "Sample Recipe Title",
  "recipeIngredient": [
    {
      "@type": "PropertyValue",
      "name": "flour",
      "value": 2,
      "unitText": "cup"
    }
  ],
  "recipeInstructions": [
    {
      "@type": "HowToStep",
      "position": 1,
      "text": "Combine ingredients."
    }
  ],
  "recipeYield": "4 servings",
  "recipeCategory": "Dessert"
}
```
```

### 2. `specs/README.md` Updates

Document that all new parser and config specs must include:
- A Detection Contract table with both positive triggers and negative `0.0` assertions.
- A Golden Output JSON block matching the expected output when run with `--no-nlp`.

### 3. `tests/test_specs.py` (Automated Spec Validator)

Create an automated test suite validating all specs:

```python
# SPDX-License-Identifier: MIT
"""Automated validation of specification frontmatter and structure."""
from pathlib import Path
import re
import pytest
import yaml

SPECS_DIR = Path(__file__).parent.parent / "specs"

def get_all_specs():
    specs = list(SPECS_DIR.glob("SPEC-*.md"))
    specs.extend((SPECS_DIR / "done").glob("SPEC-*.md"))
    return specs

@pytest.mark.parametrize("spec_path", get_all_specs(), ids=lambda p: p.name)
def test_spec_frontmatter_validity(spec_path: Path):
    content = spec_path.read_text(encoding="utf-8")
    assert content.startswith("---"), f"{spec_path.name} must start with YAML frontmatter"

    parts = content.split("---", 2)
    assert len(parts) >= 3, f"{spec_path.name} has malformed frontmatter delimiter"

    fm = yaml.safe_load(parts[1])
    assert isinstance(fm, dict), f"{spec_path.name} frontmatter is not a dictionary"

    required_keys = {"id", "title", "tier", "type", "priority", "status", "deliverables"}
    missing = required_keys - set(fm.keys())
    assert not missing, f"{spec_path.name} is missing frontmatter keys: {missing}"

    assert fm["status"] in {"active", "done", "blocked"}, f"Invalid status in {spec_path.name}"
    assert fm["priority"] in {"P0", "P1", "P2"}, f"Invalid priority in {spec_path.name}"
    assert isinstance(fm["deliverables"], list), f"{spec_path.name} deliverables must be a list"
```

---

## Edge Cases

1. **Done Directory Specs**: Completed specs in `specs/done/` may use slightly older frontmatter schemas; ensure validator handles completed specs gracefully or backfills missing optional keys.
2. **Template File Exclusion**: `specs/_template.md` should not be tested as a runnable spec since it contains placeholder values like `SPEC-NNN`.

---

## Acceptance Criteria

- [ ] `specs/_template.md` contains `## Detection Contract` and `## Golden Output` sections.
- [ ] `specs/README.md` documents detection scoring rules and golden output guidelines.
- [ ] `tests/test_specs.py` validates frontmatter structure, status, and required fields across all specifications.
- [ ] Pytest runs `test_specs.py` and passes: `./venv/bin/python3 -m pytest tests/test_specs.py -v`.

---

## Verification Plan

```bash
./venv/bin/python3 -m pytest tests/test_specs.py -v
```
