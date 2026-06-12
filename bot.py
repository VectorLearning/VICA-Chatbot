"""Teams activity handler that responds when @mentioned in a channel."""
from __future__ import annotations

import logging
import re

from botbuilder.core import ActivityHandler, TurnContext
from botbuilder.schema import ChannelAccount, Mention

from claude_client import ClaudeClient
from graph_client import GraphClient

log = logging.getLogger(__name__)


class ClaudeTeamsBot(ActivityHandler):
    def __init__(
        self,
        bot_app_id: str,
        graph: GraphClient,
        claude: ClaudeClient,
        context_window_minutes: int,
        context_max_messages: int,
    ):
        self._bot_app_id = bot_app_id
        self._graph = graph
        self._claude = claude
        self._window_minutes = context_window_minutes
        self._max_messages = context_max_messages

    async def on_turn(self, turn_context: TurnContext):
        a = turn_context.activity
        log.info(
            "on_turn: type=%s name=%s from=%s",
            getattr(a, "type", None),
            getattr(a, "name", None),
            getattr(a.from_property, "name", None) if a.from_property else None,
        )
        await super().on_turn(turn_context)

    async def on_message_activity(self, turn_context: TurnContext):
        activity = turn_context.activity

        log.info("=== incoming message activity ===")
        log.info("text: %r", activity.text)
        log.info("entities: %r", activity.entities)
        log.info("channel_data: %r", activity.channel_data)
        log.info("conversation: %r", activity.conversation)
        log.info("recipient: %r", activity.recipient)
        log.info("bot_app_id configured: %s", self._bot_app_id)

        # Only react in channels (skip 1:1 / group chats for now).
        channel_data = activity.channel_data or {}
        team_info = channel_data.get("team") or {}
        channel_info = channel_data.get("channel") or {}
        team_id = team_info.get("id")
        channel_id = channel_info.get("id") or activity.conversation.id.split(";")[0]

        log.info("derived team_id=%s channel_id=%s", team_id, channel_id)

        if not team_id:
            log.info("no team_id -> replying with 'channels only' message")
            await turn_context.send_activity(
                "I only respond in Teams channels right now. Please @mention me in a channel."
            )
            return

        # Require an @mention of the bot.
        log.info("raw entities: %r", _get_entities(activity))
        mentioned = _bot_was_mentioned(activity, self._bot_app_id)
        log.info("bot_was_mentioned=%s", mentioned)
        if not mentioned:
            return

        question = _strip_mentions(activity).strip()
        log.info("stripped question: %r", question)
        if not question:
            await turn_context.send_activity(
                "Hi! Mention me with a question and I'll read recent channel messages for context."
            )
            return

        asker = (activity.from_property.name if activity.from_property else "Someone") or "Someone"

        try:
            recent = await self._graph.get_recent_channel_messages(
                team_id=team_id,
                channel_id=channel_id,
                window_minutes=self._window_minutes,
                max_messages=self._max_messages,
            )
        except Exception:
            log.exception("Failed to read channel history from Graph")
            await turn_context.send_activity(
                "I couldn't read the channel history. Check that the bot's app registration has "
                "ChannelMessage.Read.All (application) granted with admin consent."
            )
            return

        try:
            answer = await self._claude.reply(
                question=question,
                recent_messages=recent,
                asker_name=asker,
            )
        except Exception:
            log.exception("Claude call failed")
            await turn_context.send_activity("Claude call failed — check the server logs.")
            return

        await turn_context.send_activity(answer)


def _entity_as_dict(ent) -> dict:
    """Normalize a botbuilder Entity (or dict) into a flat dict.

    botbuilder.schema.Entity stores extra fields like `mentioned` in
    `.additional_properties`, not as direct attributes.
    """
    if isinstance(ent, dict):
        return ent
    if hasattr(ent, "serialize"):
        try:
            return ent.serialize()
        except Exception:
            pass
    d = {"type": getattr(ent, "type", None)}
    extras = getattr(ent, "additional_properties", None) or {}
    d.update(extras)
    return d


def _get_entities(activity):
    """Prefer raw entity dicts (stashed in app.py) since the SDK drops fields."""
    raw = getattr(activity, "raw_entities", None)
    if raw:
        return raw
    return [_entity_as_dict(e) for e in (activity.entities or [])]


def _bot_was_mentioned(activity, bot_app_id: str) -> bool:
    bot_app_id = (bot_app_id or "").lower()
    for ent in _get_entities(activity):
        if not isinstance(ent, dict):
            ent = _entity_as_dict(ent)
        if (ent.get("type") or "").lower() != "mention":
            continue
        mentioned = ent.get("mentioned") or {}
        if not isinstance(mentioned, dict):
            mentioned = getattr(mentioned, "__dict__", {}) or {}
        mentioned_id = str(mentioned.get("id") or "").lower()
        if bot_app_id and bot_app_id in mentioned_id:
            return True
    return False


_MENTION_TAG_RE = re.compile(r"<at[^>]*>.*?</at>", re.IGNORECASE | re.DOTALL)


def _strip_mentions(activity) -> str:
    text = activity.text or ""
    # Remove <at>...</at> tags Teams uses to denote mentions.
    return _MENTION_TAG_RE.sub("", text)
