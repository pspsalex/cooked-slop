# Spec: Batch Conversion Runner
## Tier: 1
## Type: script
## Priority: P0
## Estimated file impact: ~6,500 files

## Description

Create a `batch_convert.py` script that runs `convert.py` against all processable files in `/home/alex/junk/Recipes/Ingest/ToDo`, logs results, and separates successes from failures.

This is the first step in the pipeline — it identifies which files the existing parsers can already handle and which need Tier 2/3 work.

## Behavior

### Input
- Root directory: `/home/alex/junk/Recipes/Ingest/ToDo`
- Skip list (directories to exclude):
  - `TXT/breadbakers/splitted/`
  - `TXT/breadbakers/*.txt` (raw unsplit digests — only process `split/`)
  - `HTML/fareshare/` (index pages, no recipes)
  - `HTML/fareshare/images/` (food photos)
  - `HTML/Italian Recipes (from Veneto)/` (handled elsewhere)
  - Any `*.jpg`, `*.jpeg`, `*.png`, `*.gif`, `*.bmp` image files
  - Any `*.mht` files
  - `HTML/out.json` (output file, not input)

### Processing
For each non-skipped file:
1. Run `convert.py` with auto-detection (no `--format` override, no `--html-config`)
2. Use `--no-nlp` for deterministic results
3. Capture: file path, detected parser, number of recipes extracted, success/error status, error message if any
4. Write output JSON to a structured output directory mirroring the input hierarchy

### Output
1. **Results CSV** at `batch_results.csv`:
   ```
   file,parser,recipes_extracted,status,error
   TXT/Singles/CARAMEL FROSTED TURTLE BROWNIES.txt,generic_text,1,ok,
   TXT/DRINKS.OUT,generic_text,0,empty,"No recipes extracted"
   HTML/cs.cmu/appetizers/beer-battered-nuggets.html,html,0,error,"No config matched"
   ```

2. **Output directory**: JSON-LD files at `batch_output/` mirroring input structure

3. **Summary stats** printed to stdout:
   ```
   Total files: 19504
   Skipped: 2661
   Success (≥1 recipe): 6523
   Empty (0 recipes): 4210
   Error: 8771
   Total recipes extracted: 7842
   ```

### Implementation Notes
- Use `subprocess` to call `convert.py` (same pattern as `tests/test_conversion.py`)
- Use `sys.executable` for the Python binary (never bare `python3`)
- Handle timeouts: 30 second per-file timeout for conversion
- Handle encoding errors gracefully (some old BBS files have non-UTF-8 encoding)
- Add `--dry-run` flag to just list files that would be processed without converting
- Add `--resume` flag to skip files that already have output in `batch_output/`
- Add `--dir` flag to override the default input directory
- Use multiprocessing or `concurrent.futures` for speed (configurable `--workers N`, default 4)

## Acceptance Criteria
- [ ] Script runs without errors on a `--dry-run` of the full ToDo directory
- [ ] Script converts at least 10 sample files successfully
- [ ] Results CSV is valid and parseable
- [ ] Skip list correctly excludes fareshare, splitted, images, etc.
- [ ] `--resume` flag works correctly
- [ ] No crashes on encoding errors or binary files

## Deliverables
- `batch_convert.py` in the project root (`/home/alex/junk/Recipes/scripts/`)

## Reference
- `tests/test_conversion.py` — subprocess invocation pattern
- `convert.py` — CLI flags and conversion pipeline
