# Vultr Deployment Plan

This is a future deployment plan. Phase 1 does not create Docker Compose files,
reverse-proxy config, systemd units, images, servers, DNS records, or secrets.

## Direction

- Use one Vultr VPS first.
- Use Docker Compose for service orchestration.
- Use a reverse proxy for TLS and routing.
- Keep each sibling project independently buildable and deployable.
- Do not use Kubernetes or k8s.
- Do not merge repositories into one application image.

## Candidate Runtime Shape

| Public Route | Internal Target | Notes |
|---|---|---|
| `research.example.com` | Research Hub | Links and health only. |
| `market.example.com` | Market Data Lab UI/API | UI plus API route. |
| `firn.example.com` | Firn UI/API | Auth, KB, audit, analysis. |
| `agents.example.com` | TradingAgents UI/API | Web console and markdown reports. |
| `news.example.com` | US Equity News static reports/dashboard | Static report hosting first; dashboard optional. |

## Compose Strategy

- Put Compose files in research-stack only after Phase 1.
- Build or reference each project from its own directory.
- Mount each project's data, logs, reports, and cache paths explicitly.
- Keep secrets out of git and inject them through private env files or Vultr
  secrets management.
- Use one reverse proxy container to route public hostnames to internal service
  ports.

## Service Notes

- `py-moomoo-api` depends on local moomoo OpenD. Cloud deployment needs a clear
  decision about whether OpenD runs on the VPS or only on a local machine.
- `market-data-lab` has no existing Dockerfile in Phase 1 research; it needs a
  future containerization pass.
- `Firn` has Dockerfiles for API and UI, but no top-level Compose file.
- `TradingAgents` has a Dockerfile and Compose for CLI/Ollama, but not for its
  API plus frontend web console.
- `US-equity-news-daily-analysis` has Docker and Compose for local CLI,
  pipeline, and dashboard use; production scheduling still needs a stack-level
  decision.

## Deployment Acceptance For A Later Phase

- Public TLS works for each enabled hostname.
- Reverse proxy health checks use documented health endpoints.
- No service exposes secrets in logs, static assets, or client-side config.
- Restart policy and persistent volumes are defined for stateful services.
- Long-running agent jobs have an explicit persistence or recovery story before
  multi-user production use.
