# claude-code-kit

> Universal Claude Code toolkit — agents and skills for software development

## Who this is for (design north-star)

This is a **published plugin installed into other people's projects**, not a tool for this
repo alone. Every design decision is judged by: **does this work in a consumer's
environment** — where the plugin's files live in the plugin cache (not the project cwd),
where MCP servers may be absent or different, where hooks run on every session? A change
that only works in this repo is a defect. (Concrete gate in the Contributing checklist.)

**Interoperability is a first-class goal**: the kit must compose cleanly with other
plugins (e.g., superpowers) and with whatever MCP servers the user has (memory MCPs,
search MCPs, private/company servers). Three rules: never *assume* a specific plugin/MCP
is present; never *conflict* with one that is; *leverage* generically when available
(e.g., recall-before-plan / remember-after-done if memory-style tools exist — fail-open
otherwise). Guidance lives in skills, never in agent `tools:` allowlists.

## Installation

```bash
# Basic — Anthropic community catalog (read-only mirror; nightly sync — see Release Checklist)
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
  `session-start.py`; registered from `setup/`). Warns on: python below the 3.9
  floor, missing global setup, `.claude/agents` dual-load, and a **stale venv**
  (`.venv`/`venv` console-script shebangs still pointing at the project's old
  path after a directory move/copy — `bin/python` keeps working while every
  script dies with `bad interpreter`, or silently runs the old site-packages)
- `session-start.py` — injects rules + active Work status at `SessionStart`
- `protect-sensitive.py` — `PreToolUse` on Edit/Write/MultiEdit/NotebookEdit/Read:
  blocks access to **sensitive file paths** (`.env`, keys, `.pem`) by path. env
  templates (`.env.example`/`.sample`/`.template`/`.dist`) are exempt; writes to
  them get a best-effort high-confidence secret-format content scan (W-016). It
  does **not** otherwise scan file *content* or intercept `Bash`/`git commit` —
  commit-time secret scanning is gitleaks + `setup/pre-commit`.
- `auto-format.py` — auto-formats code after edits (uses ruff for Python) (`PostToolUse`)
- `stop-validator.py` — on `Stop`, lints edited `.py` (ruff) and runs pytest on
  the test files this session edited (never the full suite — that's CI/`/test`'s
  job); on failure emits native `{"decision":"block","reason":...}` so Claude
  continues and auto-fixes. Timeouts are non-blocking (`CLAUDE_STOP_TEST_TIMEOUT`)
- `utils.py` — shared utilities

Hooks are defined in `plugins/common/hooks/hooks.json` using the **exec form**
(`command` + `args[]`) so `${CLAUDE_PLUGIN_ROOT}` paths need no shell quoting.

**Python floor: 3.9** — hooks run on the *consumer's* `python3`, and macOS still
ships 3.9.x. So hook sources must stay 3.9-loadable: use
`from __future__ import annotations` and keep 3.10-only syntax out of anything
evaluated at import time. This is enforced twice, not by convention: ruff's `FA`
rules (statically, via root `ruff.toml`) and the `python39-compat` CI job (it
actually loads every hook under 3.9). Four hooks were silently dead on 3.9 until
2.12.1 — that is the failure this guards against.

> Subagent lifecycle tracking is delegated to native OpenTelemetry
> (`agent_id` / `parent_agent_id` spans, `/usage` breakdown) — the kit no longer
> ships a custom `agent-lifecycle.py` (removed in the 2.6.0 batch, Spec 1 / W-005).

## Security

- `gitleaks` scans all pushes/PRs (config: `.gitleaks.toml`)
- Never hardcode secrets, API keys, internal IPs, or project names
- `protect-sensitive.py` runs as a `PreToolUse` hook on Edit/Write/MultiEdit/NotebookEdit/Read — path-based (plus a best-effort content scan only for env-template writes), not commit-based (see Hooks section)

## CI/CD

`.github/workflows/validate.yml` runs on push to `main` (and PRs):

1. Validates JSON syntax (`plugin.json`, `marketplace.json`)
2. Checks agent frontmatter completeness (`name`, `description` required)
3. Lints with `ruff check .` and runs pytest
4. Lints shell via `scripts/lint-shell.sh` (same script as the local gate §3b)
5. Verifies doc counts via `scripts/check_doc_counts.py` (same script as the local gate)
6. Runs gitleaks security scan
7. `python39-compat` job: loads every hook under Python 3.9 (consumer floor)

### Lint is one ruleset, everywhere

`ruff.toml` at the repo root is the **single source** for both the rule set and
the lint scope; `ruff check .` is the only command (CI, `verify-done.sh §3`, and
the `auto-format` hook all resolve to it). Two traps it exists to close:

- **No project config → ruff falls back to the developer's global
  `~/.config/ruff/ruff.toml`** (which this kit itself installs). That masked a
  real CI failure once: local green, CI red.
- **Ruff's *default* rule set changes between releases** (0.15 enables E402, 0.16
  does not), so relying on defaults makes two machines disagree. The rules are
  therefore listed explicitly, and the version is pinned in `.ruff-version`
  (CI installs exactly that; `verify-done.sh` warns when the local ruff differs).

Raising the ruff pin is a deliberate act: bump `.ruff-version`, fix what the new
version flags, land both together.

**The test runner is pinned the same way.** `.pytest-version` is the pin; CI
installs exactly it, and `verify-done.sh §4` warns when the local pytest differs.
pytest changes collection, fixture, and deprecation behavior across majors, so an
unpinned runner means CI silently floats to the newest release and can go red with
no code change — the same failure `.ruff-version` exists to prevent. Both pins are
also what makes a dev venv reproducible:

```bash
python3 -m venv .venv
./.venv/bin/python -m pip install "pytest==$(cat .pytest-version)" "ruff==$(cat .ruff-version)"
```

### Rules have a long-form mirror — and it is checksum-guarded

`plugins/common/rules/` (13) is what gets **injected every session**, so it is compressed.
`docs/architecture/rules/` (9) is the long-form human explanation of nine of those rules,
created in W-004 — tables, worked examples, anti-patterns. The remaining four
(`definition-of-done`, `feedback-loop`, `loop-engineering`, `parallel-worktree`) have no
mirror by design; the injected rule is the whole story for them.

Nothing linked the two, so they drifted silently — a 2026-08-17 audit found three behind,
and the `planning-check` mirror still told readers to search Notion/Figma MCP in order,
**assuming those MCPs are installed**, which contradicts the consumer-first north-star.
`docs/architecture/rules/MIRROR.sha256` now records, per mirrored rule, the sha256 of the
injected rule the explanation last reflected. `verify-done.sh §7` fails when they diverge;
`scripts/sync-rule-mirror.sh --regenerate` updates it. Regeneration is deliberate on
purpose — auto-updating the manifest would make the check meaningless.

Normative statements live in the injected rule. The mirror explains and points at it; it
must not redefine anything, or the drift comes back through the front door.

### Shell is linted too

The completion gate (`verify-done.sh`) and the installer (`setup.sh`) *are* shell —
linting Python rigorously while leaving them unchecked means the code that decides
"done" is the code nobody checks. `scripts/lint-shell.sh` is the single command
(CI and `verify-done.sh §3b` both call it); it owns the target list and the
severity threshold, so neither side can drift. Targets are resolved from
`git ls-files` by extension **and** shebang, so extensionless scripts like
`plugins/common/setup/pre-commit` are covered and new scripts need no registration.
shellcheck is pinned in `.shellcheck-version` and CI verifies the release tarball's
sha256 — bump both together or the step fails loudly.

One deliberate asymmetry with ruff: a *missing* shellcheck is a yellow note locally,
not a red. CI (pinned version) is the authoritative verdict; the local run is fast
feedback. It never reports green when it could not check.

## Release Checklist

**CRITICAL: Every commit that changes plugin behavior MUST bump the version in `plugins/common/.claude-plugin/plugin.json`.**

Plugin cache is keyed by `{plugin-name}/{version}` — same version = no update fetched = users never get the fix.

- Patch bump (2.x.y) for bug fixes and hook changes
- Minor bump (2.x.0) for new agents, skills, or features
- Add a matching `## [x.y.z]` entry to `CHANGELOG.md` (verify-done.sh §6 fails if
  the plugin.json version and the CHANGELOG top entry diverge)
