# Changelog

All notable changes to claude-code-kit are documented here.

Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

---

## [2.2.0] — 2026-05-03

### ⚠️ Behavior Change — Stop Hook

The `Stop` hook has been replaced with an automated validator (`stop-validator.py`).

**What changed:** Previously, the Stop hook asked Claude to self-evaluate completion. Now it runs `ruff` and `pytest` automatically and **blocks the session from stopping if either fails.**

**Who is affected:** All users with Python files modified in the current session.

**How to disable** (per-session or globally):

```json
// plugins/common/hooks/hooks.json → restore the prompt-based hook:
"Stop": [
  {
    "hooks": [
      {
        "type": "prompt",
        "prompt": "개발 작업이 완료된 경우 ...",
        "timeout": 30
      }
    ]
  }
]
```

Or remove the `Stop` section entirely to disable all stop validation.

**How it works:**
- No Python files modified → instant pass (no ruff/pytest run)
- `ruff` not installed → warning to stderr, pass
- `pytest` not installed → warning to stderr, pass
- auto-dev pipeline already validated → marker file detected, skip (no double-validation)
- Max 2 auto-fix retries before giving up

### Added

- **`stop-validator.py`** — automated Stop hook: detects Python changes, runs ruff (with auto-fix) and pytest, blocks on failure with structured JSON output
- **7 unit tests** for `stop-validator.py` (`hooks/tests/test_stop_validator.py`):
  - `test_no_py_changes_exits_zero`
  - `test_lint_auto_fixed_prints_json_and_exits_zero`
  - `test_lint_auto_fixed_json_structure`
  - `test_test_failure_exits_two_with_correct_json`
  - `test_marker_skip_exits_zero_and_consumes_marker`
  - `test_lint_error_when_auto_fix_fails_exits_two`
  - `test_max_retries_exceeded_exits_two`
- **auto-dev SKILL.md** — T-merge step now creates a validation marker to prevent double-validation when auto-dev pipeline already ran lint/test

### Fixed

- Stop hook `PROJECT_ROOT` now derived from `git rev-parse --show-toplevel` (stable regardless of harness cwd)
- git-relative paths resolved against `PROJECT_ROOT` before passing to ruff (fixes silent lint skip when hook cwd ≠ project root)
- TOCTOU race condition in marker file check replaced with atomic `try/except unlink()`

---

## [2.0.0] — 2026-04-22

### Breaking Changes

- **Removed from all agent frontmatter** (non-standard fields, unsupported by the official plugin spec):
  - `permissionMode` — removed from 6 agents
  - `context_cache` — removed from all agents
  - `output_schema` — removed from all agents
  - `next_agents` — removed from all agents
  - Inline `hooks:` blocks — removed from all agents (covered by plugin-level `hooks/hooks.json`)
- **Removed from all skill frontmatter**:
  - `domain`, `argument-hint`, `allowed-tools` — non-standard, not supported by official spec

If you extended agents by adding these fields in project-local overrides, remove them to stay compliant.

### Added

- **Manifest compliance** — all 6 `plugin.json` files now include `homepage`, `repository`, `license`, `author.email` for official registry submission
- **`maxTurns` field** — added to 11 agents to prevent infinite loops:
  - Implementation agents (`implement-code`, `fix-bugs`, `write-tests`, `plan-implementation`, `write-api-tests`): `maxTurns: 20`
  - Exploration/review agents (`review-code`, `verify-code`, `verify-integration`, `explore-codebase`, `analyze-dependencies`, `security-scan`): `maxTurns: 10`
- **New lifecycle hooks** in `hooks/hooks.json`:
  - `SubagentStart` — logs agent invocation start
  - `SubagentStop` — logs agent invocation completion
  - `PreCompact` — saves state summary before context compaction
- **`agent-lifecycle.py`** — new hook script handling the three lifecycle events above
- **91 unit tests** for all hook scripts:
  - `tests/test_session_start.py` — 19 tests (frontmatter parsing, task map parsing, rules loading, main output format)
  - `tests/test_protect_sensitive.py` — 33 tests (file path blocking, content scanning, integration)
  - `tests/test_auto_format.py` — 19 tests (path validation, ESLint config detection, pipeline execution)
  - `tests/test_utils.py` — 21 tests (safe_path, debug_log, is_debug_mode, get_project_root)
- **CI strengthened** (`.github/workflows/validate.yml`):
  - `Check plugin.json required fields` step
  - `Check agent frontmatter — no forbidden fields` step
  - `Run hook unit tests` step (`pytest plugins/common/hooks/tests/ -v`)
- **English skill descriptions** — all 14 skill `description` fields converted from Korean to English for correct Claude auto-invocation behavior

### Fixed

- `agent-creator` skill template: removed `permissionMode` from the generated agent template (it was showing a now-unsupported field)
- All `hooks/hooks.json` paths already used `${CLAUDE_PLUGIN_ROOT}` — verified correct

---

## [1.1.5] — 2026-04-21

### Fixed

- W-007 validation issues: T-merge guard, confidence wording, Bash scope

---

## [1.1.4] — 2026-04-14

### Fixed

- GitHub Actions gitleaks failure
- Documentation updates

---

## [1.1.3] and earlier

Initial releases establishing the 33-agent + 12-skill core structure across 6 plugin domains.
