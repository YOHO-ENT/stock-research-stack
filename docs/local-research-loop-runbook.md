# Local Research Loop Runbook

This runbook keeps the first local data loop repeatable without turning
research-stack into a service supervisor. Run commands from the owning sibling
repository. Do not start services from research-stack scripts.

## Goal

Confirm the local loop is usable:

```text
py-moomoo-api -> market-data-lab -> Firn / TradingAgents
```

The loop should let an operator sync the moomoo research universe into Market
Data Lab, push the normalized watchlist to Firn over HTTP, select a ticker in
TradingAgents from the Market Data Lab universe, and generate a markdown report.

## Preconditions

- moomoo OpenD is running locally and logged in.
- moomoo Account Web is available at `http://127.0.0.1:8501`.
- Market Data Lab API is available at `http://127.0.0.1:8010`.
- Firn API is available at `http://127.0.0.1:8000`.
- TradingAgents API is available at `http://127.0.0.1:8002`.
- TradingAgents UI is available at `http://127.0.0.1:5173`.

For Firn watchlist writes, start Firn with:

```bash
FIRN_WATCHLIST_EDITABLE=true uv run uvicorn src.api.app:app --host 0.0.0.0 --port 8000
```

For Market Data Lab to prefer HTTP watchlist sync, set:

```bash
FIRN_API_BASE_URL=http://127.0.0.1:8000
```

For TradingAgents to read Market Data Lab, set:

```bash
MARKET_DATA_LAB_BASE_URL=http://127.0.0.1:8010
TRADINGAGENTS_API_PORT=8002
```

## Manual Loop

1. In `py-moomoo-api`, confirm the export is reachable:

   ```bash
   curl -fsS http://127.0.0.1:8501/api/research-universe/export >/tmp/research-universe.json
   ```

2. In `market-data-lab`, preview the universe:

   ```bash
   uv run market-data moomoo-preview
   ```

3. In `market-data-lab`, sync the universe and push Firn over HTTP:

   ```bash
   FIRN_API_BASE_URL=http://127.0.0.1:8000 uv run market-data moomoo-sync --sync-firn
   ```

4. Confirm Market Data Lab has groups:

   ```bash
   curl -fsS http://127.0.0.1:8010/universes
   ```

5. Confirm Firn received categories:

   ```bash
   curl -fsS http://127.0.0.1:8000/api/config/watchlist
   ```

6. In TradingAgents UI, choose a Market Data Lab universe group and ticker,
   then run the existing single-ticker analysis flow.

7. Confirm TradingAgents can read the same universe through its adapter:

   ```bash
   curl -fsS http://127.0.0.1:8002/api/market-data/universes
   ```

## Smoke Check

From `/Users/yongnahwa/Desktop/research-stack`:

```bash
python3 scripts/smoke_local_research_loop.py
python3 scripts/smoke_local_research_loop.py --json
```

The smoke check is read-only. It does not start services, write universe files,
push Firn watchlists, or trigger a TradingAgents/LLM run.

Expected behavior:

- Exit `0`: all local control signals are healthy.
- Exit `2`: at least one local service or report signal is down or stale.
- Exit `1`: command usage or unexpected script failure.

When services are intentionally stopped, `down` output is expected.

## Boundaries

- research-stack does not read sibling caches or config files as integration
  input.
- The only filesystem status check here is DailyBrief's generated report
  artifact directory.
- moomoo account capabilities stay local and are not part of Vultr expansion in
  this phase.
- Research Hub remains a status and link control plane. It does not iframe or
  merge sibling frontends.
