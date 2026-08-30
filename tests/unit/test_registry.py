# SPDX-License-Identifier: MIT
"""Unit tests for ParserRegistry."""
import logging
from pathlib import Path
from typing import Iterator
import pytest
import parsers  # Triggers auto-discovery of all parsers
from parsers.base import BaseRecipeParser
from parsers.ingredients import RegexIngredientParser
from parsers.models import Recipe
from parsers.registry import ParserRegistry


@pytest.fixture
def ingredient_parser():
    """Returns a RegexIngredientParser."""
    return RegexIngredientParser()


def test_autodiscovery_loads_registered_parsers():
    """Importing parsers auto-registers all parser modules."""
    assert len(ParserRegistry._parsers) > 0
    format_ids = [p.format_id() for p in ParserRegistry._parsers]
    assert "mealmaster" in format_ids
    assert "mastercook" in format_ids
    assert "csv_cookware" in format_ids


def test_parsers_sorted_by_priority():
    """Registered parsers are stored in ascending priority order."""
    priorities = [p.priority() for p in ParserRegistry._parsers]
    assert priorities == sorted(priorities)


def test_format_alias_and_id_lookup(ingredient_parser):
    """Parsers can be resolved by format_id or any registered alias."""
    # Lookup by primary format_id
    p_by_id = ParserRegistry.get_parser(Path("dummy.txt"), ingredient_parser, format_name="mastercook")
    assert p_by_id is not None
    assert p_by_id.format_id() == "mastercook"

    # Lookup by aliases
    p_by_alias = ParserRegistry.get_parser(Path("dummy.txt"), ingredient_parser, format_name="mxp")
    assert p_by_alias is not None
    assert p_by_alias.format_id() == "mastercook"

    p_by_alias2 = ParserRegistry.get_parser(Path("dummy.txt"), ingredient_parser, format_name="cookware")
    assert p_by_alias2 is not None
    assert p_by_alias2.format_id() == "csv_cookware"

    # Non-existent format name
    assert ParserRegistry.get_parser(Path("dummy.txt"), ingredient_parser, format_name="nonexistent_format") is None


def test_all_format_names_returns_sorted_list():
    """all_format_names() returns a sorted list of format_ids and aliases."""
    names = ParserRegistry.all_format_names()
    assert "mastercook" in names
    assert "mxp" in names
    assert "csv_cookware" in names
    assert "cookware" in names
    assert names == sorted(names)


def test_contract_validation_not_subclass():
    """Registering a class that does not subclass BaseRecipeParser raises TypeError."""
    class DummyNotParser:
        pass

    with pytest.raises(TypeError, match="must subclass BaseRecipeParser"):
        ParserRegistry.register(DummyNotParser)  # type: ignore


def test_contract_validation_missing_detect():
    """Registering a parser missing callable detect() raises TypeError."""
    class DummyMissingDetect(BaseRecipeParser):
        detect = None  # type: ignore

        @classmethod
        def format_id(cls) -> str:
            return "dummy_no_detect"

        @classmethod
        def priority(cls) -> int:
            return 50

        def parse_content(self, content: str, filepath: str) -> Iterator[Recipe]:
            yield Recipe(title="Test")

    with pytest.raises(TypeError, match=r"must implement classmethod 'detect\(\)'"):
        ParserRegistry.register(DummyMissingDetect)


def test_contract_validation_missing_priority():
    """Registering a parser missing callable priority() raises TypeError."""
    class DummyMissingPriority(BaseRecipeParser):
        priority = None  # type: ignore

        @classmethod
        def format_id(cls) -> str:
            return "dummy_no_priority"

        @classmethod
        def detect(cls, filepath: str, content_sample: str) -> float:
            return 0.0

        def parse_content(self, content: str, filepath: str) -> Iterator[Recipe]:
            yield Recipe(title="Test")

    with pytest.raises(TypeError, match=r"must implement classmethod 'priority\(\)'"):
        ParserRegistry.register(DummyMissingPriority)


def test_contract_validation_missing_format_id():
    """Registering a parser missing callable format_id() raises TypeError."""
    class DummyMissingFormatId(BaseRecipeParser):
        format_id = None  # type: ignore

        @classmethod
        def priority(cls) -> int:
            return 50

        @classmethod
        def detect(cls, filepath: str, content_sample: str) -> float:
            return 0.0

        def parse_content(self, content: str, filepath: str) -> Iterator[Recipe]:
            yield Recipe(title="Test")

    with pytest.raises(TypeError, match=r"must implement classmethod 'format_id\(\)'"):
        ParserRegistry.register(DummyMissingFormatId)


