# Marketplace Submission & Community Listing

Submit at: https://platform.claude.com/plugins/submit

> Note: 외부 제출의 도착지는 **community 카탈로그**(`anthropics/claude-plugins-community`)다.
> 위 웹 폼으로 제출하면 스크리닝 후 community 카탈로그에 등재된다.
> `anthropics/claude-plugins-official`은 Anthropic 자체 큐레이션 전용으로 외부
> PR/신청 경로가 없다 — 이 문서의 "제출"은 전부 community 등재를 향한다.

## Status

- **v2.7.0** tagged and ready — 2026-06-14 (core-only consolidation + native foundation + git-subdir distribution)
- Recovery point before consolidation: tag `v2.6.0-with-domains`
- [x] Submit via web form — 2026-06-14
- [x] **등재 확인** — 2026-07-07: `anthropics/claude-plugins-community` 카탈로그
  (당시 2,199개)에 `claude-code-kit` 등재 확인.
- [x] **pin 자동 전진 메커니즘 실측 확정** — 2026-07-07, 카탈로그 레포 커밋 히스토리 분석:
  - 카탈로그는 `bump(<plugin>): old → new` 커밋(자동 PR)으로 기존 항목 pin을 전진시킨다.
    우리 항목 실례: `bump(claude-code-kit): 0a5629e0 → d7f80c92` (2026-07-03T17:58Z, #754).
  - 배치 주기: **매일 ~17:00–18:30 UTC** (07-02·03·04·06 관측; 07-05 스킵 — 매일 보장은 아님).
  - 버전 무변경 커밋(예: chore)은 bump되지 않는 것으로 관측됨 — 릴리스 체크리스트의
    버전 범프 규율이 카탈로그 전파의 전제.
  - 재제출 불필요. 즉시성이 필요하면 직접 마켓플레이스 경로(`This-HW/claude-code-kit`).

> 확인 방법: 아래 raw 카탈로그에서 `claude-code-kit` 검색.
> https://raw.githubusercontent.com/anthropics/claude-plugins-community/main/.claude-plugin/marketplace.json

## Submission Info

| Field | Value |
|---|---|
| Plugin Name | `claude-code-kit` |
| Submitted Version | `2.7.0` (제출 시점 고정 기록 — 현재 버전은 CHANGELOG 참조) |
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

## Install Commands

등재 경로는 **community 카탈로그**다. `@` 뒤는 마켓플레이스 `name` 필드
(repo 이름 아님 — community 카탈로그의 name은 `claude-community`로 실측 확인, 2026-07-07):

```bash
# Path 1 — community 카탈로그 (등재 경로, sync 주기만큼 지연)
/plugin marketplace add anthropics/claude-plugins-community
/plugin install claude-code-kit@claude-community

# Path 2 — 직접 마켓플레이스 (name: claude-code-kit, 즉시 업데이트)
/plugin marketplace add This-HW/claude-code-kit
/plugin install claude-code-kit@claude-code-kit
/plugin marketplace update claude-code-kit   # 업데이트
```

## What Gets Installed

`plugins/common` 서브디렉토리 (git-subdir로 sparse-clone):

- **33 agents** — planning, dev, backend, meta, review 카테고리
- **16 skills**: plan-task, auto-dev, web-research, review, multi-perspective-review, debug, test, agent-creator, skill-creator, mcp-builder, doc-coauthoring, agent-teams, brainstorming, using-claude-code-kit, native-watch, self-improve
- **13 rules** — agent-system, planning-protocol, loop-engineering, definition-of-done, feedback-loop 등 (session-start가 주입)
- **Hooks** (4 events): SessionStart, PreToolUse, PostToolUse, Stop
  - scripts: protect-sensitive, auto-format, session-start, stop-validator, feedback_ledger, utils
- **220+ unit tests** (hooks + evals 러너 — 제출 시점 v2.7.0 기록은 112)

> 단일 core 플러그인. 도메인 플러그인(frontend/infra/ops/data/integration)은 2.7.0에서
> 제거됨 (테스트 0·동결). 필요 시 `v2.6.0-with-domains` 태그에서 복원 가능.

## v2.7.0 Registry Compliance Checklist

- [x] `homepage`, `repository`, `license`, `author.email` in plugin.json
- [x] No forbidden frontmatter fields in any agent
- [x] All skill descriptions in English
- [x] All agents have `model` and `maxTurns` fields
- [x] `hooks/hooks.json` uses exec form (`command` + `args[]`) with `${CLAUDE_PLUGIN_ROOT}` paths
- [x] unit tests passing (v2.7.0 제출 시점 112 — 현재 수치는 CHANGELOG 참조)
- [x] CI validates manifest fields + forbidden fields + pytest (PRs to main + stable)
- [x] CHANGELOG.md documents all changes
- [x] README.md updated (single-plugin, 2-tier)
- [x] `marketplace.json` source = `git-subdir` (remote/versioned distribution)
- [x] `scripts/verify-done.sh` green (definition-of-done gate)
