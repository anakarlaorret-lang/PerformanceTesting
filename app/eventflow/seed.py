"""Deterministic synthetic data. Run `python -m eventflow.seed --reset` to restore the baseline."""
import sys
from datetime import datetime, timedelta

from sqlalchemy import func, select

from .config import settings
from .db import Base, SessionLocal, engine
from .models import Event

VENUES = ["Teatro Central", "Sala Norte", "Arena Sur", "Club Oeste", "Auditorio Este"]


def seed(reset: bool = False) -> int:
    if reset:
        Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    with SessionLocal() as db:
        if db.scalar(select(func.count()).select_from(Event)):
            return 0
        base = datetime(2030, 1, 1, 20, 0)
        db.add_all(
            Event(
                name=f"Demo Event {i:03d}",
                venue=VENUES[i % len(VENUES)],
                starts_at=base + timedelta(days=i),
                price=10 + (i % 10) * 5,
                capacity=settings.seed_capacity,
                available=settings.seed_capacity,
            )
            for i in range(1, settings.seed_events + 1)
        )
        db.commit()
        return settings.seed_events


if __name__ == "__main__":
    print(f"Seeded {seed(reset='--reset' in sys.argv)} events")
