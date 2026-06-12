# Troubleshooting

Every problem we hit during the initial build, with the fix. Skim by symptom.

## Installation

### `pip install -r requirements.txt` fails with aiohttp resolution conflict

> `botbuilder-integration-aiohttp 4.16.2 depends on aiohttp==3.10.5`

Make sure `requirements.txt` pins `aiohttp==3.10.5` (not 3.9.5). Bot Framework 4.16.2 requires exactly 3.10.5.

### Build failures on Python 3.13

3.13 is too new for some Bot Framework wheels (C extensions for aiohttp /
multidict) at the time of writing. Use Python 3.12:

```bash
deactivate
rm -rf .venv
brew install python@3.12   # if not present
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Azure setup

### Admin asks "Web App or Single Page Application?"

**Web App.** SPAs can't hold a client secret. The bot uses client-credentials flow, which requires a secret.

### "Type of App" options don't include Multi Tenant, or it's grayed out

Correct. Multi-tenant bot creation was deprecated July 31, 2025. Use **Single Tenant**. Set `MICROSOFT_APP_TYPE=SingleTenant` and fill in `MICROSOFT_APP_TENANT_ID`.

### "Grant admin consent" button is grayed out on API permissions

Current user isn't an Entra admin. The admin has to click it. Forward them the request — see the README's "What IT needs to do" section.

### Can't find "Messaging endpoint" anywhere

It lives on the **Azure Bot resource**, not the Entra app registration. Two different objects. Path: Azure portal → Azure Bot resource → **Settings → Configuration → Messaging endpoint**.

If you don't have an Azure Bot resource at all, see [setup.md](setup.md#14-create-the-azure-bot-resource).

## Teams app upload

### "Manifest parsing error message unavailable"

Almost always caused by:

1. **Placeholder `REPLACE_WITH_BOT_APP_ID` left in the manifest.** The top-level `"id"` and `"bots[0].botId"` must both be valid GUIDs. They can be the same GUID, or different. They CANNOT be the literal string `REPLACE_WITH_BOT_APP_ID`.
2. **Authorization block rejected by tenant policy.** Some tenants block sideloaded apps from declaring RSC permissions. Remove the `"authorization"` block, retry. If it uploads without authorization, the tenant blocks RSC for custom apps and the admin needs to allowlist your app or grant the RSC permissions out-of-band.

### "Bad Request" with no detail when uploading a new app

A custom app with the same top-level `"id"` GUID already exists in the tenant. Two fixes:

- **Delete the existing one** from Teams → **Apps → Manage your apps**, then re-upload.
- **Give the new manifest a fresh `id` GUID.** `python3 -c "import uuid; print(uuid.uuid4())"`. Replace just the top-level `id`, not `botId`.

### "Upload a custom app" option doesn't appear

Tenant blocks sideloading. Admin must enable in **Teams Admin Center → Teams apps → Setup policies → Upload custom apps**, OR upload the zip for you via **Teams Admin Center → Manage apps**.

### Cannot update an installed custom app in place

There's no reliable "Update" path through the Teams UI. Uninstall (remove from team + remove from "Manage your apps"), then upload as new. Or change the manifest `id` to a new GUID and upload as a separate app.

## Runtime

### Bot doesn't reply, terminal shows POST /api/messages 201 but no Claude call

Most likely cause: **mention detection is failing**. The Bot Framework SDK's `Entity` model in version 4.16.2 doesn't deserialize the `mentioned.id` field — it ends up dropped, and our default mention check returns False.

Fix is already in this repo: `app.py` stashes the raw `entities` list from the request body on the activity (`activity.raw_entities`), and `bot.py`'s `_bot_was_mentioned` reads from that. If you ever refactor and remove this workaround, mention detection will silently fail.

Diagnostic: enable the existing `log.info` lines in `bot.py` to see the raw entities and what `_bot_was_mentioned` returned.

### Bot replies with "I couldn't read the channel history"

`graph_client.get_recent_channel_messages` threw. Two causes:

1. **`ChannelMessage.Read.All` not granted with admin consent** in Entra. Status column on the API permissions blade must be green.
2. **RSC `ChannelMessage.Read.Group` not approved** by a team owner. If the manifest declares it, a team owner sees a consent prompt the first time the app is added to a team — if they declined, remove and re-add the app.

Channel messages are "protected APIs", so tenant-wide `ChannelMessage.Read.All` alone may still 403 — RSC is the practical workaround. Full explanation: [setup.md → Reading channel messages: RSC](setup.md#reading-channel-messages-rsc).

### Bot Web Chat test in Azure hangs

Your local `python app.py` isn't being reached. Check:

1. `python app.py` is running and showing "Running on http://0.0.0.0:3978".
2. The tunnel is running and the URL still resolves: `curl https://<tunnel>/healthz` returns `ok`.
3. Azure Bot → **Configuration → Messaging endpoint** matches the current tunnel URL + `/api/messages`.
4. The `MICROSOFT_APP_ID`, `MICROSOFT_APP_PASSWORD`, and tenant ID in `.env` match what the Azure Bot is using.

