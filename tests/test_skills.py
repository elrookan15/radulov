"""Unit tests for RADULOV Skills Discovery & Execution Engine."""

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from radulov.skills import (
    _parse_yaml_frontmatter,
    discover_skills,
    list_skills,
    load_skills_context,
    read_skill,
)


class TestRadulovSkills(unittest.TestCase):
    """Test suite for agent skills discovery and execution."""

    def test_parse_yaml_frontmatter(self):
        """Ensure YAML frontmatter is parsed correctly."""
        sample = (
            "---\n"
            "name: test-skill\n"
            'description: "A test skill description"\n'
            "---\n"
            "# Test Skill Title\n"
            "Skill instructions body."
        )
        meta, body = _parse_yaml_frontmatter(sample)
        self.assertEqual(meta.get("name"), "test-skill")
        self.assertEqual(meta.get("description"), "A test skill description")
        self.assertIn("# Test Skill Title", body)

    def test_discover_skills_finds_gemini_api_dev(self):
        """Ensure discover_skills finds the local or global gemini-api-dev skill."""
        skills = discover_skills()
        self.assertIn("gemini-api-dev", skills)
        info = skills["gemini-api-dev"]
        self.assertEqual(info["name"], "gemini-api-dev")
        self.assertIn("Gemini", info["description"])
        self.assertTrue(Path(info["skill_md_path"]).is_file())

    def test_list_skills_output(self):
        """Ensure list_skills formats discovered skills into a clean list."""
        output = list_skills()
        self.assertIn("Discovered", output)
        self.assertIn("gemini-api-dev", output)

    def test_read_skill_found(self):
        """Ensure read_skill reads the full SKILL.md content."""
        content = read_skill("gemini-api-dev")
        self.assertIn("Gemini API Development Skill", content)
        self.assertIn("gemini-3.8-flash", content)

    def test_read_skill_missing(self):
        """Ensure read_skill returns informative error message when not found."""
        output = read_skill("non_existent_skill_xyz")
        self.assertIn("Error: Skill 'non_existent_skill_xyz' not found", output)

    def test_load_skills_context(self):
        """Ensure load_skills_context formats skills into delimited prompt context."""
        context = load_skills_context(["gemini-api-dev"])
        self.assertIn("--- BEGIN SKILL: gemini-api-dev ---", context)
        self.assertIn("--- END SKILL: gemini-api-dev ---", context)


if __name__ == "__main__":
    unittest.main()
