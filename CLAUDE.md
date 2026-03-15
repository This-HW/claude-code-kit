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
├── common/     — Core agents (52) + skills (19)
├── frontend/   — Frontend agents (4) + skills (1)
├── infra/      — Infrastructure agents (7) + skills (1)
├── ops/        — Operations agents (14) + skills (4)
├── data/       — Data agents (4) + skills (3)
└── integration/ — Integration agents (4)
```

## Key Skills

| Skill                    | Command                     | Description                    |
| ------------------------ | --------------------------- | ------------------------------ |
| plan-task                | `/plan-task`                | Structured task planning       |
| auto-dev                 | `/auto-dev`                 | Automated development pipeline |
| review                   | `/review`                   | Adversarial code review        |
| multi-perspective-review | `/multi-perspective-review` | Multi-expert review            |

## Contributing

PRs welcome. See [CONTRIBUTING.md](CONTRIBUTING.md).
