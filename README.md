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
| US Equity News Daily Analysis | `/Users/yongnahwa/Desktop/US-equity-news-daily-analysis` | Daily US equity news, SEC, event analysis, and static HTML report pipeline |

## Architecture Rules

- Do not merge sibling repositories into this directory.
- Do not edit sibling project code from this layer.
- Do not read another project's private files, caches, databases, or internal
  modules as an integration mechanism.
- Use HTTP APIs between services when live integration is needed.
- Keep generated reports as explicit artifacts, not hidden coupling.
- The future Research Hub v1 is only a link and health-status entry point.
- Do not iframe sibling frontends.
- Do not combine sibling frontends into one application.
- Prefer Docker Compose plus a reverse proxy for Vultr deployment.
- Do not use Kubernetes or k8s for this stack.

## Phase 1 Contents

This phase creates documentation and machine-readable metadata only:

- [Service catalog](docs/service-catalog.md)
- [Integration map](docs/integration-map.md)
- [Ports](docs/ports.md)
- [Local start plan](docs/local-start-plan.md)
- [Vultr deployment plan](docs/vultr-deployment-plan.md)
- [Machine-readable catalog](catalog/services.json)

No services are started by this repository. Git history is used only for this
orchestration layer when explicitly requested.
