"""Loads local skills from the skills/ directory.

Skill files are Markdown with optional YAML-ish frontmatter:

    ---
    name: pricing
    description: Vector Solutions product pricing reference. Use when asked about pricing.
    ---

    # Pricing

    EHS Lite ......... $5/user/year
    ...

Files can live as:
- skills/<name>.md
- skills/<name>/SKILL.md

If no `name` is in the frontmatter, the filename (or directory name) is used.
"""
from __future__ import annotations

import os
import re
from dataclasses import dataclass
from typing import List


@dataclass
class Skill:
    name: str
    description: str
    instructions: str


_FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n(.*)$", re.DOTALL)


def _parse_skill_file(path: str, default_name: str) -> Skill | None:
    try:
        with open(path, encoding="utf-8") as f:
            content = f.read()
    except OSError:
        return None

    name = default_name
    description = ""
    body = content.strip()

    m = _FRONTMATTER_RE.match(content)
    if m:
        fm, body = m.group(1), m.group(2).strip()
        for line in fm.splitlines():
            if ":" not in line:
                continue
            key, val = line.split(":", 1)
            key = key.strip().lower()
            val = val.strip().strip('"').strip("'")
            if key == "name" and val:
                name = val
            elif key == "description":
                description = val

    if not body:
        return None
    if not description:
        description = "(no description provided)"
    # Sanitize name to be a safe identifier.
    name = re.sub(r"[^A-Za-z0-9_]+", "_", name).strip("_") or default_name
    return Skill(name=name, description=description, instructions=body)


def load_skills(skills_dir: str) -> List[Skill]:
    if not skills_dir or not os.path.isdir(skills_dir):
        return []

    out: List[Skill] = []
    seen: set[str] = set()
    for entry in sorted(os.listdir(skills_dir)):
        if entry.startswith(".") or entry.lower() in {"readme.md", "readme"}:
            continue
        full = os.path.join(skills_dir, entry)
        if os.path.isfile(full) and entry.lower().endswith(".md"):
            sk = _parse_skill_file(full, default_name=entry[:-3])
        elif os.path.isdir(full):
            inner = os.path.join(full, "SKILL.md")
            if not os.path.isfile(inner):
                continue
            sk = _parse_skill_file(inner, default_name=entry)
        else:
            continue
        if sk and sk.name not in seen:
            seen.add(sk.name)
            out.append(sk)
    return out
