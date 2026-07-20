---
name: using-claude-code-kit
description: Session-start meta-skill. claude-code-kit-specific workflow chain, agent map, and Work system rules (generic skill-invocation discipline is shared with superpowers when present).
---

# Using claude-code-kit

> **범용 스킬 규율**(스킬 우선 invoke · 합리화 차단 등)은 `superpowers:using-superpowers`와
> **공유**합니다. superpowers를 함께 쓰면 그 규율을 따르세요 — 여기서 중복 서술하지 않습니다.
> 아래는 **claude-code-kit 전용 추가분**입니다.
>
> _standalone(스킬만 설치, superpowers 없음) 자급 규율:_ **행동 전, 적용 가능한 스킬이
> 1%라도 있으면 먼저 invoke한다.** 게이트/루프/완료 규율은 `rules/`가 자동 주입한다
> (planning-protocol · loop-engineering · definition-of-done · feedback-loop).

## Workflow Chain (kit)

```
brainstorming → plan-task → auto-dev
```

- **brainstorming** — 설계·스펙 (HARD-GATE)
- **plan-task** — 구조화 계획 (HARD-GATE)
- **auto-dev** — 구현 + 검증 파이프라인

> 완료 선언 전 `scripts/verify-done.sh` 게이트 통과 필수 (definition-of-done).

## Skill Trigger Map

| 상황 | 스킬 |
|------|------|
| 새 기능 / 창작 | `brainstorming` 먼저 |
| 요구사항 불명확 | `claude-code-kit:plan-task` |
| 계획 구현 준비 | `claude-code-kit:auto-dev` |
| 버그 / 에러 | `claude-code-kit:debug` |
| 테스트 필요 | `claude-code-kit:test` |
| 코드 리뷰 | `claude-code-kit:review` |
| 리서치 필요 | `claude-code-kit:web-research` |
| 네이티브 흡수 점검(정기) | `claude-code-kit:native-watch` |
| 반복 결함 근원 개선 | `claude-code-kit:self-improve` |

## Agent Selection (kit 고유 — superpowers엔 없음)

| 키워드 | 에이전트 |
|--------|----------|
| "조사", "리서치" | `research-external` |
| "계획", "설계" | `plan-implementation` |
| "구현", "코드 작성" | `implement-code` |
| "리뷰", "검토" | `review-code` |
| "탐색", "파악" | `explore-codebase` |
| "테스트" | `write-tests` |
| "수정", "버그" | `fix-bugs` |

## Work System Detection

`docs/works/` 폴더가 있으면: Work ID 기반 추적 활성화
없으면: 파일 없이 파이프라인만 실행 (fallback mode)

## 메모리 MCP와 함께 쓸 때 (interop, 있을 때만)

세션에 **메모리형 MCP 툴**(`recall`/`search`/`remember` 류 — 서버 이름 불문)이 보이면:

- **계획 전 recall**: brainstorming/plan-task 진입 시 현재 작업 주제로 한 번 회상해
  과거 결정·교훈을 컨텍스트에 반영한다.
- **완료 후 remember**: 작업 완료(DoD 통과) 시 재사용 가치가 있는 결정·패턴을
  간결히 저장한다 (통과 사실 나열이 아니라 미래 세션이 쓸 교훈만).
- **없으면 무시**: 메모리 MCP 부재 시 이 절은 완전히 스킵 — 어떤 서버도 가정하지
  않는다 (fail-open, consumer-first).

## superpowers와 함께 쓸 때 (interop)

- **범용 지휘자 = `using-superpowers`** (스킬 규율). **kit = 에이전트·Work·체인·native/loop/DoD 델타.**
- 겹치는 스킬(brainstorming·debug·review·test·plans·verification)은 **한 네임스페이스만** 명시 invoke. 한 작업에 두 체인 동시 적용 금지.
- superpowers 고유 강점만 보완 사용: `test-driven-development`, `subagent-driven-development`, `dispatching-parallel-agents`, `writing-skills`.
- 시너지: kit `definition-of-done`(기계 게이트) + superpowers `verification-before-completion`(원칙)은 상호보강 — 함께 권장.
