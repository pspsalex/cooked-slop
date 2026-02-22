# SPDX-License-Identifier: MIT
"""
Parser factory with pluggable format detection.

This module orchestrates format detection and parser selection using:
1. The new detection registry for extensible format detection
2. MixedFormatParser only for mastercook/mealmaster/compuchef
3. Other formats applied to entire file
"""

import re
from pathlib import Path
from typing import Optional, List
from .models import Recipe, Ingredient
from .base import BaseRecipeParser, BaseIngredientParser
from .mealmaster import MealMasterParser
from .mastercook import MasterCookParser
from .compuchef import CompuChefParser
from .ricette import RicetteParser
from .ricette_md import RicetteMdParser
from .edna import EdnaParser
from .nyc import NYCParser
from .html_parser import HtmlParser
from .generic import GenericTextParser
from .stubs import PdfParser, ImageParser, SqliteParser, CsvParser
from .recipeml import RecipeMLParser
from .twentykrecipes import TwentyKRecipesParser
from .ricette_json import RicetteJsonParser
from .detection import get_detection_registry, Format, DetectionResult


def sniff_format(sample: str) -> Optional[str]:
    """
    Legacy function for backward compatibility.
    Find the earliest occurring format signature in the sample.
    """
    matches = []

    # MasterCook
    m = re.search(r'\*\s*Exported\s+from\s+MasterCook[^*]*\*', sample, re.IGNORECASE)
    if m: matches.append((m.start(), 'mastercook'))

    # MealMaster
    m = re.search(r'^(?:MMMMM|-----).*[A-Z0-9]', sample, re.MULTILINE)
    if m: matches.append((m.start(), 'mealmaster'))

    # CompuChef (at least 3 stars)
    m = re.search(r'^\s*\*{3,}\s*(?![^*]*Exported from)[^*]+\s*\*{3,}', sample, re.MULTILINE)
    if m: matches.append((m.start(), 'compuchef'))

    m = re.search(r'Recipe Via Compu-Chef', sample, re.IGNORECASE)
    if m: matches.append((m.start(), 'compuchef'))

    # Ricette
    m = re.search(r'^:Ricette', sample, re.MULTILINE)
    if m: matches.append((m.start(), 'ricette'))

    # Edna (refined to separator + id: field)
    m = re.search(r'^------------\s*(?=[\r\n]+\s*id:)', sample, re.MULTILINE)
    if m: matches.append((m.start(), 'edna'))

    # Ricette MD
    m = re.search(r'^#\s+', sample, re.MULTILINE)
    if m: matches.append((m.start(), 'ricette_md'))

    # NYC
    m = re.search(r'^@{5}\s+Now You\'re Cooking!', sample, re.MULTILINE)
    if m: matches.append((m.start(), 'nyc'))

    # RecipeML (XML)
    m = re.search(r'<recipeml|<recipe[^a-zA-Z]', sample, re.IGNORECASE)
    if m: matches.append((m.start(), 'recipeml'))

    # Ricette JSON (starts with { or [ for JSON)
    m = re.search(r'^\s*[\{\[]', sample, re.MULTILINE)
    if m:
        # Try to detect if it's Ricette JSON by looking for specific fields
        json_match = re.search(r'["\']Nome["\']|["\']Ingredienti["\']', sample)
        if json_match:
            matches.append((m.start(), 'ricette_json'))

    if not matches:
        return None

    # Return the format of the earliest match
    priority = {'mastercook': 0, 'edna': 1, 'nyc': 2, 'mealmaster': 3, 'compuchef': 4, 'ricette': 5, 'ricette_md': 6, 'recipeml': 7, 'ricette_json': 8}
    matches.sort(key=lambda x: (x[0], priority.get(x[1], 99)))
    return matches[0][1]


# Extensions that require content sniffing
AMBIGUOUS_EXTENSIONS = {'.txt', '.ccf', '.prn', '.out', '.md', '.csv', ''}


