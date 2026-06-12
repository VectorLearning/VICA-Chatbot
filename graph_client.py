"""Microsoft Graph client for reading Teams channel messages.

Uses client-credentials (app-only) flow. Requires the app registration to have
the application permission ChannelMessage.Read.All granted with admin consent.
"""
from __future__ import annotations

import re
import time
from datetime import datetime, timedelta, timezone
from typing import List, Optional

import httpx
import msal

GRAPH_BASE = "https://graph.microsoft.com/v1.0"


class GraphClient:
    def __init__(self, tenant_id: str, client_id: str, client_secret: str):
        self._app = msal.ConfidentialClientApplication(
            client_id=client_id,
            client_credential=client_secret,
            authority=f"https://login.microsoftonline.com/{tenant_id}",
        )
        self._token: Optional[str] = None
        self._token_expires_at: float = 0.0

    def _get_token(self) -> str:
        # Cache token for its lifetime.
        if self._token and time.time() < self._token_expires_at - 60:
            return self._token
        result = self._app.acquire_token_for_client(
            scopes=["https://graph.microsoft.com/.default"]
        )
        if "access_token" not in result:
            raise RuntimeError(
                f"Failed to get Graph token: {result.get('error_description') or result}"
            )
        self._token = result["access_token"]
        self._token_expires_at = time.time() + int(result.get("expires_in", 3600))
        return self._token

    async def _get(self, client: httpx.AsyncClient, url: str) -> dict:
        resp = await client.get(
            url,
            headers={"Authorization": f"Bearer {self._get_token()}"},
            timeout=30.0,
        )
        resp.raise_for_status()
        return resp.json()

    async def get_recent_channel_messages(
        self,
        team_id: str,
        channel_id: str,
        window_minutes: int,
        max_messages: int,
    ) -> List[dict]:
        """Returns most-recent-first list of message dicts within the window.

        Each message dict has keys: from_name, text, created_at (ISO).
        """
        url = (
            f"{GRAPH_BASE}/teams/{team_id}/channels/{channel_id}/messages"
            f"?$top={min(max_messages, 50)}"
        )
        cutoff = datetime.now(timezone.utc) - timedelta(minutes=window_minutes)

        async with httpx.AsyncClient() as client:
            data = await self._get(client, url)

        out: List[dict] = []
        for m in data.get("value", []):
            created = m.get("createdDateTime")
            if not created:
                continue
            try:
                ts = datetime.fromisoformat(created.replace("Z", "+00:00"))
            except ValueError:
                continue
            if ts < cutoff:
                continue
            text = _extract_plain_text(m)
            if not text:
                continue
            sender = (
                ((m.get("from") or {}).get("user") or {}).get("displayName")
                or "Unknown"
            )
            out.append({"from_name": sender, "text": text, "created_at": created})
            if len(out) >= max_messages:
                break
        return out


_TAG_RE = re.compile(r"<[^>]+>")


def _extract_plain_text(message: dict) -> str:
    body = message.get("body") or {}
    content = body.get("content") or ""
    if body.get("contentType") == "html":
        content = _TAG_RE.sub("", content)
    return content.strip()
