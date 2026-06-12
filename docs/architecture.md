# Architecture

## What the bot does

In one sentence: when a user types `@VICA <question>` in a Teams channel, the bot reads the previous hour of channel messages, sends them plus the question to Claude, and posts Claude's reply back to the channel.

## Request flow

```
1. User in Teams channel types: "@VICA what did we just discuss?"
        ▼
2. Teams routes the message to Azure Bot Service (the bot's
   "Messaging endpoint" registered in Azure points at our public URL).
        ▼
3. Azure Bot Service POSTs the activity to our /api/messages
   endpoint over the devtunnel (in local dev).
        ▼
4. app.py validates the JWT in Authorization header against the bot's
   App ID / Tenant via the Bot Framework SDK, hands the activity off
   to bot.py.
        ▼
5. bot.py checks:
   - Is this a channel message? (needs team_id in channelData)
   - Was the bot @mentioned? (needs to find the bot's App ID inside
     a "mention" entity)
   - If yes, strips the <at>...</at> tag from the message text.
        ▼
6. graph_client.py uses MSAL client-credentials to get an app-only
   Graph token, then GETs the last hour of messages from the channel
   (up to 20).
        ▼
7. claude_client.py composes a prompt (recent messages + question)
   and calls the Anthropic Messages API with two tools available:
     - use_skill   (loads a local skill's body on demand)
     - web_search  (server-side, runs inside Anthropic)
        ▼
8. If Claude calls use_skill, claude_client returns the skill's body
   as a tool_result and the loop continues. web_search resolves
   server-side, so no client work needed.
        ▼
9. When Claude returns "end_turn", we extract the text and POST a
   reply activity back via Bot Framework, which Teams renders in
   the channel.
```

## Module map

```
+----------------+        +--------------+
|   app.py       | ──────►│   bot.py     │
|  aiohttp +     │ activity│  ActivityHandler
|  Bot Framework │        │  - mention detect
|  CloudAdapter  │        │  - context fetch
+----------------+        │  - Claude call
                          │  - reply
                          +───┬──────┬───┘
                              │      │
                  ┌───────────┘      └─────────────┐
                  ▼                                 ▼
        +─────────────────+              +───────────────────+
        │ graph_client.py │              │ claude_client.py  │
        │  MSAL client    │              │  Anthropic SDK    │
        │  Graph GET msgs │              │  + tool-use loop  │
        +─────────────────+              +───────────────────+
                                                   │
                                              ┌────┴────┐
                                              ▼         ▼
                                    +───────────────+  +────────────────+
                                    │ skill_loader  │  │ web_search tool│
                                    │  reads .md    │  │ (server-side,  │
                                    │  files        │  │  Anthropic)    │
                                    +───────────────+  +────────────────+
```

## Why these design choices

**Why the Anthropic API, not Claude Max.** Claude Max is the consumer subscription and has no supported API for server-based integrations. Teams bots need a stable API the webhook handler can call 24/7. We use a key from console.anthropic.com (billed separately).

**Why Bot Framework instead of calling Teams directly.** Teams doesn't expose a direct API for bots. Microsoft requires bots to go through the Bot Framework, which handles auth, channel adapters (Teams, Slack, web chat, etc.), and message formatting.

**Why client-credentials Graph flow.** A bot acts as itself, not as a user. App-only auth via MSAL with a client secret is the standard pattern. The bot only needs read access to channel messages.

**Why a tool-use loop for skills.** Listing skill descriptions in the system prompt lets Claude decide when a skill is relevant; loading the body only on demand keeps unrelated questions cheap. Web search is a server tool (Anthropic runs it for us), so it doesn't need loop handling — it appears as `pause_turn` and resolves within the same API call.

## Auth model

```
Teams ──signed activity──► Bot Framework ──JWT──► our /api/messages
                                                          │
                                                          ▼
                                          CloudAdapter verifies JWT
                                          against APP_ID + tenant
                                                          │
                                                          ▼
                                                        bot.py
                                                          │
                              ┌───────────────────────────┤
                              ▼                            ▼
              MSAL client_credentials              Anthropic API key
              ─► access_token (Graph)              (Bearer header)
              ─► GET /teams/.../messages
```

Two separate identities are involved:
1. **The bot's identity** (`MICROSOFT_APP_ID` + secret) — used by Bot Framework to verify incoming activities and to sign outgoing replies.
2. **The Graph identity** (`GRAPH_CLIENT_ID` + secret) — used by MSAL to get a Graph access token.

In our setup they're the same Entra app registration, but they could be split if you wanted separate identities (the `.env` allows it).

## Tech stack

- Python 3.12 (3.13 may have wheel build issues — see troubleshooting)
- aiohttp 3.10.5 (pinned because botbuilder-integration-aiohttp 4.16.2 requires this version)
- botbuilder-core / -schema / -integration-aiohttp 4.16.2
- anthropic SDK >= 0.62.0
- MSAL for Graph auth
- httpx for Graph HTTP calls
- python-dotenv for `.env` loading
