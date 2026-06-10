# Vultr Deployment Plan

This is the deployment plan for the stack control layer. The current target
deployment is the expanded IP-only stack on the existing Vultr instance. It does
not create a new server, change DNS, configure HTTPS, expose moomoo OpenD, or
store secrets in git.

## Direction

- Use the existing Vultr VPS first: `149.28.156.116`.
- Use Docker Compose for service orchestration.
- Use Caddy as the reverse proxy.
- Expose IP-only HTTP on port `80` first.
- Keep each sibling project independently buildable and deployable.
- Do not use Kubernetes or k8s.
- Do not merge repositories into one application image.

## Candidate Runtime Shape

| Public Route | Internal Target | Notes |
|---|---|---|
| `http://149.28.156.116` | Research Hub | Current IP-only deployment. |
| `http://149.28.156.116/brief/` | DailyBrief static reports | Current systemd publisher output. |
| `http://149.28.156.116/market/` | Market Data Lab UI/API | Expanded Compose route. |
| `http://149.28.156.116/firn/` | Firn UI/API | Expanded Compose route. |
| `http://149.28.156.116/agents/` | TradingAgents UI/API | Expanded Compose route. |
| `http://149.28.156.116/moomoo/` | py-moomoo Account Web | Read-only Account Web route; OpenD is not exposed. |
| `research.example.com` | Research Hub | Future domain and HTTPS route. |
| `market.example.com` | Market Data Lab UI/API | UI plus API route. |
| `firn.example.com` | Firn UI/API | Auth, KB, audit, analysis. |
| `agents.example.com` | TradingAgents UI/API | Web console and markdown reports. |
| `brief.example.com` | DailyBrief static reports | Static report hosting first; no app server required. |

## Compose Strategy

- Compose starts Research Hub, Caddy, Market Data Lab API/UI, Firn API/UI,
  TradingAgents API/UI, and py-moomoo Account Web.
- DailyBrief remains a systemd timer/publisher and is not moved into Compose.
- Compose builds or references each project from its own directory.
- Mount each project's data, logs, reports, and cache paths explicitly.
- Keep secrets out of git and inject them through private env files or Vultr
  secrets management.
- Use one reverse proxy container to route public hostnames or IP-only HTTP to
  internal service ports.

## Current IP-Only Deployment Values

| Setting | Value |
|---|---|
| SSH target | `root@149.28.156.116` |
| SSH key | `~/.ssh/research_stack_vultr` |
| Public URL | `http://149.28.156.116` |
| Public ports | `80`, `22` |
| DailyBrief public URL | `http://149.28.156.116/brief/` |

## Service Notes

- `py-moomoo-api` depends on local moomoo OpenD for live account reads. The
  Vultr route exposes Account Web behind Basic Auth but does not expose OpenD
  `11111`.
- `market-data-lab` now has API/UI container definitions for stack deployment.
- `Firn` uses its existing API/UI Dockerfiles with `/firn` base-path support.
- `TradingAgents` now has API/UI container definitions for stack deployment.
- `DailyBrief` is Python-only: no database, server, or frontend framework. It
  can run via scheduler/GitHub Actions and publish static reports. The current
  control-plane deployment serves static reports at `/brief/`; the DailyBrief
  pipeline currently runs on the same VPS through systemd and publishes
  `health.json`.

## Current Operations

- `scripts/deploy_vultr.sh` deploys the current `main` branch to the existing
  host and uploads committed sibling repo source archives under `/opt`.
- `scripts/deploy_dailybrief_vultr.sh` deploys the DailyBrief systemd timer and
  publishes static reports into the Research Hub report mount.
- Caddy Basic Auth protects the IP-only site. The server `.env` stores only the
  Caddy hash, not the plaintext password.
- DailyBrief reports are served from
  `/opt/research-stack/runtime/dailybrief-reports`.

## Deployment Acceptance

- All public routes continue to return `401` without Basic Auth.
- Caddy internal checks pass for Hub, DailyBrief, Market Data Lab, Firn,
  TradingAgents, and py-moomoo Account Web.
- moomoo OpenD stays private unless a separate security decision changes that
  boundary.
- Public TLS works for each enabled hostname.
- Reverse proxy health checks use documented health endpoints.
- No service exposes secrets in logs, static assets, or client-side config.
- Restart policy and persistent volumes are defined for stateful services.
- Long-running agent jobs have an explicit persistence or recovery story before
  multi-user production use.