- Keep README/docs version-agnostic (link to CHANGELOG) so they can't drift
- Rules `.md` 변경 시 CHECKSUMS 재생성: `(cd plugins/common/rules && shasum -a 256 *.md | grep -v CHECKSUMS > CHECKSUMS.sha256)` — 이 매니페스트는 보안 경계가 아니라 우발적 드리프트 감지기다 (verify-done §7이 집합 동등성까지 강제)
- 그 룰에 **해설본 미러**가 있으면(아래 참조) 해설본도 함께 손보고 `scripts/sync-rule-mirror.sh --regenerate`
- Tag **the commit you push as the release**: `git tag -a vX.Y.Z <commit> -m "vX.Y.Z"`,
  then `git push --tags`. Later commits that leave the version untouched (docs, repo
  tooling) are not a new release and do not move the tag. `verify-done.sh §6` fails when
  any past CHANGELOG release lacks a tag — the practice lapsed silently once (20 untagged
  releases between 2.10.4 and 2.12.3), so it is a machine check now, not a convention.
  Two caveats on existing tags: the 2026-08-17 backfill could not recover which commit was
  actually pushed as each old release, so it used the closest approximation — the last
  commit carrying that version; and tags predating v2.11.0 were placed ad hoc and follow
  no single rule. Every tag does point at a commit whose `plugin.json` matches it.
