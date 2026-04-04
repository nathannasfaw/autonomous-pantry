from pydantic import BaseModel
from typing import Optional


class StartSessionResponse(BaseModel):
    conversation_id: str


class ChatRequest(BaseModel):
    conversation_id: str
    message: str


class ChatResponse(BaseModel):
    conversation_id: str
    message: str
    recipe: Optional[dict] = None
    cart: Optional[list] = None
    stage: str
    order_confirmed: bool = False
    order_details: Optional[dict] = None
