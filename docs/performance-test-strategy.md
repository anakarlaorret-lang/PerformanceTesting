# Performance Test Strategy

Strategy for performance-testing the EventFlow demo API (see [Demo Concept](demo-concept.md)) with k6 and Apache JMeter.

## 1. Purpose and Objectives

- Demonstrate a professional, reproducible performance-testing workflow for a portfolio.
- Establish a baseline for latency, throughput, and error rate, then detect regressions against it.
- Validate correctness under concurrency (no overselling, idempotent retries).

## 2. Scope

**In scope:** all endpoints listed in the Demo Concept, the SQL Server database, and the Docker Compose stack.
**Out of scope:** UI (until added), user registration, payments, third-party services, and any system not owned by this project.

## 3. System Under Test and Architecture

FastAPI (Uvicorn) -> SQLAlchemy/pyodbc -> SQL Server 2022, all in Docker Compose on the tester's machine. SSMS is used to inspect data.

## 4. Test Types and Workload Models

| Type | Purpose | Model |
| --- | --- | --- |
| Smoke | Verify script and environment with minimal load | Few VUs, short |
| Load | Expected normal usage | Ramp to target, hold |
| Stress | Find breaking point | Step up until degradation |
| Spike | Sudden surge on a hot event | Abrupt jump, then drop |
| Soak | Stability over time | Moderate load, long duration |

The initial baseline uses a closed-model mixed journey: 5 VUs for 2 minutes with 1 second of think time. These are conservative starting values, not capacity targets. Prefer arrival-rate (open model) executors for throughput targets and VU-based executors for closed-model journeys.

## 5. Workload Journeys and Data

- Browse (read-heavy), reserve/confirm/cancel (write), and a mixed journey.
- Stress and spike focus all writes on one event; inventory-contention `409` responses are expected only in those profiles.
- Synthetic, deterministic seed data; each run starts from a reset database for comparability.
- Unique idempotency keys per iteration unless testing duplicates deliberately.
- Reservation requests use a configured local user's bearer token; keep tokens out of reports and source control.

## 6. Environments and Tools

- Local Docker Compose stack; note host CPU/RAM and keep them constant between runs.
- k6 and Apache JMeter for code-based profiles, CLI execution, and result dashboards.
- Load generator and SUT share the host, so results are relative (trend comparison), not absolute capacity figures.

## 7. Metrics and Acceptance Criteria

- Latency: p50, p95, p99 per endpoint; error rate; throughput (requests/s); dropped iterations.
- Initial baseline thresholds: 100% passing request checks and under 1% HTTP request failures. Latency thresholds remain **TBD** until a valid SQL Server baseline exists.
- Correctness: zero oversold inventory after every run.

## 8. Test Data Management

Reset with `python -m eventflow.seed --reset` (or recreate the Compose volume) before each run. Reports and raw results go to `results/` (git-ignored).

## 9. Execution Plan

1. Smoke test and record the baseline using [the k6 baseline plan](test-plans/baseline.md).
2. Run the [k6 profiles](test-plans/performance-scenarios.md) and their [JMeter equivalents](test-plans/jmeter-scenarios.md) in order.
3. Repeat load at least three times under comparable host conditions before setting latency thresholds.
4. Compare summaries and resource behavior; verify inventory correctness after each run.

Runs are manual during development. Scheduling/CI is a later decision.

## 10. Monitoring and Observability

Collect k6/JMeter metrics, API logs, `docker stats` for CPU/memory, and SQL Server DMVs or SSMS Activity Monitor for waits and blocking. OpenTelemetry may be added later.

## 11. Risks and Mitigations

| Risk | Mitigation |
| --- | --- |
| Generator and SUT compete for resources | Keep load modest; note limits; compare trends only. |
| Dirty data between runs | Mandatory reset before each run. |
| SQL Server needs x86-64 and memory | Document requirements; set container memory if needed. |
| Hot-row contention skews results | Isolate as a dedicated scenario. |

## 12. Entry and Exit Criteria

**Entry:** stack healthy (`/health` returns 200), seed data present, script validated by smoke.
**Exit:** planned scenarios executed, reports archived, correctness checks passed, findings documented.

## 13. Reporting

Each run produces a summary (k6 `handleSummary`, JMeter HTML dashboard) with scenario, configuration, key metrics, threshold results, and caveats. Result interpretation options will be defined after the first baseline.

## 14. Deliverables and Responsibilities

Deliverables: this strategy, per-test plans in `docs/test-plans/`, k6 scripts, JMeter plans, result reports, and a final summary. Responsibility: project author (single owner).

## Constraints

- Only project-owned environments are tested.
- Smoke results are not capacity results.
- Synthetic data only; no real personal data.
