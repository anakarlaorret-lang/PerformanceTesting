from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class EventOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    venue: str
    starts_at: datetime
    price: float
    capacity: int
    available: int


class ReservationIn(BaseModel):
    event_id: int
    quantity: int = Field(ge=1, le=6)
    idempotency_key: str = Field(min_length=8, max_length=64)


class ReservationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    event_id: int
    quantity: int
    status: str
    expires_at: datetime
