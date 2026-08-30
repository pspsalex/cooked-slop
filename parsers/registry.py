# SPDX-License-Identifier: MIT
import inspect
import logging
from pathlib import Path
from typing import Optional, Type, List

from .base import BaseRecipeParser, BaseIngredientParser

logger = logging.getLogger(__name__)


class ParserRegistry:
    """Registry for format detection and parser selection."""

    _parsers: List[Type[BaseRecipeParser]] = []

    @classmethod
    def register(cls, parser_cls: Type[BaseRecipeParser]) -> Type[BaseRecipeParser]:
        """Decorator to register a parser class with runtime contract validation."""
        if not isinstance(parser_cls, type) or not issubclass(parser_cls, BaseRecipeParser):
            raise TypeError(f"{getattr(parser_cls, '__name__', str(parser_cls))} must subclass BaseRecipeParser")

        for method_name in ('format_id', 'priority', 'detect'):
            if not hasattr(parser_cls, method_name) or not callable(getattr(parser_cls, method_name)):
                raise TypeError(f"{parser_cls.__name__} must implement classmethod '{method_name}()'")

        if not inspect.isgeneratorfunction(parser_cls.parse_content):
            raise TypeError(
                f"{parser_cls.__name__}.parse_content must be a generator function (using 'yield', not 'return')"
            )

        # Avoid duplicate registrations if module is reloaded
        if parser_cls not in cls._parsers:
            cls._parsers.append(parser_cls)
            cls._parsers.sort(key=lambda p: p.priority())

        return parser_cls

    @classmethod
    def all_format_names(cls) -> list[str]:
        """Return sorted list of all format_ids and aliases across registered parsers."""
        names: set[str] = set()
        for p in cls._parsers:
            names.add(p.format_id())
            names.update(p.aliases())
        return sorted(names)

    @classmethod
    def get_parser(
        cls,
        filepath: Path,
        ingredient_parser: BaseIngredientParser,
        format_name: Optional[str] = None,
        debug: bool = False
    ) -> Optional[BaseRecipeParser]:
        """
        Get appropriate parser for file using explicit format name or auto-detection.
        """
        if format_name:
            fmt_lower = format_name.lower()
            for p in cls._parsers:
                if p.format_id() == fmt_lower or fmt_lower in p.aliases():
                    # Check which arguments the constructor expects
                    init_args = p.__init__.__code__.co_varnames
                    kwargs = {}
                    if 'debug' in init_args:
                        kwargs['debug'] = debug
                    return p(ingredient_parser, **kwargs)
            return None

        # Content sample for sniffing
        sample = ""
        try:
            with open(filepath, 'rb') as f:
                raw = f.read(8192)
                sample = raw.decode('utf-8', errors='ignore')
        except Exception:
            pass

        best_parser_cls = None
        best_score = 0.0

        for p_cls in cls._parsers:
            try:
                score = p_cls.detect(filepath, sample)
                if score > best_score:
                    best_score = score
                    best_parser_cls = p_cls
                    if score >= 0.99:  # Unambiguous match, stop early
                        break
            except Exception as e:
                logger.debug(
                    "Parser %s.detect() raised exception on %s: %s",
                    p_cls.__name__, filepath, e, exc_info=True
                )

        if best_parser_cls and best_score > 0:
            init_args = best_parser_cls.__init__.__code__.co_varnames
            kwargs = {}
            if 'debug' in init_args:
                kwargs['debug'] = debug
            return best_parser_cls(ingredient_parser, **kwargs)

        # Fallback for generic text
        if filepath.suffix.lower() in {'.txt', '.ccf', '.prn', '.out', ''}:
            from .generic import GenericTextParser
            return GenericTextParser(ingredient_parser)

        return None

# Convenience method to match ParserFactory API
def get_parser(filepath: Path, ingredient_parser: BaseIngredientParser, format_name: Optional[str] = None, debug: bool = False) -> Optional[BaseRecipeParser]:
    return ParserRegistry.get_parser(filepath, ingredient_parser, format_name, debug)
