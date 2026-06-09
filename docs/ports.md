# Ports

This file is the Phase 1 source of truth for local port planning.

| Component | Planned URL | Notes |
|---|---:|---|
| Research Hub | `http://127.0.0.1:3030` | Local link and health-status page. |
| moomoo Account Web | `http://127.0.0.1:8501` | Existing py-moomoo-api dashboard. |
| moomoo OpenD gateway | `127.0.0.1:11111` | Local gateway, not HTTP. |
| Market Data Lab API | `http://127.0.0.1:8010` | Existing default API port. |
| Market Data Lab UI | `http://127.0.0.1:3020` | Existing default UI port. |
| Firn API | `http://127.0.0.1:8000` | Existing documented Firn API port. |
| Firn UI | `http://127.0.0.1:3000` | Existing Next.js default. |
| TradingAgents API | `http://127.0.0.1:8002` | Planned override; avoids Firn's `8000`. |
| TradingAgents UI | `http://127.0.0.1:5173` | Existing Vite default. |
| US Equity News dashboard | `http://127.0.0.1:8502` | Planned override; avoids moomoo Account Web's `8501`. |

## Conflict Notes

- Firn API and TradingAgents API both default to `8000`; research-stack assigns
  TradingAgents API to `8002`.
- moomoo Account Web and the US Equity News Streamlit dashboard can both use
  `8501`; research-stack assigns US Equity News dashboard to `8502`.
- Future reverse proxy ports should terminate on standard `80` and `443` on
  Vultr and route to these internal services.
