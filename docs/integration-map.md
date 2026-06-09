# Integration Map

All live cross-project integrations should use HTTP APIs. File-level coupling is
not a preferred integration mechanism.

## Allowed Flows

| Flow | Current or Target | Contract |
|---|---|---|
| moomoo Account Web -> Market Data Lab | Current | py-moomoo-api may call Market Data Lab read-only endpoints for status and snapshots. |
| Market Data Lab -> moomoo Account Web | Current | Market Data Lab reads `GET /api/research-universe/export`. It must not read moomoo cache files. |
| Market Data Lab -> Firn | Target | Market Data Lab should sync watchlist/universe data to Firn through a future HTTP API. |
| US Equity News -> Firn | Current adapter shape | External audit uses outbound `POST {FIRN_AUDIT_BASE_URL}/audit-report`. |
| TradingAgents -> Market Data Lab | Target | TradingAgents should select tickers from the Market Data Lab universe via HTTP. |
| Research Hub -> all services | Target | Research Hub links to services and checks health only. |

## Explicit Non-Flows

- Research Hub must not iframe sibling frontends.
- Research Hub must not merge sibling frontends.
- research-stack must not import sibling project internals.
- market-data-lab must not read moomoo cache files.
- TradingAgents must not read Market Data Lab internal files for ticker
  selection.
- US Equity News reports must not be treated as hidden inputs to unrelated
  services unless an explicit artifact handoff is documented.

## Current Gaps

- Market Data Lab has a local `FIRN_WATCHLIST_PATH` file-sync option. This is
  transitional and manual; research-stack does not enable it by default.
- TradingAgents does not yet consume Market Data Lab universes through a
  documented HTTP flow.
- Research Hub does not exist yet; port `3030` is reserved.
- Vultr deployment needs a future Compose file and reverse proxy config.
- US Equity News has a Streamlit dashboard and CLI pipeline, not a FastAPI
  health endpoint.
