# Customizing the bot

The three things you'll change most often.

## 1. System prompt

Edit `system_prompt.md` at the repo root. It's loaded at startup, so restart `python app.py` to pick up changes.

The file is read verbatim and passed to the Anthropic API as the `system` parameter. Skills' descriptions are appended automatically — don't paste them yourself.

If the file is missing or empty, the bot falls back to a built-in default in `claude_client.py` (`DEFAULT_SYSTEM_PROMPT`).

## 2. Skills

Drop a new `.md` file into `skills/` with YAML-ish frontmatter:

```markdown
---
name: pricing
description: Vector Solutions product pricing. Use when asked about list prices, quotes, or what something costs.
---

# Pricing reference

EHS Lite — $5 per user per year
EHS Pro  — $9 per user per year
LMS Lite — $4 per user per year
...

When citing a price, always mention this is "list price — actual quote may vary".
```

How it works at runtime:

1. At startup, `skill_loader.py` scans `skills/` and parses every `.md` file. The file's `name` and `description` from the frontmatter define the skill.
2. `claude_client.py` appends a directory of skill names and descriptions to the system prompt.
3. Claude is told about a `use_skill` tool with `skill_name` as the only parameter. When Claude decides a skill is relevant, it invokes that tool.
4. The Python side responds with the skill's full body as a tool result. Claude reads it and continues the turn.

This means **only the skill description costs tokens for unrelated questions**. Long skill bodies are loaded on demand.

### Skill file format details

- Frontmatter is optional but recommended. Without it, the filename becomes the skill name and the description shows as "(no description provided)".
- `name` is sanitized to a safe identifier (`[A-Za-z0-9_]`).
- The body below the frontmatter is the full skill content — markdown, plain text, whatever Claude can read.
- A folder layout (`skills/pricing/SKILL.md`) is also supported if you want a folder of related files; only `SKILL.md` is loaded by the parser, but you can reference sibling files in the prompt.

### Tips for good skills

- **The description is everything for triggering.** Phrase it as "Use when..." with specific keywords the user might say. Vague descriptions like "Info about pricing" cause Claude to either over- or under-trigger.
- **Keep skill bodies focused.** One topic per file. If a skill grows past ~500 lines, split it.
- **Don't duplicate the system prompt.** Skills should add domain knowledge, not redefine the bot's persona or rules.

Restart `python app.py` after adding or editing skills. The startup log shows `Loaded N skill(s): name1, name2, ...` — if your new skill isn't listed there, the frontmatter didn't parse.

## 3. Web search

Enabled by default. Claude decides when to call it — typically for current events, prices, news, or anything time-sensitive. The tool is server-side (Anthropic runs the search), so the bot has no search-quota logic to maintain.

To disable: set `ENABLE_WEB_SEARCH=false` in `.env` and restart.

### Gotcha: must be enabled in Claude Console

Your org admin must enable web search in https://console.anthropic.com → Settings → Privacy. Without it, the API returns an error when the tool is requested. If you see "web_search not available" or similar in the logs, that's why.

### Pricing

$10 per 1000 web searches (in addition to standard token costs). The bot caps each request at `max_uses=5` (set in `claude_client.py`) so a single @mention can cost at most 5 searches. Adjust if needed.

## Less-common knobs

In `.env`:

- `CONTEXT_WINDOW_MINUTES` — how far back to look in the channel for context. Default 60.
- `CONTEXT_MAX_MESSAGES` — cap on messages included regardless of window. Default 20.
- `CLAUDE_MODEL` — Anthropic model name. Default `claude-sonnet-4-6`. Use `claude-opus-4-6` for higher quality at higher cost, or a haiku for cheaper.
- `PORT` — local port the aiohttp server listens on. Default 3978. Match this with your tunnel port.

In `claude_client.py`:

- `max_tokens` — output token cap, default 2048.
- `max_tool_iterations` — agentic loop safety cap, default 6. Increase if Claude needs more than 6 rounds of tool use (rare for this use case).
