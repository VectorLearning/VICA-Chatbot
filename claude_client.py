"""Anthropic API wrapper with local skills + web search.

Capabilities:
- Loads a system prompt from a file (editable without touching code).
- Loads local skills from a directory (each .md file becomes a callable skill).
- Exposes Anthropic's server-side web_search tool.
- Runs an agentic loop so Claude can call use_skill / web_search multiple times
  before producing a final answer.
"""
from __future__ import annotations

import logging
import os
from typing import Dict, List, Optional

from anthropic import AsyncAnthropic

from skill_loader import Skill, load_skills

log = logging.getLogger(__name__)

DEFAULT_SYSTEM_PROMPT = (
    "You are a helpful assistant embedded in a Microsoft Teams channel. "
    "You will be shown recent messages from the channel for context, followed "
    "by the user's question. Respond concisely in plain text suitable for a "
    "Teams message. Do not invent message authors or content."
)


def _load_system_prompt(path: Optional[str]) -> str:
    if path and os.path.isfile(path):
        try:
            with open(path, encoding="utf-8") as f:
                text = f.read().strip()
            if text:
                return text
        except OSError:
            pass
    return DEFAULT_SYSTEM_PROMPT


class ClaudeClient:
    def __init__(
        self,
        api_key: str,
        model: str,
        system_prompt_path: Optional[str] = "system_prompt.md",
        skills_dir: Optional[str] = "skills",
        enable_web_search: bool = True,
        max_tool_iterations: int = 6,
        max_tokens: int = 2048,
    ):
        self._client = AsyncAnthropic(api_key=api_key)
        self._model = model
        self._max_iters = max_tool_iterations
        self._max_tokens = max_tokens

        self._skills: Dict[str, Skill] = {
            s.name: s for s in load_skills(skills_dir or "")
        }
        if self._skills:
            log.info(
                "Loaded %d skill(s): %s",
                len(self._skills),
                ", ".join(self._skills.keys()),
            )
        else:
            log.info("No skills loaded (skills_dir=%s)", skills_dir)

        base_prompt = _load_system_prompt(system_prompt_path)
        self._system_prompt = self._compose_system_prompt(base_prompt)
        self._tools = self._build_tools(enable_web_search)
        log.info(
            "Tools enabled: %s",
            [t.get("name") for t in self._tools] if self._tools else "(none)",
        )

    def _compose_system_prompt(self, base: str) -> str:
        if not self._skills:
            return base
        listing = "\n".join(
            f"- {s.name}: {s.description}" for s in self._skills.values()
        )
        return (
            f"{base}\n\n"
            f"Available custom skills (load full instructions via the use_skill tool):\n"
            f"{listing}"
        )

    def _build_tools(self, enable_web_search: bool) -> List[dict]:
        tools: List[dict] = []
        if self._skills:
            tools.append(
                {
                    "name": "use_skill",
                    "description": (
                        "Load the full instructions for a custom skill baked "
                        "into this app. Call this when one of the skills "
                        "listed in the system prompt is relevant to the user's "
                        "request."
                    ),
                    "input_schema": {
                        "type": "object",
                        "properties": {
                            "skill_name": {
                                "type": "string",
                                "enum": sorted(self._skills.keys()),
                                "description": "Name of the skill to load.",
                            }
                        },
                        "required": ["skill_name"],
                    },
                }
            )
        if enable_web_search:
            tools.append(
                {
                    "type": "web_search_20250305",
                    "name": "web_search",
                    "max_uses": 5,
                }
            )
        return tools

    async def reply(
        self,
        question: str,
        recent_messages: List[dict],
        asker_name: str,
    ) -> str:
        chrono = list(reversed(recent_messages))
        if chrono:
            context_block = "\n".join(
                f"[{m['created_at']}] {m['from_name']}: {m['text']}" for m in chrono
            )
        else:
            context_block = "(no prior messages in window)"

        user_content = (
            f"Recent channel messages (chronological):\n{context_block}\n\n"
            f"{asker_name} just mentioned you and asked:\n{question}"
        )
        messages: List[dict] = [{"role": "user", "content": user_content}]

        last_resp = None
        for _ in range(self._max_iters):
            kwargs = dict(
                model=self._model,
                max_tokens=self._max_tokens,
                system=self._system_prompt,
                messages=messages,
            )
            if self._tools:
                kwargs["tools"] = self._tools

            resp = await self._client.messages.create(**kwargs)
            last_resp = resp
            messages.append({"role": "assistant", "content": resp.content})

            stop = getattr(resp, "stop_reason", None)
            log.info("Claude stop_reason=%s", stop)

            if stop == "end_turn" or stop == "max_tokens":
                return self._extract_text(resp.content)

            if stop == "tool_use":
                tool_results = self._handle_client_tools(resp.content)
                if not tool_results:
                    # Only server tools fired (e.g., web_search) — shouldn't
                    # normally hit this since server tools resolve inside the
                    # same call. Bail with whatever text we have.
                    return self._extract_text(resp.content)
                messages.append({"role": "user", "content": tool_results})
                continue

            if stop == "pause_turn":
                # Server tool needs another round to finish.
                continue

            # Unknown stop reason — stop to avoid infinite loop.
            log.warning("Unexpected stop_reason %r — exiting loop", stop)
            break

        return self._extract_text(last_resp.content if last_resp else []) or (
            "(no response — reached max tool iterations)"
        )

    def _handle_client_tools(self, content: list) -> List[dict]:
        results: List[dict] = []
        for block in content:
            if getattr(block, "type", None) != "tool_use":
                continue
            name = getattr(block, "name", "")
            if name == "use_skill":
                skill_name = (getattr(block, "input", {}) or {}).get("skill_name", "")
                skill = self._skills.get(skill_name)
                if skill:
                    log.info("Loading skill %r", skill_name)
                    text = (
                        f"# Skill: {skill.name}\n\n{skill.instructions}\n\n"
                        f"(Apply the above instructions to answer the user's request.)"
                    )
                else:
                    log.warning("Skill %r not found", skill_name)
                    text = f"Skill '{skill_name}' not found. Available: {sorted(self._skills)}"
                results.append(
                    {
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": text,
                    }
                )
            # web_search is a server tool — Anthropic handles execution itself,
            # so we don't return a tool_result for it.
        return results

    @staticmethod
    def _extract_text(content: list) -> str:
        parts: List[str] = []
        for block in content or []:
            if getattr(block, "type", None) == "text":
                parts.append(getattr(block, "text", ""))
        return "".join(parts).strip()
