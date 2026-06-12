# Setup

End-to-end setup, in the order you should do it:

1. [Azure and Microsoft](#1-azure-and-microsoft) — Entra app, Graph permission, Azure Bot. **Requires an Entra admin.**
2. [Local Python](#2-local-python) — environment, `.env`, tunnel, running the bot.
3. [Teams app package](#3-teams-app-package) — manifest, RSC, sideloading.

Nothing on the Python or Teams side works until the Azure side is done.

Two cross-cutting concepts are defined once and referenced throughout:

- **Protected APIs / RSC** — see [Reading channel messages: RSC](#reading-channel-messages-rsc).
- **The two manifest GUIDs** — see [The two GUIDs](#the-two-guids).

---

## 1. Azure and Microsoft

You will create one Entra app registration (it serves as both the bot identity
and the Graph identity), one Azure Bot resource that wraps it, and enable the
Teams channel on that bot.

### 1.1 Create the Entra app registration

1. Azure portal → **Microsoft Entra ID** → **App registrations** → **New registration**.
2. **Name**: e.g. "VICA Teams Bot".
3. **Supported account types**: **Single tenant**. (Multi-tenant bot creation was
   deprecated July 31, 2025 — new ones can't be created.)
4. **Redirect URI**: leave blank — the bot uses client-credentials flow, no
   browser redirect. If asked "Web App or SPA?", choose **Web App** (an SPA
   can't hold a client secret).
5. **Register.**

From the Overview page, copy and save:

- **Application (client) ID** → `MICROSOFT_APP_ID` and `GRAPH_CLIENT_ID`.
- **Directory (tenant) ID** → `MICROSOFT_APP_TENANT_ID` and `GRAPH_TENANT_ID`.

### 1.2 Create a client secret

Same app registration → **Certificates & secrets** → **Client secrets** →
**New client secret**. Any description; 24-month expiry is reasonable. **Copy the
`Value` immediately — it's shown only once.** If you miss it, delete and create
another.

That value goes into both `MICROSOFT_APP_PASSWORD` and `GRAPH_CLIENT_SECRET`.

### 1.3 Grant the Graph permission

Same app registration → **API permissions** → **Add a permission** →
**Microsoft Graph** → **Application permissions** (not Delegated) → add
**`ChannelMessage.Read.All`** → **Grant admin consent for \<tenant\>**. The Status
column must turn green. If the consent button is grayed out, the current user
isn't an Entra admin and someone who is must click it.

> See [Reading channel messages: RSC](#reading-channel-messages-rsc) — this
> tenant-level grant alone is often not sufficient.

### 1.4 Create the Azure Bot resource

1. Azure portal → **Create a resource** → search **Azure Bot** → **Create**.
2. **Bot handle**: unique name (e.g. `vica-teams-bot`).
3. **Pricing tier**: **Free (F0)** is fine.
4. **Type of App**: **Single Tenant** (must match step 1.1).
5. **Creation type**: **Use existing app registration**.
6. **App ID**: your `MICROSOFT_APP_ID`. **App tenant ID**: your tenant ID.
7. **Review + create** → **Create**.

### 1.5 Enable the Teams channel

Open the Azure Bot resource → **Settings → Channels** → click the
**Microsoft Teams** card → accept terms → **Apply**.

The **Messaging endpoint** (also under Settings → Configuration) is set later,
in [step 2.4](#24-point-azure-bot-at-the-tunnel), once you have a tunnel URL.

### Sanity check

After this section you should have an Entra app with `ChannelMessage.Read.All`
admin-consented, an Azure Bot referencing it with the Teams channel enabled, and
these values in hand:

- `MICROSOFT_APP_ID` (= `GRAPH_CLIENT_ID`)
- `MICROSOFT_APP_PASSWORD` (= `GRAPH_CLIENT_SECRET`)
- `MICROSOFT_APP_TENANT_ID` (= `GRAPH_TENANT_ID`)
- `MICROSOFT_APP_TYPE=SingleTenant`
- the Azure Bot resource name

---

## 2. Local Python

Prerequisites: macOS or Linux (Windows works, commands differ slightly), an
Anthropic API key from https://console.anthropic.com, and section 1 complete.

> **Python 3.12, not 3.13.** Some Bot Framework / aiohttp wheels fail to build on
> 3.13. See [troubleshooting.md](troubleshooting.md#build-failures-on-python-313).

### 2.1 Create the environment

```bash
cd "/path/to/Claude Chatbot"
python3.12 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

### 2.2 Fill in `.env`

```bash
cp .env.example .env
```

Fill in every value. Mapping from the Azure side:

| `.env` variable | Source |
|---|---|
| `MICROSOFT_APP_ID` | Entra app → Overview → Application (client) ID |
| `MICROSOFT_APP_PASSWORD` | Entra app → Certificates & secrets → client secret `Value` |
| `MICROSOFT_APP_TYPE` | `SingleTenant` |
| `MICROSOFT_APP_TENANT_ID` | Entra app → Overview → Directory (tenant) ID |
| `GRAPH_TENANT_ID` | same as `MICROSOFT_APP_TENANT_ID` |
| `GRAPH_CLIENT_ID` | same as `MICROSOFT_APP_ID` |
| `GRAPH_CLIENT_SECRET` | same as `MICROSOFT_APP_PASSWORD` |
| `ANTHROPIC_API_KEY` | console.anthropic.com → API keys |
| `CLAUDE_MODEL` | default `claude-sonnet-4-6` |
| `ENABLE_WEB_SEARCH` | `true` (must also be enabled org-side — see [customization.md](customization.md#3-web-search)) |
| `CONTEXT_WINDOW_MINUTES` | default `60` |
| `CONTEXT_MAX_MESSAGES` | default `20` |

The bot and Graph identities are split into separate variables on purpose; in
this setup they're the same app registration, but `.env` lets you split them.

### 2.3 Start a tunnel

Microsoft devtunnel is the smoothest for Teams (free, runs on macOS):

```bash
# one-time
brew install --cask devtunnel
devtunnel user login            # sign in with your Microsoft work account

# each run
devtunnel host -p 3978 --allow-anonymous
```

It prints a URL like `https://8pbs1phv-3978.use.devtunnels.ms`. **Leave this
terminal running** and copy the URL. (`ngrok http 3978` also works but rotates
the URL on the free plan.)

### 2.4 Point Azure Bot at the tunnel

Azure portal → your Azure Bot resource → **Settings → Configuration** →
**Messaging endpoint** = `https://<your-tunnel-url>/api/messages` → **Apply**.

You only need to redo this when the tunnel URL actually changes (devtunnel keeps
the same URL across runs for the same logged-in user).

### 2.5 Run the bot

```bash
cd "/path/to/Claude Chatbot"
source .venv/bin/activate
python app.py
```

Expected startup log:

```
======== Running on http://0.0.0.0:3978 ========
INFO:claude_client:Loaded 1 skill(s): vector_overview
INFO:claude_client:Tools enabled: ['use_skill', 'web_search']
```

### 2.6 Smoke test

```bash
curl https://<your-tunnel-url>/healthz      # -> ok
```

Then Azure Bot resource → **Test in Web Chat** → type "hi". The bot should reply
that it only responds in channels — that's the **expected** message and confirms
auth + routing are wired up. Your `python app.py` terminal logs a
`POST /api/messages`. (If Web Chat hangs, see
[troubleshooting.md](troubleshooting.md#bot-web-chat-test-in-azure-hangs).)

### Day-to-day workflow

1. Terminal 1: `devtunnel host -p 3978 --allow-anonymous`
2. Terminal 2: `source .venv/bin/activate && python app.py`
3. Edit code / `system_prompt.md` / `skills/*.md` → restart `python app.py`.

---

## 3. Teams app package

Even with Azure set up and the bot running, the bot must be wrapped in a Teams
app package and uploaded to Teams.

### What a Teams app is

A zip containing three files **at the root** (no enclosing folder):

1. `manifest.json` — name, icons, the bot's App ID, RSC permissions.
2. `color.png` — 192×192 full-color icon.
3. `outline.png` — 32×32 outline icon (white shape on transparent).

### The two GUIDs

`teams_app/manifest.json` has two GUID fields. Don't confuse them:

| Field | Identifies |
|---|---|
| top-level `"id"` | The **Teams app** in your tenant's catalog. Any valid GUID. |
| `bots[0].botId` | The **bot's Application (client) ID** (`MICROSOFT_APP_ID`). |

They can be the same GUID and often are, but they mean different things. Giving
a new manifest a fresh top-level `id` is the cleanest way to upload an updated
app while the old one is still installed (avoids the "duplicate ID" rejection).

### The manifest in this repo

`teams_app/manifest.json` is already filled in. Key fields:

```json
{
  "manifestVersion": "1.16",
  "id": "<Teams app GUID>",
  "bots": [{ "botId": "<your bot's App ID>", "scopes": ["team", "groupChat"] }],
  "name": { "short": "VICA", "full": "VICA" }
}
```

On handoff, the next dev only needs to:

1. Replace `bots[0].botId` with their bot's `MICROSOFT_APP_ID`.
2. Optionally generate a fresh top-level `id`:
   `python3 -c "import uuid; print(uuid.uuid4())"`.
3. Replace the icons (next section) if desired.

### Reading channel messages: RSC

Tenant-level `ChannelMessage.Read.All` ([step 1.3](#13-grant-the-graph-permission))
is no longer sufficient on its own for many tenants — Microsoft moved channel
messages into **protected APIs**. The practical path is **resource-specific
consent (RSC)**, declared in the manifest and approved per-team at install time:

```json
"authorization": {
  "permissions": {
    "resourceSpecific": [
      { "name": "ChannelMessage.Read.Group", "type": "Application" }
    ]
  }
}
```

When a team owner installs the app, Teams prompts them to approve this for that
specific team. After approval the bot can read that team's channel messages with
its Graph token. Without RSC, Graph calls may return 403 even with tenant-level
admin consent.

**Caveat:** some tenants block RSC for sideloaded custom apps via Teams admin
policy. If upload fails with "Manifest parsing error", try uploading without the
`authorization` block to isolate the cause — see
[troubleshooting.md](troubleshooting.md#manifest-parsing-error-message-unavailable).

### Generating placeholder icons

Any 192×192 and 32×32 PNGs work for development. With ImageMagick:

```bash
cd teams_app
convert -size 192x192 xc:'#D97706' color.png
convert -size 32x32 xc:none -fill white -gravity center -draw 'circle 16,16 16,4' outline.png
```

### Building the zip

```bash
cd "/path/to/Claude Chatbot/teams_app"
rm -f claude-teams-bot.zip
zip claude-teams-bot.zip manifest.json color.png outline.png
unzip -l claude-teams-bot.zip   # exactly three entries, no path prefix
```

### Sideloading

1. Teams → **Apps** → **Manage your apps** → **Upload an app** →
   **Upload a custom app** → pick the zip.
2. If "Upload a custom app" is missing, the tenant blocks sideloading. The Teams
   admin enables it in **Teams Admin Center → Teams apps → Setup policies**, or
   uploads the zip for you via **Manage apps**.

### Adding the bot to a channel

Open the team → **⋯ → Manage team → Apps → More apps** → find the bot →
**Add**. If RSC is declared, a team owner sees the consent prompt now.

### Updating an installed app

There's no reliable in-place "Update" through the Teams UI. Either:

- **Change the manifest `id`** to a fresh GUID, rezip, upload as a new app, then
  remove the old one; or
- **Fully uninstall first**: remove from **Manage team → Apps**, then from
  **Manage your apps**, then upload the new zip.

In-place updates that change permissions (e.g. adding RSC after the fact) often
fail silently — uninstall + reinstall is the reliable path.

### Test in Teams

In a channel where the bot has been added:

```
@VICA what did we just discuss?
```

The `python app.py` terminal logs the incoming activity, the Graph call, and the
Claude response; the reply appears in the channel within a few seconds.
