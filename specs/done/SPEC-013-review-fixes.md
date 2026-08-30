---
id: SPEC-013
title: "Code Review Fixes — Unpushed Commits"
tier: 0
type: review
priority: P1
status: done
impact: "6 fixes across 4 files"
deliverables: []
---

# Code Review Fixes — Unpushed Commits (19 ahead of origin/main)

## Scope

Code review of commits `bc24c60..a14ff4c` (19 unpushed commits on `main`).
All 68 tests pass. Three trivial fixes were applied directly; the remaining
issues are documented below for a follow-up pass.

---

## Fix 1: `convert.py` — Missing `KeyboardInterrupt` handler

**File:** `convert.py`, `main()` function (around line 622–661)  
**Severity:** Medium  
**Category:** UX / robustness

### Problem

The old code had a `try/except KeyboardInterrupt` block wrapping the conversion
that cleanly printed a message and returned exit code 1. The refactored code
replaced it with `try/finally` (to close the `stream_writer`), but dropped the
`KeyboardInterrupt` handler entirely. Now `Ctrl-C` produces an ugly traceback
instead of a clean exit.

### Fix

Add a `except KeyboardInterrupt` clause **before** the `finally` in `main()`:

```python
    try:
        if input_path.is_dir():
            process_directory(...)
        else:
            convert_recipe_file(...)
    except KeyboardInterrupt:
        print(f"\n\n{Colors.RED}Forced exit - data may be incomplete{Colors.ENDC}\n")
        return 1
    finally:
        if stream_writer:
            stream_writer.close()
```

The `finally` block still fires (closing the writer) before the `return 1`.

### Verification

- Run `./venv/bin/python3 convert.py <large-dir> -o /tmp/out.json -v` and press
  `Ctrl-C` during conversion.
- Confirm clean one-line message instead of traceback.
- Confirm the partial output JSON is valid (stream_writer closed properly).

---

## Fix 2: `convert.py` — Non-verbose single-file mode shows no progress

**File:** `convert.py`, `main()` function (around line 637–654)  
**Severity:** Low  
**Category:** UX

### Problem

The old code showed a progress bar for single-file conversions in non-verbose
mode. The refactored version only prints output in verbose mode
(`convert_recipe_file` prints only `if verbose`). In non-verbose single-file
mode, the user sees only the banner, then the "Conversion finished" message with
zero feedback in between.

### Fix

Add a single-file non-verbose progress indicator in the `else` branch of
`main()`. Either:
- Print `Converting: <filename>` before calling `convert_recipe_file`, or
- After returning from `convert_recipe_file`, print a completion summary line.

Simplest approach — add before the call:

```python
        else:
            if not args.verbose:
                print(f"  {Colors.CYAN}Converting:{Colors.ENDC} {input_path.name}")
            convert_recipe_file(...)
```

### Verification

- `./venv/bin/python3 convert.py tests/samples/garvick_sample.html -o /tmp/out.json --no-nlp`
- Confirm "Converting: garvick_sample.html" appears between banner and completion message.

---

## Fix 3: `batch_convert.py` — `timeout` parameter not passed through from CLI

**File:** `batch_convert.py`, `run_batch_conversion()` and `convert_file_job()`  
**Severity:** Low  
**Category:** Bug / missing feature

### Problem

`convert_file_job()` accepts a `timeout` parameter (default 30s), but
`run_batch_conversion()` hardcodes no timeout kwarg in the `executor.submit()` call
(so it uses the default 30s). The CLI has no `--timeout` flag, so users can't
control it. 30 seconds is very tight for large files.

### Fix

1. Add a `--timeout` CLI argument to `main()`:
   ```python
   parser.add_argument(
       "--timeout", type=int, default=120,
       help="Per-file timeout in seconds (default: 120)",
   )
   ```

2. Thread it through `run_batch_conversion()`:
   ```python
   def run_batch_conversion(
       ..., timeout: int = 120, ...
   ) -> int:
   ```

3. Pass it in `executor.submit()`:
   ```python
   executor.submit(
       convert_file_job, input_dir, rel_path, output_dir, convert_script,
       resume=resume, timeout=timeout,
   )
   ```

