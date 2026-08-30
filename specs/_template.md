---
id: SPEC-NNN
title: "Feature or Parser Title"
tier: 2
type: html-config      # html-config | parser | script | review
priority: P1           # P0 | P1 | P2
status: active         # active | done | blocked
impact: "Estimated file count / recipe count"
deliverables:
  - configs/example.yaml
---

# Spec: [Title]

## Description

Provide a clear explanation of what this specification accomplishes, what data or source it addresses, and the expected pipeline outcome.

## Input Samples

### Sample 1: `path/to/sample.ext`
**Location:** `/home/alex/junk/Recipes/Ingest/ToDo/...`

```text
[Paste representative raw input data here]
```

## Expected Behavior

### Field Mapping
- **Title**: How title is determined
- **Ingredients**: How ingredients are identified and split
- **Instructions**: How instructions are extracted and structured
- **Yield / Metadata**: Servings, categories, author, etc.

### Edge Cases
1. Missing fields
2. Unorthodox delimiters or formatting
3. Embedded multi-recipes

## Acceptance Criteria
- [ ] Deliverable file(s) exist and adhere to project standards
- [ ] Auto-detection correctly matches target input files (score >= 0.5 without explicit flags if applicable)
- [ ] Conversion produces valid Schema.org JSON-LD output matching acceptance test fixtures
- [ ] Full test suite passes: `./venv/bin/python3 -m pytest tests/ -v`

## Deliverables
- `configs/example.yaml` or `parsers/example.py`
- `tests/samples/sample_file.ext`
- `tests/expected/sample_file.ext.json`

## Reference
- `parsers/cookware.py` — Reference parser implementation
- `parsers/html_config.py` — HTML configuration schema
