# PerformanceTesting

A hands-on performance-testing portfolio built around a purpose-built demo application, k6, and Apache JMeter. The project will demonstrate workload design, controlled execution, observability, and clear result analysis.

## Project Status

The project is being refocused on an original event-ticket reservation demo, initially designed as a local API. The proposed MVP and test opportunities are described in the [Demo Concept](docs/demo-concept.md).

## Quickstart (EventFlow API)

Requires Docker with an x86-64 host (SQL Server Linux image).

Create `.env` once with a new randomly generated password. This command refuses
to overwrite an existing `.env`; keep the password private and do not reuse it:

```powershell
$bytes = New-Object byte[] 16
$rng = [System.Security.Cryptography.RandomNumberGenerator]::Create()
try { $rng.GetBytes($bytes) } finally { $rng.Dispose() }
$password = "aZ9!" + ([BitConverter]::ToString($bytes) -replace "-", "")
$template = Get-Content .env.example -Raw
New-Item -Path .env -ItemType File -Value ($template -replace "MSSQL_SA_PASSWORD=", "MSSQL_SA_PASSWORD=$password") -ErrorAction Stop | Out-Null
Remove-Variable password, bytes, template
```

For a new or existing `.env`, generate a separate token for the local `loadtest`
user. This refuses to replace existing API credentials:

```powershell
if (Select-String -Path .env -Pattern '^(API_USERS|EVENTFLOW_TOKEN)=' -Quiet) {
    throw "API credentials already exist in .env; do not overwrite them."
}
$bytes = New-Object byte[] 32
$rng = [System.Security.Cryptography.RandomNumberGenerator]::Create()
try { $rng.GetBytes($bytes) } finally { $rng.Dispose() }
$token = ([BitConverter]::ToString($bytes) -replace "-", "").ToLowerInvariant()
$sha = [System.Security.Cryptography.SHA256]::Create()
try { $digest = ([BitConverter]::ToString($sha.ComputeHash([Text.Encoding]::ASCII.GetBytes($token))) -replace "-", "").ToLowerInvariant() } finally { $sha.Dispose() }
$users = '{"loadtest":"' + $digest + '"}'
Add-Content -Path .env -Value @("API_USERS='$users'", "EVENTFLOW_TOKEN=$token") -Encoding ASCII
Remove-Variable token, digest, users, bytes
```

`.env` contains a secret token: restrict file access and do not commit, print or
share it. `API_USERS` maps stable lowercase user IDs to SHA-256 token hashes.
Generate a distinct 32-byte random hexadecimal token and hash for each user;
never reuse a user ID for another person. Removing a user revokes that token;
rotating a token while keeping its user ID preserves access to that user's
reservations. Restart the API after changing the mapping.

Then start the stack:

```powershell
docker compose -f infra/docker-compose.yml --env-file .env up --build
```

- The API and SQL Server ports bind to `127.0.0.1` only. Reservation writes require a bearer token; users can manage only their own reservations. Browsing and health remain public. This demo is not suitable for public deployment: it lacks TLS, rate limiting, and user-management facilities.
- Compose requires a nonempty `MSSQL_SA_PASSWORD`; SQL Server enforces its password complexity policy. Use a unique password for this project, not the former example password. If supplying your own, use URL-safe characters: the password is included in the database connection URL.
- Existing installations should keep their current `.env`. Changing it alone does **not** change the SQL Server password stored in an existing volume: rotate the SQL Server login first, update `.env` to match, then recreate the containers. Back up any data you need before maintenance.
- Running the API outside Compose requires explicit `DATABASE_URL` and `API_USERS` values; tests supply their own SQLite URL and test users.
- This change adds reservation ownership. Existing databases must be reset before using the new schema, which deletes all events and reservations. Back up any data you need first, then build the new image, stop the API, reset the database and start the stack:

  ```powershell
  docker compose -f infra/docker-compose.yml --env-file .env build api
  docker compose -f infra/docker-compose.yml --env-file .env stop api
  docker compose -f infra/docker-compose.yml --env-file .env run --rm --no-deps api python -m eventflow.seed --reset
  docker compose -f infra/docker-compose.yml --env-file .env up -d
  ```
- API docs: http://localhost:8000/docs - health: http://localhost:8000/health
- In `/docs`, use **Authorize** with the user's token for reservation operations.
- SSMS: server `localhost,1433`, SQL Server Authentication, login `sa`, database `eventflow`, check "Trust server certificate".
- Reset data: `docker compose -f infra/docker-compose.yml --env-file .env exec api python -m eventflow.seed --reset`
- Unit tests (SQLite, no Docker): `cd app; pip install -r requirements.txt; pytest`

## Documentation

- [Performance Test Strategy](docs/performance-test-strategy.md) - objectives, scope, test types, and open design decisions.
- [Demo Concept](docs/demo-concept.md) - proposed app journeys, API, data rules, and performance-testing opportunities.
- [Performance Baseline](docs/test-plans/baseline.md) - workload, execution commands, and initial criteria for k6.
- [k6 Performance Scenarios](docs/test-plans/performance-scenarios.md) - smoke, load, stress, spike, and soak profiles.
- [JMeter Performance Scenarios](docs/test-plans/jmeter-scenarios.md) - equivalent Apache JMeter plans and run commands.
