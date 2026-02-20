# SPDX-License-Identifier: MIT
import re
from typing import List
from .models import Recipe, Ingredient
from .base import BaseRecipeParser, BaseIngredientParser
from .units import normalize_unit

try:
    import nltk
    HAS_NLTK = True
except ImportError:
    HAS_NLTK = False

class MasterCookParser(BaseRecipeParser):
    PREP_VERBS = r'stemmed|washed|chopped|minced|diced|sliced|peeled|grated|shredded|cleaned|crushed|beaten|melted|sifted|mashed|halved|quartered|separated|softened|cooked|drained|thawed|frozen|chilled|warmed|sprinkled|garnished|cut'
    PREP_REGEX = re.compile(fr'^(?:(?:well|freshly|finely|roughly|thinly)\s+)?(?:{PREP_VERBS})(?:\s+(?:and|or)\s+(?:(?:well|freshly|finely|roughly|thinly)\s+)?(?:{PREP_VERBS}))?$')

    def __init__(self, ingredient_parser: BaseIngredientParser):
        super().__init__(ingredient_parser)
        self.source_format = "MasterCook"

    def parse_content(self, content: str, filepath: str) -> List[Recipe]:
        recipes = []
        
        # Split by MasterCook export header, allowing for version numbers like "MasterCook II"
        # We use a non-greedy catch-all for the content between MasterCook and the final asterisk
        recipe_sections = re.split(r'\*\s*Exported\s+from\s+MasterCook[^*]*\*', content, flags=re.IGNORECASE)
        for section in recipe_sections:
            section_stripped = section.strip()
            if not section_stripped: continue
            
            recipe = self._parse_mastercook_section(section_stripped, filepath)
            if recipe and recipe.title:
                recipes.append(recipe)
        return recipes
    
    def _parse_mastercook_section(self, section: str, filepath: str) -> Recipe:
        recipe = Recipe(source_file=filepath, source_format=self.source_format)
        lines = section.split('\n')
        in_ingredients = False
        in_instructions = False
        in_categories = False
        current_instruction_paragraph = []
        found_ingredient_header = False
        
        for line in lines:
            line_stripped = line.strip()
            
            # MasterCook end-of-recipe or footer metadata separator
            if line_stripped.startswith('- - - -') or line_stripped.startswith('Per serving:') or line_stripped.startswith('Nutr. Assoc.'):
                break
                
            if not line_stripped:
                in_categories = False
                # An empty line while in ingredients section transitions us to the instructions.
                if in_ingredients:
                    in_ingredients = False
                    in_instructions = True
                elif in_instructions and current_instruction_paragraph:
                    recipe.instructions.append(' '.join(current_instruction_paragraph))
                    current_instruction_paragraph = []
                continue
            
            if not recipe.title and line_stripped:
                recipe.title = line_stripped
                continue
            
            if re.match(r'Recipe [Bb]y\s*:', line_stripped, re.IGNORECASE):
                in_categories = False
                continue
            elif re.match(r'Serving Size\s*:', line_stripped, re.IGNORECASE):
                in_categories = False
                parts = line_stripped.split(':', 1)[1].strip()
                recipe.yield_amount = parts.split()[0] if parts else ''
                continue
            elif re.match(r'Categories?\s*:', line_stripped, re.IGNORECASE):
                in_categories = True
                cats = line_stripped.split(':', 1)[1].strip()
                # Split by 2 or more spaces to keep "Side Dish" together
                recipe.categories = [c.strip() for c in re.split(r'\s{2,}', cats) if c.strip()]
                continue
            elif in_categories and line.startswith(' ') and line_stripped:
                # Continuation of categories block
                new_cats = [c.strip() for c in re.split(r'\s{2,}', line_stripped) if c.strip()]
                recipe.categories.extend(new_cats)
                continue
            else:
                in_categories = False
            
            if 'Amount' in line and 'Measure' in line and 'Ingredient' in line:
                found_ingredient_header = True
                continue
            elif found_ingredient_header and '---' in line and len(line_stripped.replace('-', '').strip()) == 0:
                in_ingredients = True
                in_instructions = False
                continue
            elif line_stripped.upper() == 'INGREDIENTS':
                in_ingredients = True
                in_instructions = False
                continue
            elif line_stripped.upper() in ['DIRECTIONS', 'INSTRUCTIONS', 'PREPARATION']:
                in_ingredients = False
                in_instructions = True
                if current_instruction_paragraph:
                    recipe.instructions.append(' '.join(current_instruction_paragraph))
                    current_instruction_paragraph = []
                continue
            
            if in_ingredients:
                is_indented = line.startswith(' ') or line.startswith('\t')
                has_leading_hyphen = line_stripped.startswith('-')
                
                looks_like_instruction = (not is_indented) and len(line_stripped) > 20 and not line_stripped[0].isdigit() and not has_leading_hyphen
                
                if looks_like_instruction:
                    in_ingredients = False
                    in_instructions = True
                    current_instruction_paragraph.append(line_stripped)
                    continue

                if line_stripped and not line_stripped.startswith('---'):
                    # Strip leading hyphen for processing, but remember it for continuation logic
                    processed_line = line_stripped.lstrip('-').strip()
                    if not processed_line:
                        continue
                        
                    # Tabular extraction based on two or more spaces separating the columns
                    parts = re.split(r'\s{2,}', processed_line)
                    if len(parts) >= 2 and (parts[0][:1].isdigit() or parts[0].startswith('/')):
                        if len(parts) == 2:
                            ing = Ingredient(
                                raw=processed_line,
                                quantity=parts[0].strip(),
                                unit=None,
                                name=parts[1].strip()
                            )
                        else:
                            ing = Ingredient(
                                raw=processed_line,
                                quantity=parts[0].strip(),
                                unit=normalize_unit(parts[1].strip()),
                                name=' '.join(parts[2:]).strip()
                            )
                        recipe.ingredients.append(ing)
                    elif recipe.ingredients:
                        # Multi-factor Heuristic for continuations vs new unmeasured ingredients
                        is_continuation = False
                        line_lower = processed_line.lower()
                        
                        # Rule 1: Explicit prefixes
                        if has_leading_hyphen or line_lower.startswith(('and ', 'or ', 'with ', 'plus ')):
                            is_continuation = True
                            
                        # Rule 2: Hanging words from previous line
                        prev_ing = recipe.ingredients[-1]
                        prev_raw_lower = prev_ing.raw.lower()
                        # Expanded hanging words to include more prepositions and common adjective endings
                        hanging_words = (
                            'with', 'and', 'or', 'in', 'black', 'red', 'of', ',', 'into', 'to', 'from',
                            'vegetable', 'fresh', 'dried', 'chopped', 'sliced', 'minced', 'granulated',
                            'powdered', 'all-purpose', 'low-fat', 'non-fat', 'reduced-fat', 'sodium'
                        )
                        if prev_raw_lower.endswith(hanging_words):
                            is_continuation = True
                            
                        # Rule 3: Preparation-only phrases (e.g., "stemmed and well washed", "to taste")
                        if not is_continuation:
                            if self.PREP_REGEX.match(line_lower) or line_lower == 'to taste':
                                is_continuation = True
                            elif HAS_NLTK:
                                try:
                                    words = nltk.word_tokenize(line_lower)
                                    tags = nltk.pos_tag(words)
                                    has_noun = any(tag.startswith('NN') for word, tag in tags)
                                    if not has_noun:
                                        is_continuation = True
                                except Exception:
                                    pass # Skip if nltk corpora are missing
                            
                        if is_continuation:
                            # Append to the previous ingredient as a continuation
                            addon = processed_line
                            prev_ing.raw += f" {addon}"
                            if prev_ing.name:
                                prev_ing.name += f" {addon}"
                            else:
                                prev_ing.name = addon
                        else:
                            # Treat as a brand new ingredient without an amount
                            # Bypass NLP parser since we know there is no amount/unit from tabular layout
                            recipe.ingredients.append(Ingredient(raw=processed_line, name=processed_line))
                    else:
                        recipe.ingredients.append(Ingredient(raw=processed_line, name=processed_line))
            elif in_instructions:
                if not any(line_stripped.startswith(x) for x in ['Source:', 'Yield:', 'T(', 'S(', 'Per Serving', 'Nutr.', '"']):
                    current_instruction_paragraph.append(line_stripped)
            elif not in_ingredients and not in_instructions and line_stripped:
                if recipe.ingredients and not line_stripped.startswith(('Source:', 'Yield:', 'T(', 'S(', 'Per Serving', 'Nutr.', '"', '-')):
                    in_instructions = True
                    current_instruction_paragraph.append(line_stripped)
        
        if current_instruction_paragraph:
            recipe.instructions.append(' '.join(current_instruction_paragraph))
        return recipe