### Verification

- `./venv/bin/python3 batch_convert.py --dir tests/samples --output-dir /tmp/batch --csv /tmp/results.csv --timeout 5 -v`
- Confirm timeout value is respected.

---

## Fix 4: `parsers/llm_parser.py` — Hardcoded localhost fallback URL

**File:** `parsers/llm_parser.py`, `LLMClient.chat()` (around line 230)  
**Severity:** Medium  
**Category:** Correctness / config hygiene

### Problem

When the OpenAI-compatible endpoint returns a 404 and the `base_url` doesn't
contain `/v1`, the fallback URL is hardcoded to `http://localhost:11434/api/chat`.
This silently ignores any host/port the user configured (e.g. a remote Ollama
instance on a different machine or port).

```python
fallback_url = (
    f"{self.base_url.split('/v1')[0].rstrip('/')}/api/chat"
    if "/v1" in self.base_url
    else "http://localhost:11434/api/chat"   # ← hardcoded
)
```

### Fix

Always derive the fallback from the configured `base_url`:

```python
# Strip path components and build Ollama native endpoint
from urllib.parse import urlparse, urlunparse
parsed = urlparse(self.base_url.rstrip("/"))
base_origin = urlunparse((parsed.scheme, parsed.netloc, "", "", "", ""))
fallback_url = f"{base_origin}/api/chat"
```

### Verification

- Unit test: Mock a 404 on `http://myserver:11434/v1/chat/completions` and
  verify fallback hits `http://myserver:11434/api/chat` (not localhost).
- Existing `test_marked_llm_parser.py` tests should still pass.

---

## Fix 5: `parsers/html_config.py` — `_parse_garvick_recipes` oversized function with magic strings

**File:** `parsers/html_config.py`, lines 217–344  
**Severity:** Low  
**Category:** Maintainability

### Problem

`_parse_garvick_recipes()` is 128 lines with a large inline list of hardcoded
filter keywords (line 245–252) embedded directly in the function body. This makes
it hard to maintain, test, or extend the filter list.

### Fix

Extract the keyword filter list to a module-level constant:

```python
_GARVICK_TITLE_EXCLUDE_KEYWORDS = frozenset([
    "tip:", "barbeque tip:", "links to", "click here", "recipes:",
    "site map", "privacy policy", "free recipes", "garvick home",
    "top 100", "for book lovers", "for chocolate lovers", "for candy lovers",
    "for movie buffs", "for cookie lovers", "for a child", "bath products",
    "your own creations", "recipe of the month", "chill dough overnight.",
    "try this recipe", "back to annual events", "annual events",
    "easter crafts", "easter games", "easter gifts", "easter recipes",
    "garnish:",
])
```

Then in the loop:
```python
if any(kw in t_lower for kw in _GARVICK_TITLE_EXCLUDE_KEYWORDS):
    continue
```

### Verification

- `./venv/bin/python3 -m pytest tests/test_conversion.py -k garvick -v`
- `./venv/bin/python3 -m pytest tests/test_detection.py -v`

---

## Fix 6: `parsers/base.py` — `get_display_name()` suffix logic is misleading

**File:** `parsers/base.py`, `get_display_name()` (lines 23–28)  
**Severity:** Very low  
**Category:** Cosmetic / code clarity

### Problem

The check `if not fmt.lower().endswith("parser")` always appends " Parser",
but the preceding line strips "Parser" from the class name. So
`GenericMdParser` → `GenericMd` → `GenericMd Parser`. But `MealMasterParser`
→ `MealMaster` (source_format) → `MealMaster Parser`. This is fine but the
intermediate step of checking `endswith("parser")` on `fmt` is redundant since
`fmt` already has "Parser" stripped and `source_format` values never end in
"Parser". The check is dead code.

### Fix

Remove the condition and always append `" Parser"`:

```python
def get_display_name(self, filepath: str | None = None) -> str:
    fmt = self.source_format
    if not fmt or fmt == "Unknown":
        fmt = self.__class__.__name__.replace("Parser", "")
    return f"{fmt} Parser"
```

### Verification

- `./venv/bin/python3 -m pytest tests/test_detection.py::test_parser_display_names -v`