### Anthropic API returns 403 / "web search not available"

The org admin must enable web search in https://console.anthropic.com → Settings → Privacy. Until they do, set `ENABLE_WEB_SEARCH=false` to work around.

### Anthropic API returns 401

`ANTHROPIC_API_KEY` is wrong, expired, or for a different org than the one with web search enabled. Generate a fresh key in console.anthropic.com.

### Anthropic API returns "model not found"

Model name in `CLAUDE_MODEL` is wrong. Default working values:
- `claude-sonnet-4-6` (recommended default)
- `claude-opus-4-6` (higher quality, more expensive)
- `claude-haiku-4-5-20251001` (cheaper, faster)

### Tunnel URL changes between runs

`devtunnel host` keeps the same URL across runs **for the same logged-in user**. If you log out / log in or use a different machine, you get a new tunnel ID. Update the Azure Bot messaging endpoint accordingly.

`ngrok` always gives a new URL on the free plan. Either pay for a static URL or update Azure on every run.

### Bot replies but doesn't see the most recent messages in the channel

Two possibilities:

1. `CONTEXT_WINDOW_MINUTES` or `CONTEXT_MAX_MESSAGES` is too small. Bump in `.env`.
2. The Graph API has a ~5–30 second lag between a message being sent and being readable. The bot's reply to a @mention captures messages up to about a minute earlier reliably; replies to messages sent in the past few seconds may not see them.

### Bot replies with a generic error message after invoking a skill

Check the Python terminal for the exception. Common: skill body contains characters that confuse the system prompt (very rare). The skill body itself is just text — almost any content is fine.

## Configuration mistakes

### "Missing required env var: MICROSOFT_APP_ID"

`.env` not loaded or value blank. Make sure you ran `cp .env.example .env` and filled in every required value. The `_require` function in `config.py` enumerates which variables are mandatory.

### Bot replies "I only respond in Teams channels right now."

You're testing via Azure's "Test in Web Chat" or in a 1:1 chat. This message is expected — the bot is hardcoded to only respond when there's a team/channel context. To remove this restriction, edit `bot.py`'s `on_message_activity` and adjust the early return.

### Skill not being triggered when you expect

- Check the startup log: `Loaded N skill(s): name1, name2, ...`. If your skill isn't in that list, the frontmatter didn't parse — check the `---` delimiters.
- Check the skill description. Phrase as "Use when..." with specific trigger words. Vague descriptions cause Claude to under-trigger.
- Watch the runtime log. When Claude invokes a skill you'll see `INFO:claude_client:Loading skill 'name'`. If you don't see that line, Claude didn't decide to invoke it.

## Logs to add when stuck

If something is wrong and the existing logs don't show it, the most useful additions:

In `bot.py`:
```python
log.info("activity dict: %r", activity.serialize() if hasattr(activity, "serialize") else vars(activity))
```

In `graph_client.py`, after the Graph response:
```python
log.info("graph response: %r", data)
```

In `claude_client.py`, before the `messages.create` call:
```python
log.info("sending to Claude: messages=%d tools=%s", len(messages), [t.get("name") for t in self._tools])
```

Remove or downgrade to DEBUG before deploying.
