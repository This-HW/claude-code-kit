# Official Marketplace Submission

Submit at: https://platform.claude.com/plugins/submit

> Note: anthropics/claude-plugins-official does not accept external PRs.
> All submissions must go through the web form above.

## Status

- **v2.0.0** tagged and ready — 2026-04-22
- All success criteria met (see `docs/superpowers/specs/2026-04-21-claude-upgrade-design.md`)
- [ ] Submit via web form
- [ ] Await approval

## Submission Info (A Plan: common only)

| Field | Value |
|---|---|
| Plugin Name | `claude-code-kit` |
| Version | `2.0.0` |
| Description | Turn any task into production-ready code. Specialized agents automatically handle planning, implementation, code review, and security scanning for any stack. |
| Source Type | `git-subdir` |
| Repository | `This-HW/claude-code-kit` |
| Path | `plugins/common` |
| Ref | `main` (tag: `v2.0.0`) |
| Category | `development` |
| Homepage | https://github.com/This-HW/claude-code-kit |
| License | MIT |
| Author | This-HW (thisyj.work@gmail.com) |

## Install Command (after approval)

```bash
/plugin install claude-code-kit@claude-plugins-official
```

## What Gets Installed

The `plugins/common` subdirectory contains:
- 33 agents across planning, dev, backend, meta, and review categories
- 12 skills: plan-task, auto-dev, web-research, review, multi-perspective-review, debug, test, agent-creator, skill-creator, mcp-builder, doc-coauthoring, agent-teams
- 91 unit-tested hook scripts (protect-sensitive, auto-format, session-start, utils)
- SubagentStart / SubagentStop / PreCompact lifecycle hooks

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

## v2.0.0 Registry Compliance Checklist

- [x] `homepage`, `repository`, `license`, `author.email` in all plugin.json
- [x] No forbidden frontmatter fields in any agent
- [x] All skill descriptions in English
- [x] All agents have `model` and `maxTurns` fields
- [x] `hooks/hooks.json` uses `${CLAUDE_PLUGIN_ROOT}` paths only
- [x] 91 unit tests passing
- [x] CI validates manifest fields + forbidden fields + pytest
- [x] CHANGELOG.md documents all breaking changes
- [x] README.md updated
