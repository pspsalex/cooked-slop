# SPDX-License-Identifier: MIT
"""Streaming JSON array writer with optional chunking."""
import json
from pathlib import Path
from typing import Any, Dict, Optional, TextIO


class JSONStreamWriter:
    """Writes a JSON array to one or multiple files in a streaming fashion."""

    def __init__(
        self,
        base_output_path: Path,
        indent: int = 2,
        chunk: bool = False,
        max_recipes_per_chunk: int = 35000,
        max_chunk_size_bytes: int = 50 * 1024 * 1024,
    ):
        """Initialize the JSON stream writer.

        Args:
            base_output_path: Base file path for JSON output.
            indent: JSON indentation spaces.
            chunk: Whether to chunk into part files.
            max_recipes_per_chunk: Maximum recipes per chunk file.
            max_chunk_size_bytes: Maximum size in bytes per chunk file.
        """
        self.base_path = base_output_path
        self.indent = indent
        self.chunk = chunk
        self.max_recipes_per_chunk = max_recipes_per_chunk
        self.max_chunk_size_bytes = max_chunk_size_bytes

        self.current_f: Optional[TextIO] = None
        self.current_chunk_num = 1
        self.current_recipe_count = 0
        self.current_size_bytes = 0
        self.total_recipes = 0

        self.base_path.parent.mkdir(parents=True, exist_ok=True)

    def _get_current_path(self) -> Path:
        """Get output path for current chunk."""
        if not self.chunk:
            return self.base_path
        return (
            self.base_path.parent
            / f"{self.base_path.stem}_part{self.current_chunk_num:03d}{self.base_path.suffix}"
        )

    def _open_new_file(self) -> None:
        """Open a new file and write opening JSON array bracket."""
        dest = self._get_current_path()
        self.current_f = open(dest, "w", encoding="utf-8")
        self.current_f.write("[\n")
        self.current_recipe_count = 0
        self.current_size_bytes = 2  # "[" and "\n"

    def _close_current_file(self) -> None:
        """Close current open file with closing JSON array bracket."""
        if self.current_f:
            self.current_f.write("\n]")
            self.current_f.close()
            self.current_f = None
            self.current_chunk_num += 1

    def write_recipe(self, recipe: Dict[str, Any]) -> None:
        """Write a single recipe object into current JSON stream.

        Args:
            recipe: Recipe dictionary to serialize and write.
        """
        # Calculate size if needed for chunking
        recipe_json = json.dumps(recipe, indent=self.indent, ensure_ascii=False)
        recipe_size = len(recipe_json.encode("utf-8"))

        # Check if we need to rotate
        if self.chunk and self.current_f:
            if self.current_recipe_count >= self.max_recipes_per_chunk or (
                self.current_recipe_count > 0
                and self.current_size_bytes + recipe_size > self.max_chunk_size_bytes
            ):
                self._close_current_file()

        if not self.current_f:
            self._open_new_file()
        elif self.current_recipe_count > 0:
            assert self.current_f is not None
            self.current_f.write(",\n")
            self.current_size_bytes += 2

        assert self.current_f is not None
        self.current_f.write(recipe_json)
        self.current_recipe_count += 1
        self.total_recipes += 1
        self.current_size_bytes += recipe_size

    def close(self) -> None:
        """Finalize and close the stream, ensuring valid JSON output."""
        self._close_current_file()
        if self.total_recipes == 0 and not self.chunk:
            # Create an empty array file if no recipes were processed
            self._open_new_file()
            self._close_current_file()
