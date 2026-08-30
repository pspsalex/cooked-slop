---
id: SPEC-015
title: "Modular CLI and Conversion Architecture"
tier: 1
type: refactor
priority: P0
status: active
impact: "Decomposes 670+ LOC convert.py into 4 focused modules with 100% backwards compatibility"
deliverables:
  - converter.py
  - writer.py
  - shard.py
  - ui.py
  - convert.py
---

# Spec: Modular CLI and Conversion Architecture

## Description

`convert.py` is currently over 670 lines long and conflates four distinct responsibilities:
1. Schema.org JSON-LD conversion logic (`SchemaOrgConverter`)
2. Streaming and chunking file I/O (`JSONStreamWriter`)
3. Sharding algorithms based on MinHash prefixes (`_minhash_bucket`, `_get_recipe_sharded_path`)
4. CLI parsing, terminal color definitions, and batch directory traversal orchestration

This tight coupling makes unit testing difficult (testing `SchemaOrgConverter` requires importing `convert.py`, triggering ANSI escape definitions and argument parsing imports) and complicates refactoring.

This specification decomposes `convert.py` into single-responsibility modules:
- `converter.py`: Schema.org transformation
- `writer.py`: Streaming JSON array file writer with chunking
- `shard.py`: MinHash-based path sharding
- `ui.py`: Terminal formatting, color constants, and progress indicators
- `convert.py`: Slim orchestrator and CLI entry point re-exporting key classes for backward compatibility

## Worktree & Branch Protocol

Following repository golden rules:
```bash
git worktree add -b feat/spec-015-modular-cli .worktrees/spec-015 main
cd .worktrees/spec-015
```
After verification, commit, merge to `main`, and remove worktree.

---

## Detailed Specification

### 1. `converter.py` (New Module)

Extract `SchemaOrgConverter` from `convert.py`:

```python
# SPDX-License-Identifier: MIT
"""Schema.org JSON-LD recipe converter."""
from datetime import datetime
from typing import List, Optional, Union, Dict, Any
from parsers.models import Recipe

class SchemaOrgConverter:
    """Converter to schema.org Recipe JSON-LD format."""

    def convert(
        self,
        recipe: Recipe,
        parse_ingredients: bool = True,
        add_date: bool = False
    ) -> Dict[str, Any]:
        """Convert a internal Recipe dataclass instance into a Schema.org dict."""
        instructions = self._build_instructions(recipe.instructions)
        recipe_ingredients = []

        if parse_ingredients:
            for ing in recipe.ingredients:
                if ing.quantity or ing.unit:
                    prop_value: Dict[str, Any] = {
                        "@type": "PropertyValue",
                        "name": ing.name or ing.raw
                    }
                    if ing.quantity:
                        try:
                            prop_value["value"] = (
                                float(ing.quantity)
                                if "/" not in ing.quantity and "." in ing.quantity
                                else int(ing.quantity)
                            )
                        except ValueError:
                            prop_value["value"] = ing.quantity
                    if ing.unit:
                        prop_value["unitText"] = ing.unit
                    if ing.comment:
                        prop_value["description"] = ing.comment

                    recipe_ingredients.append(prop_value)
                else:
                    recipe_ingredients.append(ing.raw)
        else:
            recipe_ingredients = [ing.raw for ing in recipe.ingredients]

        schema_recipe: Dict[str, Any] = {
            "@context": "https://schema.org",
            "@type": "Recipe",
            "name": recipe.title or "Untitled Recipe",
            "recipeIngredient": recipe_ingredients,
            "recipeInstructions": instructions,
        }

        if recipe.yield_amount:
            schema_recipe["recipeYield"] = recipe.yield_amount

        if recipe.categories:
            schema_recipe["recipeCategory"] = recipe.categories[0]
            schema_recipe["keywords"] = ", ".join(recipe.categories)

        if recipe.source_file:
            schema_recipe["comment"] = f"Imported from {recipe.source_file}"
            if recipe.url:
                schema_recipe["url"] = recipe.url
            elif recipe.sqlite_table and recipe.sqlite_id:
                schema_recipe["url"] = (
                    f"file://{recipe.source_file}#{recipe.sqlite_table},{recipe.sqlite_id}"
                )
            else:
                schema_recipe["url"] = f"file://{recipe.source_file}"

        if add_date:
            schema_recipe["datePublished"] = datetime.now().isoformat()

        schema_recipe["description"] = (
            f"Recipe converted from {recipe.source_format} format"
        )

        return schema_recipe

    @staticmethod
    def _build_instructions(instructions: List[str]) -> List[Any]:
        if not instructions:
            return []
        if len(instructions) == 1:
            return [instructions[0]]
        return [
            {"@type": "HowToStep", "position": position, "text": instruction}
            for position, instruction in enumerate(instructions, 1)
        ]
```

