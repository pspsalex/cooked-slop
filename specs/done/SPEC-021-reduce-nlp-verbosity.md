---
id: SPEC-021
title: "Reduce NLP Verbosity Under -v Flag"
tier: 1
type: refactor
priority: P1
status: done
impact: "Reduces noisy stdout debug output from ingredient-parser under -v while providing -vv and --debug-nlp for troubleshooting"
deliverables:
  - convert.py
  - tests/unit/test_logging.py
---

# Spec: Reduce NLP Verbosity Under -v Flag

## Description

When running recipe conversions with the `-v` / `--verbose` flag, `convert.py` sets the root logger level to `logging.DEBUG`. Because the third-party `ingredient-parser-nlp` library uses Python standard logging under the logger names `ingredient-parser`, `ingredient_parser`, and `nltk`, every single ingredient parsed with the NLP parser emits 15–20 lines of internal preprocessing debug logs (e.g. `DEBUG:ingredient-parser.preprocess:_remove_price_annotations`, `_replace_html_fractions`, `combine_quantities_split_by_and`, etc.).

For a recipe with 10–20 ingredients, a single file conversion produces hundreds of lines of internal regex and tokenization trace output, completely overwhelming the user-facing conversion progress (such as `✓ Recipe Title` and parser detection results).

This specification addresses the issue by:
1. Changing `-v` / `--verbose` from a boolean `action="store_true"` to a counter `action="count", default=0`.
2. Adding a dedicated `--debug-nlp` CLI flag (analogous to `--debug-sql`) to explicitly enable verbose NLP debug output.
3. Decoupling application/conversion verbosity from NLP library verbosity:
   - `-v`: Shows conversion progress, parser detection, and application debug logs, while suppressing `ingredient-parser` debug logs (setting their level to `logging.INFO` or higher).
   - `-vv` (or higher count) OR `--debug-nlp`: Shows full debug logging including detailed NLP preprocessing steps.
4. Preserving backward compatibility for boolean checks on `args.verbose` and helper function signatures.

## Input Samples / Invocation Matrix

### 1. Default (No Verbose Flags)
```bash
./venv/bin/cook tests/samples/GERMAN.MMF -o /tmp/out.json
```
- Root logging: `INFO`
- NLP loggers (`ingredient-parser`, `ingredient_parser`, `nltk`): `INFO` (or `WARNING`)
- Terminal: Clean progress bar / final summary.

### 2. Standard Verbose (`-v` or `--verbose`)
```bash
./venv/bin/cook tests/samples/GERMAN.MMF -o /tmp/out.json -v
```
- Root logging: `DEBUG`
- Application logs: Emitted
- NLP loggers (`ingredient-parser`, `ingredient_parser`, `nltk`): Suppressed to `INFO`
- Terminal: Shows detected parser, per-recipe status (`✓ Apfelquarkkuchen`), and application debug information without being flooded by ingredient preprocessing traces.

### 3. Detailed Verbose (`-vv` or `--debug-nlp`)
```bash
./venv/bin/cook tests/samples/GERMAN.MMF -o /tmp/out.json -vv
# or
./venv/bin/cook tests/samples/GERMAN.MMF -o /tmp/out.json -v --debug-nlp
```
- Root logging: `DEBUG`
- NLP loggers (`ingredient-parser`, `ingredient_parser`, `nltk`): Set to `DEBUG`
- Terminal: Shows full NLP preprocessing, sentence normalizations, and foundation model inference traces for troubleshooting ingredient extraction.

## Expected Behavior

### CLI Flag Specifications

| Flag | Type | Default | Description |
|:---|:---|:---|:---|
| `-v`, `--verbose` | `action="count"` | `0` | Verbosity level: `1` (`-v`) for conversion/app details, `>= 2` (`-vv`) for deep NLP debug traces |
| `--debug-nlp` | `action="store_true"` | `False` | Explicitly enable detailed NLP ingredient parser debug logging |
| `--debug-sql` | `action="store_true"` | `False` | Existing flag; explicitly enables SQL queries at TRACE level |

### Logging Hierarchy Configuration

Logging configuration in `convert.py` should be encapsulated in a helper function `configure_logging(verbose: int = 0, debug_sql: bool = False, debug_nlp: bool = False)`:

```python
NLP_LOGGERS = ("ingredient-parser", "ingredient_parser", "nltk")

def configure_logging(verbose: int = 0, debug_sql: bool = False, debug_nlp: bool = False) -> None:
    if debug_sql:
        log_level = TRACE_LEVEL
    elif verbose >= 1:
        log_level = logging.DEBUG
    else:
        log_level = logging.INFO

    logging.basicConfig(
        level=log_level,
        format="%(name)s - %(levelname)s - %(message)s",
        force=True,
    )

    # NLP logging: only DEBUG if -vv or --debug-nlp
    nlp_level = logging.DEBUG if (debug_nlp or verbose >= 2) else logging.INFO
    for logger_name in NLP_LOGGERS:
        logging.getLogger(logger_name).setLevel(nlp_level)
```

### Edge Cases

1. **Repeated flags**: `-vvv` or `-v -v` sets `verbose = 2` or `3`, maintaining `nlp_level = logging.DEBUG`.
2. **`--verbose` single use**: Sets `verbose = 1`, which enables application DEBUG but keeps NLP at `INFO`.
3. **`--no-nlp` with `-v`**: When `--no-nlp` is passed, regex parsing is used; NLP log level configuration is a safe no-op.
4. **`--debug-nlp` without `-v`**: Sets NLP loggers to `DEBUG` and ensures root log level is at least `DEBUG` (or configures handlers) so that NLP debug records are emitted.
5. **Calls to `convert_recipe_file` and `process_directory`**: Signatures accept `verbose: bool | int = False`. Passing `bool(args.verbose)` ensures complete compatibility with existing callers and tests.

## Worktree & Branch Protocol

Following repository golden rules:
```bash
git worktree add -b feat/spec-021-nlp-verbosity .worktrees/spec-021 main
cd .worktrees/spec-021
```
After implementation and verification, commit with conventional commit message (`refactor(cli): reduce nlp verbosity under -v and add --debug-nlp`), merge `--ff-only` to `main`, and remove worktree.

## Acceptance Criteria

- [x] CLI argument `-v` / `--verbose` uses `action="count", default=0` in `convert.py`.
- [x] New CLI argument `--debug-nlp` is registered in `convert.py`.
- [x] A single `-v` outputs conversion details and application debug logs without `ingredient-parser` preprocessing debug lines.
- [x] Multiple `-v`s (e.g. `-vv`) or `--debug-nlp` outputs `ingredient-parser` debug logs.
- [x] Unit tests in `tests/unit/test_logging.py` verify verbosity counting, flag handling, and logger level configurations.
- [x] Existing test suites (`tests/test_conversion.py`, `tests/test_detection.py`, `tests/test_specs.py`) pass without regressions.
- [x] Documentation in `AGENTS.md` and `CLAUDE.md` updated with `--debug-nlp` and `-vv` usage.

## Deliverables

- `convert.py`
- `tests/unit/test_logging.py`
- Documentation updates in `AGENTS.md` and `CLAUDE.md`
