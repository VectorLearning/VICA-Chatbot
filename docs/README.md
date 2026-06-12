# Claude Teams Bot — Documentation

Handoff documentation for **VICA**, an `@mention`-able Microsoft Teams bot
powered by Claude.

## Read in this order

Picking this project up cold:

1. **[architecture.md](architecture.md)** — what the bot does, the request flow, how the modules fit, and why the design choices were made. Start here.
2. **[setup.md](setup.md)** — end-to-end setup: Azure (Entra app, Graph, Azure Bot), local Python, and the Teams app package. Section 1 needs an Entra admin.
3. **[customization.md](customization.md)** — changing the system prompt, adding skills, web search, and the less-common `.env` knobs.
4. **[troubleshooting.md](troubleshooting.md)** — every error hit during the build, by symptom.
5. **[deployment.md](deployment.md)** — moving off the local tunnel to a hosted service.

(For agent/developer-facing orientation, see [`../CLAUDE.md`](../CLAUDE.md).)

## Quick orientation

- **Codebase**: ~600 lines of Python. A single stateless aiohttp service.
- **External services**: Microsoft Bot Framework (free), Microsoft Graph (free with tenant), Anthropic API (paid — per token, plus $10/1000 web searches).
- **Auth**: client-credentials (app-only) flow for Graph. No user delegation.
- **Trigger**: acts only when `@mentioned` in a channel. Reads the previous hour of channel messages (capped at 20) as context.
- **Skills**: local `.md` files in `skills/`. No external dependencies.

## Key files

| File | Purpose |
|---|---|
| `app.py` | aiohttp server; `/api/messages` webhook and `/healthz` |
| `bot.py` | Activity handler — mention detection, context fetch, Claude call, reply |
| `graph_client.py` | Microsoft Graph client for reading channel messages |
| `claude_client.py` | Anthropic wrapper with tool-use loop (web search + skills) |
| `skill_loader.py` | Parses skill files from `skills/` |
| `config.py` | Loads and validates `.env` |
| `system_prompt.md` | The bot's system prompt — edit freely, no code change needed |
| `skills/` | Local skill definitions (one `.md` per skill) |
| `teams_app/manifest.json` | Teams app manifest for sideloading |
| `.env.example` | Template for required environment variables |
