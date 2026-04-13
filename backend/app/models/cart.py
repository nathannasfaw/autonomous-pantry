from pydantic import BaseModel
from typing import Optional


class CartItem(BaseModel):
    item: str
    quantity: float
    unit: str
    estimated_price: float = 5.00
    score: Optional[float] = None


class Cart(BaseModel):
    items: list[CartItem]

    @property
    def total(self) -> float:
        return sum(item.estimated_price for item in self.items)
