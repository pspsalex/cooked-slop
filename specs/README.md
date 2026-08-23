# Recipe ToDo Specs — Agent Execution Guide

## Overview

This directory contains self-contained specification files for processing the recipe files in `/home/alex/junk/Recipes/Ingest/ToDo`. Each spec describes a single, independent task that an agent can implement without coordination.

## Tiers

| Tier | Type | Description |
|:---|:---|:---|
| **Tier 1** | Script | Batch conversion using existing parsers |
| **Tier 2** | HTML Config | YAML XPath configs for specific websites |
| **Tier 3** | Parser / Script | New parsers for niche formats + extract scripts |

## How to Trigger a Spec

### Single spec execution

```
Work on the spec at scripts/specs/tier2-cscmu.md — read it carefully, implement everything described, verify the acceptance criteria, and commit with a conventional-commit message.
```

### Multiple specs in sequence

```
Work through all tier2-*.md specs in scripts/specs/ — implement each one, run tests after each, and commit separately with conventional-commit messages.
```

### Model selection

Specs are designed to be self-contained enough for smaller models. Use **Flash** model tier when launching agents to control costs.

## Spec Format

Each spec contains:

- **Description**: What the task produces
- **Input Samples**: Paths + inline content of representative files
- **Expected Behavior**: Field mapping and extraction rules
- **Acceptance Criteria**: Concrete checks the agent must pass
- **Deliverables**: Exact file paths to create or modify
- **Reference**: Existing implementations to study

## Key References

All agents should read `AGENTS.md` in the project root before starting work. Key files:

| File | Purpose |
|:---|:---|
| `parsers/cookware.py` | Reference parser implementation (copy structure from here) |
| `parsers/base.py` | Base class all parsers inherit from |
| `parsers/models.py` | `Recipe` and `Ingredient` dataclasses |
| `parsers/registry.py` | `@ParserRegistry.register` decorator |
| `parsers/__init__.py` | All parser imports + `__all__` |
| `parsers/html_config.py` | HTML YAML config schema |
| `parsers/html_parser.py` | HTML parser (uses YAML configs) |
| `configs/*.yaml` | Existing YAML configs for reference |
| `convert.py` | CLI entry point |
| `tests/test_conversion.py` | Regression test suite |

## Commands

```bash
# Convert a single file
./venv/bin/python3 convert.py <input_file> -o <output.json> --no-nlp

# Convert with HTML config
./venv/bin/python3 convert.py <input.html> --html-config configs/<config>.yaml -o <output.json> --no-nlp

# Run all tests
./venv/bin/python3 -m pytest tests/ -v

# Generate expected test output (always use --no-nlp for determinism)
./venv/bin/python3 convert.py tests/samples/<file> -o tests/expected/<file>.json --no-nlp
```
