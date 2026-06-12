# Claude Teams Bot (VICA)

A Microsoft Teams bot that listens for `@mentions` in a channel, reads the most recent messages, and replies using Claude (Anthropic API). Supports local skills (markdown files baked into the app) and web search.

## Documentation

Full handoff documentation lives in [`docs/`](docs/). Start with [`docs/README.md`](docs/README.md) for orientation, then read in the order it suggests. Agents and developers working in the code should also read [`CLAUDE.md`](CLAUDE.md).

Quick links:

- [Architecture](docs/architecture.md) — how it works and why
- [Setup](docs/setup.md) — Azure (Entra app, Graph, Azure Bot), local Python, and the Teams app package
- [Customization](docs/customization.md) — system prompt, skills, web search
- [Troubleshooting](docs/troubleshooting.md) — every error we've hit, with fixes
- [Deployment](docs/deployment.md) — moving off the local tunnel

## Hello-world summary for the impatient

```bash
# 1. Python env
python3.12 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# 2. Config
cp .env.example .env
# Fill in MICROSOFT_APP_ID / PASSWORD / TENANT_ID, GRAPH_*, ANTHROPIC_API_KEY

# 3. Tunnel (terminal 1)
devtunnel host -p 3978 --allow-anonymous

# 4. Bot (terminal 2)
python app.py

# 5. In Azure Bot resource → Configuration:
#    Messaging endpoint = https://<your-tunnel>/api/messages

# 6. Sideload teams_app/claude-teams-bot.zip into Teams
```

Then `@VICA hello` in a channel.

This works only after Azure-side setup is complete — see [docs/setup.md](docs/setup.md).

## Repo layout

```
.
├── app.py              # aiohttp server, /api/messages webhook
├── bot.py              # Bot Framework activity handler
├── graph_client.py     # Microsoft Graph (channel history)
├── claude_client.py    # Anthropic API + tool-use loop
├── skill_loader.py     # Parses skills/ into Skill objects
├── config.py           # Loads .env
├── system_prompt.md    # Editable system prompt
├── skills/             # Local skills (one .md per skill)
├── teams_app/          # Teams app manifest + icons
├── docs/               # Full handoff docs (start here)
├── CLAUDE.md           # Orientation for AI agents / developers
├── requirements.txt
├── .env.example
└── .gitignore
```

## What IT / Azure admin needs to do

Forward this to your admin:

> Please:
> 1. In Microsoft Entra ID, register an app for a Teams bot (Single Tenant, Web App platform).
> 2. Generate a client secret and share its value.
> 3. Add Microsoft Graph **application permission** `ChannelMessage.Read.All` and grant admin consent.
> 4. Create an **Azure Bot** resource using that app registration. Enable the Microsoft Teams channel.
> 5. Allow sideloading of custom Teams apps for me (or upload our zip via Teams Admin Center).
>
> The bot only reads messages in channels it's been added to, and only responds when @mentioned. Detailed steps in `docs/setup.md` (section 1).
