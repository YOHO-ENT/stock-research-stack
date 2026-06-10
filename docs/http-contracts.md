# HTTP Contracts

This document records cross-project HTTP boundaries for research-stack. It is a
contract and planning document only. The sibling projects still own their code,
runtime state, tests, secrets, and release workflow.

## Contract Rules

- Live integration should use HTTP APIs.
- research-stack must not import sibling project internals.
- research-stack must not read sibling project caches, private files, databases,
  or local config files as an integration mechanism.
- Authentication is a placeholder in these contracts until each service defines
  its production access model.
- File sync paths are transitional/manual unless this document explicitly says
  otherwise.

## py-moomoo-api to Market Data Lab

Status: current contract.

Deployment boundary: this contract is local-only. Vultr production does not run
moomoo Account Web, does not route `/moomoo/`, and leaves
`MOOMOO_ACCOUNT_WEB_URL` empty so account sync cannot run on the VPS.

Purpose: Market Data Lab imports the read-only moomoo research universe through
the moomoo Account Web API.

Owner boundaries:

- Provider: `py-moomoo-api`
- Consumer: `market-data-lab`
- research-stack: documents the boundary only

Base URLs:

- Local provider: `http://127.0.0.1:8501`
- Local consumer: `http://127.0.0.1:8010`
- Suggested env: `MOOMOO_ACCOUNT_WEB_BASE_URL=http://127.0.0.1:8501`

Provider endpoint:

```http
GET /api/research-universe/export
```

Consumer endpoints already present in Market Data Lab:

```http
GET /integrations/moomoo/research-universe/preview
POST /integrations/moomoo/research-universe/sync
```

Example provider response shape:

```json
{
  "status": "ok",
  "synced_at": "2026-06-10T02:00:00Z",
  "items": [
    {
      "ticker": "NVDA",
      "market": "US",
      "name": "NVIDIA",
      "primary_source": "watchlist:AI Watch",
      "sources": ["watchlist:AI Watch", "positions"],
      "watchlist_refs": [
        {
          "group_name": "AI Watch",
          "group_order": 0,
          "security_order": 0
        }
      ]
    }
  ]
}
```

Failure modes:

- `200` with `status != "ok"`: consumer should show a recoverable import
  warning and avoid overwriting a good universe.
- `4xx`: request or access problem; operator action required.
- `5xx` or timeout: provider unavailable; retry later without reading cache
  files.

Idempotency and retry:

- Preview is read-only and safe to retry.
- Sync replaces the Market Data Lab universe from the provider payload and
  should be operator-triggered or scheduled with clear logs.

Non-flow:

- Market Data Lab must not read moomoo cache files directly.
- research-stack must not hold moomoo account secrets.

## Market Data Lab to Firn

Status: current local v1. Market Data Lab can use this HTTP path when
`FIRN_API_BASE_URL` is configured, and Firn accepts writes only when
`FIRN_WATCHLIST_EDITABLE=true`.

Purpose: Market Data Lab publishes a normalized universe/watchlist to Firn over
HTTP. The local `FIRN_WATCHLIST_PATH` file handoff remains a transitional
fallback when `FIRN_API_BASE_URL` is not configured.

Owner boundaries:

- Provider: `market-data-lab`
- Consumer/owner of persisted watchlist: `Firn`
- research-stack: documents the target boundary only

Base URLs:

- Market Data Lab: `http://127.0.0.1:8010`
- Firn API: `http://127.0.0.1:8000`
- Suggested env in Market Data Lab: `FIRN_API_BASE_URL=http://127.0.0.1:8000`
- Optional env in Market Data Lab: `FIRN_API_TOKEN=<future-token>`
- Required Firn gate for writes: `FIRN_WATCHLIST_EDITABLE=true`

Target Firn endpoint:

```http
PUT /api/config/watchlist
Content-Type: application/json
```

Example request:

```json
{
  "categories": {
    "moomoo_watchlist_ai_watch": {
      "label": "Moomoo Watchlist: AI Watch",
      "tickers": ["NVDA", "0700.HK"],
      "tags": ["moomoo", "watchlist", "ai-watch"]
    },
    "moomoo_positions": {
      "label": "Moomoo Positions",
      "tickers": ["NVDA"],
      "tags": ["moomoo", "positions"]
    }
  }
}
```

