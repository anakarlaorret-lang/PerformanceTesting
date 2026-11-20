# EventFlow Demo Concept

EventFlow is an original, synthetic event-ticket reservation API built to be a safe, reproducible target for k6 and Apache JMeter. It is not a real business: all data is synthetic, there are no payments and no external integrations.

## Goals

- Provide a realistic read-heavy and write-contended workload (browsing events, reserving limited inventory).
- Be fully owned and local, so any test type (smoke, load, stress, spike, soak) can run without third-party authorization.
- Be reproducible: deterministic seed data and a documented reset.

## Technology Stack

| Layer | Choice | Reason |
| --- | --- | --- |
| API | FastAPI (Python) | Lightweight, auto-generated OpenAPI docs at `/docs`. |
| ORM | SQLAlchemy 2.x + pyodbc | Mature SQL Server support. |
| Database | Microsoft SQL Server 2022 (Linux container) | Realistic relational engine; managed from SSMS. |
| Orchestration | Docker Compose | One command to start DB, DB initialization, and API. |
| Load tools | k6, Apache JMeter | Scripts in `k6/` and plans in `jmeter/`. |

The UI is out of scope for the MVP and will be added after the API is stable.

## User Journeys

1. **Browse:** list events, open an event detail, check availability.
2. **Reserve:** request tickets for an event (holds inventory for a limited time).
3. **Confirm:** confirm a pending reservation (simulated, no payment).
4. **Cancel:** cancel a reservation and release inventory.

## API (MVP)

| Method | Path | Description |
| --- | --- | --- |
| GET | `/health` | Liveness plus a database round trip. |
| GET | `/api/events?limit=&offset=` | Paginated event list (limit capped at 100). |
| GET | `/api/events/{id}` | Event detail. |
| GET | `/api/events/{id}/availability` | Remaining tickets. |
| POST | `/api/reservations` | Create a reservation `{event_id, quantity, idempotency_key}`. |
| POST | `/api/reservations/{id}/confirm` | Confirm a pending, non-expired reservation. |
| DELETE | `/api/reservations/{id}` | Cancel and release inventory. |

## Business Rules

- Quantity per reservation: 1 to 6.
- Inventory is never oversold: availability is decremented with a single conditional `UPDATE ... WHERE available >= quantity`; if no row is affected the API returns `409`.
- `idempotency_key` (8 to 64 characters) makes retries safe: the same key returns the original reservation.
- Reservation writes require a bearer token. Each user can confirm or cancel only their own reservations, and idempotency keys are scoped to that user.
- A pending reservation expires after 10 minutes (`RESERVATION_TTL_MINUTES`); an API background task checks every 30 seconds, marks expired reservations `EXPIRED`, and releases their inventory.
- A reservation cannot be confirmed after expiry; cancelling an expired reservation is a no-op because its inventory has already been released.
- Confirming an already confirmed reservation is idempotent; cancelling twice is a no-op.

## Data Model

- `events`: id, name, venue, starts_at, price, capacity, available.
- `reservations`: id, owner, event_id, quantity, status (`PENDING`, `CONFIRMED`, `CANCELLED`, `EXPIRED`), idempotency_key (unique per owner), created_at, expires_at.

## Seed Data

Deterministic: 50 events (`Demo Event 001` ... `050`), capacity 500 each, 5 venues, prices 10 to 55. Configurable through `SEED_EVENTS` and `SEED_CAPACITY`. Reset with `python -m eventflow.seed --reset`.

## Performance Test Opportunities

| Scenario | Endpoints | What it reveals |
| --- | --- | --- |
| Smoke | `/health`, `/api/events`, one reservation cycle | Environment and script correctness. |
| Browse load | `GET /api/events`, `/api/events/{id}` | Read throughput and latency percentiles. |
| Reservation load | `POST /api/reservations` on many events | Write path and connection pool behavior. |
| Hot-event contention (stress/spike) | `POST /api/reservations` on one event | Lock contention, `409` correctness, no overselling. |
| Idempotency | Repeated `POST` with the same key | Duplicate handling under concurrency. |
| Soak | Mixed journey over a long period | Leaks, pool exhaustion, degradation over time. |

Correctness checks to assert in every load test: no oversold inventory (`capacity - available` equals active reserved quantity) and expected status codes (`201`, `409`, `404`).

## Out of Scope (MVP)

User registration, payments, email or notifications, caching layer, UI, and any real-world data.

## Repository Layout

```
app/        FastAPI application, Dockerfile, tests
infra/      docker-compose.yml
k6/         k6 scripts
jmeter/     JMeter test plans
docs/       strategy, concept, test plans
results/    generated reports (git-ignored)
```
