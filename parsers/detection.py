# SPDX-License-Identifier: MIT
"""
Format detection system for recipe files.

This module provides pluggable format detection based on:
1. File extension hints
2. Content analysis (magic bytes, patterns)
3. Column layout (for CSV)
4. Schema patterns (for SQLite)
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Optional, List, Dict, Tuple, Set
import re
import csv
import io


class Format(Enum):
    """Supported recipe formats."""
    # Text-based single format
    MASTERCOOK = "mastercook"
    MEALMASTER = "mealmaster"
    COMPUCHEF = "compuchef"
    RICETTE = "ricette"
    RICETTE_MD = "ricette_md"
    EDNA = "edna"
    NYC = "nyc"
    RECIPEML = "recipeml"
    RICETTE_JSON = "ricette_json"

    # Multi-format
    MIXED = "mixed"  # Only for mastercook/mealmaster/compuchef

    # Structured formats
    CSV = "csv"
    CSV_20KRECIPES = "csv_20krecipes"
    CSV_GENERIC = "csv_generic"
    SQLITE = "sqlite"
    HTML = "html"
    PDF = "pdf"
    IMAGE = "image"
    GENERIC_TEXT = "generic_text"

    UNKNOWN = "unknown"


@dataclass
class DetectionResult:
    """Result of format detection."""
    format: Format
    confidence: float  # 0.0-1.0
    reason: str
    metadata: Dict = None  # Additional context (e.g., csv_columns, sqlite_schema)

    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}


class FormatDetector(ABC):
    """Abstract base class for format detectors."""

    @abstractmethod
    def detect(self, filepath: Path, content_sample: Optional[str] = None) -> Optional[DetectionResult]:
        """
        Detect if this format matches the given file.

        Args:
            filepath: Path to the file
            content_sample: First few KB of file content for sniffing

        Returns:
            DetectionResult if format matches, None otherwise
        """
        pass

    @abstractmethod
    def priority(self) -> int:
        """Lower numbers = higher priority when multiple detectors match."""
        pass


# --- Text-based Format Detectors ---

class MasterCookDetector(FormatDetector):
    def detect(self, filepath: Path, content_sample: Optional[str] = None) -> Optional[DetectionResult]:
        if not content_sample:
            return None
        m = re.search(r'\*\s*Exported\s+from\s+MasterCook[^*]*\*', content_sample, re.IGNORECASE)
        if m:
            return DetectionResult(
                format=Format.MASTERCOOK,
                confidence=0.95,
                reason=f"Found MasterCook signature at offset {m.start()}",
                metadata={'position': m.start()}
            )
        return None

    def priority(self) -> int:
        return 1  # High priority


class MealMasterDetector(FormatDetector):
    def detect(self, filepath: Path, content_sample: Optional[str] = None) -> Optional[DetectionResult]:
        if not content_sample:
            return None
        m = re.search(r'^(?:MMMMM|-----).*[A-Z0-9]', content_sample, re.MULTILINE)
        if m:
            return DetectionResult(
                format=Format.MEALMASTER,
                confidence=0.90,
                reason=f"Found MealMaster signature at offset {m.start()}",
                metadata={'position': m.start()}
            )
        return None

    def priority(self) -> int:
        return 2


class CompuChefDetector(FormatDetector):
    def detect(self, filepath: Path, content_sample: Optional[str] = None) -> Optional[DetectionResult]:
        if not content_sample:
            return None

        # Check for explicit Recipe Via Compu-Chef marker first
        m = re.search(r'Recipe Via Compu-Chef', content_sample, re.IGNORECASE)
        if m:
            return DetectionResult(
                format=Format.COMPUCHEF,
                confidence=0.95,
                reason=f"Found explicit Compu-Chef marker at offset {m.start()}",
                metadata={'position': m.start()}
            )

        # Then check for star patterns (but not MasterCook)
        m = re.search(r'^\s*\*{3,}\s*(?![^*]*Exported from)[^*]+\s*\*{3,}', content_sample, re.MULTILINE)
        if m:
            return DetectionResult(
                format=Format.COMPUCHEF,
                confidence=0.75,
                reason=f"Found Compu-Chef star pattern at offset {m.start()}",
                metadata={'position': m.start()}
            )
        return None

    def priority(self) -> int:
        return 3


class RicetteDetector(FormatDetector):
    def detect(self, filepath: Path, content_sample: Optional[str] = None) -> Optional[DetectionResult]:
        if not content_sample:
            return None
        m = re.search(r'^:Ricette', content_sample, re.MULTILINE)
        if m:
            return DetectionResult(
                format=Format.RICETTE,
                confidence=0.95,
                reason=f"Found Ricette signature at offset {m.start()}",
                metadata={'position': m.start()}
            )
        return None

    def priority(self) -> int:
        return 5


class EdnaDetector(FormatDetector):
    def detect(self, filepath: Path, content_sample: Optional[str] = None) -> Optional[DetectionResult]:
        if not content_sample:
            return None
        m = re.search(r'^------------\s*(?=[\r\n]+\s*id:)', content_sample, re.MULTILINE)
        if m:
            # Edna requires double newline before if preceded by content
            prefix = content_sample[:m.start()].strip()
            if prefix:
                before = content_sample[max(0, m.start()-4):m.start()]
                if not before.endswith('\n\n') and not before.endswith('\r\n\r\n'):
                    return None
            return DetectionResult(
                format=Format.EDNA,
                confidence=0.90,
                reason=f"Found Edna separator pattern at offset {m.start()}",
                metadata={'position': m.start()}
            )
        return None

    def priority(self) -> int:
        return 4


class NYCDetector(FormatDetector):
    def detect(self, filepath: Path, content_sample: Optional[str] = None) -> Optional[DetectionResult]:
        if not content_sample:
            return None
        m = re.search(r'^@{5}\s+Now You\'re Cooking!', content_sample, re.MULTILINE)
        if m:
            return DetectionResult(
                format=Format.NYC,
                confidence=0.95,
                reason=f"Found NYC signature at offset {m.start()}",
                metadata={'position': m.start()}
            )
        return None

    def priority(self) -> int:
        return 6


class RicetteMdDetector(FormatDetector):
    def detect(self, filepath: Path, content_sample: Optional[str] = None) -> Optional[DetectionResult]:
        if not content_sample:
            return None
        m = re.search(r'^#\s+', content_sample, re.MULTILINE)
        if m:
            return DetectionResult(
                format=Format.RICETTE_MD,
                confidence=0.60,  # Low confidence - many formats start with #
                reason=f"Found markdown heading at offset {m.start()}",
                metadata={'position': m.start()}
            )
        return None

    def priority(self) -> int:
        return 10


class RecipeMLDetector(FormatDetector):
    def detect(self, filepath: Path, content_sample: Optional[str] = None) -> Optional[DetectionResult]:
        if not content_sample:
            return None
        m = re.search(r'<recipeml|<recipe[^a-zA-Z]', content_sample, re.IGNORECASE)
        if m:
            return DetectionResult(
                format=Format.RECIPEML,
                confidence=0.95,
                reason=f"Found XML/RecipeML tag at offset {m.start()}",
                metadata={'position': m.start()}
            )
        return None

    def priority(self) -> int:
        return 7


class RicetteJsonDetector(FormatDetector):
    def detect(self, filepath: Path, content_sample: Optional[str] = None) -> Optional[DetectionResult]:
        if not content_sample:
            return None
        m = re.search(r'^\s*[\{\[]', content_sample, re.MULTILINE)
        if m:
            # Check for Ricette JSON specific fields
            json_match = re.search(r'["\']Nome["\']|["\']Ingredienti["\']', content_sample)
            if json_match:
                return DetectionResult(
                    format=Format.RICETTE_JSON,
                    confidence=0.85,
                    reason=f"Found JSON with Ricette fields at offset {m.start()}",
                    metadata={'position': m.start()}
                )
        return None

    def priority(self) -> int:
        return 11


# --- CSV Format Detectors ---

class CsvDetector(FormatDetector):
    """Base CSV detector that examines column headers."""

    def _analyze_csv_headers(self, filepath: Path) -> Optional[Dict]:
        """Extract CSV headers and metadata."""
        try:
            with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
                # Read first line to detect delimiter
                first_line = f.readline()
                f.seek(0)

                # Try common delimiters
                for delimiter in [',', ';', '\t', '|']:
                    reader = csv.DictReader(f, delimiter=delimiter)
                    headers = reader.fieldnames
                    if headers and len(headers) > 1:
                        # Found a delimiter that works
                        f.seek(0)
                        return {
                            'headers': [h.strip().lower() if h else '' for h in headers],
                            'original_headers': headers,
                            'delimiter': delimiter,
                            'count': len(headers)
                        }
        except Exception:
            pass
        return None

    def detect(self, filepath: Path, content_sample: Optional[str] = None) -> Optional[DetectionResult]:
        if filepath.suffix.lower() != '.csv':
            return None

        headers_info = self._analyze_csv_headers(filepath)
        if not headers_info:
            return None

        headers = headers_info['headers']

        # Check for 20krecipes format (TITLE, INSTRUCT, INGRED, SERVES, ORIGIN, KEYWORD, TITLE_NO, SUBDIR)
        if self._is_20krecipes_format(headers):
            return DetectionResult(
                format=Format.CSV_20KRECIPES,
                confidence=0.95,
                reason="Detected 20krecipes CSV format",
                metadata=headers_info
            )

        # Check for generic recipe format (name/title, ingredients, instructions)
        if self._is_generic_recipe_format(headers):
            return DetectionResult(
                format=Format.CSV_GENERIC,
                confidence=0.80,
                reason="Detected generic recipe CSV format",
                metadata=headers_info
            )

        return None

    def _is_20krecipes_format(self, headers: List[str]) -> bool:
        """Check if headers match 20krecipes format."""
        key_fields = {'title', 'instruct', 'ingred', 'serves', 'origin', 'keyword'}
        return key_fields.issubset(set(headers))

    def _is_generic_recipe_format(self, headers: List[str]) -> bool:
        """Check if headers match generic recipe format."""
        has_title = any(h in headers for h in ['title', 'name', 'recipe_name', 'recipe name'])
        has_ingredients = any(h in headers for h in ['ingredients', 'ingredient', 'ingred', 'ingredient_list'])
        has_instructions = any(h in headers for h in ['instructions', 'instruction', 'directions', 'method', 'instruct', 'steps'])
        return has_title and has_ingredients and has_instructions

    def priority(self) -> int:
        return 20


# --- SQLite Detector ---

class SqliteDetector(FormatDetector):
    """Detects SQLite database files."""

    def detect(self, filepath: Path, content_sample: Optional[str] = None) -> Optional[DetectionResult]:
        if filepath.suffix.lower() not in {'.sqlite', '.db', '.sqlite3'}:
            return None

        # Check magic bytes for SQLite
        try:
            with open(filepath, 'rb') as f:
                magic = f.read(16)
                if magic.startswith(b'SQLite format 3\x00'):
                    return DetectionResult(
                        format=Format.SQLITE,
                        confidence=0.99,
                        reason="File has SQLite magic bytes",
                        metadata={}
                    )
        except Exception:
            pass

        return None

    def priority(self) -> int:
        return 25


# --- HTML/PDF/Image Detectors ---

class HtmlDetector(FormatDetector):
    def detect(self, filepath: Path, content_sample: Optional[str] = None) -> Optional[DetectionResult]:
        if filepath.suffix.lower() not in {'.html', '.htm'}:
            return None

        if content_sample and ('<html' in content_sample.lower() or '<!doctype' in content_sample.lower()):
            return DetectionResult(
                format=Format.HTML,
                confidence=0.95,
                reason="File has HTML extension and HTML markers",
                metadata={}
            )

        return None

    def priority(self) -> int:
        return 30


class PdfDetector(FormatDetector):
    def detect(self, filepath: Path, content_sample: Optional[str] = None) -> Optional[DetectionResult]:
        if filepath.suffix.lower() != '.pdf':
            return None

        try:
            with open(filepath, 'rb') as f:
                magic = f.read(4)
                if magic.startswith(b'%PDF'):
                    return DetectionResult(
                        format=Format.PDF,
                        confidence=0.99,
                        reason="File has PDF magic bytes",
                        metadata={}
                    )
        except Exception:
            pass

        return None

    def priority(self) -> int:
        return 35


class ImageDetector(FormatDetector):
    def detect(self, filepath: Path, content_sample: Optional[str] = None) -> Optional[DetectionResult]:
        if filepath.suffix.lower() not in {'.jpg', '.jpeg', '.png', '.gif', '.bmp'}:
            return None

        try:
            with open(filepath, 'rb') as f:
                magic = f.read(8)
                # Check for JPEG, PNG, GIF magic bytes
                if (magic.startswith(b'\xff\xd8\xff') or
                    magic.startswith(b'\x89PNG') or
                    magic.startswith(b'GIF8')):
                    return DetectionResult(
                        format=Format.IMAGE,
                        confidence=0.99,
                        reason="File has image magic bytes",
                        metadata={}
                    )
        except Exception:
            pass

        return None

    def priority(self) -> int:
        return 36


# --- Extension-based Fallbacks ---

class ExtensionDetector(FormatDetector):
    """Maps file extensions to formats when content sniffing isn't available."""

    EXTENSION_MAP = {
        '.mmf': Format.MEALMASTER,
        '.mm': Format.MEALMASTER,
        '.mxp': Format.MASTERCOOK,
        '.mx2': Format.MASTERCOOK,
        '.mz2': Format.MASTERCOOK,
        '.ccf': Format.COMPUCHEF,
        '.xml': Format.RECIPEML,
        '.recipeml': Format.RECIPEML,
        '.json': Format.RICETTE_JSON,
        '.md': Format.RICETTE_MD,
    }

    def detect(self, filepath: Path, content_sample: Optional[str] = None) -> Optional[DetectionResult]:
        ext = filepath.suffix.lower()
        fmt = self.EXTENSION_MAP.get(ext)
        if fmt:
            return DetectionResult(
                format=fmt,
                confidence=0.70,  # Lower confidence - could be wrong
                reason=f"Matched file extension {ext}",
                metadata={}
            )
        return None

    def priority(self) -> int:
        return 100  # Very low priority - use only as fallback


