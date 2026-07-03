# Agent System Rules

Agents are auto-discovered from the plugin directory — check the available
subagent_type list before calling Task (there is no manifest to consult).
NEVER use general-purpose subagent when a specialized agent exists.
ALWAYS specify subagent_type explicitly — no general-purpose fallback.

## Model Selection

- Opus: strategy/analysis/review (clarify-requirements, review-code)
- Sonnet: code implementation/fixes (implement-code, fix-bugs, write-tests)
- Haiku: exploration/verification/simple tasks (explore-codebase, verify-code, verify-integration)

## Agent Selection by Keyword

- "조사", "리서치" → research-external
- "계획", "설계" → plan-implementation
- "구현", "코드 작성" → implement-code
- "리뷰", "검토" → review-code
- "탐색", "파악" → explore-codebase
- "테스트" → write-tests
- "수정", "버그" → fix-bugs

## general-purpose Allowed Only When

- No specialized agent exists for the task
- Task spans multiple domains simultaneously

## Delegation Signal Format

Canonical definition (SSOT): `agent-delegation-chain.md`. Every agent ends output
with this block (TYPE values must match the canonical set):

```
---DELEGATION_SIGNAL---
TYPE: DELEGATE_TO | TASK_COMPLETE | NEED_USER_INPUT | NEED_CLARIFICATION
TARGET: [agent-name]        # DELEGATE_TO 일 때만
REASON: [reason]
CONTEXT: [handoff context]
---END_SIGNAL---
```

## isolation: worktree

ALWAYS set `isolation: worktree` for file-modifying agents: implement-code, fix-bugs, write-tests, write-api-tests, implement-api, generate-boilerplate, sync-docs, optimize-logic.
NEVER set `isolation: worktree` on read-only agents: explore-codebase, review-code, plan-implementation.
Merge-back protocol: see parallel-worktree.md (verify-then-exit, sequential merge, conflict → git-workflow).

## disallowedTools Policy

- Meta agents (facilitator, synthesizer, etc. — 6 total): disallowedTools: [Bash]
- Regular agents (implement-code, fix-bugs, etc.): disallowedTools: [Task]
- Skills: no restriction (main Claude runs them via Task)

## Phase Gate

ALWAYS complete each phase before proceeding to the next.

Phase 1 → Phase 2 (Planning → Dev):

- P0 ambiguity = 0, business rules defined, data model defined, user flows clear

Phase 2 → Phase 3 (Dev → Validation):

- Build passes, core logic tests ≥80%, lint/type checks pass

Phase 3 → Complete (Validation → Done):

- review-code Must Fix = 0, Critical security issues = 0, integration tests pass
