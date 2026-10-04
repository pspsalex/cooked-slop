---
id: SPEC-029
title: "Consolidate Directory Batch Conversion into convert.py and Remove batch_convert"
tier: 1
type: refactor
priority: P0
status: active
impact: "Core CLI and pipeline consolidation"
deliverables:
  - convert.py
  - pyproject.toml
  - AGENTS.md
  - tests/test_directory_convert.py
---

# Spec: Consolidate Directory Batch Conversion into convert.py and Remove batch_convert

## Tier: 1
## Type: refactor
## Priority: P0
## Estimated file impact: Entire Ingest collection (21,271+ files)

## Description

Consolidate directory batch conversion functionality directly into `convert.py` and eliminate the redundant `batch_convert.py` runner script and its `recipe-batch` CLI entrypoint.

Historically, `batch_convert.py` was introduced in SPEC-001 as an exploratory diagnostic test harness that spawned a separate `python3` subprocess for every single file. This resulted in an enormous performance bottleneck: over 99% of execution time was spent repeatedly bootstrapping the Python interpreter and re-importing libraries (`parsers`, `lxml`, `pyyaml`, `requests`, `sqlite3`).

By incorporating native persistent worker multiprocessing (`concurrent.futures.ProcessPoolExecutor`) directly into `convert.py`, all modules are initialized once per worker process. Directory processing performance improves by over 200x, reducing execution time across 20,000+ files from ~20 minutes to under 20 seconds.

Furthermore, command line usage is streamlined so users can process entire directories with minimal options:
```bash
./venv/bin/cook <input_directory> -o <output_file_or_dir> [--no-nlp]
```

## Requirements

### 1. Native Multiprocessing in `convert.py`
- When converting a directory of recipe files, utilize `concurrent.futures.ProcessPoolExecutor` with worker count defaulting to `min(os.cpu_count() or 4, 8)`, configurable via `-w` / `--workers`.
- Worker processes must use an initializer (`_worker_init`) to import and initialize ingredient parsers and Schema.org converters once per process, eliminating repeated import overhead.
- When outputting to a single JSON file (`-o out.json`), worker tasks return converted recipe dictionaries, and the main process streams them into `JSONStreamWriter`.
- When outputting to a directory (`-o out_dir`), workers write individual recipe JSON files.

### 2. Streamlined CLI Options
- When the `input` argument is a directory, scanning must default to recursive (`recursive=True`) so `-r` is no longer mandatory for directories.
- Progress reporting should display clean progress updates without flooding terminal output.
- Non-recipe binary/media extensions (`.jpg`, `.png`, `.gif`, `.bmp`, `.pdf` when unparsed, `.json`, `.git`) are safely skipped.

### 3. Removal of `batch_convert`
- Remove `tools/batch_convert.py` and the root compatibility shim `batch_convert.py`.
- Remove `recipe-batch = "tools.batch_convert:main"` entrypoint from `pyproject.toml`.
- Remove `tests/test_batch_convert.py` and replace with `tests/test_directory_convert.py`.
- Update `AGENTS.md` documentation to reflect the consolidated architecture.

### 4. Split Files Normalization
- Rename 11,720 split files in `/home/alex/junk/Recipes/Ingest/ToDo/` from `*.txt-split-NNN` or `*-split-NNN` to standard `*-split-NNN.txt` files so they are recognized by all standard text and markdown parsers without special flags.