- Run `scripts/verify-done.sh` (green) before claiming a release ready (definition-of-done)

```bash
# Before git commit — update version field:
# plugins/common/.claude-plugin/plugin.json  → "version": "x.y.z"
```

### Distribution & catalog propagation

Two install channels propagate a pushed `main` differently — know which one a user is on:

- **Direct marketplace** (`This-HW/claude-code-kit` → `@claude-code-kit`): reflects `main`
  HEAD **immediately** on `/plugin marketplace update`. This is the "fastest updates" path.
- **Anthropic community catalog** (`anthropics/claude-plugins-community` → `@claude-community`):
  a **read-only mirror synced nightly** from Anthropic's internal review pipeline. Its entry
  is **pinned to a commit SHA**; the pin advances **automatically** as you push to `main`,
  but only after the pipeline re-runs safety screening and the nightly mirror sync — expect
  **~a day, not instant**. You do **NOT** PR the catalog (direct PRs are auto-closed); the
  one-time listing was via `clau.de/plugin-directory-submission`, and **version updates
  need no re-submission**. (Verified 2026-07-29 against the catalog repo README.)
- **Implication**: right after a release, the fix is live on the direct marketplace but the
  community catalog still serves the previous pinned SHA until the next nightly sync. Point
  users who need a fix immediately to the direct marketplace path.

## Contributing

PRs welcome. Checklist:

- [ ] **Consumer-first**: works in an installing user's environment, not just this repo —
      no reliance on the project cwd containing plugin files, no assumption a specific MCP
      server is installed, hooks fail-open when their assumptions don't hold
- [ ] No `mcp__*` tools in any agent `tools:` allowlist (MCP lives in skills — see
      `rules/mcp-usage.md`; absent MCP in an agent allowlist hallucinates, CC #13898)
- [ ] Agent frontmatter has `name`, `description`, `model`, `maxTurns`
- [ ] No forbidden fields: `permissionMode`, `context_cache`, `output_schema`, `next_agents`, inline `hooks`
- [ ] Description includes `MUST USE when:` trigger conditions
- [ ] File-modifying agents have `isolation: worktree`
- [ ] Regular agents have `disallowedTools: [Task]`
- [ ] Skill `description` field is in English
- [ ] Registered in `plugins/common/.claude-plugin/plugin.json`
- [ ] CI passes (JSON valid, frontmatter complete, no forbidden fields, pytest green, no secrets)
