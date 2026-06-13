# Agent Delegation Chain Rules

NEVER allow subagents to call other subagents.
ALWAYS have main Claude manage the delegation chain directly.

> 근거: 네이티브 중첩 서브에이전트가 가능해도, 우리 스케일에서 leaf 중첩은 성능 이득
> 없이 예측불가능성 부채만 더한다. 대규모 병렬은 네이티브 `ultracode`로 위임한다
> (Spec 2 / W-006, `CLAUDE.md` → Orchestration Model).

## Canonical Delegation Signal Format (SSOT)

모든 에이전트는 출력 끝에 아래 블록 하나만 사용한다. 이 형식이 표준이며, 다른 문서는
이 정의를 참조한다.

```
---DELEGATION_SIGNAL---
TYPE: DELEGATE_TO | TASK_COMPLETE | NEED_USER_INPUT | NEED_CLARIFICATION
TARGET: [agent-name]        # TYPE=DELEGATE_TO 일 때만
REASON: [한 줄 이유]
CONTEXT: [다음 에이전트로 넘길 핸드오프 컨텍스트]
---END_SIGNAL---
```

- 정확히 이 구분자(`---DELEGATION_SIGNAL---` / `---END_SIGNAL---`)를 사용한다.
- 필드 누락 시 main이 NEED_CLARIFICATION으로 처리한다.

## On Receiving Subagent Output

1. Scan for DELEGATION_SIGNAL block
2. If P0 ambiguity exists, ask user first (AskUserQuestion)
3. If TARGET specified, auto-call that agent with CONTEXT
4. After chain completes, report summary to user

## Signal Type → Action

- NEED_USER_INPUT → AskUserQuestion with QUESTIONS items
- NEED_CLARIFICATION → call clarify-requirements
- DELEGATE_TO → call TARGET agent, pass CONTEXT
- JOURNEY_COMPLETE → call define-business-logic or plan-implementation
- BUSINESS_LOGIC_COMPLETE → call plan-implementation
- PLANNING_COMPLETE → report results to user, implementation ready

## Auto-call Prompt MUST Include

- Original user request
- Previous agent result summary
- Resolved P0 items
- Specific task being requested

## Stop Delegation When

- P0 unresolved (user answer required)
- Loop detected (same agent called 2+ times)
- Explicit completion signal received
- Error occurred
