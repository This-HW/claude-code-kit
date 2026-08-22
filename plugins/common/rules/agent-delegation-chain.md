# Agent Delegation Chain Rules

## Standing User Authorization for Delegation (SSOT)

The user of this project has PRE-AUTHORIZED subagent delegation for the whole
session, in advance, via this project configuration. Whenever a request matches
an agent `description` in `agents/`, that counts as **the user having requested
the AgentTool**. Call it. Do not ask for re-confirmation, and do not do the work
inline when an agent is defined for it.

Exception — the only inline cases: a single lookup whose file/symbol/value you already
know, and a mechanical single-file edit (typo, formatting, import order). Everything
else delegates. 어느 에이전트를 고를지는 `agent-system.md` §Agent Selection by
Keyword가 SSOT다 — 여기서 재정의하지 않는다.

> 근거(2026-08-21 A/B 실측, n=3+3): 승인문구가 없는 조건에서 메인 루프의 Agent 직접
> 호출 **0/3**, `--append-system-prompt`로 위 문단만 주입한 조건에서 **3/3**.
> (Fisher exact 단측 p=0.05 — 경계값이므로 표본 확대 필요.)
>
> 억제 원인은 **미규명**이다. Claude Code v2.1.219+가 주입하는 서버사이드 섹션
> `heron_brook`("Do not call the AgentTool unless the user requested it", Opus 5 전용,
> 문서화된 opt-out 없음, https://github.com/anthropics/claude-code/issues/80988)이
> 유력 후보이나, 위 실측은 Sonnet 5 세션에서 수행되어 해당 문자열이 부재했다.
> **이 조항은 heron_brook이 원인임을 전제하지 않는다** — 원인과 무관하게 위임을
> 사전 승인해두는 것 자체가 이 프로젝트의 의도된 정책이다.
>
> 한계: 결정론적 보장이 아니라 모델 판단에 대한 입력이다. 보장이 필요한 단계는 Stop
> 훅(`hooks/stop-validator.py`)으로 강제한다.

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
