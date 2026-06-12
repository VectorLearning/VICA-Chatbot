"""Loads settings from environment / .env file."""
import os
from dataclasses import dataclass
from dotenv import load_dotenv

load_dotenv()


def _require(name: str) -> str:
    val = os.environ.get(name, "").strip()
    if not val:
        raise RuntimeError(f"Missing required env var: {name}")
    return val


@dataclass
class Config:
    # Bot Framework
    app_id: str
    app_password: str
    app_type: str
    app_tenant_id: str

    # Graph
    graph_tenant_id: str
    graph_client_id: str
    graph_client_secret: str

    # Anthropic
    anthropic_api_key: str
    claude_model: str
    enable_web_search: bool
    system_prompt_path: str
    skills_dir: str

    # Behavior
    context_window_minutes: int
    context_max_messages: int

    # Server
    port: int


def load_config() -> Config:
    return Config(
        app_id=_require("MICROSOFT_APP_ID"),
        app_password=_require("MICROSOFT_APP_PASSWORD"),
        app_type=os.environ.get("MICROSOFT_APP_TYPE", "MultiTenant"),
        app_tenant_id=os.environ.get("MICROSOFT_APP_TENANT_ID", ""),
        graph_tenant_id=_require("GRAPH_TENANT_ID"),
        graph_client_id=_require("GRAPH_CLIENT_ID"),
        graph_client_secret=_require("GRAPH_CLIENT_SECRET"),
        anthropic_api_key=_require("ANTHROPIC_API_KEY"),
        claude_model=os.environ.get("CLAUDE_MODEL", "claude-sonnet-4-6"),
        enable_web_search=os.environ.get("ENABLE_WEB_SEARCH", "true").strip().lower()
        not in {"0", "false", "no", "off"},
        system_prompt_path=os.environ.get("SYSTEM_PROMPT_PATH", "system_prompt.md"),
        skills_dir=os.environ.get("SKILLS_DIR", "skills"),
        context_window_minutes=int(os.environ.get("CONTEXT_WINDOW_MINUTES", "60")),
        context_max_messages=int(os.environ.get("CONTEXT_MAX_MESSAGES", "20")),
        port=int(os.environ.get("PORT", "3978")),
    )
