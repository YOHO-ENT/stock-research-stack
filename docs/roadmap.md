# Roadmap

This roadmap keeps the control repo focused on orchestration and contract work.

## Phase 2: Research Hub v1

- Serve a local dashboard on `127.0.0.1:3030`.
- Show service links from `catalog/services.json`.
- Show best-effort health status.
- Do not start sibling services.
- Do not iframe or merge sibling frontends.

Status: implemented in this repository.

## Phase 3: HTTP Contract Hardening

- Define a Market Data Lab to Firn watchlist HTTP contract.
- Replace local file-sync assumptions with explicit API handoff docs.
- Add minimal contract examples and failure modes.

## Phase 4: Local Compose Draft

- Draft Docker Compose for services that are ready to run in containers.
- Keep services independently buildable.
- Keep secrets in private env files.
- Document services that are intentionally not containerized yet.

## Phase 5: Vultr Deployment

- Add reverse proxy routing.
- Add TLS and hostnames.
- Define persistent volumes and backup paths.
- Add production health checks and restart policy.
