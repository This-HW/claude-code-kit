# claude-code-kit

> Universal Claude Code toolkit — agents and skills for software development

## Installation

```bash
# Basic (Plugin only)
claude plugin marketplace add grimm/claude-code-kit
claude plugin install claude-code-kit@stable --scope user

# Full (with security hooks)
git clone https://github.com/grimm/claude-code-kit && ./setup.sh
```

## Structure

```
plugins/
├── common/      — Core agents (52) + skills (19) + rules (10) + hooks
├── frontend/    — Frontend agents (4) + skills (1)
├── infra/       — Infrastructure agents (7) + skills (1)
├── ops/         — Operations agents (14) + skills (4)
├── data/        — Data agents (4) + skills (3)
└── integration/ — Integration agents (4)
```

Each domain lives in `plugins/{domain}/` with:

- `.claude-plugin/plugin.json` — plugin manifest
- `agents/` — agent `.md` files
- `skills/` — skill `.md` files
- `hooks/` — Python hook scripts (common only)
- `rules/` — governance rules (common only)

## Key Skills

| Skill                    | Command                     | Description                    |
| ------------------------ | --------------------------- | ------------------------------ |
| plan-task                | `/plan-task`                | Structured task planning       |
| auto-dev                 | `/auto-dev`                 | Automated development pipeline |
| review                   | `/review`                   | Adversarial code review        |
| multi-perspective-review | `/multi-perspective-review` | Multi-expert review            |

## Agent Architecture

### 3-Tier Model

```
Tier 1: plugins/common/    — All projects (52 agents)
Tier 2: plugins/{domain}/  — Domain-specific (29 agents)
Tier 3: project-local/     — Project-specific (user-added)
```

### Agent Frontmatter

Every agent is a `.md` file with YAML frontmatter:

```yaml
---
name: agent-name # kebab-case, matches filename
description: | # Korean + English trigger conditions
  MUST USE when: "keywords"
  OUTPUT: result format
model: sonnet # opus | sonnet | haiku
effort: medium # low | medium | high | max
isolation: worktree # optional: run in isolated git worktree
tools:
  - Read
  - Edit
  - Bash
disallowedTools:
  - Task # regular agents cannot spawn sub-agents
permissionMode: acceptEdits
hooks:
  PreToolUse:
    - matcher: "Edit"
      hooks:
        - type: command
          command: "python3 ~/.claude/hooks/protect-sensitive.py"
context_cache:
  use_session: true
  session_includes:
    - CLAUDE.md
---
```

### Model Selection

| Model      | Use case                   | Examples                              |
| ---------- | -------------------------- | ------------------------------------- |
| **Opus**   | Strategy, analysis, review | clarify-requirements, review-code     |
| **Sonnet** | Code implementation, fixes | implement-code, fix-bugs, write-tests |
| **Haiku**  | Exploration, simple checks | explore-codebase, verify-code         |

### isolation: worktree

Apply to agents that **modify files** — prevents filesystem conflicts:

- ✅ implement-code, fix-bugs, write-tests, write-api-tests, write-ui-tests
- ❌ explore-codebase, review-code, plan-implementation (read-only)

### Delegation Signal

All agents end with a structured delegation signal:

```
---DELEGATION_SIGNAL---
TYPE: DELEGATE_TO | TASK_COMPLETE | NEED_USER_INPUT
TARGET: [agent-name]
REASON: [reason]
CONTEXT: [handoff context]
---END_SIGNAL---
```

## Development Conventions

### Adding a New Agent

1. Create `plugins/{domain}/agents/{category}/{name}.md`
2. Add required frontmatter (see template above)
3. Write Korean description with `MUST USE when:` trigger conditions
4. Add delegation chain at the end
5. Register in `plugins/{domain}/.claude-plugin/plugin.json`

### Adding a New Skill

1. Create `plugins/{domain}/skills/{name}/skill.md`
2. Optionally add `README.md` in the same directory
3. Register in `plugins/{domain}/.claude-plugin/plugin.json`

### Naming Conventions

- Agents: `verb-noun.md` (fix-bugs, plan-refactor, explore-codebase)
- Skills: `noun-action` or `domain-task` (web-research, data-modeler)
- All agent names must be kebab-case and match the `name:` frontmatter field

### Sub-agent Rules

- Regular agents: `disallowedTools: [Task]` — cannot spawn sub-agents
- Meta agents (facilitator, synthesizer, devil's advocate, impact-analyzer): `disallowedTools: [Bash]`
- Only the main Claude orchestrator coordinates agents

### Phase Gate Pattern

```
Phase 1 (Planning)    → 100% ambiguity removed via planning agents
Phase 2 (Development) → implement based on Phase 1 artifacts
Phase 3 (Validation)  → review + security scan (parallel)
```

## Hooks

Located in `plugins/common/hooks/`:

- `protect-sensitive.py` — blocks commits/edits containing secrets
- `auto-format.py` — auto-formats code after edits (uses ruff for Python)
- `utils.py` — shared utilities

Hooks are defined in `plugins/common/hooks/hooks.json` and run via `SessionStart`.

## Security

- `gitleaks` scans all pushes/PRs (config: `.gitleaks.toml`)
- Never hardcode secrets, API keys, internal IPs, or project names
- `protect-sensitive.py` runs as a `PreToolUse` hook on Edit operations

## CI/CD

`.github/workflows/validate.yml` runs on push to `main`/`stable`:

1. Validates JSON syntax (`plugin.json`, `marketplace.json`)
2. Checks agent frontmatter completeness (`name`, `description` required)
3. Runs gitleaks security scan

## Contributing

PRs welcome. Checklist:

- [ ] Agent frontmatter has `name`, `description`, `model`
- [ ] Description includes `MUST USE when:` trigger conditions
- [ ] File-modifying agents have `isolation: worktree`
- [ ] Regular agents have `disallowedTools: [Task]`
- [ ] Registered in domain `plugin.json`
- [ ] CI passes (JSON valid, frontmatter complete, no secrets)
