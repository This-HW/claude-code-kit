# Official Marketplace Submission

Submit at: https://clau.de/plugin-directory-submission

> Note: anthropics/claude-plugins-official does not accept external PRs.
> All submissions must go through the web form above.

## Submission Info (A Plan: common only)

| Field | Value |
|---|---|
| Plugin Name | `claude-code-kit` |
| Description | Universal AI toolkit: 33 agents + 12 skills for planning, development, code review, and multi-agent workflows. |
| Source Type | `git-subdir` |
| Repository | `This-HW/claude-code-kit` |
| Path | `plugins/common` |
| Ref | `main` |
| Category | `development` |
| Homepage | https://github.com/This-HW/claude-code-kit |
| License | MIT |
| Author | This-HW |

## Install Command (after approval)

```bash
/plugin install claude-code-kit@claude-plugins-official
```

## What Gets Installed

The `plugins/common` subdirectory contains:
- 33 agents across planning, dev, backend, meta, and review categories
- 12 skills: plan-task, auto-dev, web-research, review, multi-perspective-review, debug, test, agent-creator, skill-creator, mcp-builder, doc-coauthoring, agent-teams

## Domain Plugins (custom marketplace only)

Users wanting domain-specific plugins can add the custom marketplace:

```bash
/plugin marketplace add This-HW/claude-code-kit
/plugin install claude-code-kit-ops@This-HW/claude-code-kit
/plugin install claude-code-kit-infra@This-HW/claude-code-kit
/plugin install claude-code-kit-data@This-HW/claude-code-kit
/plugin install claude-code-kit-frontend@This-HW/claude-code-kit
/plugin install claude-code-kit-integration@This-HW/claude-code-kit
```
