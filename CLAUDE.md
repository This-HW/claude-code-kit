# claude-code-kit

> Universal Claude Code toolkit — agents and skills for software development

## Installation

```bash
# Basic — Anthropic community catalog (listed; syncs periodically, ~a day)
/plugin marketplace add anthropics/claude-plugins-community
/plugin install claude-code-kit@claude-community

# Basic — direct marketplace (fastest updates)
/plugin marketplace add This-HW/claude-code-kit
/plugin install claude-code-kit@claude-code-kit

# Full (with security hooks + auto-format + pre-commit)
git clone https://github.com/This-HW/claude-code-kit && cd claude-code-kit && ./setup.sh
```

## Structure

```
plugins/
└── common/      — Core agents (33) + skills (16) + rules (13) + hooks
```

`plugins/common/` contains:

- `.claude-plugin/plugin.json` — plugin manifest
- `agents/` — agent `.md` files
- `skills/` — skill `.md` files
- `hooks/` — Python hook scripts (common only)
- `rules/` — governance rules (common only)

## Key Skills

| Skill                    | Command                     | Description                                     |
| ------------------------ | --------------------------- | ----------------------------------------------- |
| plan-task                | `/plan-task`                | Structured task planning                        |
| auto-dev                 | `/auto-dev`                 | Automated development pipeline                  |
| web-research             | `/web-research`             | MCP-powered research                            |
| review                   | `/review`                   | Code review: ruff + review-code + security-scan |
| multi-perspective-review | `/multi-perspective-review` | 3-Round Deliberation with 10 perspectives       |
| doc-coauthoring          | `/doc-coauthoring`          | AI-assisted documentation authoring             |
| debug                    | `/debug`                    | 4-Phase debug pipeline                          |
| test                     | `/test`                     | Run tests and auto-fix failures                 |
| agent-creator            | `/agent-creator`            | Generate plugin agents                          |
| skill-creator            | `/skill-creator`            | Generate plugin skills                          |
| mcp-builder              | `/mcp-builder`              | Scaffold MCP servers                            |
| agent-teams              | `/agent-teams`              | Large-scale parallel work — routes to native `ultracode` |
| native-watch             | `/native-watch`             | Audit native-feature absorption vs the kit (SSOT: docs/native-absorption.md) |
| self-improve             | `/self-improve`             | Propose agent/skill/rule improvements from ledger+evals (proposal-only, gated) |

## Agent Architecture

### 2-Tier Model

