---
name: using-claude-code-kit
description: Session-start meta-skill. Establishes workflow discipline and skill invocation rules for claude-code-kit.
---

# Using claude-code-kit

<EXTREMELY_IMPORTANT>
If there is even a 1% chance a skill applies to what you are doing, you MUST invoke it before any response or action.

This is not optional. This is not negotiable.
</EXTREMELY_IMPORTANT>

## Workflow Chain

For any new feature, fix, or task:

```
brainstorming → plan-task → auto-dev
```

- **brainstorming** — design and spec BEFORE any planning or code (HARD-GATE)
- **plan-task** — structured planning BEFORE any implementation (HARD-GATE)
- **auto-dev** — implementation + validation pipeline

Skipping a stage means shipping unverified work.

## Skill Trigger Map

| Situation | Skill |
|-----------|-------|
| New feature / anything creative | `brainstorming` first |
| Requirements unclear | `claude-code-kit:plan-task` |
| Ready to implement a plan | `claude-code-kit:auto-dev` |
| Bug / error | `claude-code-kit:debug` |
| Tests needed | `claude-code-kit:test` |
| Code review | `claude-code-kit:review` |
| Research needed | `claude-code-kit:web-research` |

## Agent Selection

| Keyword | Agent |
|---------|-------|
| "조사", "리서치" | `research-external` |
| "계획", "설계" | `plan-implementation` |
| "구현", "코드 작성" | `implement-code` |
| "리뷰", "검토" | `review-code` |
| "탐색", "파악" | `explore-codebase` |
| "테스트" | `write-tests` |
| "수정", "버그" | `fix-bugs` |

## Red Flags (rationalization stoppers)

| Thought | Reality |
|---------|---------|
| "이건 간단한 작업이야" | 간단해도 phase gate는 필수 |
| "컨텍스트 먼저 파악하고" | 스킬 체크가 먼저 |
| "스킬은 과한 것 같아" | 스킬이 존재하면 사용 |
| "이미 알고 있어" | 스킬은 진화한다. 항상 invoke |
| "이건 개발 작업이 아니야" | 행동 = 작업. 체크 필수 |

## Work System Detection

`docs/works/` 폴더가 있으면: Work ID 기반 추적 활성화
없으면: 파일 없이 파이프라인만 실행 (fallback mode)
