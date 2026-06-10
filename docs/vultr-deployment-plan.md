# Vultr Deployment Plan

This is the deployment plan for the stack control layer. The current supported
deployment is IP-only Research Hub on the existing Vultr instance. It does not
create a new server, change DNS, configure HTTPS, deploy sibling projects, or
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
| `research.example.com` | Research Hub | Future domain and HTTPS route. |
| `market.example.com` | Market Data Lab UI/API | UI plus API route. |
| `firn.example.com` | Firn UI/API | Auth, KB, audit, analysis. |
| `agents.example.com` | TradingAgents UI/API | Web console and markdown reports. |
| `brief.example.com` | DailyBrief static reports | Static report hosting first; no app server required. |

## Compose Strategy

- Compose currently starts Research Hub plus Caddy only.
- Future Compose expansion should build or reference each project from its own
  directory.
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

- `py-moomoo-api` depends on local moomoo OpenD. Cloud deployment needs a clear
  decision about whether OpenD runs on the VPS or only on a local machine.
- `market-data-lab` has no existing Dockerfile in Phase 1 research; it needs a
  future containerization pass.
- `Firn` has Dockerfiles for API and UI, but no top-level Compose file.
- `TradingAgents` has a Dockerfile and Compose for CLI/Ollama, but not for its
  API plus frontend web console.
- `DailyBrief` is Python-only: no database, server, or frontend framework. It
  can run via scheduler/GitHub Actions and publish static reports. The current
  control-plane deployment only serves a static report directory at `/brief/`;
  it does not run the DailyBrief pipeline.

## Current Operations

- `scripts/deploy_vultr.sh` deploys the current `main` branch to the existing
  host.
- Caddy Basic Auth protects the IP-only site. The server `.env` stores only the
  Caddy hash, not the plaintext password.
- DailyBrief reports are served from
  `/opt/research-stack/runtime/dailybrief-reports`.

## Deployment Acceptance For A Later Phase

- Public TLS works for each enabled hostname.
- Reverse proxy health checks use documented health endpoints.
- No service exposes secrets in logs, static assets, or client-side config.
- Restart policy and persistent volumes are defined for stateful services.
- Long-running agent jobs have an explicit persistence or recovery story before
  multi-user production use.
