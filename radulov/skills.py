"""Skills Discovery & Context Injection Engine for RADULOV.

Discovers, parses, and provides agent skills from local repository paths
(.agents/skills, skills) and global customization roots.
"""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent

SEARCH_ROOTS: list[Path] = [
    REPO_ROOT / ".agents" / "skills",
    REPO_ROOT / "skills",
    Path.home() / ".agents" / "skills",
    Path.home() / ".gemini" / "config" / "plugins" / "gemini-api" / "skills",
    Path.home() / ".gemini" / "config" / "skills",
]


def _parse_yaml_frontmatter(content: str) -> tuple[dict[str, str], str]:
    """Extract YAML frontmatter and body from markdown content."""
    meta: dict[str, str] = {}
    body = content
    if content.startswith("---"):
        parts = content.split("---", 2)
        if len(parts) >= 3:
            raw_meta = parts[1].strip()
            body = parts[2].strip()
            for line in raw_meta.splitlines():
                if ":" in line:
                    key, val = line.split(":", 1)
                    meta[key.strip()] = val.strip().strip("\"'")
    return meta, body


def discover_skills() -> dict[str, dict[str, Any]]:
    """Scan all search roots and discover available skills.

    Returns:
        Mapping of skill_name -> {name, description, path, skill_md_path}.
    """
    discovered: dict[str, dict[str, Any]] = {}

    for root in SEARCH_ROOTS:
        if not root.is_dir():
            continue

        try:
            for item in root.iterdir():
                if not item.is_dir():
                    continue
                skill_md = item / "SKILL.md"
                if not skill_md.is_file():
                    continue

                skill_name = item.name
                if skill_name in discovered:
                    continue

                try:
                    content = skill_md.read_text(encoding="utf-8", errors="replace")
                    meta, _ = _parse_yaml_frontmatter(content)
                    discovered[skill_name] = {
                        "name": meta.get("name", skill_name),
                        "description": meta.get("description", "No description provided."),
                        "path": str(item.resolve()),
                        "skill_md_path": str(skill_md.resolve()),
                    }
                except Exception:
                    continue
        except Exception:
            continue

    return discovered


def list_skills() -> str:
    """List all available agent skills discovered in local and global environments.

    Returns:
        Formatted catalog of discovered skills with names and descriptions.
    """
    skills = discover_skills()
    if not skills:
        return "No agent skills found in repository or global search paths."

    lines: list[str] = [f"Discovered {len(skills)} Available Agent Skills:\n"]
    for s_id, s_info in sorted(skills.items()):
        lines.append(f"- **{s_info['name']}** (`{s_id}`)")
        lines.append(f"  Description: {s_info['description']}")
        lines.append(f"  Path: {s_info['skill_md_path']}\n")

    return "\n".join(lines).strip()


def read_skill(skill_name: str) -> str:
    """Read the full instruction content of a specific agent skill.

    Args:
        skill_name: Name or folder identifier of the skill (e.g. 'gemini-api-dev').

    Returns:
        Full text of the skill's instructions.
    """
    skills = discover_skills()
    matched = skills.get(skill_name)
    if not matched:
        # Try case-insensitive or partial match
        lowered = skill_name.lower()
        for k, v in skills.items():
            if k.lower() == lowered or v["name"].lower() == lowered:
                matched = v
                break

    if not matched:
        available = ", ".join(skills.keys()) or "None"
        return f"Error: Skill '{skill_name}' not found. Available skills: {available}"

    try:
        skill_path = Path(matched["skill_md_path"])
        return skill_path.read_text(encoding="utf-8", errors="replace")
    except Exception as err:
        return f"Error reading skill '{skill_name}': {err}"


def load_skills_context(skill_names: list[str] | None = None) -> str:
    """Build a consolidated contextual markdown block for specified or default skills."""
    skills = discover_skills()
    target_names = skill_names or ["gemini-api-dev"]

    blocks: list[str] = []
    for name in target_names:
        if name in skills:
            content = read_skill(name)
            if not content.startswith("Error"):
                blocks.append(f"--- BEGIN SKILL: {name} ---\n{content}\n--- END SKILL: {name} ---")

    return "\n\n".join(blocks)


def compose_system_instruction(
    base: str, skill_names: list[str] | None = None
) -> str:
    """Append discovered skill instructions onto a system prompt."""
    extra = load_skills_context(skill_names)
    if not extra:
        return base
    return f"{base}\n\n## Loaded Agent Skills\n\n{extra}"
