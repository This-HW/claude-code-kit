# claude-code-kit

> Universal Claude Code toolkit — 33 agents + 14 skills for software development

A focused, single-plugin AI agent system built for Claude Code. Covers the full software development lifecycle: planning, implementation, review, testing, and meta-tooling.

**Current version: 2.7.0** — Consolidated to a single, well-tested core plugin (removed 5 untested/frozen domain plugins). Built on native-first foundation, scale-appropriate orchestration, feedback learning loop, loop engineering, and a Definition-of-Done gate. See [CHANGELOG.md](CHANGELOG.md) and [docs/specs/](docs/specs/).

---

## Quick Install

**Prerequisites:** [Claude Code CLI](https://code.claude.com) installed (`claude --version`)

```bash
# Add the marketplace and install (recommended — works today)
/plugin marketplace add This-HW/claude-code-kit
/plugin install claude-code-kit@This-HW/claude-code-kit

# Updating: refresh the marketplace, then the new version is picked up
/plugin marketplace update claude-code-kit
```

> **Official registry:** submission to `claude-plugins-official` is pending Anthropic
> review. Once approved, `/plugin install claude-code-kit@claude-plugins-official`
> will also work. Until then, use the marketplace command above.

## Full Mode (Security Hooks + Auto-format)

```bash
git clone https://github.com/This-HW/claude-code-kit
cd claude-code-kit
./setup.sh
```

Options:

- `./setup.sh --status` — Check setup state
- `./setup.sh --migrate` — Migrate from legacy `.claude/agents/` setup
- `./setup.sh --force` — Reset and re-run setup

---

## Architecture & Concepts

claude-code-kit이 무엇을 어떻게 융합하는지 — 한눈에 보는 설계 원리.

### 설계 철학 — 네이티브 우선, kit은 의견 레이어

> **기술부채의 최대 원천은 Claude Code가 네이티브로 하는 일을 자체 구현으로 중복하는 것이다.**

네이티브 프리미티브(agents·skills·hooks·dynamic workflows·OTEL·memory)는 거의 매주
진화한다. 그래서 이 kit의 가치는 **인프라가 아니라, 그 위에 얹는 "의견이 담긴
에이전트·스킬·규율 레이어"** 다. 관측·위임·훅 실행 같은 인프라는 네이티브에 위임하고,
손으로 만든 대체물은 삭제한다 → zero-debt.

### 네 갈래의 융합

| 갈래 | 무엇을 가져왔나 | kit에서 |
| --- | --- | --- |
| **Claude Code 네이티브** | agents, skills, hooks, dynamic workflow, OTEL, memory | 토대 프리미티브 — 매니페스트 의존성, exec-form 훅, `decision:block` 자동수정, 네이티브 관측 |
| **superpowers 규율** | brainstorming→plan→execute, phase gate, TDD, verification-before-completion | `brainstorming → plan-task → auto-dev` HARD-GATE 체인, Iron Law 검증 |
| **Hermes 피드백 루프** | "메모리·피드백 루프가 코어" | validation 결함 → feedback ledger → 다음 구현 컨텍스트 주입 (학습 루프) |
| **자체 Work 시스템** | 파일 기반 감사 가능 추적 | `docs/works/` Work ID·progress.md·decisions.md |

### Harness × Loop Engineering

두 상보 개념이 kit의 자율성을 만든다:

- **Harness Engineering** — *어디서·무엇으로* 행동하는가. 컨텍스트 주입(session-start),
  도구 큐레이션(per-agent tools), 가드레일(protect-sensitive·stop-validator), Work 메모리.
- **Loop Engineering** — *얼마나 오래·끈질기게* 행동하는가. 승인된 배치를 P0·완료·가드
  전까지 자율 완주. 게이트(설계·사람 멈춤)와 루프(실행·자율)를 분리한다.

### 결합 방식

```
 [설계 게이트 — 사람 승인]              [실행 루프 — 자율 완주]
 brainstorming → plan-task    ──승인──▶  auto-dev 배치 드라이버
 (무엇을 만들지 HARD-GATE)               (TaskList 폴링 + 종료 가드)
                                              │
        ┌─────────────────────────────────────┤ 스케일별 오케스트레이션
        ▼                                     ▼
   Small/Medium: 스킬 주도 플랫 dispatch   Large: 네이티브 ultracode
        │                                     │
        ▼  validation (review + security)     ▼
   continueOnBlock 자동수정 마이크로루프
        │
        ▼  결함 → feedback ledger → 다음 세션 LESSONS 주입  ◀─┐
        └──────────────────── 학습 루프 ──────────────────────┘
```

세부는 SSOT 문서 참조: [CLAUDE.md](CLAUDE.md) (오케스트레이션·규율),
[docs/specs/](docs/specs/) (설계 스펙), `plugins/common/rules/` (규칙).

---

## What's New in 2.7.0

- **Core-only consolidation** — 테스트 0·v2.0.0 이후 동결 상태였던 5개 도메인 플러그인(frontend/infra/ops/data/integration, 33 agents)을 제거. 잘 테스트된 단일 core로 집중 → 유지보수 부채 제거. (이전 상태는 `v2.6.0-with-domains` 태그로 보존)

## What's New in 2.6.0

Native-first foundation + 자체 재구현 제거 (Spec 1~6). 전부 하위호환. 세부: [CHANGELOG.md](CHANGELOG.md).

- **Native foundation** — 매니페스트 `dependencies` 선언, 훅 exec form, Stop 훅 `decision:block` 자동수정, `agent-lifecycle.py` 제거(→네이티브 OTEL 관측)
- **Scale-appropriate orchestration** — Small/Medium 스킬 주도 플랫, Large 네이티브 `ultracode`. `agent-teams` → 네이티브 workflow 가이드
- **Feedback learning loop** — validation 결함을 ledger에 누적 → 다음 세션 `=== LESSONS ===` 주입
- **Loop engineering** — 게이트(설계·사람) vs 루프(실행·자율 완주) 분리, auto-dev 배치 드라이버 + 종료 가드
- **Architecture & Concepts** — 위 "Architecture & Concepts" 섹션에 개념 융합 narrative 추가

## What's New in v2.0.0

- **Official plugin registry compliant** — all manifests meet `claude-plugins-official` marketplace standards (`homepage`, `repository`, `license`, `author.email`)
- **Clean frontmatter** — removed non-standard fields (`permissionMode`, `context_cache`, `output_schema`, `next_agents`, inline `hooks`) from all 66 agents
- **Loop prevention** — `maxTurns` added to all agents (20 for implementation, 10 for exploration/review)
- **CI strengthened** — manifest required-fields check, forbidden-frontmatter check, and pytest step added to CI
- **English skill descriptions** — all skill `description` fields converted to English for correct Claude auto-invocation

---

## What's Included

| Plugin            | Agents | Skills | Description                               |
| ----------------- | ------ | ------ | ----------------------------------------- |
| `claude-code-kit` | 33     | 14     | Core: planning, development, review, meta |

---

## Architecture

### 2-Tier Agent Model

```
Tier 1: plugins/common/  — Core agents for all projects (33 agents)
Tier 2: project-local/   — Project-specific agents (user-defined)
```

### Phase Gate Pattern

All workflows follow a 3-phase gate:

```
Phase 1 (Planning)     → Remove 100% ambiguity via planning agents
Phase 2 (Development)  → Implement based on Phase 1 artifacts
Phase 3 (Validation)   → Parallel review + security scan
```

### Delegation Signal

Every agent ends its response with a structured handoff:

```
---DELEGATION_SIGNAL---
TYPE: DELEGATE_TO | TASK_COMPLETE | NEED_USER_INPUT
TARGET: [agent-name]
REASON: [reason]
CONTEXT: [handoff context]
---END_SIGNAL---
```

### Model Selection

| Model      | Use Case                   | Examples                                                     |
| ---------- | -------------------------- | ------------------------------------------------------------ |
| **Opus**   | Strategy, analysis, review | `clarify-requirements`, `review-code`, `plan-implementation` |
| **Sonnet** | Code implementation, fixes | `implement-code`, `fix-bugs`, `write-tests`                  |
| **Haiku**  | Exploration, quick checks  | `explore-codebase`, `verify-code`, `enforce-structure`       |

### Worktree Isolation

File-modifying agents run in an isolated git worktree to prevent conflicts:

- `implement-code`, `fix-bugs`, `write-tests`
- `write-api-tests`, `write-ui-tests`

---

## Components (Core)

### Key Skills

| Skill                      | Command                     | Description                                                                |
| -------------------------- | --------------------------- | -------------------------------------------------------------------------- |
| `plan-task`                | `/plan-task`                | 5-phase planning pipeline: explore → clarify → journey → logic → implement |
| `auto-dev`                 | `/auto-dev`                 | Full automated development pipeline                                        |
| `web-research`             | `/web-research`             | MCP-powered research: Context7 (docs) + Exa (code) + Tavily (web)          |
| `review`                   | `/review`                   | Code review pipeline: ruff + review-code + security-scan                   |
| `multi-perspective-review` | `/multi-perspective-review` | 3-Round Deliberation: 10 perspectives, consensus-driven                    |
| `doc-coauthoring`          | `/doc-coauthoring`          | AI-assisted documentation authoring and review                             |
| `debug`                    | `/debug`                    | 4-Phase debug: diagnose → fix-bugs → verify-code                           |
| `test`                     | `/test`                     | Run tests and auto-fix failures via verify-code + fix-bugs                 |
| `agent-creator`            | `/agent-creator`            | Generate claude-code-kit plugin agents with correct frontmatter            |
| `skill-creator`            | `/skill-creator`            | Generate claude-code-kit skills with best practices                        |
| `mcp-builder`              | `/mcp-builder`              | Scaffold MCP servers and configure Claude Code integration                 |
| `agent-teams`              | `/agent-teams`              | Large-scale parallel work — routes to native `ultracode` (dynamic workflow) |

### Planning Agents (5 — Opus)

Read-only. No file modifications. Used in Phase 1.

| Agent                   | Description                                                                   |
| ----------------------- | ----------------------------------------------------------------------------- |
| `clarify-requirements`  | Detects ambiguous requests, generates P0/P1/P2 questions                      |
| `analyze-domain`        | DDD-based domain analysis, bounded context identification                     |
| `define-business-logic` | Defines policies, rules, calculations, state transitions (CALC/VAL/STATE/POL) |
| `design-user-journey`   | UX flows, screen design, onboarding, payment processes                        |
| `define-metrics`        | KPI, SLO, SLA, dashboard metric definitions                                   |

### Meta Agents (6 — Opus)

Orchestrate multi-perspective review workflows. No `Bash` access.

| Agent               | Description                                                                                         |
| ------------------- | --------------------------------------------------------------------------------------------------- |
| `facilitator`       | Analyzes what perspectives are needed, assigns agents                                               |
| `facilitator-teams` | Manages Round 0/2/3, integrates facilitator + synthesizer + consensus-builder                       |
| `synthesizer`       | Consolidates Round 1/2 results, identifies conflicts and duplicates                                 |
| `devils-advocate`   | Failure scenario analysis via 4 attack personas (scalability / dependency / maintainability / cost) |
| `consensus-builder` | Conflict analysis across perspectives → Win-Win resolution                                          |
| `impact-analyzer`   | System-wide impact, risk, and development cost of proposed changes                                  |

### Backend Agents (4)

| Agent             | Model  | Description                                                |
| ----------------- | ------ | ---------------------------------------------------------- |
| `design-services` | Opus   | Clean/Hexagonal architecture, microservices, DDD patterns  |
| `implement-api`   | Sonnet | REST/GraphQL API implementation (Express, FastAPI, NestJS) |
| `write-api-tests` | Sonnet | API unit / integration / E2E tests                         |
| `optimize-logic`  | Sonnet | Algorithm optimization, caching, N+1 query fixes           |

### Dev Agents (18)

Core development workflow agents.

| Agent                  | Model  | Description                                                                |
| ---------------------- | ------ | -------------------------------------------------------------------------- |
| `explore-codebase`     | Haiku  | Project structure, dependencies, pattern analysis                          |
| `plan-implementation`  | Opus   | Requirements → tech decisions → task breakdown → risk analysis             |
| `implement-code`       | Sonnet | Code implementation (worktree isolated)                                    |
| `write-tests`          | Sonnet | Unit / integration / E2E tests (worktree isolated)                         |
| `review-code`          | Opus   | Adversarial review via 4 personas: hacker, murphy, future-self, picky-user |
| `fix-bugs`             | Sonnet | Minimal-change bug fixes (worktree isolated)                               |
| `verify-code`          | Haiku  | Type check, lint, build, test execution                                    |
| `security-scan`        | Sonnet | OWASP Top 10, secret exposure, vulnerable component detection              |
| `verify-integration`   | Haiku  | Connection integrity, data flow, version compatibility                     |
| `git-workflow`         | Sonnet | Branches, PRs, commit messages, merge strategies                           |
| `sync-docs`            | Sonnet | API and architecture documentation sync                                    |
| `plan-refactor`        | Opus   | Structural improvement planning, ARCHITECTURE_LIMIT resolution             |
| `analyze-dependencies` | Sonnet | Library versions, security updates                                         |
| `manage-api-versions`  | Opus   | API versioning strategy, migration, backwards compatibility                |
| `analyze-tech-debt`    | Sonnet | Code quality analysis, tech debt prioritization                            |
| `research-external`    | Sonnet | External library / technology / best practice research                     |
| `generate-boilerplate` | Sonnet | Project templates, base structure generation                               |
| `enforce-structure`    | Haiku  | File placement, naming convention compliance                               |

---

## Typical Workflows

### Feature Development

```
clarify-requirements → analyze-domain → design-user-journey → define-business-logic
  → plan-implementation → implement-code → write-tests → verify-code
  → review-code + security-scan (parallel) → fix-bugs → sync-docs
```

### Multi-perspective Review

```
/multi-perspective-review
  → facilitator (assigns perspectives)
  → [devils-advocate + synthesizer + impact-analyzer] (Round 1 parallel)
  → synthesizer (Round 2 consolidation)
  → consensus-builder (Round 3 resolution)
```

### Debug

```
/debug
  → diagnose → fix-bugs → verify-code → (loop until green)
```

---

## Security

- **Hooks:** `protect-sensitive.py` runs on every Edit — blocks commits containing secrets
- **Auto-format:** `auto-format.py` runs after edits (uses ruff for Python)
- **CI:** gitleaks scans all pushes to `main`/`stable`
- **Policy:** Never hardcode API keys, secrets, or internal IPs

---

## Project Structure

```
plugins/
└── common/      — Core agents (33) + skills (14) + rules (12) + hooks
```

The plugin contains:

- `.claude-plugin/plugin.json` — plugin manifest
- `agents/` — agent `.md` files with YAML frontmatter
- `skills/` — skill `.md` files
- `hooks/` — Python hook scripts
- `rules/` — governance rules

---

## Contributing

PRs welcome. Checklist:

- [ ] Agent frontmatter has `name`, `description`, `model`, `maxTurns`
- [ ] Description includes `MUST USE when:` trigger conditions
- [ ] No forbidden fields: `permissionMode`, `context_cache`, `output_schema`, `next_agents`, inline `hooks`
- [ ] File-modifying agents have `isolation: worktree`
- [ ] Regular agents have `disallowedTools: [Task]`
- [ ] Skill `description` field is in English
- [ ] Registered in `plugin.json` (with `homepage`, `repository`, `license`, `author.email`)
- [ ] CI passes (JSON valid, frontmatter complete, no forbidden fields, pytest green, no secrets)

---

## License

MIT
