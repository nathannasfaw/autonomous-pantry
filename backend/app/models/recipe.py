from pydantic import BaseModel
from typing import Optional


class Ingredient(BaseModel):
    item: str
    quantity: float
    unit: str


class Recipe(BaseModel):
    name: str
    servings: int
    prep_time: str
    cook_time: str
    source_url: Optional[str] = None
    ingredients: list[Ingredient]
    steps_summary: str