### 2. `writer.py` (New Module)

Extract `JSONStreamWriter` from `convert.py`:

```python
# SPDX-License-Identifier: MIT
"""Streaming JSON array writer with optional chunking."""
import json
from pathlib import Path
from typing import Optional, Any, Dict

class JSONStreamWriter:
    """Writes a JSON array to one or multiple files in a streaming fashion."""

    def __init__(
        self,
        base_output_path: Path,
        indent: int = 2,
        chunk: bool = False,
        max_recipes_per_chunk: int = 35000,
        max_chunk_size_bytes: int = 50 * 1024 * 1024
    ):
        self.base_path = base_output_path
        self.indent = indent
        self.chunk = chunk
        self.max_recipes_per_chunk = max_recipes_per_chunk
        self.max_chunk_size_bytes = max_chunk_size_bytes

        self.current_f: Optional[Any] = None
        self.current_chunk_num = 1
        self.current_recipe_count = 0
        self.current_size_bytes = 0
        self.total_recipes = 0

        self.base_path.parent.mkdir(parents=True, exist_ok=True)

    def _get_current_path(self) -> Path:
        if not self.chunk:
            return self.base_path
        return (
            self.base_path.parent
            / f"{self.base_path.stem}_part{self.current_chunk_num:03d}{self.base_path.suffix}"
        )

    def _open_new_file(self) -> None:
        dest = self._get_current_path()
        self.current_f = open(dest, "w", encoding="utf-8")
        self.current_f.write("[\n")
        self.current_recipe_count = 0
        self.current_size_bytes = 2

    def _close_current_file(self) -> None:
        if self.current_f:
            self.current_f.write("\n]")
            self.current_f.close()
            self.current_f = None
            self.current_chunk_num += 1

    def write_recipe(self, recipe: Dict[str, Any]) -> None:
        recipe_json = json.dumps(recipe, indent=self.indent, ensure_ascii=False)
        recipe_size = len(recipe_json.encode("utf-8"))

        if self.chunk and self.current_f:
            if self.current_recipe_count >= self.max_recipes_per_chunk or (
                self.current_recipe_count > 0
                and self.current_size_bytes + recipe_size > self.max_chunk_size_bytes
            ):
                self._close_current_file()

        if not self.current_f:
            self._open_new_file()
        elif self.current_recipe_count > 0:
            self.current_f.write(",\n")
            self.current_size_bytes += 2

        self.current_f.write(recipe_json)
        self.current_recipe_count += 1
        self.total_recipes += 1
        self.current_size_bytes += recipe_size

    def close(self) -> None:
        self._close_current_file()
        if self.total_recipes == 0 and not self.chunk:
            self._open_new_file()
            self._close_current_file()
```

### 3. `shard.py` (New Module)

Extract MinHash bucketing and sharded path computation:

