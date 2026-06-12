"""aiohttp entry point for the Teams bot."""
from __future__ import annotations

import logging
import sys

from aiohttp import web
from botbuilder.core import TurnContext
from botbuilder.core.integration import aiohttp_error_middleware
from botbuilder.integration.aiohttp import CloudAdapter, ConfigurationBotFrameworkAuthentication
from botbuilder.schema import Activity

from bot import ClaudeTeamsBot
from claude_client import ClaudeClient
from config import load_config
from graph_client import GraphClient

logging.basicConfig(level=logging.INFO, stream=sys.stdout)
log = logging.getLogger("app")


class _BotSettings:
    """Adapter for ConfigurationBotFrameworkAuthentication (expects attribute lookups)."""

    def __init__(self, cfg):
        self.APP_ID = cfg.app_id
        self.APP_PASSWORD = cfg.app_password
        self.APP_TYPE = cfg.app_type
        self.APP_TENANTID = cfg.app_tenant_id


def build_app() -> web.Application:
    cfg = load_config()

    auth = ConfigurationBotFrameworkAuthentication(_BotSettings(cfg))
    adapter = CloudAdapter(auth)

    async def on_error(context: TurnContext, error: Exception):
        log.exception("Bot adapter error: %s", error)
        try:
            await context.send_activity("Something went wrong handling your message.")
        except Exception:
            pass

    adapter.on_turn_error = on_error

    graph = GraphClient(
        tenant_id=cfg.graph_tenant_id,
        client_id=cfg.graph_client_id,
        client_secret=cfg.graph_client_secret,
    )
    claude = ClaudeClient(
        api_key=cfg.anthropic_api_key,
        model=cfg.claude_model,
        system_prompt_path=cfg.system_prompt_path,
        skills_dir=cfg.skills_dir,
        enable_web_search=cfg.enable_web_search,
    )
    bot = ClaudeTeamsBot(
        bot_app_id=cfg.app_id,
        graph=graph,
        claude=claude,
        context_window_minutes=cfg.context_window_minutes,
        context_max_messages=cfg.context_max_messages,
    )

    async def messages(req: web.Request) -> web.Response:
        body = await req.json()
        activity = Activity().deserialize(body)
        # The botbuilder SDK drops unknown fields on Entity objects (mention.id,
        # mention.name), so preserve the raw entity dicts for our handler.
        try:
            setattr(activity, "raw_entities", body.get("entities") or [])
        except Exception:
            pass
        auth_header = req.headers.get("Authorization", "")
        response = await adapter.process_activity(auth_header, activity, bot.on_turn)
        if response:
            return web.json_response(data=response.body, status=response.status)
        return web.Response(status=201)

    async def healthz(_req: web.Request) -> web.Response:
        return web.Response(text="ok")

    app = web.Application(middlewares=[aiohttp_error_middleware])
    app.router.add_post("/api/messages", messages)
    app.router.add_get("/healthz", healthz)
    app["port"] = cfg.port
    return app


def main():
    app = build_app()
    web.run_app(app, host="0.0.0.0", port=app["port"])


if __name__ == "__main__":
    main()
