# Service Catalog

This catalog describes the projects managed by `research-stack` during Phase 1.
It is documentation for orchestration only; it does not move code or own the
runtime state of the sibling projects.

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
  - Firn watchlist file sync is a transitional manual option, not a default
    research-stack integration.

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
  - Future ticker selection should come from Market Data Lab via HTTP.
  - Markdown reports remain generated and served by TradingAgents.

## US Equity News Daily Analysis

- Path: `/Users/yongnahwa/Desktop/US-equity-news-daily-analysis`
- Role: daily US equity news, SEC, event analysis, and static HTML report
  pipeline.
- Planned dashboard: `http://127.0.0.1:8502`
- Useful commands in the source project:
  - `python -m app.jobs.run_daily_brief`
  - `python -m app.jobs.run_pipeline`
  - `streamlit run app/dashboard/streamlit_app.py`
  - `scripts/run_firn_audit.py`
- Boundaries:
  - No FastAPI service was found during Phase 1 research.
  - External Firn audit is outbound: `POST {FIRN_AUDIT_BASE_URL}/audit-report`.
  - Static reports and databases remain owned by this source project.
