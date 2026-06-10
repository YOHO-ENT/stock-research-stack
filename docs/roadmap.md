# Roadmap

This roadmap keeps the control repo focused on orchestration and contract work.

## Phase 2: Research Hub v1

- Serve a local dashboard on `127.0.0.1:3030`.
- Show service links from `catalog/services.json`.
- Show best-effort health status.
- Do not start sibling services.
- Do not iframe or merge sibling frontends.

Status: implemented in this repository.

## Phase 2.5: IP-Only Hub Deployment

- Run Research Hub behind Caddy with Docker Compose on the existing Vultr host.
- Protect the public IP route with temporary Basic Auth.
- Serve DailyBrief static report artifacts from `/brief/`.
- Keep the production catalog limited to Research Hub and DailyBrief.

Status: implemented and deployed to the current IP-only Vultr host.

## Phase 3: HTTP Contract Hardening

- Define a Market Data Lab to Firn watchlist HTTP contract.
- Define a TradingAgents ticker-selection contract from Market Data Lab.
- Replace local file-sync assumptions with explicit API handoff docs.
- Add minimal contract examples and failure modes.

Status: contracts are documented in [HTTP contracts](http-contracts.md);
Market Data Lab has local Firn HTTP watchlist sync, and TradingAgents has a
local Market Data Lab ticker selector. Production deployment of these sibling
service integrations remains future work.

## Phase 3.5: Local Loop Stability

- Document the local operator loop from moomoo export to Market Data Lab, Firn,
  and TradingAgents.
- Add a read-only local smoke check for loop status.
- Add Research Hub control signals for universe, watchlist, ticker selection,
  and DailyBrief local reports.
- Do not start services, deploy services, or trigger LLM runs from this layer.

Status: implemented in this repository as a local control-plane capability.

## Phase 4: Local Compose Draft

- Draft Docker Compose for services that are ready to run in containers.
- Keep services independently buildable.
- Keep secrets in private env files.
- Document services that are intentionally not containerized yet.

Status: partially implemented for the Research Hub control plane only. Sibling
projects remain independently deployed or local-only until the local loop smoke
check is stable and they have explicit container contracts.

## Phase 5: Vultr Deployment

- Install the DailyBrief systemd publishing pipeline.
- Publish generated DailyBrief reports into the Research Hub `/brief/` mount.
- Verify production health checks and restart policy.
- Add TLS and hostnames when DNS is ready.
- Define persistent volumes and backup paths.

Status: DailyBrief systemd publishing, `/brief/` static report serving, and
production smoke checks are implemented. TLS, DNS, access control for sibling
services, sibling service deployment, and broader backup policy remain future
work.
