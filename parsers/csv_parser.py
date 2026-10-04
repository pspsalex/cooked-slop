# SPDX-License-Identifier: MIT
"""YAML-configurable CSV recipe parser.

Layouts are described in ``configs/*.csv.yaml`` (see ``parsers/csv_config.py``).
One parser class replaces the former hard-coded Cookware and 20krecipes
parsers and lets new CSV layouts be added without writing Python.
"""

import csv
import io
import logging
import re
from pathlib import Path
from typing import Any, Callable, Dict, Iterator, List, Optional

from .base import BaseIngredientParser, BaseRecipeParser, sanitize_recipe
from .csv_config import CsvSchema, get_csv_schema_registry
from .models import Ingredient, Recipe
from .registry import ParserRegistry
from .twentykrecipes import parse_ingredient_line

logger = logging.getLogger(__name__)

_SNIFF_BYTES = 8192
_FALLBACK_ENCODINGS = ("utf-8", "cp1252", "latin-1")

# Named per-line ingredient transforms selectable via ``transform:`` in YAML.
LINE_TRANSFORMS: Dict[str, Callable[[str], str]] = {
    "twentyk_decimal": parse_ingredient_line,
}


def decode_csv_bytes(data: bytes, preferred: Optional[str] = None) -> str:
    """Decode bytes trying ``preferred`` first, then utf-8, cp1252, latin-1."""
    encodings = ([preferred] if preferred else []) + list(_FALLBACK_ENCODINGS)
    for enc in encodings:
        try:
            return data.decode(enc)
        except (UnicodeDecodeError, LookupError):
            continue
    return data.decode("utf-8", errors="replace")


