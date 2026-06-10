# Service Catalog

This catalog describes the projects managed by `research-stack` during Phase 1.
It is documentation for orchestration only; it does not move code or own the
runtime state of the sibling projects.

Cross-project HTTP boundaries are documented in
[HTTP contracts](http-contracts.md).

## Research Hub

- Path: `/Users/yongnahwa/Desktop/research-stack`
- Role: unified local entry point with service links and health status.
- Local dashboard/API: `http://127.0.0.1:3030`
- Useful endpoints:
  - `GET /api/services`
  - `GET /api/health`
  - `GET /api/control/status`
- Boundaries:
  - Does not start sibling services.
  - Does not iframe sibling frontends.
  - Performs best-effort local health and control-signal checks only.

## py-moomoo-api

- Path: `/Users/yongnahwa/Desktop/py-moomoo-api`
- Role: read-only moomoo account, positions, watchlist, and research-universe
  export source.
- Local dashboard/API: `http://127.0.0.1:8501`
- OpenD gateway: `127.0.0.1:11111`
- Useful endpoints:
  - `GET /api/watchlists/status`
  - `GET /api/watchlists/export`
  - `POST /api/watchlists/sync`
  - `GET /api/positions/export`
  - `GET /api/research-universe/export`
- Boundaries:
  - Requires moomoo OpenD to be started and logged in outside this stack.
  - research-stack does not manage account secrets, trading passwords, or RSA
    private keys.
  - Exports must remain read-only and account-safe.

## market-data-lab

- Path: `/Users/yongnahwa/Desktop/market-data-lab`
- Role: market history cache, technical snapshots, chart data, screen workflow,
  and research universe center.
- API: `http://127.0.0.1:8010`
- UI: `http://127.0.0.1:3020`
- Useful endpoints:
  - `GET /health`
  - `GET /status`
  - `GET /universes`
  - `GET /screen`
  - `GET /snapshot/{ticker}`
  - `GET /chart/{ticker}`
  - `GET /integrations/moomoo/research-universe/preview`
  - `POST /integrations/moomoo/research-universe/sync`
- Boundaries:
  - Reads moomoo via the `py-moomoo-api` HTTP export.
  - Must not read moomoo cache files directly.
  - Firn watchlist file sync is a transitional manual fallback, not the default
    research-stack integration.
  - Firn HTTP sync is implemented locally through the contract documented in
    [HTTP contracts](http-contracts.md).

## Firn

- Path: `/Users/yongnahwa/Desktop/Firn`
- Role: audit, evidence, knowledge base, claim verification, digest, and deeper
  research memory.
- API: `http://127.0.0.1:8000`
- UI: `http://127.0.0.1:3000`
- Useful endpoints:
  - `GET /api/health`
  - `GET /api/status`
  - `POST /api/analysis`
  - `GET /api/analysis/{exec_id}`
  - `GET /api/analysis/{exec_id}/audit`
  - `POST /api/analysis/{exec_id}/audit`
  - `GET /api/kb/themes`
  - `GET /api/kb/stocks`
  - `GET /api/kb/core-mind`
  - `GET /api/config/watchlist`
- Boundaries:
  - Many endpoints depend on Firn auth state.
  - Health checks should use `GET /api/health`.
  - KB, logs, and audit artifacts remain owned by Firn.
  - Market Data Lab watchlist sync should use the HTTP contract rather than
    direct file writes.

## TradingAgents

- Path: `/Users/yongnahwa/Desktop/TradingAgents`
- Role: deep ticker and portfolio-style multi-agent analysis with markdown
  report output.
- Planned API: `http://127.0.0.1:8002`
- UI: `http://127.0.0.1:5173`
- Useful endpoints:
  - `GET /health`
  - `GET /api/config/options`
  - `POST /api/analyses`
  - `GET /api/analyses/{job_id}`
  - `GET /api/analyses/{job_id}/events`
  - `GET /api/analyses/{job_id}/report.md`
  - `GET /api/reports`
- Boundaries:
  - Project default API port is `8000`; research-stack uses `8002` to avoid
    Firn.
  - Ticker selection from Market Data Lab is implemented locally through the
    contract documented in [HTTP contracts](http-contracts.md).
  - Markdown reports remain generated and served by TradingAgents.

## DailyBrief

- Path: `/Users/yongnahwa/Desktop/DailyBrief`
- Role: local-first Python AI news and markets digest generator with static
  HTML report output.
- Local service URL: none.
- Useful commands in the source project:
  - `dailybrief daily`
  - `dailybrief dry-run`
  - `dailybrief build-site`
  - `dailybrief open [date]`
  - `dailybrief run-scheduled`
  - `dailybrief deploy [date]`
- Boundaries:
  - DailyBrief has no database, web server, web framework, or frontend service.
  - Reports are static files under `daily_reports/<YYYY-MM-DD>/`.
  - Research Hub should show this as a backend/static-report pipeline, not a
    dashboard link, until a public static report URL is intentionally added.
  - Generated reports, logs, schedules, and deployment credentials remain owned
    by DailyBrief.
