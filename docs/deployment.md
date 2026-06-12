# Deployment (off the local tunnel)

When you're ready to retire the devtunnel + laptop setup and run this for real.

## What needs to change

Pretty much only the hosting. The bot code is already a stateless aiohttp service — no database, no local file mutations (skills are read-only at startup), no sticky sessions.

The differences from local dev:

| | Local | Production |
|---|---|---|
| Public URL | devtunnel URL, changes occasionally | Stable HTTPS endpoint |
| Process | `python app.py` in a terminal | Container, systemd, or PaaS |
| Secrets | `.env` file | Secrets Manager / env vars |
| Logs | stdout | CloudWatch / Loki / etc. |
| Restart on edit | manual | None — deploy a new image |

## Recommended targets

### Easiest: AWS App Runner

App Runner runs a single container with autoscaling, HTTPS termination, and no infra to manage. Cost is roughly $50/mo at low traffic.

1. Write a `Dockerfile` (see below).
2. Push to ECR.
3. Create an App Runner service pointing at the image.
4. Inject env vars via App Runner config or Secrets Manager.
5. Update the Azure Bot **Messaging endpoint** to App Runner's HTTPS URL + `/api/messages`.

### Also good: ECS Fargate

More control, more setup. Standard ECS service with an Application Load Balancer in front.

### Skip: AWS Lambda

The Bot Framework SDK and aiohttp don't fit Lambda's model well — cold starts will hurt response latency, and the SDK assumes a persistent process. Not recommended.

## Dockerfile

Add this at the repo root:

```dockerfile
FROM python:3.12-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

ENV PORT=8080
EXPOSE 8080

CMD ["python", "app.py"]
```

Note the port change: App Runner expects 8080. Either set `PORT=8080` in the container env or edit `app.py` to default to 8080.

## Secrets

Three sensitive values to inject as env vars (not in the image):

- `MICROSOFT_APP_PASSWORD`
- `GRAPH_CLIENT_SECRET`
- `ANTHROPIC_API_KEY`

In AWS, store them in Secrets Manager and reference from the App Runner service config. Never commit `.env` to git.

## Update the Azure Bot

After the production URL exists:

Azure portal → Azure Bot resource → **Settings → Configuration → Messaging endpoint**:
```
https://<your-prod-host>/api/messages
```
Apply.

If you want a fallback to dev while testing, keep the dev bot resource separate — create a second Azure Bot pointing at the dev tunnel, and a second Teams app pointing at it. That way you can iterate locally without breaking prod users.

## Skills and the system prompt in production

Both `system_prompt.md` and `skills/` are read from the container's working directory at startup. You have two choices:

1. **Bake them into the image** (simpler). Edits require a redeploy.
2. **Mount them from a volume** (e.g., S3 sync into an EFS mount). Non-engineers can edit a markdown file in a shared drive and the next bot restart picks them up.

For a small team, option 1 is fine. For broader content ownership, option 2 lets domain experts maintain skills without code access.

## Monitoring

The bot currently logs to stdout. In production, capture and alert on:

- 5xx responses from `/api/messages` (indicates the bot itself is failing).
- Exceptions during Graph calls (often signals expired secrets or revoked consent).
- Exceptions during Anthropic calls (could be rate limits, expired key, or model issues).
- Average Claude response time per request (creeps up if web_search is over-triggered).

A `/healthz` endpoint already returns 200 OK — wire that to your load balancer / App Runner health check.

## Cost estimate at low usage

For ~100 mentions/day with web search:

- App Runner: ~$50/mo
- Anthropic API: ~$5–15/mo (Sonnet, modest output)
- Web search: ~$5/mo (assuming 50% of mentions trigger search, ~3 searches each)
- Total: roughly $60–70/mo

At higher volumes the Anthropic costs dominate. Monitor `usage` in API response logs.
