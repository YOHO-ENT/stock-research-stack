# Local Start Plan

This is a manual runbook only. Research Hub shows links and health status, but
it does not start sibling services.

## 1. Start Research Hub

From `/Users/yongnahwa/Desktop/research-stack`:

```bash
python3 -m research_hub --host 127.0.0.1 --port 3030
```

Expected URL:

```text
http://127.0.0.1:3030
```

## 2. Start moomoo OpenD

Start and log in to moomoo OpenD outside research-stack.

Expected gateway:

```text
127.0.0.1:11111
```

## 3. Start moomoo Account Web

From `/Users/yongnahwa/Desktop/py-moomoo-api`:

```bash
python3 -m moomoo.examples.account_web
```

Expected URL:

```text
http://127.0.0.1:8501
```

## 4. Start Market Data Lab

From `/Users/yongnahwa/Desktop/market-data-lab`:

```bash
./scripts/start_api.sh
./scripts/start_ui.sh
```

Expected URLs:

```text
http://127.0.0.1:8010
http://127.0.0.1:3020
```

Research universe sync should read moomoo through:

```text
GET http://127.0.0.1:8501/api/research-universe/export
```

## 5. Start Firn

From `/Users/yongnahwa/Desktop/Firn/global-market-agent`:

```bash
uv run uvicorn src.api.app:app --host 0.0.0.0 --port 8000
```

From `/Users/yongnahwa/Desktop/Firn/web-ui`:

```bash
pnpm dev
```

Expected URLs:

```text
http://127.0.0.1:8000
http://127.0.0.1:3000
```

## 6. Start TradingAgents

From `/Users/yongnahwa/Desktop/TradingAgents`:

```bash
TRADINGAGENTS_API_PORT=8002 tradingagents-api
```

From `/Users/yongnahwa/Desktop/TradingAgents/frontend`:

```bash
VITE_API_BASE_URL=http://127.0.0.1:8002 npm run dev
```

Expected URLs:

```text
http://127.0.0.1:8002
http://127.0.0.1:5173
```

## 7. Start US Equity News Dashboard

From `/Users/yongnahwa/Desktop/US-equity-news-daily-analysis`:

```bash
streamlit run app/dashboard/streamlit_app.py --server.address=127.0.0.1 --server.port=8502
```

Expected URL:

```text
http://127.0.0.1:8502
```

Research Hub should show offline sibling services as `down` or `skipped` until
you start them.