```python
# SPDX-License-Identifier: MIT
"""MinHash path sharding helpers."""
import re
import zlib
from pathlib import Path
from typing import Set, Union

def get_tokens(text: str) -> Set[str]:
    """Extract lowercased word tokens (3+ chars) from text."""
    return set(re.findall(r'\b[a-z]{3,}\b', text.lower().replace("_", " ")))

def minhash_bucket(text: str, num_perm: int = 16) -> str:
    """Computes a short, fast MinHash bucket prefix (xx/yy)."""
    tokens = get_tokens(text)
    if not tokens:
        tokens = {"default"}

    sig = []
    for i in range(num_perm):
        min_val = float('inf')
        for token in tokens:
            val = zlib.crc32(f"{i}:{token}".encode('utf-8'))
            if val < min_val:
                min_val = val
        sig.append(min_val)

    bucket_1 = f"{sig[0] % 256:02x}"
    bucket_2 = f"{sig[1] % 256:02x}"
    return f"{bucket_1}/{bucket_2}"

def get_recipe_sharded_path(
    url: str,
    title: str,
    base_dir: Union[str, Path] = "recipes"
) -> Path:
    """Returns a MinHash-based sharded directory path for a recipe."""
    bucket_dir = minhash_bucket(f"{title}")
    return Path(base_dir) / bucket_dir
```

### 4. `ui.py` (New Module)

Terminal output formatting and progress reporting:

```python
# SPDX-License-Identifier: MIT
"""Terminal styling and console output reporters."""
import sys

class Colors:
    HEADER = "\033[95m"
    BLUE = "\033[94m"
    CYAN = "\033[96m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    RED = "\033[91m"
    ENDC = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"

def print_progress_bar(iteration: int, total: int, prefix: str = "", suffix: str = "", length: int = 40, fill: str = "█") -> None:
    if total <= 0:
        return
    percent = f"{100 * (iteration / float(total)):.1f}"
    filled_length = int(length * iteration // total)
    bar = fill * filled_length + "-" * (length - filled_length)
    sys.stdout.write(f"\r{Colors.CYAN}{prefix}{Colors.ENDC} |{bar}| {percent}% {suffix}")
    sys.stdout.flush()
    if iteration == total:
        sys.stdout.write("\n")
        sys.stdout.flush()
```

### 5. `convert.py`: Clean Orchestrator & Backward Compatibility

- Import `SchemaOrgConverter` from `converter.py`.
- Import `JSONStreamWriter` from `writer.py`.
- Import sharding functions from `shard.py`.
- Import `Colors` and `print_progress_bar` from `ui.py`.
- Re-export `SchemaOrgConverter`, `JSONStreamWriter`, `Colors`, `get_recipe_sharded_path` in `convert.py` so any legacy imports continue to function without errors.

---

## Edge Cases

1. **Circular Imports**: `converter.py` and `writer.py` must not import `convert.py`.
2. **Backward Compatibility**: Any script or test doing `from convert import SchemaOrgConverter, JSONStreamWriter, main` must not break.
3. **Empty Output Flush**: `JSONStreamWriter.close()` must still write a valid empty JSON array `[]` when `total_recipes == 0` and not chunked.

---

## Acceptance Criteria

- [ ] `converter.py` contains `SchemaOrgConverter` with full type annotations.
- [ ] `writer.py` contains `JSONStreamWriter` with streaming and chunking.
- [ ] `shard.py` contains MinHash bucketing and sharded path functions.
- [ ] `ui.py` contains `Colors` and `print_progress_bar`.
- [ ] `convert.py` imports from these modules and acts as CLI orchestrator.
- [ ] `convert.py` re-exports `SchemaOrgConverter` and `JSONStreamWriter` for backward compatibility.
- [ ] All 70 existing pytest tests pass without regression: `./venv/bin/python3 -m pytest tests/ -v`.

---

## Verification Plan

```bash
# 1. Run all pytest tests
./venv/bin/python3 -m pytest tests/ -v

# 2. Verify backward-compatible imports from convert
./venv/bin/python3 -c "from convert import SchemaOrgConverter, JSONStreamWriter, main; assert callable(main)"

# 3. Verify clean isolated module imports
./venv/bin/python3 -c "from converter import SchemaOrgConverter; from writer import JSONStreamWriter; from shard import minhash_bucket; from ui import Colors"
```
