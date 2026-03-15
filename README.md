# claude-code-kit

> Universal Claude Code toolkit — 52 agents + 19 skills for software development

## Quick Install (3 commands)

**Prerequisites:** [Claude Code CLI](https://code.claude.com) installed (`claude --version`)

```bash
claude plugin marketplace add grimm/claude-code-kit
claude plugin install claude-code-kit@stable --scope user
# Done! Agents and skills are ready.
```

## What's Included

| Plugin                        | Agents | Skills | Description                               |
| ----------------------------- | ------ | ------ | ----------------------------------------- |
| `claude-code-kit`             | 52     | 19     | Core: planning, development, review, meta |
| `claude-code-kit-frontend`    | 4      | 1      | React, Vue, UI/UX                         |
| `claude-code-kit-infra`       | 7      | 1      | Terraform, Docker, Kubernetes             |
| `claude-code-kit-ops`         | 14     | 4      | Deploy, monitor, incident response        |
| `claude-code-kit-data`        | 4      | 3      | Database design, query optimization       |
| `claude-code-kit-integration` | 4      | 0      | Webhook, Slack, CI/CD                     |

## Domain Plugins

Install specific domains as needed:

```bash
claude plugin install claude-code-kit-frontend@stable --scope user
claude plugin install claude-code-kit-infra@stable --scope user
claude plugin install claude-code-kit-ops@stable --scope user
claude plugin install claude-code-kit-data@stable --scope user
claude plugin install claude-code-kit-integration@stable --scope user
```

## Full Mode (Power Users)

For security hooks + ruff + pre-commit:

```bash
git clone https://github.com/grimm/claude-code-kit
cd claude-code-kit
./setup.sh
```

Options:

- `./setup.sh --list` — Show available domain plugins
- `./setup.sh --status` — Check setup state
- `./setup.sh --full` — Include additional workflow hooks
- `./setup.sh --migrate` — Migrate from legacy .claude/agents/ setup
- `./setup.sh --force` — Reset and re-run setup

## License

MIT