def test_contract_validation_non_generator_parse_content():
    """Registering a parser whose parse_content is not a generator function raises TypeError."""
    class DummyReturnParser(BaseRecipeParser):
        @classmethod
        def format_id(cls) -> str:
            return "dummy_return"

        @classmethod
        def priority(cls) -> int:
            return 50

        @classmethod
        def detect(cls, filepath: str, content_sample: str) -> float:
            return 0.0

        def parse_content(self, content: str, filepath: str):  # type: ignore
            # Returns a list instead of using yield
            return [Recipe(title="Test")]

    with pytest.raises(TypeError, match="parse_content must be a generator function"):
        ParserRegistry.register(DummyReturnParser)


def test_detection_exception_logging(caplog, tmp_path, ingredient_parser):
    """When a parser raises an exception during detect(), get_parser() logs debug without crashing."""
    class FaultyDetectParser(BaseRecipeParser):
        @classmethod
        def format_id(cls) -> str:
            return "faulty_detect"

        @classmethod
        def priority(cls) -> int:
            return 1  # Try first

        @classmethod
        def detect(cls, filepath: str, content_sample: str) -> float:
            raise RuntimeError("Simulated crash in detect()")

        def parse_content(self, content: str, filepath: str) -> Iterator[Recipe]:
            yield Recipe(title="Test")

    # Register temporarily
    FaultyDetectParser = ParserRegistry.register(FaultyDetectParser)
    test_file = tmp_path / "test_file.txt"
    test_file.write_text("Some recipe text", encoding="utf-8")

    try:
        with caplog.at_level(logging.DEBUG):
            parser = ParserRegistry.get_parser(test_file, ingredient_parser)

        # Should not raise; should log the exception
        assert any(
            "Parser FaultyDetectParser.detect() raised exception" in record.message
            for record in caplog.records
        )
        assert any(
            "Simulated crash in detect()" in record.message
            for record in caplog.records
        )
        # Should still return generic text fallback for .txt
        assert parser is not None
    finally:
        if FaultyDetectParser in ParserRegistry._parsers:
            ParserRegistry._parsers.remove(FaultyDetectParser)


def test_supported_extensions():
    """ParserRegistry.supported_extensions() aggregates all supported extensions."""
    exts = ParserRegistry.supported_extensions()
    assert isinstance(exts, set)
    assert len(exts) > 0
    assert ".nyc" in exts
    assert ".xml" in exts
    assert ".json" in exts
    assert ".mmf" in exts
    assert ".mm" in exts
    assert ".mxp" in exts
    assert ".ccf" in exts
    assert ".mca" in exts
    assert ".csv" in exts
    assert ".md" in exts
    assert ".txt" in exts
    assert ".sqlite" in exts
    assert ".db" in exts
    assert ".html" in exts
    assert ".pdf" in exts
    assert ".jpg" in exts


def test_base_recipe_parser_supported_extensions_default():
    """Default BaseRecipeParser.supported_extensions() returns an empty set."""
    assert BaseRecipeParser.supported_extensions() == set()


def test_convert_parse_arguments_ext():
    """--ext flag correctly parses list of extensions."""
    from convert import parse_arguments
    args = parse_arguments(["dummy_dir", "--ext", ".mmf", ".txt"])
    assert args.ext == [".mmf", ".txt"]


def test_process_directory_cli_extensions_filter(tmp_path, monkeypatch):
    """process_directory respects cli_extensions argument and filters files."""
    from convert import process_directory

    in_dir = tmp_path / "inputs"
    in_dir.mkdir()
    out_dir = tmp_path / "outputs"
    out_dir.mkdir()

    (in_dir / "recipe1.mmf").write_text("dummy", encoding="utf-8")
    (in_dir / "recipe2.txt").write_text("dummy", encoding="utf-8")
    (in_dir / "recipe3.nyc").write_text("dummy", encoding="utf-8")

    converted_files = []

    def fake_convert(recipe_file, *args, **kwargs):
        converted_files.append(recipe_file.name)
        return 0

    monkeypatch.setattr("convert.convert_recipe_file", fake_convert)

    process_directory(
        in_dir,
        out_dir,
        one_file_per_recipe=True,
        verbose=False,
        recursive=False,
        parse_ingredients=False,
        ingredient_parser=RegexIngredientParser(),
        cli_extensions=[".mmf"],
    )

    assert converted_files == ["recipe1.mmf"]