@ParserRegistry.register
class ConfigurableCsvParser(BaseRecipeParser):
    """CSV parser driven by YAML schemas from ``configs/*.csv.yaml``."""

    def __init__(self, ingredient_parser: BaseIngredientParser):
        super().__init__(ingredient_parser)
        self.source_format = "CSV"
        self._schema: Optional[CsvSchema] = None

    @classmethod
    def format_id(cls) -> str:
        return "csv"

    @classmethod
    def aliases(cls) -> list[str]:
        return ["csv_config", "csv_cookware", "cookware", "csv_20krecipes", "20krecipes", "csv_chefs", "chefs"]

    @classmethod
    def priority(cls) -> int:
        return 22

    @classmethod
    def supported_extensions(cls) -> set[str]:
        return {".csv"}

    @classmethod
    def detect(cls, filepath: str, content_sample: str) -> float:
        if Path(filepath).suffix.lower() != ".csv":
            return 0.0
        return get_csv_schema_registry().best_score(content_sample, str(filepath))

    def get_display_name(self, filepath: str | None = None) -> str:
        if self._schema:
            return f"{self._schema.source_format} Parser"
        return "CSV Parser"

    # ------------------------------------------------------------------ I/O

    def parse_file(self, filepath: str) -> Iterator[Recipe]:
        """Read ``filepath`` with encoding fallbacks and yield sanitized recipes."""
        try:
            with open(filepath, "rb") as f:
                raw = f.read()
        except OSError as e:
            logger.error("Error reading %s: %s", filepath, e)
            return

        sample = decode_csv_bytes(raw[:_SNIFF_BYTES])
        schema = get_csv_schema_registry().detect_schema(sample, str(filepath))
        content = decode_csv_bytes(raw, schema.encoding if schema else None)
        for recipe in self.parse_content(content, filepath):
            sanitize_recipe(recipe)
            if not recipe.description:
                recipe.description = f"Imported from {self.source_format}"
            if not recipe.url:
                recipe.url = f"file://{filepath}"
            yield recipe

    def parse_content(self, content: str, filepath: str) -> Iterator[Recipe]:
        """Detect the matching schema and yield one Recipe per CSV row."""
        schema = get_csv_schema_registry().detect_schema(content[:_SNIFF_BYTES], str(filepath))
        if schema is None:
            logger.warning("No CSV schema matches %s", filepath)
            return
        self._schema = schema
        self.source_format = schema.source_format

        try:
            reader = csv.reader(io.StringIO(content), delimiter=schema.delimiter)
            header_map: Dict[str, int] = {}
            if schema.has_header:
                header = next(reader, [])
                for idx, name in enumerate(header):
                    header_map.setdefault(name.strip(), idx)

            row_number = 0
            for row in reader:
                if not any(c.strip() for c in row):
                    continue
                row_number += 1
                recipe = self._row_to_recipe(row, schema, header_map, filepath)
                if recipe.title:
                    recipe.url = f"file://{filepath}#{row_number}"
                    yield recipe
        except csv.Error as e:
            logger.warning("Error parsing CSV %s: %s", filepath, e)

    # -------------------------------------------------------------- mapping

    @staticmethod
    def _cell(row: List[str], spec: Dict[str, Any], header_map: Dict[str, int]) -> str:
        """Return the stripped cell addressed by ``column_name``/``column_index``."""
        idx: Optional[int] = spec.get("column_index")
        if idx is None and "column_name" in spec:
            idx = header_map.get(spec["column_name"])
        if idx is None or idx < 0 or idx >= len(row):
            return ""
        return row[idx].strip()

    @staticmethod
    def _is_null(value: str, schema: CsvSchema, spec: Dict[str, Any]) -> bool:
        if not value:
            return True
        upper = value.upper()
        if upper in schema.null_values:
            return True
        return value in [str(v) for v in spec.get("ignore_values", [])]

    def _split(self, text: str, spec: Dict[str, Any]) -> List[str]:
        delim = spec.get("split_delimiter", "\n")
        return [p.strip() for p in text.split(delim) if p.strip()]

    def _make_ingredient(self, line: str, transform: Optional[str]) -> Ingredient:
        if transform:
            line = LINE_TRANSFORMS[transform](line)
        if not line:
            return Ingredient(raw="")
        return self.ingredient_parser.parse(line) if self.ingredient_parser else Ingredient(raw=line)

    def _row_to_recipe(
        self, row: List[str], schema: CsvSchema, header_map: Dict[str, int], filepath: str
    ) -> Recipe:
        fields = schema.fields
        recipe = Recipe(source_file=filepath, source_format=schema.source_format)

        # Title
        t_spec = fields.get("title", {})
        title = self._cell(row, t_spec, header_map)
        if self._is_null(title, schema, t_spec):
            title = ""
        recipe.title = title or t_spec.get("default", "")

        # Source -> description
        s_spec = fields.get("source")
        if s_spec:
            source = self._cell(row, s_spec, header_map)
            if source and not self._is_null(source, schema, s_spec):
                recipe.description = f"Source: {source}"

        d_spec = fields.get("description")
        if d_spec:
            desc = self._cell(row, d_spec, header_map)
            if desc and not self._is_null(desc, schema, d_spec):
                recipe.description = desc

        # Categories
        cats: List[str] = []
        for c_spec in (fields.get("categories") or {}).get("columns", []):
            value = self._cell(row, c_spec, header_map)
            if self._is_null(value, schema, c_spec):
                continue
            value = c_spec.get("value_map", {}).get(value, value)
            if c_spec.get("strip_chars"):
                value = value.rstrip(c_spec["strip_chars"])
            if value:
                cats.append(value)
        recipe.categories = list(dict.fromkeys(cats))

        # Yield
        y_spec = fields.get("yield_amount")
        if y_spec:
            serves = self._cell(row, y_spec, header_map)
            if not self._is_null(serves, schema, y_spec):
                recipe.yield_amount = serves

        # Ingredients & instructions
        ing_lines, inst_lines = self._extract_body(row, schema, header_map)
        transform = (fields.get("ingredients") or {}).get("transform")
        for line in ing_lines:
            ing = self._make_ingredient(line, transform)
            if ing.raw:
                recipe.ingredients.append(ing)
        recipe.instructions = inst_lines
        return recipe

    def _extract_body(
        self, row: List[str], schema: CsvSchema, header_map: Dict[str, int]
    ) -> tuple[List[str], List[str]]:
        """Return (ingredient_lines, instruction_lines) for a row."""
        fields = schema.fields
        ing_spec = fields.get("ingredients") or {}
        inst_spec = fields.get("instructions") or {}
        ing_lines: List[str] = []
        inst_lines: List[str] = []

        if "start_column_index" in ing_spec:
            split_re = ing_spec.get("cell_split_pattern")
            found_sep = False
            for cell in row[ing_spec["start_column_index"]:]:
                cell = cell.strip()
                if not cell:
                    if ing_lines:
                        found_sep = True
                    continue
                if found_sep:
                    if "after_marker" in inst_spec:
                        inst_lines.append(cell)
                    continue
                parts = re.split(split_re, cell) if split_re else [cell]
                ing_lines.extend(p.strip() for p in parts if p.strip())
            return ing_lines, inst_lines

        names = ing_spec.get("column_names") or ([ing_spec["column_name"]] if "column_name" in ing_spec else [])
        for name in names:
            text = self._cell(row, {"column_name": name}, header_map)
            if not self._is_null(text, schema, ing_spec):
                ing_lines.extend(self._split(text, ing_spec))

        if inst_spec and "after_marker" not in inst_spec:
            text = self._cell(row, inst_spec, header_map)
            if not self._is_null(text, schema, inst_spec):
                inst_lines = self._split(text, inst_spec)
        return ing_lines, inst_lines
