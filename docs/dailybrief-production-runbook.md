# DailyBrief Production Runbook

This runbook covers the current IP-only Vultr production path for DailyBrief
inside research-stack. DailyBrief remains an independent project; research-stack
only deploys the control-plane integration, systemd units, static report mount,
and smoke checks.

## Current Production Shape

| Item | Value |
|---|---|
| Public Hub URL | `http://149.28.156.116/` |
| Public DailyBrief URL | `http://149.28.156.116/brief/` |
| SSH target | `root@149.28.156.116` |
| SSH key | `~/.ssh/research_stack_vultr` |
| research-stack path | `/opt/research-stack` |
| DailyBrief path | `/home/deploy/DailyBrief` |
| Published report mount | `/opt/research-stack/runtime/dailybrief-reports` |
| DailyBrief env file | `/etc/dailybrief/dailybrief.env` |
| Timer | `dailybrief.timer` |
| Service | `dailybrief.service` |
| Schedule | daily at `08:00 Asia/Shanghai` |

The public site is intentionally protected by Caddy Basic Auth. Unauthenticated
requests to `/` and `/brief/` should return `401`.

## Standard Deployment

Run from `/Users/yongnahwa/Desktop/research-stack`.

1. Validate locally:

   ```bash
   python3 scripts/check.py
   python3 -m json.tool catalog/services.json >/tmp/research-stack-services.json
   python3 -m compileall -q research_hub scripts
   node --check research_hub/static/app.js
   git diff --check
   ```

2. Deploy Research Hub and Caddy:

   ```bash
   scripts/deploy_vultr.sh
   ```

3. Install or refresh DailyBrief without starting a live LLM run:

   ```bash
   RUN_DAILYBRIEF_NOW=0 scripts/deploy_dailybrief_vultr.sh
   ```

4. Run the smoke check:

   ```bash
   python3 scripts/smoke_dailybrief_vultr.py
   ```

5. Trigger one production run only when the deploy and smoke check are clean:

   ```bash
   ssh -i ~/.ssh/research_stack_vultr root@149.28.156.116 \
     'systemctl reset-failed dailybrief.service && systemctl start dailybrief.service'
   ```

6. Run the smoke check again:

   ```bash
   python3 scripts/smoke_dailybrief_vultr.py
   python3 scripts/smoke_dailybrief_vultr.py --json
   ```

## Operations

Check Docker Compose services:

```bash
ssh -i ~/.ssh/research_stack_vultr root@149.28.156.116 \
  'cd /opt/research-stack && docker compose ps'
```

Follow Hub and Caddy logs:

```bash
ssh -i ~/.ssh/research_stack_vultr root@149.28.156.116 \
  'cd /opt/research-stack && docker compose logs -f --tail=200'
```

Check the DailyBrief timer:

```bash
ssh -i ~/.ssh/research_stack_vultr root@149.28.156.116 \
  'systemctl list-timers dailybrief.timer --no-pager && systemctl status dailybrief.timer --no-pager'
```

Check the DailyBrief service and recent journal:

```bash
ssh -i ~/.ssh/research_stack_vultr root@149.28.156.116 \
  'systemctl status dailybrief.service --no-pager || true; journalctl -u dailybrief.service -n 200 --no-pager'
```

Check the DailyBrief service log written by the oneshot wrapper:

```bash
ssh -i ~/.ssh/research_stack_vultr root@149.28.156.116 \
  'tail -n 200 /home/deploy/DailyBrief/logs/dailybrief-service-$(date -u +%F).log'
```

Run DailyBrief readiness checks from the VPS:

```bash
ssh -i ~/.ssh/research_stack_vultr root@149.28.156.116 \
  'cd /home/deploy/DailyBrief && .venv/bin/python scripts/check_vps_production.py --output-json'

ssh -i ~/.ssh/research_stack_vultr root@149.28.156.116 \
  'cd /home/deploy/DailyBrief && .venv/bin/python scripts/check_dailybrief_acceptance.py --days 1 --output-dir /opt/research-stack/runtime/dailybrief-reports --output-json'
```

## Report Health

The static report publisher writes:

```text
/opt/research-stack/runtime/dailybrief-reports/health.json
```

Check it through the internal Caddy route:

```bash
ssh -i ~/.ssh/research_stack_vultr root@149.28.156.116 \
  'cd /opt/research-stack && docker compose exec -T caddy wget -q -O - http://127.0.0.1:8080/brief/health.json'
```

Expected `health.json` fields:

- `status`: `ok` when the latest publish has all required artifacts.
- `latest_report_date`: latest dated report directory.
- `latest_report_url`: public URL for the latest HTML report.
- `artifacts`: booleans for `index`, `archive`, `html`, `json`, and `articles`.
- `missing`: empty list when publish health is clean.
- `generated_at`: UTC timestamp for the publish health file.

Check public Basic Auth behavior from the local machine:

```bash
curl -sS -o /dev/null -w 'root=%{http_code}\n' http://149.28.156.116/
curl -sS -o /dev/null -w 'brief=%{http_code}\n' http://149.28.156.116/brief/
```

Both should return `401` without credentials.

## Rollback

Rollback Research Hub and Caddy to a known good research-stack commit:

```bash
ssh -i ~/.ssh/research_stack_vultr root@149.28.156.116 '
  cd /opt/research-stack &&
  git fetch origin &&
  git checkout <GOOD_RESEARCH_STACK_SHA> &&
  docker compose up -d --build
'
```

Rollback DailyBrief while keeping the last published static reports online:

```bash
ssh -i ~/.ssh/research_stack_vultr root@149.28.156.116 '
  systemctl disable --now dailybrief.timer &&
  cd /home/deploy/DailyBrief &&
  git fetch origin &&
  git checkout <GOOD_DAILYBRIEF_SHA> &&
  .venv/bin/pip install -e ".[test]" &&
  install -m 0644 deploy/vultr/dailybrief.service /etc/systemd/system/dailybrief.service &&
  install -m 0644 deploy/vultr/dailybrief.timer /etc/systemd/system/dailybrief.timer &&
  systemctl daemon-reload &&
  systemctl enable --now dailybrief.timer
'
```

After rollback, run:

```bash
python3 scripts/smoke_dailybrief_vultr.py
```

The `/brief/` static report mount should remain available throughout the
rollback unless `/opt/research-stack/runtime/dailybrief-reports` is deleted.
