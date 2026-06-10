# Integration Map

All live cross-project integrations should use HTTP APIs. File-level coupling is
not a preferred integration mechanism.

## Allowed Flows

| Flow | Current or Target | Contract |
|---|---|---|
| moomoo Account Web -> Market Data Lab | Current | py-moomoo-api may call Market Data Lab read-only endpoints for status and snapshots. |
| Market Data Lab -> moomoo Account Web | Current | Market Data Lab reads `GET /api/research-universe/export`. It must not read moomoo cache files. See [HTTP contracts](http-contracts.md). |
| Market Data Lab -> Firn | Target | Contract documented in [HTTP contracts](http-contracts.md); implementation remains in sibling repositories. |
| DailyBrief -> generated reports | Current | DailyBrief writes static HTML/JSON report artifacts under its own `daily_reports/` directory. |
| TradingAgents -> Market Data Lab | Target | Contract documented in [HTTP contracts](http-contracts.md); implementation remains in sibling repositories. |
| Research Hub -> all services | Current | Research Hub links to services and checks health only. |

## Explicit Non-Flows

- Research Hub must not iframe sibling frontends.
- Research Hub must not merge sibling frontends.
- research-stack must not import sibling project internals.
- market-data-lab must not read moomoo cache files.
- TradingAgents must not read Market Data Lab internal files for ticker
  selection.
- DailyBrief reports must not be treated as hidden inputs to unrelated
  services unless an explicit artifact handoff is documented.

## Current Gaps

- Market Data Lab has a local `FIRN_WATCHLIST_PATH` file-sync option. This is
  transitional and manual; research-stack does not enable it by default.
- TradingAgents does not yet consume Market Data Lab universes through a
  implemented HTTP flow.
- Research Hub v1 is deployed locally and on the current IP-only Vultr host.
- DailyBrief systemd publishing is running on the Vultr host and publishes
  static reports plus `health.json` into the Research Hub `/brief/` mount.
- DailyBrief has a Python CLI/static report pipeline, not a web server,
  frontend, or FastAPI health endpoint.
