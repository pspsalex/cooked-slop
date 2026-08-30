# Recipe Specifications (Specs)

## Overview

This directory contains self-contained technical specifications for recipe parsers, HTML layout configurations, and ingestion pipelines.

In this project's spec-driven development workflow:
- **`specs/`** contains technical design documents detailing *what* needs to be parsed, with raw sample extracts, field mapping rules, and acceptance criteria.
- **`tasks.md`** (in the repository root) is the **single actionable backlog** of tasks. Each spec corresponds to a task in `tasks.md`, broken down into atomic subtasks for AI agent execution.
- Completed specifications are archived in **`specs/done/`**.

## Directory Structure

```
specs/
├── README.md               # This document
├── _template.md            # Template for authoring new specifications
├── done/                   # Archive for completed specifications
│   ├── SPEC-001-batch-runner.md
│   ├── SPEC-002-cscmu.md
│   └── ...
└── SPEC-NNN-slug.md        # Active specifications
```

## Spec Naming & Frontmatter

All specs follow the naming convention `SPEC-NNN-<kebab-case-name>.md` and include YAML frontmatter at the top:

```yaml
---
id: SPEC-001
title: "cs.cmu Usenet Recipe Archive HTML Config"
tier: 2
type: html-config      # html-config | parser | script | review
priority: P0           # P0 | P1 | P2
status: active         # active | done | blocked
impact: "~735 files"
deliverables:
  - configs/cscmu.yaml
---
```

## Authoring a New Spec

1. Copy [`_template.md`](_template.md) to `specs/SPEC-NNN-<name>.md`.
2. Fill out the YAML frontmatter and required sections:
   - **Description**: What format or collection this targets.
   - **Input Samples**: Verbatim raw file samples.
   - **Expected Behavior**: Mapping rules and edge cases.
   - **Detection Contract**: Markdown table defining detection scoring behavior, including:
     - Positive matches (e.g. extension pattern + signature content `>= 0.85`, content-only `>= 0.60`).
     - Negative assertions: non-matching or generic content must return `== 0.0` to avoid score inflation and format collisions.
   - **Golden Output (Canonical JSON-LD)**: Expected Schema.org Recipe JSON-LD fixture generated with `--no-nlp` (deterministic regex ingredient parser) to establish exact fixture expectations.
   - **Acceptance Criteria**: Concrete, testable checkboxes.
   - **Deliverables**: Explicit target files to create or modify.
3. Add the corresponding task entry into [`../tasks.md`](../tasks.md) with atomic checklist items derived from the acceptance criteria.

## Agent Workflow

Agents should refer to [`../AGENTS.md`](../AGENTS.md) for master guidelines, environment commands, and development standards.
