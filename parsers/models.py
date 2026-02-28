# SPDX-License-Identifier: MIT
from dataclasses import dataclass, field
from typing import List, Optional

@dataclass
class Ingredient:
    """Structured ingredient"""
    raw: str
    quantity: Optional[str] = None
    unit: Optional[str] = None
    name: Optional[str] = None
    comment: Optional[str] = None

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
