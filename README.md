# research-stack

`research-stack` is the top-level orchestration, documentation, and future
deployment layer for a set of independently maintained research projects.

It is not a merged codebase, not a monorepo app, and not an application that
imports sibling project internals. Each project keeps its own repository,
tooling, runtime data, secrets, and release workflow. Cross-project integration
must happen through documented HTTP APIs or generated report artifacts.

## Managed Projects

| Project | Path | Role |
|---|---|---|
| py-moomoo-api | `/Users/yongnahwa/Desktop/py-moomoo-api` | Read-only moomoo account, positions, watchlist, and research-universe export source |
| market-data-lab | `/Users/yongnahwa/Desktop/market-data-lab` | Market history, technical indicators, chart data, and research universe center |
| Firn | `/Users/yongnahwa/Desktop/Firn` | Audit, evidence, knowledge base, claim verification, and deeper research memory |
| TradingAgents | `/Users/yongnahwa/Desktop/TradingAgents` | Deep ticker and portfolio-style agent analysis with markdown report output |
| DailyBrief | `/Users/yongnahwa/Desktop/DailyBrief` | Local-first AI news and markets digest generator with static HTML report output |

## Control Repo Operating Model

Use this repository for stack-level planning and orchestration:

- architecture boundaries
- service catalog and ports
- HTTP integration contracts
- local runbooks
- Research Hub
- future Vultr deployment plans

Use each sibling project's own repository and Codex session for code changes
inside that project. After a sibling project changes an API, port, or env
contract, update this repository's catalog and docs.

## Architecture Rules

- Do not merge sibling repositories into this directory.
- Do not edit sibling project code from this layer.
- Do not read another project's private files, caches, databases, or internal
  modules as an integration mechanism.
- Use HTTP APIs between services when live integration is needed.
- Keep generated reports as explicit artifacts, not hidden coupling.
- Research Hub v1 is only a link and health-status entry point.
- Do not iframe sibling frontends.
- Do not combine sibling frontends into one application.
- Prefer Docker Compose plus a reverse proxy for Vultr deployment.
- Do not use Kubernetes or k8s for this stack.

## Research Hub v1

Run the local control-plane dashboard:

```bash
python3 -m research_hub --host 127.0.0.1 --port 3030
```

Open:

```text
http://127.0.0.1:3030
```

API endpoints:

- `GET /api/services`
- `GET /api/health`

Research Hub reads [catalog/services.json](catalog/services.json), serves
service links, and performs best-effort backend health checks. It does not
start sibling services.

## IP-Only Vultr Deployment

Research Hub can be deployed to the existing Vultr instance at:

```text
http://149.28.156.116
```

The IP-only deployment uses Docker Compose plus Caddy on port `80`. It does not
use a domain, HTTPS, Kubernetes, DNS changes, or sibling project deployments.
Production catalog mode shows Research Hub and DailyBrief only. Caddy protects
the site with temporary Basic Auth and serves DailyBrief static reports under
`/brief/`.

See [IP-only Vultr deployment](docs/ip-only-vultr-deployment.md).
See [DailyBrief production runbook](docs/dailybrief-production-runbook.md) for
the report pipeline, systemd timer, smoke checks, and rollback steps.

## Contents

This repository contains:

- [Service catalog](docs/service-catalog.md)
- [Integration map](docs/integration-map.md)
- [HTTP contracts](docs/http-contracts.md)
- [Ports](docs/ports.md)
- [Local start plan](docs/local-start-plan.md)
- [IP-only Vultr deployment](docs/ip-only-vultr-deployment.md)
- [DailyBrief production runbook](docs/dailybrief-production-runbook.md)
- [Operating model](docs/operating-model.md)
- [Roadmap](docs/roadmap.md)
- [Vultr deployment plan](docs/vultr-deployment-plan.md)
- [Machine-readable catalog](catalog/services.json)
- [Research Hub](research_hub/)

Validate this repo:

```bash
python3 scripts/check.py
```

Deploy the current `main` branch to the existing Vultr host:

```bash
scripts/deploy_vultr.sh
```

Deploy the DailyBrief systemd pipeline and publish reports into `/brief/`:

```bash
scripts/deploy_dailybrief_vultr.sh
```

Smoke-check the DailyBrief production path:

```bash
python3 scripts/smoke_dailybrief_vultr.py
```

Git history is used only for this orchestration layer.
