# Agent Delegation Chain Rules

NEVER allow subagents to call other subagents.
ALWAYS have main Claude manage the delegation chain directly.

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
