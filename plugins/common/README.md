# claude-code-kit

> 33 agents + 12 skills for the full software development lifecycle

## Install

```bash
# Via official marketplace
/plugin install claude-code-kit@claude-plugins-official
```

```bash
# Via custom marketplace
/plugin marketplace add This-HW/claude-code-kit
/plugin install claude-code-kit@This-HW/claude-code-kit
```

For domain-specific plugins (frontend, infra, ops, data, integration), see the [full repository](https://github.com/This-HW/claude-code-kit).

## Skills

| Command                     | Description                                     |
| --------------------------- | ----------------------------------------------- |
| `/plan-task`                | Structured task planning with Work system       |
| `/auto-dev`                 | Automated development pipeline                  |
| `/review`                   | Code review: ruff + adversarial review + security scan |
| `/debug`                    | 4-Phase debug pipeline                          |
| `/test`                     | Run tests and auto-fix failures                 |
| `/multi-perspective-review` | 10-perspective deliberation, consensus-driven   |
| `/web-research`             | MCP-powered research (Context7 + Exa + Tavily)  |
| `/doc-coauthoring`          | AI-assisted documentation authoring             |
| `/agent-creator`            | Generate plugin agents with correct frontmatter |
| `/skill-creator`            | Generate plugin skills                          |
| `/mcp-builder`              | Scaffold MCP servers                            |
| `/agent-teams`              | Parallel tasks via Agent Teams (experimental)   |

## Agents

33 agents across planning, development, review, backend, and meta categories.

| Category   | Count | Examples                                                    |
| ---------- | ----- | ----------------------------------------------------------- |
| Planning   | 5     | `clarify-requirements`, `analyze-domain`, `define-business-logic` |
| Dev        | 18    | `implement-code`, `fix-bugs`, `review-code`, `security-scan` |
| Backend    | 4     | `design-services`, `implement-api`, `write-api-tests`       |
| Meta       | 6     | `facilitator`, `devils-advocate`, `consensus-builder`       |

## Hooks (auto-registered)

- **SessionStart** — Injects governance rules + active work context
- **PreToolUse** — Blocks edits containing secrets (`protect-sensitive.py`)
- **PostToolUse** — Auto-formats code after edits (`auto-format.py`, ruff)
- **Stop** — Phase-gate check before session ends

## License

MIT — [github.com/This-HW/claude-code-kit](https://github.com/This-HW/claude-code-kit)
