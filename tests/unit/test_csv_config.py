# SPDX-License-Identifier: MIT
"""Unit tests for CSV schema loading and detection."""

from pathlib import Path

from parsers.csv_config import CsvConfigRegistry, CsvSchema, get_csv_schema_registry

SAMPLES = Path(__file__).parent.parent / "samples"


def _sample(name: str) -> str:
    return (SAMPLES / name).read_text(encoding="utf-8", errors="ignore")[:8192]


def test_registry_autodiscovers_builtin_schemas():
    names = {s.name for s in get_csv_schema_registry().schemas()}
    assert {"cookware", "twentyk", "chefs_catalog"} <= names


def test_schema_from_dict_defaults():
    schema = CsvSchema.from_dict({"name": "x", "type": "csv"})
    assert schema.delimiter == ","
    assert schema.has_header is True
    assert schema.source_format == "x"


def test_detects_header_schemas():
    reg = get_csv_schema_registry()
    assert reg.detect_schema(_sample("cookware.csv"), "cookware.csv").name == "cookware"
    assert reg.detect_schema(_sample("sample_20krecipes.csv"), "x.csv").name == "twentyk"
    assert reg.score_schema(reg.get_schema("cookware"), _sample("cookware.csv"), "a.csv") >= 0.9


def test_detects_headerless_chefs_by_content():
    reg = get_csv_schema_registry()
    sample = _sample("chefs.csv")
    assert reg.detect_schema(sample, "anything.csv").name == "chefs_catalog"
    # Filename + content is the strongest match.
    assert reg.score_schema(reg.get_schema("chefs_catalog"), sample, "chefs.csv") >= 0.95


def test_rejects_non_csv_and_unrelated_content():
    reg = get_csv_schema_registry()
    assert reg.best_score(_sample("chefs.csv"), "chefs.txt") == 0.0
    assert reg.detect_schema("a,b,c\n1,2,3\n", "plain.csv") is None
    assert reg.best_score("", "plain.csv") == 0.0


def test_load_ignores_non_csv_type(tmp_path):
    (tmp_path / "bad.csv.yaml").write_text("name: nope\ntype: html\n")
    (tmp_path / "good.csv.yaml").write_text("name: good\ntype: csv\ndetection:\n  header_columns: [A]\n")
    reg = CsvConfigRegistry()
    reg.load_schemas_from_yaml(tmp_path)
    assert [s.name for s in reg.schemas()] == ["good"]
    assert reg.schemas()[0].config_file == "good.csv.yaml"
