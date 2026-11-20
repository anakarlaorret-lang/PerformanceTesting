import asyncio
import hashlib
import hmac
import logging
import re
import time
from contextlib import asynccontextmanager
from datetime import timedelta

from fastapi import Depends, FastAPI, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select, text, update
from sqlalchemy.exc import IntegrityError, OperationalError, SQLAlchemyError
from sqlalchemy.orm import Session

from .config import settings
from .db import SessionLocal, get_db
from .models import Event, Reservation, utcnow
from .schemas import EventOut, ReservationIn, ReservationOut
from .seed import seed

logger = logging.getLogger(__name__)
EXPIRATION_CHECK_INTERVAL_SECONDS = 30


def expire_pending_reservations() -> int:
    now = utcnow()
    with SessionLocal() as db:
        expired = db.execute(
            select(Reservation.id, Reservation.event_id, Reservation.quantity).where(
                Reservation.status == "PENDING",
                Reservation.expires_at <= now,
            )
        ).all()
        released = 0
        for reservation_id, event_id, quantity in expired:
            result = db.execute(
                update(Reservation)
                .where(
                    Reservation.id == reservation_id,
                    Reservation.status == "PENDING",
                    Reservation.expires_at <= now,
                )
                .values(status="EXPIRED")
            )
            if result.rowcount == 1:
                db.execute(
                    update(Event)
                    .where(Event.id == event_id)
                    .values(available=Event.available + quantity)
                )
                released += 1
        db.commit()
        return released


async def _expiration_worker(stop_event: asyncio.Event) -> None:
    while True:
        try:
            await asyncio.wait_for(
                stop_event.wait(),
                timeout=EXPIRATION_CHECK_INTERVAL_SECONDS,
            )
        except asyncio.TimeoutError:
            pass
        if stop_event.is_set():
            return
        try:
            released = await asyncio.to_thread(expire_pending_reservations)
        except SQLAlchemyError:
            logger.exception("Failed to expire pending reservations")
            continue
        if released:
            logger.info("Expired and released %s reservations", released)


@asynccontextmanager
async def lifespan(_: FastAPI):
    # SQL Server may still be starting even when the container is up.
    for attempt in range(30):
        try:
            if settings.seed_on_start:
                seed()
            break
        except OperationalError:
            if attempt == 29:
                raise
            time.sleep(2)
    stop_event = asyncio.Event()
    async with asyncio.TaskGroup() as tasks:
        tasks.create_task(_expiration_worker(stop_event))
        try:
            yield
        finally:
            stop_event.set()


app = FastAPI(title="EventFlow Demo API", version="0.1.0", lifespan=lifespan)
bearer = HTTPBearer(auto_error=False)


def current_user(credentials: HTTPAuthorizationCredentials | None = Depends(bearer)) -> str:
    if credentials and re.fullmatch(r"[0-9a-f]{64}", credentials.credentials):
        digest = hashlib.sha256(credentials.credentials.encode("ascii")).hexdigest()
        for user, expected in settings.api_users.items():
            if hmac.compare_digest(digest, expected):
                return user
    raise HTTPException(401, "Invalid authentication credentials", headers={"WWW-Authenticate": "Bearer"})


@app.get("/health")
def health(db: Session = Depends(get_db)):
    db.execute(text("SELECT 1"))
    return {"status": "ok"}


@app.get("/api/events", response_model=list[EventOut])
def list_events(limit: int = 20, offset: int = 0, db: Session = Depends(get_db)):
    limit = max(1, min(limit, 100))
    stmt = select(Event).order_by(Event.id).offset(max(offset, 0)).limit(limit)
    return db.scalars(stmt).all()


def _get_event(db: Session, event_id: int) -> Event:
    event = db.get(Event, event_id)
    if event is None:
        raise HTTPException(404, "Event not found")
    return event


@app.get("/api/events/{event_id}", response_model=EventOut)
def get_event(event_id: int, db: Session = Depends(get_db)):
    return _get_event(db, event_id)


@app.get("/api/events/{event_id}/availability")
def availability(event_id: int, db: Session = Depends(get_db)):
    event = _get_event(db, event_id)
    return {"event_id": event.id, "available": event.available}


def _by_key(db: Session, owner: str, key: str):
    return db.scalar(select(Reservation).where(
        Reservation.owner == owner, Reservation.idempotency_key == key
    ))


@app.post("/api/reservations", response_model=ReservationOut, status_code=201)
def create_reservation(
    body: ReservationIn, owner: str = Depends(current_user), db: Session = Depends(get_db)
):
    existing = _by_key(db, owner, body.idempotency_key)
    if existing:
        return existing
    _get_event(db, body.event_id)
    try:
        # Atomic conditional decrement: never oversells under concurrency.
        result = db.execute(
            update(Event)
            .where(Event.id == body.event_id, Event.available >= body.quantity)
            .values(available=Event.available - body.quantity)
        )
        if result.rowcount != 1:
            db.rollback()
            raise HTTPException(409, "Not enough tickets available")
        reservation = Reservation(
            owner=owner,
            event_id=body.event_id,
            quantity=body.quantity,
            idempotency_key=body.idempotency_key,
            expires_at=utcnow() + timedelta(minutes=settings.reservation_ttl_minutes),
        )
        db.add(reservation)
        db.commit()
    except IntegrityError:
        # Concurrent retry with the same idempotency key.
        db.rollback()
        existing = _by_key(db, owner, body.idempotency_key)
        if existing:
            return existing
        raise
    return reservation


@app.post("/api/reservations/{reservation_id}/confirm", response_model=ReservationOut)
def confirm_reservation(
    reservation_id: int, owner: str = Depends(current_user), db: Session = Depends(get_db)
):
    result = db.execute(
        update(Reservation)
        .where(
            Reservation.id == reservation_id,
            Reservation.owner == owner,
            Reservation.status == "PENDING",
            Reservation.expires_at > utcnow(),
        )
        .values(status="CONFIRMED")
    )
    reservation = db.scalar(select(Reservation).where(
        Reservation.id == reservation_id, Reservation.owner == owner
    ))
    if reservation is None:
        raise HTTPException(404, "Reservation not found")
    if result.rowcount != 1 and reservation.status != "CONFIRMED":
        raise HTTPException(409, "Reservation is not confirmable")
    db.commit()
    return reservation


@app.delete("/api/reservations/{reservation_id}", status_code=204)
def cancel_reservation(
    reservation_id: int, owner: str = Depends(current_user), db: Session = Depends(get_db)
):
    reservation_data = db.execute(
        select(Reservation.event_id, Reservation.quantity).where(
            Reservation.id == reservation_id, Reservation.owner == owner
        )
    ).one_or_none()
    if reservation_data is None:
        raise HTTPException(404, "Reservation not found")
    result = db.execute(
        update(Reservation)
        .where(
            Reservation.id == reservation_id,
            Reservation.owner == owner,
            Reservation.status.in_(("PENDING", "CONFIRMED")),
        )
        .values(status="CANCELLED")
    )
    if result.rowcount == 1:
        event_id, quantity = reservation_data
        db.execute(
            update(Event)
            .where(Event.id == event_id)
            .values(available=Event.available + quantity)
        )
        db.commit()