```
Tier 1: plugins/common/  — All projects (33 agents)
Tier 2: project-local/   — Project-specific (user-added)
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
maxTurns: 20 # 20 for implementation agents, 10 for exploration/review
isolation: worktree # optional: run in isolated git worktree
tools:
  - Read
  - Edit
  - Bash
disallowedTools:
  - Task # regular agents cannot spawn sub-agents
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

- ✅ implement-code, fix-bugs, write-tests, write-api-tests, implement-api, generate-boilerplate, sync-docs, optimize-logic
- ❌ explore-codebase, review-code, plan-implementation (read-only)

Merge-back protocol (exit conditions, sequential merge, conflict escalation) is
governed by `plugins/common/rules/parallel-worktree.md`.

### Delegation Signal

All agents end with a structured delegation signal:

```
---DELEGATION_SIGNAL---
TYPE: DELEGATE_TO | TASK_COMPLETE | NEED_USER_INPUT | NEED_CLARIFICATION
TARGET: [agent-name]
REASON: [reason]
CONTEXT: [handoff context]
---END_SIGNAL---
```

## Development Conventions

### Adding a New Agent

1. Create `plugins/common/agents/{category}/{name}.md`
2. Add required frontmatter (see template above)
3. Write Korean description with `MUST USE when:` trigger conditions
4. Add delegation chain at the end
5. No manifest edit needed — agents are auto-discovered from the directory
   (plugin.json has no agent/skill registry)

### Adding a New Skill

1. Create `plugins/common/skills/{name}/SKILL.md`
2. Optionally add `README.md` in the same directory
3. No manifest edit needed — skills are auto-discovered from the directory

### Naming Conventions

- Agents: `verb-noun.md` (fix-bugs, plan-refactor, explore-codebase)
- Skills: `noun-action` (web-research, plan-task, auto-dev)
- All agent names must be kebab-case and match the `name:` frontmatter field

### Sub-agent Rules

- Regular agents: `disallowedTools: [Task]` — cannot spawn sub-agents
- Meta agents (facilitator, synthesizer, devil's advocate, impact-analyzer, consensus-builder, facilitator-teams — 6 total): `disallowedTools: [Bash]`
- Skills (auto-dev, etc.) drive delegation; leaf agents stay flat.

### Orchestration Model — Scale-Appropriate Primitives (Spec 2 / W-006)

오케스트레이션은 전통이 아니라 **스케일별로 올바른 프리미티브**를 쓴다. leaf 에이전트가
Task를 갖지 않는 이유는 "main만 조율" 도그마가 아니라, 우리 스케일에서 에이전트 중첩이
성능 이득 없이 예측불가능성·디버깅 부채만 더하기 때문이다.

| 작업 규모 | 오케스트레이션 |
| --------- | -------------- |
| Small / Medium | 스킬 주도 플랫 위임 (main이 Agent 병렬 dispatch → 결과 수집). 예측가능·검증된 경로 |
| Large (10~100+) | 네이티브 `ultracode`(dynamic workflow)를 **사용자가 수동 트리거** — 백그라운드 오케스트레이션. auto-dev는 Large 작업을 청크로 분할해 안내 |

> 네이티브 dynamic workflow / `/goal`은 대화형 전용이라 스킬에서 프로그래밍 트리거가
> 불가하다(2026.6 기준). 따라서 자동 위임은 검증된 Task 시스템 + 스킬 루프로 하고,
> 대규모 병렬은 사용자가 `ultracode`로 트리거한다. 실험적 자체 조율(구 agent-teams)은
> 이 네이티브 경로로 대체됐다.

### Phase Gate Pattern

```
Phase 1 (Planning)    → 100% ambiguity removed via planning agents
Phase 2 (Development) → implement based on Phase 1 artifacts
Phase 3 (Validation)  → review + security scan (parallel)
```

## Hooks

Located in `plugins/common/hooks/` (except `session-check.py`, which lives in
`plugins/common/setup/`):

- `session-check.py` — `SessionStart` environment/setup check (runs before
  `session-start.py`; registered from `setup/`)
- `session-start.py` — injects rules + active Work status at `SessionStart`
- `protect-sensitive.py` — `PreToolUse` on Edit/Write/MultiEdit/NotebookEdit/Read:
  blocks access to **sensitive file paths** (`.env`, keys, `.pem`) by path. It does
  **not** scan file *content* or intercept `Bash`/`git commit` — commit-time secret
  scanning is gitleaks + `setup/pre-commit`.
- `auto-format.py` — auto-formats code after edits (uses ruff for Python) (`PostToolUse`)
- `stop-validator.py` — on `Stop`, lints edited `.py` (ruff) and runs pytest on
  the test files this session edited (never the full suite — that's CI/`/test`'s
  job); on failure emits native `{"decision":"block","reason":...}` so Claude
  continues and auto-fixes. Timeouts are non-blocking (`CLAUDE_STOP_TEST_TIMEOUT`)
- `utils.py` — shared utilities

Hooks are defined in `plugins/common/hooks/hooks.json` using the **exec form**
(`command` + `args[]`) so `${CLAUDE_PLUGIN_ROOT}` paths need no shell quoting.

> Subagent lifecycle tracking is delegated to native OpenTelemetry
> (`agent_id` / `parent_agent_id` spans, `/usage` breakdown) — the kit no longer
> ships a custom `agent-lifecycle.py` (removed in the 2.6.0 batch, Spec 1 / W-005).

## Security

- `gitleaks` scans all pushes/PRs (config: `.gitleaks.toml`)
- Never hardcode secrets, API keys, internal IPs, or project names
- `protect-sensitive.py` runs as a `PreToolUse` hook on Edit/Write/MultiEdit/NotebookEdit/Read — path-based, not content/commit-based (see Hooks section)

## CI/CD

`.github/workflows/validate.yml` runs on push to `main` (and PRs):

1. Validates JSON syntax (`plugin.json`, `marketplace.json`)
2. Checks agent frontmatter completeness (`name`, `description` required)
3. Runs gitleaks security scan

## Release Checklist

**CRITICAL: Every commit that changes plugin behavior MUST bump the version in `plugins/common/.claude-plugin/plugin.json`.**

Plugin cache is keyed by `{plugin-name}/{version}` — same version = no update fetched = users never get the fix.

- Patch bump (2.x.y) for bug fixes and hook changes
- Minor bump (2.x.0) for new agents, skills, or features
- Add a matching `## [x.y.z]` entry to `CHANGELOG.md` (verify-done.sh §6 fails if
  the plugin.json version and the CHANGELOG top entry diverge)
- Keep README/docs version-agnostic (link to CHANGELOG) so they can't drift
- Run `scripts/verify-done.sh` (green) before claiming a release ready (definition-of-done)

```bash
# Before git commit — update version field:
# plugins/common/.claude-plugin/plugin.json  → "version": "x.y.z"
```

## Contributing

PRs welcome. Checklist:

- [ ] Agent frontmatter has `name`, `description`, `model`, `maxTurns`
- [ ] No forbidden fields: `permissionMode`, `context_cache`, `output_schema`, `next_agents`, inline `hooks`
- [ ] Description includes `MUST USE when:` trigger conditions
- [ ] File-modifying agents have `isolation: worktree`
- [ ] Regular agents have `disallowedTools: [Task]`
- [ ] Skill `description` field is in English
- [ ] Registered in `plugins/common/.claude-plugin/plugin.json`
- [ ] CI passes (JSON valid, frontmatter complete, no forbidden fields, pytest green, no secrets)
