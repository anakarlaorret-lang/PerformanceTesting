# EventFlow Performance Baseline

## Purpose

Capture a repeatable, low-load reference for the EventFlow API before setting latency or throughput targets. This is a closed-model test; it is for trend comparisons, not a capacity claim.

## Workload

- 5 virtual users for 2 minutes, with 1 second of think time after each journey.
- Each iteration lists events, reads one event and its availability, then creates, confirms, and cancels one reservation.
- Event selection is distributed across the returned event list.
- Every request checks its expected status. No `409` responses are expected in this workload.

Override the defaults with `BASE_URL`, `VUS`, `DURATION`, and `THINK_TIME_SECONDS`. Reservation operations require `EVENTFLOW_TOKEN` from the local `.env` described in the README.

## Prerequisites and repeatability

1. Start the local Docker Compose stack from the repository root and wait for `http://localhost:8000/health` to return `200`.
2. Do not run other tests or send traffic to the API during the measurement.
3. Reset the synthetic database before each run:

   ```powershell
   docker compose -f infra/docker-compose.yml --env-file .env exec api python -m eventflow.seed --reset
   ```

4. Keep host resources and Docker configuration consistent between runs. Record the date, host CPU/RAM, VUs, duration, and any stack changes with each result.

## Run

From the repository root, first use a short smoke run:

```powershell
$env:BASE_URL = "http://localhost:8000"
$env:EVENTFLOW_TOKEN = ((Get-Content .env | Where-Object { $_ -match '^EVENTFLOW_TOKEN=' }) -replace '^EVENTFLOW_TOKEN=', '')
k6 run --summary-export results\k6-smoke.json k6\smoke.js
```

If the smoke run passes, reset the database again and run the baseline:

```powershell
$env:VUS = "5"
$env:DURATION = "2m"
$env:THINK_TIME_SECONDS = "1"
k6 run --summary-export results\k6-baseline.json k6\baseline.js
```

The JSON summaries are written under `results/`, which is git-ignored.

After a run, check that inventory matches active reservations. This query should return no rows:

```sql
SELECT e.id, e.name,
       e.capacity - e.available AS sold_tickets,
       COALESCE(SUM(CASE WHEN r.status IN ('PENDING', 'CONFIRMED')
                         THEN r.quantity ELSE 0 END), 0) AS active_reserved
FROM events AS e
LEFT JOIN reservations AS r ON r.event_id = e.id
GROUP BY e.id, e.name, e.capacity, e.available
HAVING e.capacity - e.available <>
       COALESCE(SUM(CASE WHEN r.status IN ('PENDING', 'CONFIRMED')
                         THEN r.quantity ELSE 0 END), 0);
```

## Measurements and initial criteria

The report includes request rate, failures, and latency statistics (average, median, p90, p95, and p99) for each journey endpoint. The script enforces 100% passing status checks and less than 1% HTTP request failures. It does not impose latency thresholds; use the first valid SQL Server run to decide whether to set them.

Because the load generator and API/database share the local host, compare runs only under similar host conditions. Do not interpret this baseline as production capacity.

## First measured baseline

Run on 2026-11-17 against the local Docker Compose stack with SQL Server 2022:

- Host: Windows 11 Pro, Intel Core i7-11850H, 31.7 GiB RAM.
- Workload: 5 VUs, 2 minutes, 1 second think time.
- Completed journeys: 558 (3,348 HTTP requests; 4.64 iterations/s; 27.83 requests/s).
- Checks: 4,464 passed, 0 failed; HTTP request failure rate: 0%.
- Inventory reconciliation: 50 events checked, 0 mismatches between sold tickets and active reservations.

| Endpoint | p95 (ms) | p99 (ms) |
| --- | ---: | ---: |
| `GET /api/events` | 37.40 | 60.07 |
| `GET /api/events/{id}` | 12.72 | 21.43 |
| `GET /api/events/{id}/availability` | 11.41 | 17.87 |
| `POST /api/reservations` | 32.93 | 39.01 |
| `POST /api/reservations/{id}/confirm` | 25.48 | 28.79 |
| `DELETE /api/reservations/{id}` | 23.13 | 28.01 |
| All HTTP requests | 27.08 | 39.11 |

Raw k6 summary: `results/k6-baseline.json` (local and git-ignored). Treat these numbers as an initial reference, not an acceptance target: they come from one run, and the load generator shares the host with Docker. Repeat the run under the same conditions before setting latency thresholds.

Equivalent JMeter scenarios are documented in [the JMeter performance plan](jmeter-scenarios.md).
