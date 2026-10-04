# SPDX-License-Identifier: MIT
import re
from dataclasses import dataclass, field
from typing import List, Optional
from .units import normalize_unit

@dataclass
class Ingredient:
    """Structured ingredient"""
    raw: str
    quantity: Optional[str] = None
    unit: Optional[str] = None
    name: Optional[str] = None
    comment: Optional[str] = None

    def __post_init__(self):
        if self.unit is not None:
            self.unit = normalize_unit(self.unit)
        if self.raw is not None:
            self.raw = re.sub(r'\\([.-])', r'\1', self.raw)
        if self.name is not None:
            self.name = re.sub(r'\\([.-])', r'\1', self.name)


@dataclass
class Recipe:
    """Internal representation of a recipe"""
    title: str = ''
    categories: List[str] = field(default_factory=list)
    yield_amount: str = ''
    ingredients: List[Ingredient] = field(default_factory=list)
    instructions: List[str] = field(default_factory=list)
    source_file: Optional[str] = None
    source_format: str = 'Unknown'
    sqlite_table: Optional[str] = None
    sqlite_id: Optional[str] = None
    description: Optional[str] = None
    url: Optional[str] = None

    def sanitize(self) -> "Recipe":
        """Sanitize title, yield, instructions, and ingredients."""
        from .base import sanitize_recipe
        return sanitize_recipe(self)
