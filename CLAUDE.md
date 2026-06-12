# CLAUDE.md

Guidance for AI coding agents (and humans) working in this repo.

## What this is

A Microsoft Teams bot, **VICA**, that listens for `@mentions` in a Teams channel,
reads the recent channel messages for context, and replies using the Anthropic
API (Claude). It supports two extra capabilities: local **skills** (markdown
files baked into the app) and Anthropic's server-side **web search**.

It is a single, stateless aiohttp service — no database, no user delegation,
~600 lines of Python.

## Commands

```bash
# Environment (Python 3.12 — see "Gotchas" before using 3.13)
python3.12 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# Config
cp .env.example .env   # then fill in every required value

# Run the bot (serves on PORT, default 3978)
python app.py

# Health check
curl http://localhost:3978/healthz   # -> "ok"

# Public tunnel for local Teams testing (separate terminal)
devtunnel host -p 3978 --allow-anonymous

# Rebuild the Teams app package after editing the manifest
cd teams_app && rm -f claude-teams-bot.zip && \
  zip claude-teams-bot.zip manifest.json color.png outline.png
```

There is no test suite or linter configured. Verify changes by running the bot
and exercising it via Azure's "Test in Web Chat" or a real `@mention` in Teams.

## Architecture

Request flow on each `@mention`:

```
Teams → Azure Bot Service → POST /api/messages (app.py)
  → bot.py: verify channel context + bot was @mentioned, strip mention tags
  → graph_client.py: app-only Graph token (MSAL), GET recent channel messages
  → claude_client.py: build prompt, call Anthropic with tool-use loop
       (use_skill = local; web_search = server-side)
  → reply posted back to the channel via Bot Framework
```

Module responsibilities:

| File | Responsibility |
|---|---|
| `app.py` | aiohttp server; `/api/messages` webhook and `/healthz`; wires up adapter, Graph, Claude, bot |
| `bot.py` | Bot Framework activity handler: mention detection, context fetch, Claude call, reply |
| `graph_client.py` | Microsoft Graph client (MSAL client-credentials) for reading channel messages |
| `claude_client.py` | Anthropic wrapper + agentic tool-use loop (skills + web search) |
| `skill_loader.py` | Parses `skills/*.md` (and `skills/<name>/SKILL.md`) into `Skill` objects |
| `config.py` | Loads/validates `.env` into a `Config` dataclass |
| `system_prompt.md` | The bot's system prompt — edit freely, no code change needed |
| `skills/` | Local skill definitions (one `.md` per skill) |
| `teams_app/` | Teams app manifest + icons + built zip |
| `docs/` | Full handoff documentation |

## Conventions

- **Configuration lives in `.env`, never in code.** Add new settings to both
  `config.py` (the `Config` dataclass + `load_config`) and `.env.example`.
  Use `_require(...)` for mandatory vars and `os.environ.get(...)` with a
  default for optional ones.
- **The system prompt and skills are data, not code.** Change behaviour by
  editing `system_prompt.md` or adding a file under `skills/` — don't hardcode
  prompt text in `claude_client.py`. The built-in `DEFAULT_SYSTEM_PROMPT` is
  only a fallback for when the file is missing.
- **Skills are loaded at startup**, so restart `python app.py` after editing
  `system_prompt.md` or anything under `skills/`. The startup log prints
  `Loaded N skill(s): ...` — if a skill is missing there, its frontmatter
  didn't parse.
- **Skill descriptions drive triggering.** Claude only sees the `description`
  (not the body) when deciding whether to load a skill. Phrase descriptions as
  "Use when..." with concrete trigger words.
- Code targets Python 3.12, uses `from __future__ import annotations`, type
  hints, and stdlib `logging` (configured in `app.py`). Keep modules small and
  single-purpose.

## Gotchas (read before editing)

- **Mention detection depends on a workaround in `app.py`.** The Bot Framework
  SDK (4.16.2) drops `mentioned.id` when it deserializes entities, so `app.py`
  stashes the raw `entities` list on the activity as `activity.raw_entities`,
  and `bot.py`'s `_bot_was_mentioned` reads from that. **If you remove this,
  mention detection silently fails** and the bot stops replying.
- **Use Python 3.12, not 3.13.** Some Bot Framework / aiohttp wheels fail to
  build on 3.13. `aiohttp` is pinned to `3.10.5` because
  `botbuilder-integration-aiohttp==4.16.2` requires exactly that version — don't
  bump it casually.
- **Reading channel messages needs RSC, not just tenant consent.** Microsoft
  moved channel messages into "protected APIs". The practical path is
  resource-specific consent (`ChannelMessage.Read.Group`) declared in
  `teams_app/manifest.json` and approved by a team owner at install time.
  Tenant-wide `ChannelMessage.Read.All` alone may still return 403. See
  `docs/setup.md`.
- **The manifest has two GUIDs.** Top-level `"id"` identifies the *Teams app*;
  `bots[0].botId` is the *bot's Azure App ID*. They may be equal but mean
  different things. Changing the top-level `id` is the clean way to upload an
  updated app alongside an installed one.
- **The bot only responds in channels, when @mentioned.** 1:1 and group chats
  get a canned "channels only" message. That message during a Web Chat test is
  expected, not a bug.
- **Web search must be enabled org-side** in the Anthropic Console
  (Settings → Privacy) or the API errors when the tool is offered. It's billed
  at $10 / 1000 searches on top of token costs; each request is capped at
  `max_uses=5` in `claude_client.py`.

## Documentation

Full handoff docs are in `docs/` — start with `docs/README.md`. The most
relevant for code work: `docs/architecture.md` (design rationale) and
`docs/troubleshooting.md` (every error hit during the build, by symptom).
`docs/setup.md` covers Azure, local Python, and Teams packaging;
`docs/customization.md` covers prompt/skills/search; `docs/deployment.md`
covers moving off the local tunnel.
