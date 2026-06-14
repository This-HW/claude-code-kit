# Official Marketplace Submission

Submit at: https://platform.claude.com/plugins/submit

> Note: `anthropics/claude-plugins-official` does not accept external PRs.
> All submissions must go through the web form above, then await Anthropic review/approval.

## Status

- **v2.7.0** tagged and ready — 2026-06-14 (core-only consolidation + native foundation + git-subdir distribution)
- Recovery point before consolidation: tag `v2.6.0-with-domains`
- [x] Submit via web form — 2026-06-14
- [ ] Await approval (Anthropic 심사 대기)

## Submission Info

| Field | Value |
|---|---|
| Plugin Name | `claude-code-kit` |
| Version | `2.7.0` |
| Description | Turn any task into production-ready code. Specialized agents automatically handle planning, implementation, code review, and security scanning for any stack. |
| Source Type | `git-subdir` |
| Repository | `This-HW/claude-code-kit` |
| Path | `plugins/common` |
| Ref | `main` (tag: `v2.7.0`) |
| Category | `development` |
| Homepage | https://github.com/This-HW/claude-code-kit |
| License | MIT |
| Author | This-HW (thisyj.work@gmail.com) |

> 참고: `marketplace.json`의 source가 이미 `git-subdir`로 설정되어 있어, 제출 정보와
> 실제 배포 구성이 일치한다.

## Install Command (after approval)

```bash
/plugin install claude-code-kit@claude-plugins-official
```

승인 전까지는 커스텀 마켓플레이스로 설치/업데이트한다:

```bash
/plugin marketplace add This-HW/claude-code-kit
/plugin install claude-code-kit@claude-code-kit
/plugin marketplace update claude-code-kit   # 업데이트
```

## What Gets Installed

`plugins/common` 서브디렉토리 (git-subdir로 sparse-clone):

- **33 agents** — planning, dev, backend, meta, review 카테고리
- **14 skills**: plan-task, auto-dev, web-research, review, multi-perspective-review, debug, test, agent-creator, skill-creator, mcp-builder, doc-coauthoring, agent-teams, brainstorming, using-claude-code-kit
- **12 rules** — agent-system, planning-protocol, loop-engineering, definition-of-done, feedback-loop 등 (session-start가 주입)
- **Hooks** (4 events): SessionStart, PreToolUse, PostToolUse, Stop
  - scripts: protect-sensitive, auto-format, session-start, stop-validator, feedback_ledger, utils
- **112 unit tests** (hooks)

> 단일 core 플러그인. 도메인 플러그인(frontend/infra/ops/data/integration)은 2.7.0에서
> 제거됨 (테스트 0·동결). 필요 시 `v2.6.0-with-domains` 태그에서 복원 가능.

## v2.7.0 Registry Compliance Checklist

- [x] `homepage`, `repository`, `license`, `author.email` in plugin.json
- [x] No forbidden frontmatter fields in any agent
- [x] All skill descriptions in English
- [x] All agents have `model` and `maxTurns` fields
- [x] `hooks/hooks.json` uses exec form (`command` + `args[]`) with `${CLAUDE_PLUGIN_ROOT}` paths
- [x] 112 unit tests passing
- [x] CI validates manifest fields + forbidden fields + pytest (PRs to main + stable)
- [x] CHANGELOG.md documents all changes
- [x] README.md updated (single-plugin, 2-tier)
- [x] `marketplace.json` source = `git-subdir` (remote/versioned distribution)
- [x] `scripts/verify-done.sh` green (definition-of-done gate)