Expected response:

```json
{
  "categories": {
    "moomoo_watchlist_ai_watch": {
      "label": "Moomoo Watchlist: AI Watch",
      "tickers": ["NVDA", "0700.HK"],
      "tags": ["moomoo", "watchlist", "ai-watch"]
    }
  },
  "editable": true,
  "managed_by": "market-data-lab/moomoo"
}
```

Failure modes:

- `403`: Firn write gate is disabled; keep the Market Data Lab universe and show
  a clear operator message.
- `400`: payload validation failed; do not retry unchanged payload.
- `401` or `403` after auth is added: credentials or role are wrong.
- `5xx` or timeout: Firn unavailable; retry with backoff.

Idempotency and retry:

- The same category payload should be safe to send repeatedly.
- Market Data Lab should treat Firn as the owner of persisted watchlist state
  after the HTTP call succeeds.
- Retries must not create duplicate categories or duplicate tickers.

Non-flow:

- research-stack must not enable `FIRN_WATCHLIST_PATH`.
- Market Data Lab must not write Firn config files directly as the default stack
  integration. The file fallback is transitional and should not be enabled from
  research-stack.
- Firn KB, audit logs, and runtime artifacts remain owned by Firn.

## TradingAgents to Market Data Lab

Status: current local v1. TradingAgents exposes its own Market Data Lab adapter
for ticker selection and keeps manual ticker input available when Market Data
Lab is down.

Purpose: TradingAgents selects tickers from Market Data Lab instead of requiring
manual ticker entry for every run.

Owner boundaries:

- Provider: `market-data-lab`
- Consumer: `TradingAgents`
- TradingAgents still owns analysis jobs and markdown reports.
- research-stack: documents the target boundary only

Base URLs:

- Market Data Lab: `http://127.0.0.1:8010`
- TradingAgents API: `http://127.0.0.1:8002`
- Suggested env in TradingAgents: `MARKET_DATA_LAB_BASE_URL=http://127.0.0.1:8010`
- Optional env in TradingAgents: `MARKET_DATA_LAB_TIMEOUT_SECONDS=5`

Provider endpoints:

```http
GET /universes
GET /screen?group={group}
```

TradingAgents analysis endpoint:

```http
POST /api/analyses
Content-Type: application/json
```

Example universe response excerpt:

```json
{
  "groups": {
    "moomoo_watchlist_ai_watch": ["NVDA", "0700.HK"],
    "moomoo_positions": ["NVDA"]
  },
  "editable": true
}
```

Example screen response excerpt:

```json
{
  "items": [
    {
      "ticker": "NVDA",
      "price": 123.45,
      "trend_score": 82,
      "liquidity_score": 91
    }
  ]
}
```

Example TradingAgents request after ticker selection:

```json
{
  "ticker": "NVDA",
  "trade_date": "2026-06-10",
  "asset_type": "auto",
  "analysts": ["market", "news", "fundamentals"],
  "llm_provider": "deepseek",
  "quick_think_llm": "deepseek-chat",
  "deep_think_llm": "deepseek-reasoner",
  "research_depth": 1,
  "output_language": "English",
  "checkpoint_enabled": false
}
```

Failure modes:

- Market Data Lab `404` or empty group: show no selectable tickers for that
  group; do not fall back to reading files.
- Market Data Lab `5xx` or timeout: TradingAgents returns an unavailable
  adapter payload and keeps manual ticker input available.
- TradingAgents `400`: request invalid or ticker preflight failed; show the API
  error to the operator.
- TradingAgents `503`: provider key or market-data preflight unavailable; retry
  only after operator review.

Idempotency and retry:

- Reading universes and screens is safe to retry.
- Creating an analysis job is not idempotent by default; the UI should avoid
  accidental duplicate submissions.

Non-flow:

- TradingAgents must not read Market Data Lab config files directly.
- research-stack must not enqueue TradingAgents jobs by itself.
- Research Hub remains a link and health-status surface only.
