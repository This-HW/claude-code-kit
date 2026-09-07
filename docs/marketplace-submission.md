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
  - 배치 주기(2026-07 관측): 매일 ~17:00–18:30 UTC (07-02·03·04·06 관측; 07-05 스킵).
    **이 관측은 2026-09-08 재실측에서 무너졌다 — 아래 절 참고.**
  - 버전 무변경 커밋(예: chore)은 bump되지 않는 것으로 관측됨 — 릴리스 체크리스트의
    버전 범프 규율이 카탈로그 전파의 전제.
  - 재제출 불필요. 즉시성이 필요하면 직접 마켓플레이스 경로(`This-HW/claude-code-kit`).

> 확인 방법: 아래 raw 카탈로그에서 `claude-code-kit` 검색.
> https://raw.githubusercontent.com/anthropics/claude-plugins-community/main/.claude-plugin/marketplace.json

## 2026-09-08 재실측 — pin 자동 전진을 **신뢰할 수 없다**

위 2026-07 관측(매일 배치, 재제출 불필요)은 **더 이상 성립하지 않는다.** 오늘 실측:

| 관측 | 값 |
| --- | --- |
| 우리 항목 마지막 bump | **2026-08-09** — `d0a5752c → 292ba07e` (#1961), 즉 **v2.12.3** |
| 그 이후 미반영 릴리스 | 2.13.0 → **2.20.0** (164 커밋) |
| `marketplace.json` 커밋 **300개** 중 우리 항목 bump | **1건**(위 8/9 건) |
| 카탈로그 미러 레포 최종 커밋(경로 무관) | **2026-08-24** — 이후 전체가 조용 |
| 카탈로그 README 의 서술 | 여전히 *"synced nightly"* |

**두 가지가 겹쳐 있다.** 8/9~8/24 사이 카탈로그는 다른 항목(`qodo`·`inkbox` 등)을 bump
하고 있었으므로 **그 구간엔 우리만 누락**됐고, 8/24 이후로는 **미러 전체가 멈췄다.**

**원인은 이 레포에서 판정할 수 없다** — 스크리닝 실패인지, 큐 지연인지, 파이프라인
중단인지 밖에서는 구분이 안 된다. `docs/conventions/warning-signal.md` 원칙대로,
관측할 수단이 없는 것을 추측으로 채우지 않고 **관측된 것만 적는다.**

**실무 결론**: 릴리스 안내에 **"하루면 전파된다"고 쓰지 마라.** 전파 시점을 약속할 근거가
없다. 즉시성이 필요한 사용자는 **직접 마켓플레이스**로 보낸다.

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

## v3.0.0 개명 — **재제출이 필요하다** (27-6)

> 위 "재제출 불필요"는 **버전 갱신**에 대한 것이다. **이름 변경은 다르다.**

카탈로그 항목은 `claude-code-kit` 이라는 **이름으로 등재**돼 있고, pin 자동 전진은
`bump(<plugin>): old → new` 로 **같은 이름 항목의 커밋만** 옮긴다. 이름이 바뀌면
자동 전진 대상이 아니므로 **새 리스팅으로 제출해야 한다.**

### 사람이 해야 하는 것 (자동화 불가 — 웹 폼)

1. https://platform.claude.com/plugins/submit 에서 **`hiway-kit` 으로 신규 제출**
   - 저장소: `This-HW/claude-code-kit` (레포명은 바뀌지 않았다)
   - 플러그인 이름: `hiway-kit`
   - 경로: `plugins/common`
2. 등재 확인 후, 구 항목(`claude-code-kit`)에 대한 처리를 문의한다 —
   카탈로그는 읽기 전용 미러라 **직접 PR 로 지울 수 없다**(직접 PR 은 자동 close 된다).

### 그때까지의 상태 (정직하게)

- **직접 마켓플레이스**(`This-HW/claude-code-kit` → `@hiway-kit`)는 **즉시** 동작한다.
  `main` HEAD 를 반영하므로 재설치하면 v3.0.0 이 온다.
- **커뮤니티 카탈로그**는 구 이름 `claude-code-kit` 을 **마지막 pin(v2.19.0 이전)으로 계속 서빙**한다.
  그 경로로 설치한 사용자는 개명을 **자동으로 알 수 없다** — CHANGELOG 의 재설치 절차가
  유일한 안내다.
- 이 비대칭은 개명의 **불가피한 비용**이다. 프로브(Q3)가 확인한 대로 `enabledPlugins` 이행이
  수동이므로, 어떤 경로로도 자동 승계는 없다.

### 왜 별칭을 두지 않았나

D-52 참조. 프로브 실측: 구·신 이름이 공존하면 스킬이 **경고 없이 중복 로드**된다.
"기한 있는 폐기 별칭"은 그 중복을 기간만큼 보장하는 것이므로 설계로 성립하지 않는다.