# --- Format Detection Registry ---

class FormatDetectionRegistry:
    """Registry and orchestrator for format detection."""

    def __init__(self):
        self.detectors: List[FormatDetector] = []
        self._register_default_detectors()

    def _register_default_detectors(self):
        """Register all standard detectors."""
        self.detectors.extend([
            MasterCookDetector(),
            MealMasterDetector(),
            CompuChefDetector(),
            EdnaDetector(),
            NYCDetector(),
            RicetteDetector(),
            RecipeMLDetector(),
            RicetteMdDetector(),
            RicetteJsonDetector(),
            CsvDetector(),
            SqliteDetector(),
            HtmlDetector(),
            PdfDetector(),
            ImageDetector(),
            ExtensionDetector(),
        ])
        # Sort by priority
        self.detectors.sort(key=lambda d: d.priority())

    def register_detector(self, detector: FormatDetector, position: Optional[int] = None):
        """Register a custom detector."""
        if position is not None:
            self.detectors.insert(position, detector)
        else:
            self.detectors.append(detector)
        # Re-sort
        self.detectors.sort(key=lambda d: d.priority())

    def detect(self, filepath: Path, sample_size: int = 8192) -> DetectionResult:
        """
        Detect file format using registered detectors.

        Args:
            filepath: Path to file
            sample_size: Number of bytes to read for content sniffing

        Returns:
            DetectionResult with best match (confidence ordered)
        """
        # Read content sample for sniffing
        content_sample = None
        try:
            with open(filepath, 'rb') as f:
                raw = f.read(sample_size)
                # Try to decode as text
                try:
                    content_sample = raw.decode('utf-8', errors='ignore')
                except Exception:
                    pass
        except Exception:
            pass

        # Run all detectors
        results = []
        for detector in self.detectors:
            try:
                result = detector.detect(filepath, content_sample)
                if result:
                    results.append(result)
            except Exception:
                # Detectors should not raise; skip on error
                pass

        # Return highest confidence result
        if results:
            results.sort(key=lambda r: (-r.confidence, self._detector_priority(r.format)))
            return results[0]

        # Fallback to generic text or unknown
        if filepath.suffix.lower() in {'.txt', '.ccf', '.prn', '.out', ''}:
            return DetectionResult(
                format=Format.GENERIC_TEXT,
                confidence=0.30,
                reason="No specific format detected; treating as generic text",
                metadata={}
            )

        return DetectionResult(
            format=Format.UNKNOWN,
            confidence=0.0,
            reason="Unable to detect file format",
            metadata={}
        )

    def _detector_priority(self, fmt: Format) -> int:
        """Get priority for format (lower = higher priority)."""
        priority_map = {
            Format.MASTERCOOK: 1,
            Format.MEALMASTER: 2,
            Format.COMPUCHEF: 3,
            Format.EDNA: 4,
            Format.RICETTE: 5,
            Format.NYC: 6,
            Format.RECIPEML: 7,
            Format.RICETTE_MD: 10,
            Format.RICETTE_JSON: 11,
            Format.CSV_20KRECIPES: 20,
            Format.CSV_GENERIC: 21,
            Format.CSV: 22,
            Format.SQLITE: 25,
            Format.HTML: 30,
            Format.PDF: 35,
            Format.IMAGE: 36,
            Format.GENERIC_TEXT: 100,
            Format.MIXED: 200,
            Format.UNKNOWN: 999,
        }
        return priority_map.get(fmt, 500)


# Global registry instance
_global_registry: Optional[FormatDetectionRegistry] = None


def get_detection_registry() -> FormatDetectionRegistry:
    """Get the global format detection registry."""
    global _global_registry
    if _global_registry is None:
        _global_registry = FormatDetectionRegistry()
    return _global_registry
