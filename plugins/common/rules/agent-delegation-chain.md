# 에이전트 자동 위임 체인 규칙

> 메인 Claude가 서브에이전트 결과를 받은 후 자동으로 다음 에이전트를 호출하도록 합니다.

## 핵심 원칙

**서브에이전트는 다른 서브에이전트를 호출할 수 없습니다.**
메인 Claude가 위임 체인을 직접 관리해야 합니다.

## 위임 신호 감지

서브에이전트 결과에서 **DELEGATION_SIGNAL** 블록을 감지하면 자동으로 다음 행동을 수행합니다.

### 표준 신호 형식

```
---DELEGATION_SIGNAL---
TYPE: [신호 유형]
TARGET: [대상 에이전트 - 해당 시]
REASON: [이유]
CONTEXT: [전달할 컨텍스트]
---END_SIGNAL---
```

### 신호 유형별 행동

| TYPE | 행동 |
|------|------|
| `NEED_USER_INPUT` | AskUserQuestion으로 사용자에게 QUESTIONS 항목 질문 |
| `NEED_CLARIFICATION` | clarify-requirements 에이전트 호출 |
| `DELEGATE_TO` | TARGET 에이전트 호출 (CONTEXT 전달) |
| `JOURNEY_COMPLETE` | define-business-logic 또는 plan-implementation으로 진행 |
| `BUSINESS_LOGIC_COMPLETE` | plan-implementation으로 진행 |
| `PLANNING_COMPLETE` | 사용자에게 결과 보고, 구현 준비 완료 |

### 레거시 패턴 (하위 호환)

```
"→ Planning/clarify-requirements" / "→ Planning/design-user-journey"
"→ Planning/define-business-logic" / "→ Dev/plan-implementation"
"P0 모호함" + "사용자 확인 필요"
```

## 자동 위임 행동

- **P0 모호함 발견**: AskUserQuestion으로 질문 → 답변 후 동일 에이전트 재호출
- **다른 Planning 에이전트 필요**: 현재 결과를 컨텍스트로 포함하여 해당 에이전트 Task 호출
- **Dev 위임 준비 완료**: Planning 결과 요약 → plan-implementation 호출

## 메인 Claude 행동 규칙

서브에이전트 결과 수신 후:

1. **위임 신호 스캔**: DELEGATION_SIGNAL 탐지
2. **P0 확인**: P0 모호함이 있으면 사용자 질문 우선
3. **자동 연계**: 위임 대상 명시 시 자동 호출
4. **결과 종합**: 체인 완료 후 사용자에게 요약 보고

**자동 호출 시 prompt에 포함:** 원래 사용자 요청 / 이전 에이전트 결과 요약 / 해결된 P0 항목 / 요청하는 구체적 작업

## 위임 중단 조건

1. P0 미해결 (사용자 답변 필요)
2. 순환 감지 (동일 에이전트 2회 이상 호출)
3. 명시적 완료 신호 ("Planning 완료", "구현 준비 완료")
4. 오류 발생
