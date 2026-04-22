"""Tests for session-start.py hook."""

import importlib.util
import json
import sys
from io import StringIO
from pathlib import Path
from unittest.mock import patch

# session-start.py has a hyphen — use importlib to load it
HOOKS_DIR = Path(__file__).resolve().parent.parent
_spec = importlib.util.spec_from_file_location(
    "session_start", HOOKS_DIR / "session-start.py"
)
_mod = importlib.util.module_from_spec(_spec)
sys.modules["session_start"] = _mod
_spec.loader.exec_module(_mod)

load_rules = _mod.load_rules
parse_frontmatter = _mod.parse_frontmatter
parse_task_map = _mod.parse_task_map
summarize_work = _mod.summarize_work


class TestParseFrontmatter:
    def test_valid_frontmatter(self, tmp_path):
        f = tmp_path / "work.md"
        f.write_text(
            "---\nwork_id: W-001\ntitle: My Work\ncurrent_phase: dev\n---\nBody"
        )
        fm = parse_frontmatter(f)
        assert fm["work_id"] == "W-001"
        assert fm["title"] == "My Work"
        assert fm["current_phase"] == "dev"

    def test_no_frontmatter(self, tmp_path):
        f = tmp_path / "work.md"
        f.write_text("Just body text")
        assert parse_frontmatter(f) == {}

    def test_empty_file(self, tmp_path):
        f = tmp_path / "work.md"
        f.write_text("")
        assert parse_frontmatter(f) == {}

    def test_missing_file(self, tmp_path):
        f = tmp_path / "nonexistent.md"
        assert parse_frontmatter(f) == {}

    def test_quoted_values(self, tmp_path):
        f = tmp_path / "work.md"
        f.write_text('---\ntitle: "Quoted Title"\n---\n')
        fm = parse_frontmatter(f)
        assert fm["title"] == "Quoted Title"

    def test_value_with_colon(self, tmp_path):
        f = tmp_path / "work.md"
        f.write_text("---\nurl: http://example.com\n---\n")
        fm = parse_frontmatter(f)
        assert fm["url"] == "http://example.com"


class TestParseTaskMap:
    def _make_progress(self, tmp_path, content):
        p = tmp_path / "progress.md"
        p.write_text(content)
        return p

    def test_missing_file(self, tmp_path):
        assert parse_task_map(tmp_path / "nonexistent.md") == []

    def test_no_task_map_section(self, tmp_path):
        p = self._make_progress(tmp_path, "# Some Doc\n\nNo tasks here.")
        assert parse_task_map(p) == []

    def test_basic_task_map(self, tmp_path):
        content = (
            "## Task Map\n\n"
            "| Task ID | Title | Description | Status | Blocked By |\n"
            "|---------|-------|-------------|--------|------------|\n"
            "| T-001 | Do thing | desc | ✅ done | - |\n"
            "| T-002 | Fix thing | desc2 | ⏳ wip | T-001 |\n"
            "| T-003 | Next thing | desc3 | ⬜ todo | T-002 |\n"
        )
        p = self._make_progress(tmp_path, content)
        tasks = parse_task_map(p)
        assert len(tasks) == 3
        assert tasks[0]["id"] == "T-001"
        assert "✅" in tasks[0]["status"]
        assert tasks[1]["id"] == "T-002"
        assert "⏳" in tasks[1]["status"]
        assert tasks[2]["id"] == "T-003"
        assert "⬜" in tasks[2]["status"]

    def test_skips_non_t_rows(self, tmp_path):
        content = (
            "## Task Map\n\n"
            "| Task ID | Title | Status | Blocked By |\n"
            "|---------|-------|--------|------------|\n"
            "| (placeholder) | - | - | - |\n"
            "| T-001 | Real | ✅ done | - |\n"
        )
        p = self._make_progress(tmp_path, content)
        tasks = parse_task_map(p)
        assert len(tasks) == 1
        assert tasks[0]["id"] == "T-001"

    def test_stops_at_next_section(self, tmp_path):
        content = (
            "## Task Map\n\n"
            "| Task ID | Title | Description | Status | Blocked By |\n"
            "|---------|-------|-------------|--------|------------|\n"
            "| T-001 | Task | d | ✅ done | - |\n"
            "\n## Notes\n\n"
            "| T-002 | Should not appear | d | ⬜ | - |\n"
        )
        p = self._make_progress(tmp_path, content)
        tasks = parse_task_map(p)
        assert len(tasks) == 1


class TestLoadRules:
    def test_no_rules_dir(self, tmp_path):
        result = load_rules(tmp_path, include_task_resume=False)
        assert result == ""

    def test_loads_existing_rules(self, tmp_path):
        rules_dir = tmp_path / "rules"
        rules_dir.mkdir()
        (rules_dir / "agent-system.md").write_text("# Agent Rules\nContent here.")
        result = load_rules(tmp_path, include_task_resume=False)
        assert "=== RULES ===" in result
        assert "Agent Rules" in result
        assert "=== END RULES ===" in result

    def test_missing_rule_file_skipped(self, tmp_path):
        rules_dir = tmp_path / "rules"
        rules_dir.mkdir()
        # Only create one of the many expected files
        (rules_dir / "agent-system.md").write_text("# Exists")
        result = load_rules(tmp_path, include_task_resume=False)
        assert "Exists" in result

    def test_all_missing_returns_empty(self, tmp_path):
        (tmp_path / "rules").mkdir()
        result = load_rules(tmp_path, include_task_resume=False)
        assert result == ""

    def test_task_resume_included_when_has_active_work(self, tmp_path):
        rules_dir = tmp_path / "rules"
        rules_dir.mkdir()
        (rules_dir / "task-resume.md").write_text("# Resume Rules")
        result = load_rules(tmp_path, include_task_resume=True)
        assert "Resume Rules" in result

    def test_task_resume_excluded_when_no_active_work(self, tmp_path):
        rules_dir = tmp_path / "rules"
        rules_dir.mkdir()
        (rules_dir / "task-resume.md").write_text("# Resume Rules")
        result = load_rules(tmp_path, include_task_resume=False)
        assert "Resume Rules" not in result


class TestMain:
    def test_main_outputs_valid_json(self, tmp_path):
        with (
            patch.object(_mod, "get_project_root", return_value=str(tmp_path)),
            patch("sys.stdout", new_callable=StringIO) as mock_stdout,
        ):
            _mod.main()
            output = mock_stdout.getvalue().strip()

        data = json.loads(output)
        assert "hookSpecificOutput" in data
        assert "additionalContext" in data["hookSpecificOutput"]
        assert data["hookSpecificOutput"]["hookEventName"] == "SessionStart"

    def test_main_survives_missing_works_dir(self, tmp_path):
        with (
            patch.object(_mod, "get_project_root", return_value=str(tmp_path)),
            patch("sys.stdout", new_callable=StringIO) as mock_stdout,
        ):
            _mod.main()
            output = mock_stdout.getvalue().strip()

        data = json.loads(output)
        assert isinstance(data["hookSpecificOutput"]["additionalContext"], str)
