# EventFlow Performance Scenarios

These k6 profiles exercise only the project-owned EventFlow API. They use synthetic seeded data and default to `http://localhost:8000`. Do not point them at systems without explicit authorization.

Equivalent Apache JMeter plans are documented in [the JMeter scenarios guide](jmeter-scenarios.md).

## Shared behavior and criteria

- Each iteration lists events, opens an event, checks availability, creates a one-ticket reservation, confirms it, and cancels it.
- The smoke profile also calls `/health`.
- Stress and spike select the first event for all VUs to exercise a hot inventory row. HTTP `409` on reservation creation is accepted only in these profiles; every other unexpected status fails a check.
- Every profile requires all checks to pass and fewer than 1% failed HTTP requests. k6 treats `201` and expected hot-event `409` as valid responses in stress/spike.
- Reservation cancellation returns inventory during the run. After each profile, verify inventory against active reservations before interpreting correctness results. For a database-level inventory check, use the reconciliation procedure in [the baseline plan](baseline.md).
- Results are written to `results/`, which is git-ignored. Run one profile at a time; the load generator and API/database share the host.

Set the API URL once in PowerShell:

```powershell
$env:BASE_URL = "http://localhost:8000"
$env:EVENTFLOW_TOKEN = ((Get-Content .env | Where-Object { $_ -match '^EVENTFLOW_TOKEN=' }) -replace '^EVENTFLOW_TOKEN=', '')
```

Generate the token as described in the README. Keep it private and do not include it in reports.

Reset the seeded database before each measured run:

```powershell
docker compose -f infra/docker-compose.yml --env-file .env exec api python -m eventflow.seed --reset
```

## Smoke

One VU for 10 seconds. Checks health and one complete reservation journey; it is a script/environment check, not a capacity measurement.

```powershell
k6 run --summary-export results\k6-smoke.json k6\smoke.js
```

Override duration with `SMOKE_DURATION`.

## Load

Ramps to 10 VUs over 30 seconds, holds 3 minutes, then ramps down over 30 seconds.

```powershell
k6 run --summary-export results\k6-load.json k6\load.js
```

Override with `LOAD_VUS` and `LOAD_HOLD`.

## Stress

Exercises one hot event in bounded steps: 5 VUs, then 10, 20, and at most 30 VUs, followed by ramp-down. The default profile lasts 4 minutes. Expected inventory-contention `409` responses are reported as valid; other failed checks indicate a problem.

```powershell
k6 run --summary-export results\k6-stress.json k6\stress.js
```

The maximum is configurable with `STRESS_MAX_VUS`; stage lengths can be shortened with `STRESS_RAMP_DURATION`, `STRESS_STEP_DURATION`, and `STRESS_RAMP_DOWN_DURATION` for script validation. Increase the VU maximum only deliberately and while monitoring the local host.

## Spike

Holds 5 VUs for 30 seconds, jumps to 30 VUs for 15 seconds, returns to 5 VUs for 30 seconds, then ramps down. Requests target one hot event.

```powershell
k6 run --summary-export results\k6-spike.json k6\spike.js
```

Override VUs with `SPIKE_BASE_VUS` and `SPIKE_VUS`, or stage lengths with `SPIKE_BASE_DURATION`, `SPIKE_DURATION`, `SPIKE_RECOVERY_DURATION`, and `SPIKE_RAMP_DOWN_DURATION`.

## Soak

Runs 5 VUs for 30 minutes on the mixed journey, distributed across events. Monitor API/SQL Server CPU, memory, logs, latency drift, and database connection behavior during the run.

```powershell
k6 run --summary-export results\k6-soak.json k6\soak.js
```

Override with `SOAK_VUS` and `SOAK_DURATION`. Begin at the defaults before increasing duration or load.

## Recommended execution order

1. Smoke; resolve any failed checks before continuing.
2. Load; record throughput, endpoint p95/p99, error rate, and host/container resources.
3. Stress; note the load point where latency/error rates degrade.
4. Spike; observe recovery after the sudden hot-event surge.
5. Soak; compare early and late latency/resources and check for resource growth.

Repeat load at least three times under comparable host conditions before setting latency acceptance thresholds. Stress, spike, and soak are diagnostic profiles; retain their summaries and compare them to the load baseline.
