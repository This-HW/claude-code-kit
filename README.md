# claude-code-kit

> Universal Claude Code toolkit — 66 agents + 22 skills for software development

A structured, multi-domain AI agent system built for Claude Code. Covers the full software development lifecycle: planning, implementation, review, testing, infrastructure, operations, and more.

---

## Quick Install

**Prerequisites:** [Claude Code CLI](https://code.claude.com) installed (`claude --version`)

```bash
# Core toolkit (common domain)
/plugin marketplace add This-HW/claude-code-kit
/plugin install claude-code-kit@This-HW/claude-code-kit

# Add domain plugins as needed
/plugin install claude-code-kit-frontend@This-HW/claude-code-kit
/plugin install claude-code-kit-infra@This-HW/claude-code-kit
/plugin install claude-code-kit-ops@This-HW/claude-code-kit
/plugin install claude-code-kit-data@This-HW/claude-code-kit
/plugin install claude-code-kit-integration@This-HW/claude-code-kit
```

## Full Mode (Security Hooks + Auto-format)

```bash
git clone https://github.com/This-HW/claude-code-kit
cd claude-code-kit
./setup.sh
```

Options:

- `./setup.sh --list` — Show available domain plugins
- `./setup.sh --status` — Check setup state
- `./setup.sh --migrate` — Migrate from legacy `.claude/agents/` setup
- `./setup.sh --force` — Reset and re-run setup

---

## What's Included

| Plugin                        | Agents | Skills | Description                               |
| ----------------------------- | ------ | ------ | ----------------------------------------- |
| `claude-code-kit`             | 33     | 12     | Core: planning, development, review, meta |
| `claude-code-kit-frontend`    | 4      | 1      | React, Vue, UI/UX                         |
| `claude-code-kit-infra`       | 7      | 1      | Terraform, Docker, Kubernetes             |
| `claude-code-kit-ops`         | 14     | 5      | Deploy, monitor, incident response        |
| `claude-code-kit-data`        | 4      | 3      | Database design, query optimization       |
| `claude-code-kit-integration` | 4      | 0      | Webhook, Slack, CI/CD triggers            |

---

## Architecture

### 3-Tier Agent Model

```
Tier 1: plugins/common/    — Core agents for all projects (33 agents)
Tier 2: plugins/{domain}/  — Domain-specific agents (33 agents)
Tier 3: project-local/     — Project-specific agents (user-defined)
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

## Common Domain (Core)

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
| `agent-teams`              | `/agent-teams`              | Parallel large tasks via Agent Teams (experimental, Opus 4.6 required)     |

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

## Frontend Domain

### Agents (4)

| Agent               | Model  | Description                                              |
| ------------------- | ------ | -------------------------------------------------------- |
| `design-components` | Opus   | Atomic Design, design systems, component API design      |
| `implement-ui`      | Sonnet | React / Next.js / Vue component implementation           |
| `write-ui-tests`    | Sonnet | Jest, Playwright, Cypress tests (worktree isolated)      |
| `optimize-ux`       | Sonnet | Core Web Vitals, accessibility, performance improvements |

### Skills (1)

| Skill            | Command           | Description                                             |
| ---------------- | ----------------- | ------------------------------------------------------- |
| `webapp-testing` | `/webapp-testing` | E2E automation via Playwright MCP (login/payment flows) |

---

## Infrastructure Domain

### Agents (7)

| Agent                    | Model  | Description                                                 |
| ------------------------ | ------ | ----------------------------------------------------------- |
| `explore-infrastructure` | Haiku  | Cloud resources, network, security configuration analysis   |
| `plan-infrastructure`    | Sonnet | Cloud architecture, resource planning, cost estimation      |
| `write-iac`              | Sonnet | Terraform / CloudFormation / Ansible IaC authoring          |
| `setup-containers`       | Sonnet | Docker / Kubernetes container setup                         |
| `configure-cicd`         | Sonnet | GitHub Actions / GitLab CI / Jenkins pipeline configuration |
| `security-compliance`    | Opus   | Regulatory requirements, audits, security policies          |
| `verify-infrastructure`  | Haiku  | Deployment state, health checks                             |

### Skills (1)

| Skill   | Command  | Description                                                |
| ------- | -------- | ---------------------------------------------------------- |
| `infra` | `/infra` | Full pipeline: explore → plan → implement → verify → apply |

---

## Operations Domain

### Agents (14)

| Agent              | Model  | Description                                           |
| ------------------ | ------ | ----------------------------------------------------- |
| `deploy`           | Sonnet | Blue-Green / Canary / Rolling deployment execution    |
| `monitor`          | Sonnet | Metrics, logs, alert configuration and analysis       |
| `diagnose`         | Opus   | Root cause analysis and problem diagnosis             |
| `respond-incident` | Sonnet | Incident handling, escalation, logging                |
| `rollback`         | Sonnet | Deployment rollback, data recovery, state restoration |
| `postmortem`       | Opus   | Failure analysis, lessons learned, improvement plans  |
| `scale`            | Sonnet | Resource scaling, auto-scaling, capacity management   |
| `optimize-costs`   | Sonnet | Cloud cost analysis and optimization                  |
| `manage-runbooks`  | Sonnet | Operational procedure documentation                   |
| `schedule-task`    | Sonnet | Batch / scheduled job management                      |
| `workflow-runner`  | Sonnet | Automated workflow execution and coordination         |
| `self-heal`        | Sonnet | Self-healing mechanisms, auto-restart                 |
| `track-sla`        | Sonnet | SLA monitoring and violation detection                |
| `event-trigger`    | Sonnet | Event-driven automation triggers                      |

### Skills (5)

| Skill               | Command              | Description                                  |
| ------------------- | -------------------- | -------------------------------------------- |
| `alert-setup`       | `/alert-setup`       | Alert configuration automation               |
| `deploy`            | `/deploy`            | Deployment automation pipeline               |
| `incident-response` | `/incident-response` | Incident management workflow                 |
| `loop`              | `/loop`              | Recurring task loop (interval-based polling) |
| `monitor`           | `/monitor`           | Monitoring setup and configuration           |

---

## Data Domain

### Agents (4)

| Agent              | Model  | Description                                       |
| ------------------ | ------ | ------------------------------------------------- |
| `design-database`  | Opus   | Schema design, normalization, index strategy      |
| `analyze-data`     | Sonnet | Data exploration, statistics, pattern recognition |
| `migrate-data`     | Sonnet | Schema changes, data migration, validation        |
| `optimize-queries` | Sonnet | Query performance analysis, index optimization    |

### Skills (3)

| Skill          | Command         | Description                                                |
| -------------- | --------------- | ---------------------------------------------------------- |
| `data-modeler` | `/data-modeler` | ORM entity modeling (Prisma, TypeORM, Drizzle, SQLAlchemy) |
| `db-architect` | `/db-architect` | SQL schema design (Opus)                                   |
| `db-query`     | `/db-query`     | Query optimization analysis                                |

---

## Integration Domain

### Agents (4)

| Agent              | Model  | Description                                 |
| ------------------ | ------ | ------------------------------------------- |
| `manage-webhooks`  | Sonnet | Webhook setup, monitoring, retry management |
| `notify-team`      | Sonnet | Slack / Email / Teams notification dispatch |
| `sync-issues`      | Sonnet | Jira / GitHub Issues synchronization        |
| `trigger-pipeline` | Sonnet | CI/CD pipeline execution triggers           |

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

### Infrastructure Change

```
/infra
  → explore-infrastructure → plan-infrastructure → write-iac
  → setup-containers / configure-cicd → verify-infrastructure
```

### Incident Response

```
/incident-response
  → diagnose → respond-incident → rollback (if needed)
  → postmortem → manage-runbooks
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
├── common/      — Core agents (33) + skills (12) + rules (8) + hooks
├── frontend/    — Frontend agents (4) + skills (1)
├── infra/       — Infrastructure agents (7) + skills (1)
├── ops/         — Operations agents (14) + skills (5)
├── data/        — Data agents (4) + skills (3)
└── integration/ — Integration agents (4)
```

Each domain contains:

- `.claude-plugin/plugin.json` — plugin manifest
- `agents/` — agent `.md` files with YAML frontmatter
- `skills/` — skill `.md` files
- `hooks/` — Python hook scripts (common only)
- `rules/` — governance rules (common only)

---

## Contributing

PRs welcome. Checklist:

- [ ] Agent frontmatter has `name`, `description`, `model`
- [ ] Description includes `MUST USE when:` trigger conditions
- [ ] File-modifying agents have `isolation: worktree`
- [ ] Regular agents have `disallowedTools: [Task]`
- [ ] Registered in domain `plugin.json`
- [ ] CI passes (JSON valid, frontmatter complete, no secrets)

---

## License

MIT
