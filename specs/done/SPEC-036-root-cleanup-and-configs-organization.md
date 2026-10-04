---
id: SPEC-036
title: "Root Directory Cleanup and Configs Subsystem Organization"
tier: 1
type: refactor
priority: P1
status: done
impact: "Cleans up repository root leaving only convert.py; modularizes pipeline into core/; establishes dual-identification for configs"
deliverables:
  - core/__init__.py
  - core/converter.py
  - core/writer.py
  - core/shard.py
  - core/ui.py
  - convert.py
  - configs/*.html.yaml
  - configs/*.sqlite.yaml
  - configs/*.llm.yaml
  - parsers/html_config.py
  - parsers/sqlite/sqlite_config.py
  - pyproject.toml
  - AGENTS.md
---

# Spec: Root Directory Cleanup and Configs Subsystem Organization

## Description

The repository root directory had accumulated multiple responsibilities:
1. Four core conversion pipeline modules (`converter.py`, `writer.py`, `shard.py`, `ui.py`) extracted during SPEC-015 were left loose in root.
2. Root-level backward compatibility forwarding shims (`dedup.py`, `import_to_mealie.py`, `import_to_tandoor.py`, `update_expected.py`, `vjje.py`, and `extract/`) cluttered the root.
3. Example SQLite schema configurations (`sqlite_schema_examples.yaml`) sat in root rather than in `configs/`.
4. Configuration files in `configs/` lacked clear identification of which parser subsystem (HTML XPath vs. SQLite vs. LLM vs. CSV) consumed them.

This specification:
1. Moves the four conversion pipeline modules into a dedicated `core/` package (`core/converter.py`, `core/writer.py`, `core/shard.py`, `core/ui.py`), with `core/__init__.py` providing package-level re-exports.
2. Updates `convert.py` to import from `core` while maintaining all public re-exports in `__all__` for backward compatibility.
3. Removes obsolete root-level forwarding shims. Tools are run via CLI console scripts or directly under `tools/` and `tools/extract/`.
4. Adopts a **dual identification system** for `configs/`:
   - **Pre-extension naming convention**: `<name>.<type>.yaml` (e.g. `bbc.html.yaml`, `cc-rec.sqlite.yaml`, `llm_example.llm.yaml`, `chefs.csv.yaml`).
   - **Generic `type:` YAML property**: `type: html`, `type: sqlite`, `type: llm`, `type: csv`.
5. Updates `HtmlConfigRegistry` and `SqliteSchemaRegistry` to skip mismatched pre-extensions and recognize `type:`, with fallback for backward compatibility.
6. Relocates `sqlite_schema_examples.yaml` to `configs/sqlite_schema_examples.sqlite.yaml`.
7. Updates packaging (`pyproject.toml`), test imports, and `AGENTS.md`.

## Acceptance Criteria

- [x] Conversion pipeline modules moved into `core/` with `core/__init__.py`.
- [x] Only `convert.py` remains at root as an executable script.
- [x] Obsolete root shims deleted (`dedup.py`, `import_to_mealie.py`, `import_to_tandoor.py`, `update_expected.py`, `vjje.py`, `extract/`).
- [x] `configs/` standardized with `<name>.<type>.yaml` and top-level `type:` property.
- [x] `parsers/html_config.py` and `parsers/sqlite/sqlite_config.py` filter by pre-extension and support multi-document YAML via `safe_load_all`.
- [x] All 264 automated tests pass deterministically.