class MixedFormatParser(BaseRecipeParser):
    """
    Parser for files containing multiple recipes in DIFFERENT FORMATS.

    IMPORTANT: This only applies to mastercook/mealmaster/compuchef formats.
    All other formats are applied to the entire file (no mixed-format splitting).

    This restriction prevents false positives where generic patterns (e.g., markdown headings)
    accidentally split a single-format file.
    """

    # Only these formats support mixed-format files
    MIXED_FORMAT_SUPPORT = {'mastercook', 'mealmaster', 'compuchef'}

    def __init__(self, ingredient_parser: BaseIngredientParser):
        super().__init__(ingredient_parser)
        self.source_format = "Mixed"

    def parse_content(self, content: str, filepath: str) -> List[Recipe]:
        """
        Parse content, supporting mixed formats.
        
        For MasterCook/MealMaster/CompuChef files, look for ALL three signatures.
        For other formats, apply single format to entire file.
        """
        # First, try to find ALL mixed format signatures (mastercook, mealmaster, compuchef)
        # These are the ONLY formats that support true mixed-file parsing
        recipes = self._try_parse_all_mixed_formats(content, filepath)
        if recipes:
            return recipes
        
        # If no mixed formats found, try single format detection
        sample = content[:8192]
        registry = get_detection_registry()
        
        from pathlib import Path as PathlibPath
        temp_path = PathlibPath(filepath)
        
        detection_result = None
        try:
            detection_result = registry.detect(temp_path, sample_size=len(sample))
        except Exception:
            pass
        
        if detection_result:
            detected_fmt = detection_result.format
            # For any detected format, use the appropriate parser
            return self._parse_single_format(content, filepath, detected_fmt)
        
        # Fallback: use generic parser
        return GenericTextParser(self.ingredient_parser).parse_content(content, filepath)
    
    def _try_parse_all_mixed_formats(self, content: str, filepath: str) -> List[Recipe]:
        """
        Try to parse a file containing recipes from multiple formats.
        Looks for mastercook, mealmaster, and compuchef signatures.
        Returns recipes if ANY mixed format found, empty list otherwise.
        """
        # Define start signatures for all three formats
        sigs = {
            'mastercook': r'\*\s*Exported\s+from\s+MasterCook[^*]*\*',
            'mealmaster': r'^(?:MMMMM|-----).*[A-Z0-9]',
            'compuchef': r'^\s*\*{3,}\s*(?![^*]*Exported from)[^*]+\s*\*{3,}',
        }
        
        # End markers for formats that have them
        end_markers = {
            'compuchef': r'\*{3,}\s*Recipe Via Compu-Chef.*?\*{3,}',
        }
        
        priority = {'mastercook': 0, 'mealmaster': 1, 'compuchef': 2}
        
        # Find ALL candidate starts for ANY mixed format
        all_matches = []
        for fmt, sig in sigs.items():
            for m in re.finditer(sig, content, re.MULTILINE | re.IGNORECASE):
                start = m.start()
                all_matches.append((start, fmt))
        
        # If no mixed format signatures found, return empty (caller will try other detection)
        if not all_matches:
            return []
        
        # Check if we have multiple formats or just one
        unique_formats = set(fmt for _, fmt in all_matches)
        if len(unique_formats) == 1:
            # Only one format found - not a true mixed file
            return []
        
        # We have a true mixed-format file! Parse it.
        # Sort by position and then priority
        all_matches.sort(key=lambda x: (x[0], priority.get(x[1], 99)))
        
        recipes = []
        idx = 0
        while idx < len(all_matches):
            msg_start, fmt = all_matches[idx]
            
            # Determine end of this block
            footer_sig = end_markers.get(fmt)
            end_pos = -1
            if footer_sig:
                m_end = re.search(footer_sig, content[msg_start:], re.MULTILINE | re.IGNORECASE)
                if m_end:
                    end_pos = msg_start + m_end.end()
            
            if end_pos != -1:
                chunk = content[msg_start:end_pos]
                # Skip matches within this chunk
                while idx + 1 < len(all_matches) and all_matches[idx + 1][0] < end_pos:
                    idx += 1
            else:
                # Find next start
                if idx + 1 < len(all_matches):
                    end_pos = all_matches[idx + 1][0]
                else:
                    end_pos = len(content)
                chunk = content[msg_start:end_pos]
            
            # Parse chunk with appropriate parser
            if fmt == 'mastercook':
                parser = MasterCookParser(self.ingredient_parser)
            elif fmt == 'mealmaster':
                parser = MealMasterParser(self.ingredient_parser)
            elif fmt == 'compuchef':
                parser = CompuChefParser(self.ingredient_parser)
            else:
                parser = None
            
            if parser:
                recipes.extend(parser.parse_content(chunk, filepath))
            
            idx += 1
        
        return recipes

    def _parse_single_format(self, content: str, filepath: str, detected_fmt: Format) -> List[Recipe]:
        """Apply a single format to the entire file."""
        parser = self._create_parser(detected_fmt)
        if parser:
            return parser.parse_content(content, filepath)
        return GenericTextParser(self.ingredient_parser).parse_content(content, filepath)

    def _create_parser(self, fmt: Format) -> Optional[BaseRecipeParser]:
        """Create appropriate parser for format."""
        parser_map = {
            Format.MASTERCOOK: MasterCookParser,
            Format.MEALMASTER: MealMasterParser,
            Format.COMPUCHEF: CompuChefParser,
            Format.RICETTE: RicetteParser,
            Format.EDNA: EdnaParser,
            Format.RICETTE_MD: RicetteMdParser,
            Format.NYC: NYCParser,
            Format.RECIPEML: RecipeMLParser,
            Format.RICETTE_JSON: RicetteJsonParser,
        }
        parser_class = parser_map.get(fmt)
        if parser_class:
            return parser_class(self.ingredient_parser)
        return None


