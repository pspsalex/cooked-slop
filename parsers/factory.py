# SPDX-License-Identifier: MIT
import re
from pathlib import Path
from typing import Optional, List
from .models import Recipe, Ingredient
from .base import BaseRecipeParser, BaseIngredientParser
from .mealmaster import MealMasterParser
from .mastercook import MasterCookParser
from .compuchef import CompuChefParser
from .ricette import RicetteParser
from .html_parser import HtmlParser
from .generic import GenericTextParser
from .stubs import PdfParser, ImageParser, SqliteParser, CsvParser


# --- Format signature detectors ---

def sniff_format(sample: str) -> Optional[str]:
    """Find the earliest occurring format signature in the sample."""
    matches = []
    
    # MasterCook
    m = re.search(r'\*\s*Exported\s+from\s+MasterCook[^*]*\*', sample, re.IGNORECASE)
    if m: matches.append((m.start(), 'mastercook'))
    
    # MealMaster
    # MMMMM or ----- followed by space and then some characters (usually word or dashes)
    m = re.search(r'^(?:MMMMM|-----)\s*[-A-Z0-9]+', sample, re.MULTILINE)
    if m: matches.append((m.start(), 'mealmaster'))
    
    # CompuChef (start block title)
    m = re.search(r'^\*+\s*[^*]+\s*\*+$', sample, re.MULTILINE)
    if m: matches.append((m.start(), 'compuchef'))
    
    # CompuChef (end tag fallback)
    m = re.search(r'Recipe Via Compu-Chef', sample, re.IGNORECASE)
    if m: matches.append((m.start(), 'compuchef'))
    
    # Ricette
    m = re.search(r'^:Ricette', sample, re.MULTILINE)
    if m: matches.append((m.start(), 'ricette'))
    
    if not matches:
        return None
    
    # Return the format of the earliest match
    # If same position, prioritize more specific formats
    priority = {'mastercook': 0, 'mealmaster': 1, 'compuchef': 2, 'ricette': 3}
    matches.sort(key=lambda x: (x[0], priority.get(x[1], 99)))
    return matches[0][1]


# Extensions that require content sniffing (not unambiguous on their own)
AMBIGUOUS_EXTENSIONS = {'.txt', '.ccf', '.prn', '.out', ''}


class MixedFormatParser(BaseRecipeParser):
    """Parser that handles files containing multiple recipes in different formats."""
    
    def __init__(self, ingredient_parser: BaseIngredientParser):
        super().__init__(ingredient_parser)
        self.source_format = "Mixed"

    def parse_content(self, content: str, filepath: str) -> List[Recipe]:
        # We want to split the content into blocks that look like recipes
        # Each block starts where any known header is found
        sigs = [
            r'\*\s*Exported\s+from\s+MasterCook[^*]*\*',
            r'^(?:MMMMM|-----)\s*[-A-Z0-9]+',
            r'^\*+\s*[^*]+\s*\*+$', # CompuChef title
            r'Recipe Via Compu-Chef', # CompuChef footer
            r'^:Ricette'
        ]
        
        # Find all start positions
        all_starts = []
        for sig in sigs:
            for m in re.finditer(sig, content, re.MULTILINE | re.IGNORECASE):
                all_starts.append(m.start())
        
        all_starts = sorted(list(set(all_starts)))
        
        if not all_starts:
            from .generic import GenericTextParser
            return GenericTextParser(self.ingredient_parser).parse_content(content, filepath)
            
        recipes = []
        for i in range(len(all_starts)):
            start = all_starts[i]
            end = all_starts[i+1] if i+1 < len(all_starts) else len(content)
            chunk = content[start:end]
            
            # Detect format for this specific chunk
            fmt = sniff_format(chunk)
            parser = None
            if fmt == 'mastercook':
                parser = MasterCookParser(self.ingredient_parser)
            elif fmt == 'mealmaster':
                parser = MealMasterParser(self.ingredient_parser)
            elif fmt == 'compuchef':
                parser = CompuChefParser(self.ingredient_parser)
            elif fmt == 'ricette':
                parser = RicetteParser(self.ingredient_parser)
            
            if parser:
                # We use parse_content to avoid reading the file again
                # and to avoid infinite recursion if MixedFormatParser was used
                recipes.extend(parser.parse_content(chunk, filepath))
                
        return recipes


class ParserFactory:
    """Registry to detect which parser to use, first by file content then by extension."""

    @staticmethod
    def get_parser(filepath: Path, ingredient_parser: BaseIngredientParser) -> Optional[BaseRecipeParser]:
        ext = filepath.suffix.lower()

        # Always sniff ambiguous extensions (and extensions that could hold multiple formats)
        if ext in AMBIGUOUS_EXTENSIONS:
            # We return MixedFormatParser for ambiguous files
            # It will handle sniffing and delegation internally
            return MixedFormatParser(ingredient_parser)

        # Unambiguous extension dispatch
        if ext in {'.mmf', '.mm'}:
            return MealMasterParser(ingredient_parser)
        elif ext in {'.mxp', '.mx2', '.mz2'}:
            return MasterCookParser(ingredient_parser)
        elif ext in {'.html', '.htm'}:
            return HtmlParser(ingredient_parser)
        elif ext == '.pdf':
            return PdfParser(ingredient_parser)
        elif ext in {'.jpg', '.jpeg', '.png'}:
            return ImageParser(ingredient_parser)
        elif ext in {'.sqlite', '.db'}:
            return SqliteParser(ingredient_parser)
        elif ext == '.csv':
            return CsvParser(ingredient_parser)

        return None
