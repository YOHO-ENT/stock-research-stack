# IP-Only Vultr Deployment

This runbook deploys only Research Hub to the existing Vultr instance. It does
not deploy sibling projects, create a new server, change DNS, or configure
HTTPS.

## Current Values

| Setting | Value |
|---|---|
| Public URL | `http://149.28.156.116` |
| SSH target | `root@149.28.156.116` |
| SSH key | `~/.ssh/vultr_daily_news` |
| Public ports | `80`, `22` |
| DailyBrief public URL | empty for now |

## Local Preparation

Validate the repo before deployment:

```bash
python3 scripts/check.py
python3 -m json.tool catalog/services.json >/tmp/research-stack-services.json
python3 -m compileall -q research_hub scripts/check.py
node --check research_hub/static/app.js
git diff --check
```

If SSH key login fails because the private key has a passphrase, load it into
the local agent:

```bash
ssh-add ~/.ssh/vultr_daily_news
```

## Server Deployment

Connect to the server:

```bash
ssh -i ~/.ssh/vultr_daily_news root@149.28.156.116
```

Install Docker if it is missing:

```bash
apt-get update
apt-get install -y ca-certificates curl git
install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
chmod a+r /etc/apt/keyrings/docker.asc
. /etc/os-release
echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/ubuntu ${VERSION_CODENAME} stable" > /etc/apt/sources.list.d/docker.list
apt-get update
apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
```

Clone or update the control repo:

```bash
mkdir -p /opt/research-stack
if [ -d /opt/research-stack/.git ]; then
  git -C /opt/research-stack fetch origin
  git -C /opt/research-stack checkout main
  git -C /opt/research-stack pull --ff-only origin main
else
  git clone https://github.com/YOHO-ENT/stock-research-stack.git /opt/research-stack
fi
```

Start Research Hub:

```bash
cd /opt/research-stack
cp .env.production.example .env
docker compose up -d --build
```

## Verification

```bash
docker ps
curl -fsS http://127.0.0.1/api/services
curl -fsS http://127.0.0.1/api/health
```

From the local machine:

```bash
curl http://149.28.156.116/
curl http://149.28.156.116/api/services
curl http://149.28.156.116/api/health
```

Expected behavior:

- Research Hub is reachable at `http://149.28.156.116`.
- Production catalog shows Research Hub and DailyBrief only.
- DailyBrief is `skipped` until `DAILYBRIEF_PUBLIC_REPORTS_URL` is set.
- Deprecated news-project references are absent.

## Operations

```bash
cd /opt/research-stack
docker compose ps
docker compose logs -f --tail=200
docker compose pull
docker compose up -d --build
docker compose down
```

## Future Domain Upgrade

When a domain is available:

1. Point an A record such as `hub.example.com` to `149.28.156.116`.
2. Update `.env` with `RESEARCH_HUB_PUBLIC_URL=https://hub.example.com`.
3. Replace `deploy/Caddyfile` with the domain block already shown in comments.
4. Add port `443` to the Vultr firewall.
5. Restart with `docker compose up -d`.
