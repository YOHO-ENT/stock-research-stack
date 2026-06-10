# Ports

This file is the source of truth for local and current IP-only Vultr ports.

| Component | Planned URL | Notes |
|---|---:|---|
| Research Hub | `http://127.0.0.1:3030` | Local link and health-status page. |
| Research Hub on Vultr | `http://149.28.156.116:80` | IP-only production entry point through Caddy. |
| moomoo Account Web | `http://127.0.0.1:8501` | Existing py-moomoo-api dashboard. |
| moomoo OpenD gateway | `127.0.0.1:11111` | Local gateway, not HTTP. |
| Market Data Lab API | `http://127.0.0.1:8010` | Existing default API port. |
| Market Data Lab UI | `http://127.0.0.1:3020` | Existing default UI port. |
| Firn API | `http://127.0.0.1:8000` | Existing documented Firn API port. |
| Firn UI | `http://127.0.0.1:3000` | Existing Next.js default. |
| TradingAgents API | `http://127.0.0.1:8002` | Planned override; avoids Firn's `8000`. |
| TradingAgents UI | `http://127.0.0.1:5173` | Existing Vite default. |
| DailyBrief | N/A | Python CLI/static report pipeline; no local web port. |

## Conflict Notes

- Firn API and TradingAgents API both default to `8000`; research-stack assigns
  TradingAgents API to `8002`.
- DailyBrief does not reserve a port because it has no web server or frontend.
- Current IP-only deployment exposes `80` only for Research Hub. Future domain
  deployment should add `443`.
