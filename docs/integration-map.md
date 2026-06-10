# Integration Map

All live cross-project integrations should use HTTP APIs. File-level coupling is
not a preferred integration mechanism.

## Allowed Flows

| Flow | Current or Target | Contract |
|---|---|---|
| moomoo Account Web -> Market Data Lab | Current | py-moomoo-api may call Market Data Lab read-only endpoints for status and snapshots. |
| Market Data Lab -> moomoo Account Web | Current | Market Data Lab reads `GET /api/research-universe/export`. It must not read moomoo cache files. See [HTTP contracts](http-contracts.md). |
| Market Data Lab -> Firn | Current local v1 | Market Data Lab can push normalized watchlists to Firn `PUT /api/config/watchlist` over HTTP when Firn enables `FIRN_WATCHLIST_EDITABLE=true`. |
| DailyBrief -> generated reports | Current | DailyBrief writes static HTML/JSON report artifacts under its own `daily_reports/` directory. |
| TradingAgents -> Market Data Lab | Current local v1 | TradingAgents can read Market Data Lab universes through its own `/api/market-data/universes` adapter and fill the existing analysis form. |
| Research Hub -> all services | Current | Research Hub links to services, checks health, and reads local control signals only. |

## Explicit Non-Flows

- Research Hub must not iframe sibling frontends.
- Research Hub must not merge sibling frontends.
- Research Hub must not start, deploy, or mutate sibling services.
- research-stack must not import sibling project internals.
- market-data-lab must not read moomoo cache files.
- TradingAgents must not read Market Data Lab internal files for ticker
  selection.
- DailyBrief reports must not be treated as hidden inputs to unrelated
  services unless an explicit artifact handoff is documented.

## Current Gaps

- Market Data Lab still keeps a local `FIRN_WATCHLIST_PATH` file-sync fallback.
  This is transitional and manual; research-stack documents HTTP as the default
  stack integration.
- TradingAgents ticker selection is implemented for API/UI use and is included
  in the expanded IP-only Vultr Compose route.
- Research Hub v1 is deployed locally and on the current IP-only Vultr host.
- DailyBrief systemd publishing is running on the Vultr host and publishes
  static reports plus `health.json` into the Research Hub `/brief/` mount.
- DailyBrief has a Python CLI/static report pipeline, not a web server,
  frontend, or FastAPI health endpoint.
