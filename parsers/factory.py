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
from .ricette_md import RicetteMdParser
from .edna import EdnaParser
from .nyc import NYCParser
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
    
    if not matches:
        return None
    
    # Return the format of the earliest match
    priority = {'mastercook': 0, 'edna': 1, 'nyc': 2, 'mealmaster': 3, 'compuchef': 4, 'ricette': 5, 'ricette_md': 6}
    matches.sort(key=lambda x: (x[0], priority.get(x[1], 99)))
    return matches[0][1]


# Extensions that require content sniffing
AMBIGUOUS_EXTENSIONS = {'.txt', '.ccf', '.prn', '.out', '.md', ''}


class MixedFormatParser(BaseRecipeParser):
    """Parser that handles files containing multiple recipes in different formats."""
    
    def __init__(self, ingredient_parser: BaseIngredientParser):
        super().__init__(ingredient_parser)
        self.source_format = "Mixed"

    def parse_content(self, content: str, filepath: str) -> List[Recipe]:
        # Define start signatures and priorities
        sigs = {
            'mastercook': r'\*\s*Exported\s+from\s+MasterCook[^*]*\*',
            'mealmaster': r'^(?:MMMMM|-----).*[A-Z0-9]',
            'compuchef': r'^\s*\*{3,}\s*(?![^*]*Exported from)[^*]+\s*\*{3,}',
            'ricette': r'^:Ricette',
            'edna': r'^------------\s*(?=[\r\n]+\s*id:)',
            'ricette_md': r'^#\s+',
            'nyc': r'^@{5}\s+Now You\'re Cooking!'
        }
        
        # End markers for formats that have them
        end_markers = {
            'compuchef': r'\*{3,}\s*Recipe Via Compu-Chef.*?\*{3,}',
            'nyc': r'\*\* Exported from Now You.re Cooking!.* \*\*'
        }
        
        priority = {'mastercook': 0, 'edna': 1, 'nyc': 2, 'mealmaster': 3, 'compuchef': 4, 'ricette': 5, 'ricette_md': 6}
        
        # Find all candidate starts
        all_matches = []
        for fmt, sig in sigs.items():
            for m in re.finditer(sig, content, re.MULTILINE | re.IGNORECASE):
                start = m.start()
                # Apply Edna rule: must follow \n\n if preceded by content
                if fmt == 'edna':
                    prefix = content[:start].strip()
                    if prefix:
                        before = content[max(0, start-4):start]
                        if not before.endswith('\n\n') and not before.endswith('\r\n\r\n'):
                            continue
                all_matches.append((start, fmt))
        
        if not all_matches:
            from .generic import GenericTextParser
            return GenericTextParser(self.ingredient_parser).parse_content(content, filepath)
            
        # Sort by position and then priority
        all_matches.sort(key=lambda x: (x[0], priority.get(x[1], 99)))
        
        recipes = []
        idx = 0
        while idx < len(all_matches):
            msg_start, fmt = all_matches[idx]
            
            # Determine end of this block
            # If it has a footer, find the first footer AFTER msg_start
            footer_sig = end_markers.get(fmt)
            end_pos = -1
            if footer_sig:
                m_end = re.search(footer_sig, content[msg_start:], re.MULTILINE | re.IGNORECASE)
                if m_end:
                    end_pos = msg_start + m_end.end()
            
            if end_pos != -1:
                # We have a clear end. Take the chunk and skip any starts inside it.
                chunk = content[msg_start:end_pos]
                # Advance idx to skip matches within this chunk
                while idx + 1 < len(all_matches) and all_matches[idx + 1][0] < end_pos:
                    idx += 1
            else:
                # No fixed footer.
                # Find the next start that is strictly GREATER than msg_start
                next_start_idx = idx + 1
                while next_start_idx < len(all_matches) and all_matches[next_start_idx][0] == msg_start:
                    next_start_idx += 1
                
                # If there are more recipes of the SAME format following immediately (same msg_start),
                # they are already handled by priority.
                # We want the next REAL start at a higher position.
                next_real_start_idx = next_start_idx
                if next_real_start_idx < len(all_matches):
                    end_pos = all_matches[next_real_start_idx][0]
                    # Since many parsers handle multiple recipes, we could potentially
                    # take all consecutive recipes of the same format.
                    # But for now, taking until the next start is safest.
                    idx = next_real_start_idx - 1
                else:
                    end_pos = len(content)
                    idx = len(all_matches)
                
                chunk = content[msg_start:end_pos]
            
            # Now parse the chunk
            if fmt == 'mastercook':
                parser = MasterCookParser(self.ingredient_parser)
            elif fmt == 'mealmaster':
                parser = MealMasterParser(self.ingredient_parser)
            elif fmt == 'compuchef':
                parser = CompuChefParser(self.ingredient_parser)
            elif fmt == 'ricette':
                parser = RicetteParser(self.ingredient_parser)
            elif fmt == 'edna':
                parser = EdnaParser(self.ingredient_parser)
            elif fmt == 'ricette_md':
                parser = RicetteMdParser(self.ingredient_parser)
            elif fmt == 'nyc':
                parser = NYCParser(self.ingredient_parser)
            else:
                parser = None
                
            if parser:
                recipes.extend(parser.parse_content(chunk, filepath))
            
            idx += 1
            
        return recipes


class ParserFactory:
    """Registry to detect which parser to use, first by file content then by extension."""

    @staticmethod
    def get_parser(filepath: Path, ingredient_parser: BaseIngredientParser, format_name: Optional[str] = None) -> Optional[BaseRecipeParser]:
        if format_name:
            fmt = format_name.lower()
            if fmt == 'mastercook':
                return MasterCookParser(ingredient_parser)
            elif fmt == 'mealmaster':
                return MealMasterParser(ingredient_parser)
            elif fmt == 'compuchef':
                return CompuChefParser(ingredient_parser)
            elif fmt == 'ricette':
                return RicetteParser(ingredient_parser)
            elif fmt == 'edna':
                return EdnaParser(ingredient_parser)
            elif fmt == 'ricette_md':
                return RicetteMdParser(ingredient_parser)
            elif fmt == 'nyc':
                return NYCParser(ingredient_parser)
            # Add more overrides as needed

        ext = filepath.suffix.lower()

        if ext in AMBIGUOUS_EXTENSIONS:
            return MixedFormatParser(ingredient_parser)

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
