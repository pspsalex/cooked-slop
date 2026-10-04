# SPDX-License-Identifier: MIT
"""YAML-driven CSV schema definitions and auto-detection.

Each ``configs/<name>.csv.yaml`` file (``type: csv``) describes a CSV recipe
layout: dialect options, detection rules and a mapping from columns (by name
or index) to recipe fields.
"""

import csv
import fnmatch
import io
import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml

logger = logging.getLogger(__name__)

HEADER_SCORE = 0.95
PATTERN_SCORE = 0.90


@dataclass
class CsvDetection:
    """Rules used to decide whether a file matches a schema."""

    filename_patterns: List[str] = field(default_factory=list)
    header_columns: List[str] = field(default_factory=list)
    content_patterns: List[str] = field(default_factory=list)
    min_columns: int = 0


@dataclass
class CsvSchema:
    """A CSV layout definition loaded from YAML.

    Attributes:
        name: Unique schema name.
        description: Human readable description.
        source_format: Value stored in ``Recipe.source_format``.
        delimiter: CSV delimiter.
        has_header: Whether the first row holds column names.
        encoding: Optional preferred encoding (fallbacks still apply).
        null_values: Case-insensitive cell values treated as empty.
        detection: Detection rules.
        fields: Raw field mapping (title, categories, ingredients, ...).
        config_file: Basename of the YAML file this schema came from.
    """

    name: str
    description: str = ""
    source_format: str = ""
    delimiter: str = ","
    has_header: bool = True
    encoding: Optional[str] = None
    null_values: List[str] = field(default_factory=list)
    detection: CsvDetection = field(default_factory=CsvDetection)
    fields: Dict[str, Any] = field(default_factory=dict)
    config_file: str = ""

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "CsvSchema":
        """Build a schema from a parsed YAML mapping."""
        opts = data.get("csv_options") or {}
        det = data.get("detection") or {}
        name = data["name"]
        return cls(
            name=name,
            description=data.get("description", ""),
            source_format=data.get("source_format") or name,
            delimiter=opts.get("delimiter", ","),
            has_header=bool(opts.get("has_header", True)),
            encoding=opts.get("encoding"),
            null_values=[str(v).upper() for v in data.get("null_values", [])],
            detection=CsvDetection(
                filename_patterns=list(det.get("filename_patterns", [])),
                header_columns=list(det.get("header_columns", [])),
                content_patterns=list(det.get("content_patterns", [])),
                min_columns=int(det.get("min_columns", 0)),
            ),
            fields=dict(data.get("fields") or {}),
        )


class CsvConfigRegistry:
    """Loads ``type: csv`` YAML configs and scores them against input files."""

    def __init__(self) -> None:
        self._schemas: Dict[str, CsvSchema] = {}

    def register_schema(self, schema: CsvSchema) -> None:
        """Register (or replace) a schema by name."""
        self._schemas[schema.name] = schema

    def get_schema(self, name: str) -> Optional[CsvSchema]:
        """Return a schema by name, if known."""
        return self._schemas.get(name)

    def schemas(self) -> List[CsvSchema]:
        """Return all registered schemas."""
        return list(self._schemas.values())

    def load_schemas_from_yaml(self, config_dir: Path) -> None:
        """Load every ``*.csv.yaml`` file in ``config_dir`` with ``type: csv``."""
        if not config_dir.exists():
            return
        for yaml_file in sorted(config_dir.glob("*.csv.y*ml")):
            try:
                with open(yaml_file, "r", encoding="utf-8") as f:
                    for data in yaml.safe_load_all(f):
                        if isinstance(data, dict) and data.get("type") == "csv":
                            schema = CsvSchema.from_dict(data)
                            schema.config_file = yaml_file.name
                            self.register_schema(schema)
            except Exception as e:
                logger.warning("Failed to load CSV schema from %s: %s", yaml_file, e)

    @staticmethod
    def _first_row(sample: str, schema: CsvSchema) -> List[str]:
        try:
            return next(csv.reader(io.StringIO(sample), delimiter=schema.delimiter), [])
        except csv.Error:
            return []

    def score_schema(self, schema: CsvSchema, sample: str, filepath: str = "") -> float:
        """Return a confidence in 0.0-1.0 that ``schema`` describes the file."""
        if filepath and Path(filepath).suffix.lower() != ".csv":
            return 0.0
        if not sample:
            return 0.0

        det = schema.detection
        row = self._first_row(sample, schema)
        if len(row) < det.min_columns:
            return 0.0

        if det.header_columns:
            headers = {h.strip() for h in row}
            if all(h in headers for h in det.header_columns):
                return HEADER_SCORE
            return 0.0

        name_ok = bool(filepath) and any(
            fnmatch.fnmatch(Path(filepath).name.lower(), pat.lower())
            for pat in det.filename_patterns
        )
        content_ok = any(
            re.search(pat, sample, re.MULTILINE) for pat in det.content_patterns
        )
        if det.content_patterns and det.filename_patterns:
            return HEADER_SCORE if (name_ok and content_ok) else (PATTERN_SCORE if content_ok else 0.0)
        if content_ok or name_ok:
            return PATTERN_SCORE
        return 0.0

    def detect_schemas(self, sample: str, filepath: str = "") -> List[CsvSchema]:
        """Return all schemas scoring >= 0.5, best first."""
        scored = [(self.score_schema(s, sample, filepath), s) for s in self._schemas.values()]
        scored = [(sc, s) for sc, s in scored if sc >= 0.5]
        scored.sort(key=lambda x: x[0], reverse=True)
        return [s for _, s in scored]

    def detect_schema(self, sample: str, filepath: str = "") -> Optional[CsvSchema]:
        """Return the best matching schema, or ``None``."""
        found = self.detect_schemas(sample, filepath)
        return found[0] if found else None

    def best_score(self, sample: str, filepath: str = "") -> float:
        """Return the highest schema score for the given input."""
        return max((self.score_schema(s, sample, filepath) for s in self._schemas.values()), default=0.0)


_global_csv_registry: Optional[CsvConfigRegistry] = None


def get_csv_schema_registry() -> CsvConfigRegistry:
    """Return the global CSV registry, auto-loading YAML configs on first use."""
    global _global_csv_registry
    if _global_csv_registry is None:
        _global_csv_registry = CsvConfigRegistry()
        for config_dir in (Path(__file__).parent.parent / "configs", Path.cwd() / "configs"):
            _global_csv_registry.load_schemas_from_yaml(config_dir)
    return _global_csv_registry
