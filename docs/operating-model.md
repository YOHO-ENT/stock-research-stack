# Operating Model

`research-stack` is the control repository for system-level decisions. It owns
the map, contracts, ports, local runbooks, deployment plans, and the Research
Hub entry point.

## What Belongs Here

- Service catalog and ownership boundaries.
- Cross-project HTTP contracts.
- Local and deployment port maps.
- Research Hub links and health checks.
- Stack-level docs for Vultr, reverse proxy, and orchestration.
- Validation scripts for this repository.

## What Stays In Sibling Projects

- Application source code.
- Project-specific tests.
- Project-specific secrets and private env files.
- Project-specific generated data, logs, caches, reports, and databases.
- Project-specific commits and release workflows.

## Codex Session Pattern

- Use this repo's session for architecture and orchestration.
- Use each sibling project's own Codex session for code changes inside that
  project.
- After a sibling project changes an API, port, or env contract, update this
  repo's catalog and docs.
- Do not use this repo as a staging area for sibling project patches.

## Current Guardrails

- No code merging across sibling repositories.
- No direct imports from sibling project internals.
- No hidden file or cache coupling for live integrations.
- No iframe composition.
- No Kubernetes or k8s.