class ParserFactory:
    """
    Factory for selecting appropriate recipe parser based on file format.

    Uses a two-stage process:
    1. Format override (if provided)
    2. Automatic detection:
       - Extension-based detection (for unambiguous extensions)
       - Content-based detection (for ambiguous extensions like .txt)
    """

    @staticmethod
    def get_parser(filepath: Path, ingredient_parser: BaseIngredientParser,
                  format_name: Optional[str] = None) -> Optional[BaseRecipeParser]:
        """
        Get appropriate parser for file.

        Args:
            filepath: Path to recipe file
            ingredient_parser: Ingredient parser instance
            format_name: Optional format override (e.g., 'mastercook', 'csv_20krecipes')

        Returns:
            Appropriate parser instance, or None if format unknown
        """
        # Stage 1: Handle explicit format override
        if format_name:
            return ParserFactory._get_parser_by_name(format_name, ingredient_parser)

        # Stage 2: Auto-detect format
        ext = filepath.suffix.lower()

        # Check for unambiguous extensions first
        ext_parser = ParserFactory._get_parser_by_extension(ext, ingredient_parser)
        if ext_parser:
            return ext_parser

        # For ambiguous extensions, use content sniffing
        if ext in AMBIGUOUS_EXTENSIONS:
            return ParserFactory._detect_and_get_parser(filepath, ingredient_parser)

        return None

    @staticmethod
    def _get_parser_by_name(format_name: str, ingredient_parser: BaseIngredientParser) -> Optional[BaseRecipeParser]:
        """Get parser by explicit format name."""
        fmt = format_name.lower()

        # Legacy names and format aliases
        format_map = {
            'mastercook': Format.MASTERCOOK,
            'mealmaster': Format.MEALMASTER,
            'compuchef': Format.COMPUCHEF,
            'ricette': Format.RICETTE,
            'edna': Format.EDNA,
            'ricette_md': Format.RICETTE_MD,
            'nyc': Format.NYC,
            'recipeml': Format.RECIPEML,
            'ricette_json': Format.RICETTE_JSON,
            '20krecipes': Format.CSV_20KRECIPES,
            'csv_20krecipes': Format.CSV_20KRECIPES,
            'csv_generic': Format.CSV_GENERIC,
            'csv': Format.CSV,
            'html': Format.HTML,
            'sqlite': Format.SQLITE,
        }

        detected_format = format_map.get(fmt)
        if detected_format:
            return ParserFactory._create_parser_for_format(detected_format, ingredient_parser)

        return None

    @staticmethod
    def _get_parser_by_extension(ext: str, ingredient_parser: BaseIngredientParser) -> Optional[BaseRecipeParser]:
        """Get parser by file extension (unambiguous cases only)."""
        extension_map = {
            '.mmf': Format.MEALMASTER,
            '.mm': Format.MEALMASTER,
            '.mxp': Format.MASTERCOOK,
            '.mx2': Format.MASTERCOOK,
            '.mz2': Format.MASTERCOOK,
            '.ccf': Format.COMPUCHEF,  # Actually ambiguous - handled separately
            '.xml': Format.RECIPEML,
            '.recipeml': Format.RECIPEML,
            '.json': Format.RICETTE_JSON,
            '.html': Format.HTML,
            '.htm': Format.HTML,
            '.pdf': Format.PDF,
            '.jpg': Format.IMAGE,
            '.jpeg': Format.IMAGE,
            '.png': Format.IMAGE,
            '.gif': Format.IMAGE,
            '.bmp': Format.IMAGE,
            '.sqlite': Format.SQLITE,
            '.sqlite3': Format.SQLITE,
            '.db': Format.SQLITE,
        }

        fmt = extension_map.get(ext)
        if fmt:
            return ParserFactory._create_parser_for_format(fmt, ingredient_parser)

        return None

    @staticmethod
    def _detect_and_get_parser(filepath: Path, ingredient_parser: BaseIngredientParser) -> Optional[BaseRecipeParser]:
        """Auto-detect format from content and return appropriate parser."""
        try:
            registry = get_detection_registry()
            result = registry.detect(filepath)
            
            # For formats that support mixed files, return MixedFormatParser
            # so it can check for multiple formats in the same file
            if result.format in {Format.MASTERCOOK, Format.MEALMASTER, Format.COMPUCHEF}:
                return MixedFormatParser(ingredient_parser)
            
            return ParserFactory._create_parser_for_format(result.format, ingredient_parser)
        except Exception:
            return None

    @staticmethod
    def _create_parser_for_format(fmt: Format, ingredient_parser: BaseIngredientParser) -> Optional[BaseRecipeParser]:
        """Create parser instance for detected format."""
        if fmt == Format.MASTERCOOK:
            return MasterCookParser(ingredient_parser)
        elif fmt == Format.MEALMASTER:
            return MealMasterParser(ingredient_parser)
        elif fmt == Format.COMPUCHEF:
            return CompuChefParser(ingredient_parser)
        elif fmt == Format.RICETTE:
            return RicetteParser(ingredient_parser)
        elif fmt == Format.EDNA:
            return EdnaParser(ingredient_parser)
        elif fmt == Format.RICETTE_MD:
            return RicetteMdParser(ingredient_parser)
        elif fmt == Format.NYC:
            return NYCParser(ingredient_parser)
        elif fmt == Format.RECIPEML:
            return RecipeMLParser(ingredient_parser)
        elif fmt == Format.RICETTE_JSON:
            return RicetteJsonParser(ingredient_parser)
        elif fmt == Format.CSV_20KRECIPES:
            return TwentyKRecipesParser(ingredient_parser)
        elif fmt in {Format.CSV, Format.CSV_GENERIC}:
            return CsvParser(ingredient_parser)
        elif fmt == Format.HTML:
            return HtmlParser(ingredient_parser)
        elif fmt == Format.PDF:
            return PdfParser(ingredient_parser)
        elif fmt == Format.IMAGE:
            return ImageParser(ingredient_parser)
        elif fmt == Format.SQLITE:
            return SqliteParser(ingredient_parser)
        elif fmt == Format.GENERIC_TEXT:
            return GenericTextParser(ingredient_parser)
        elif fmt == Format.MIXED:
            return MixedFormatParser(ingredient_parser)
        else:
            return None
