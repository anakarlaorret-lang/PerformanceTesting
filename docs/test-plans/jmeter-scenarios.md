# EventFlow Performance Scenarios with JMeter

The JMeter plans cover the same EventFlow browse-and-reserve journey as the k6 profiles. They are intended only for the project-owned local API and use synthetic event data. Run from the repository root because each plan includes `jmeter/eventflow-journey.jmx` by a repository-relative path.

## Requirements and common setup

- Apache JMeter 5.6.3 and Java 17 are the validated combination. On this workstation, Java 25 caused JMeter's bundled Groovy compiler to reject the runtime class-file version.
- Start the Docker Compose stack and confirm `http://localhost:8000/health` returns `200`.
- Set the test target and default event count as JMeter properties. Do not direct the plans to systems without authorization.
- Generate the local user's bearer token as described in the README and pass it through the `EVENTFLOW_TOKEN` environment variable, not a command-line property. Do not include request headers or tokens in saved results.
- Reset synthetic data before each measured run. Inventory reconciliation should return no rows; see the SQL query in [the baseline plan](baseline.md).
- Each journey randomly selects an event from IDs 1–50, uses a unique idempotency key, confirms the reservation, and cancels it. Stress and spike pin the workload to event 1.
- The shared fragment adds a configurable think-time sample. The result checker excludes non-HTTP samples and fails on any failed HTTP assertion. Expected `409` reservation conflicts are accepted only when `allow409=true`.

Run all commands from PowerShell at the repository root:

```powershell
$jmeter = "C:\path\to\apache-jmeter-5.6.3\bin\jmeter.bat"
$docker = "C:\Program Files\Docker\Docker\resources\bin\docker.exe"
$env:EVENTFLOW_TOKEN = ((Get-Content .env | Where-Object { $_ -match '^EVENTFLOW_TOKEN=' }) -replace '^EVENTFLOW_TOKEN=', '')
$common = @("-Jhost=localhost", "-Jport=8000", "-JeventCount=50", "-JthinkTimeMillis=1000")
& $docker compose -f infra/docker-compose.yml --env-file .env exec api python -m eventflow.seed --reset
```

After each run, validate the JTL result file:

```powershell
.\jmeter\check-results.ps1 -ResultsFile results\jmeter-smoke.jtl
```

JMeter may return a successful process exit even if an assertion fails or a thread aborts; the checker also requires journey samples (and confirmation and cancellation if a reservation was created). Use it before considering a run passed. The `.jtl` files go under `results/`, which is git-ignored.

## Smoke

One user for 10 seconds. Calls `/health` and runs the full reservation journey.

```powershell
& $jmeter -n -t jmeter\smoke.jmx -l results\jmeter-smoke.jtl @common -JthinkTimeMillis=0
if ($LASTEXITCODE -ne 0) { throw "JMeter smoke process failed" }
.\jmeter\check-results.ps1 -ResultsFile results\jmeter-smoke.jtl
```

Shorten or lengthen with `-JsmokeDuration=<seconds>`; user count is configurable with `-JsmokeUsers`.

## Load

Two native Thread Groups approximate the k6 load profile: ramp to 5 users, add 5 more, hold 10 users for 3 minutes, then fall back to 5 users for 30 seconds before stopping (4 minutes total).

```powershell
& $docker compose -f infra/docker-compose.yml --env-file .env exec api python -m eventflow.seed --reset
& $jmeter -n -t jmeter\load.jmx -l results\jmeter-load.jtl @common
if ($LASTEXITCODE -ne 0) { throw "JMeter load process failed" }
.\jmeter\check-results.ps1 -ResultsFile results\jmeter-load.jtl
```

Tune `loadBaseUsers`, `loadExtraUsers`, `loadRampSeconds`, `loadBaseDuration`, `loadExtraDuration`, and `loadExtraDelay` with `-Jname=value`.

## Stress

Four staggered Thread Groups increase the hot-event workload from 5 to 10, 20, and 30 users in steps across 4 minutes. A `409` means inventory contention and is allowed in this profile.

```powershell
& $docker compose -f infra/docker-compose.yml --env-file .env exec api python -m eventflow.seed --reset
& $jmeter -n -t jmeter\stress.jmx -l results\jmeter-stress.jtl @common -JhotEvent=true -Jallow409=true
if ($LASTEXITCODE -ne 0) { throw "JMeter stress process failed" }
.\jmeter\check-results.ps1 -ResultsFile results\jmeter-stress.jtl
```

Each step's users, duration, and delay can be overridden with the matching `stressStep1...` through `stressStep4...` properties; `stressRampSeconds` controls the step ramps. Lower the values for a short validation run. Increase the default maximum only while monitoring the local host.

## Spike

Five baseline users run for 75 seconds. A second Thread Group adds 25 users from 30 to 45 seconds, producing a peak of 30, then leaves 5 users to observe recovery until the test ends at 75 seconds. Requests target event 1 and expected `409` contention responses are accepted.

```powershell
& $docker compose -f infra/docker-compose.yml --env-file .env exec api python -m eventflow.seed --reset
& $jmeter -n -t jmeter\spike.jmx -l results\jmeter-spike.jtl @common -JhotEvent=true -Jallow409=true
if ($LASTEXITCODE -ne 0) { throw "JMeter spike process failed" }
.\jmeter\check-results.ps1 -ResultsFile results\jmeter-spike.jtl
```

Override baseline/surge users, ramp, delay, and duration with the `spike...` JMeter properties in `jmeter/spike.jmx`.

## Soak

Five users run the mixed journey for 30 minutes. Observe API and SQL Server CPU/memory, logs, latency drift, and pool behavior throughout.

```powershell
& $docker compose -f infra/docker-compose.yml --env-file .env exec api python -m eventflow.seed --reset
& $jmeter -n -t jmeter\soak.jmx -l results\jmeter-soak.jtl @common
if ($LASTEXITCODE -ne 0) { throw "JMeter soak process failed" }
.\jmeter\check-results.ps1 -ResultsFile results\jmeter-soak.jtl
```

Adjust `soakUsers`, `soakRampSeconds`, and `soakDuration` as needed; start with the defaults before increasing the run.

## Reporting and comparison

Use the JTL labels for endpoint-level latency and exclude the `Think time` sample from HTTP statistics. JMeter HTML dashboards can be generated with `-e -o results\jmeter-report` (the output directory must not already exist). Compare runs only under similar host conditions; this local stack shares resources with the load generator.

## Validation record

- Validated on 2026-11-17 with JMeter 5.6.3 and Temurin Java 17.
- The default 10-second smoke recorded 1,594 HTTP samples with 0 failures.
- Short, parameter-reduced executions of load, stress, spike, and soak all passed the JTL checker.
- A separate hot-event check exhausted event 1 temporarily and confirmed that expected `409` reservation samples are accepted only with `allow409=true`; the synthetic database was reset afterward.
- These short runs validate the plans and assertions; they are not performance baselines or full-duration results.
