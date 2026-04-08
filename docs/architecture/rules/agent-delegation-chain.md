# 에이전트 자동 위임 체인

> 이 문서는 메인 Claude가 에이전트 결과를 받아 다음 에이전트로 자동 위임하는 체인 메커니즘을 설명합니다.

---

## 1. 핵심 원칙

```
NEVER allow subagents to call other subagents.
ALWAYS have main Claude manage the delegation chain directly.
```

**왜 메인 Claude가 직접 관리해야 하는가?**

- 서브에이전트가 또 다른 서브에이전트를 호출하면 무한 재귀 위험
- 위임 체인의 상태(현재 어느 단계인지)를 추적하는 단일 주체가 필요
- 사용자 개입이 필요한 P0 상황을 감지할 수 있는 곳은 메인 Claude뿐

---

## 2. 위임 체인 플로우 다이어그램

```
사용자 요청
    │
    ▼
┌─────────────────────────────────────────────────────────┐
│  메인 Claude                                            │
│  1. 요청 분석 → 첫 번째 에이전트 선택                  │
│  2. 에이전트 호출 (Task tool)                           │
│  3. 결과 수신 → DELEGATION_SIGNAL 파싱                  │
│  4. TYPE에 따라 행동 결정                               │
└─────────────────────────────────────────────────────────┘
    │
    ├─ NEED_USER_INPUT ──────────────► 사용자에게 질문
    │                                       │
    │                                       ▼ 답변 수신
    │                                  다음 에이전트로 재개
    │
    ├─ DELEGATE_TO ──────────────────► 다음 에이전트 호출
    │                                       │
    │                                       ▼ 결과 수신
    │                                  DELEGATION_SIGNAL 파싱
    │                                  (체인 반복)
    │
    └─ TASK_COMPLETE ────────────────► 사용자에게 최종 보고
```

---

## 3. 메인 Claude 행동 규칙 (단계별)

### Step 1: 서브에이전트 출력 수신

서브에이전트가 완료되면 메인 Claude는 출력에서 `---DELEGATION_SIGNAL---` 블록을 찾습니다.

```python
# 내부 처리 로직 (개념적)
output = agent_result.text
signal = parse_delegation_signal(output)

# TYPE 확인
if signal.type == "NEED_USER_INPUT":
    ask_user(signal.questions)
elif signal.type == "DELEGATE_TO":
    call_agent(signal.target, signal.context)
elif signal.type == "TASK_COMPLETE":
    report_to_user(output)
```

### Step 2: P0 모호함 확인

`DELEGATE_TO` 신호를 받았어도 P0 모호함이 존재하면 사용자에게 먼저 질문합니다.

```
P0 모호함이란?
- 데이터 무결성에 영향: "삭제 시 관련 데이터도 삭제하나요?"
- 보안 정책: "관리자만 접근 가능한가요, 모든 인증 사용자가 접근 가능한가요?"
- 금융/비용 계산: "할인이 중복 적용되나요?"
- 핵심 비즈니스 분기: "재고 없을 때 주문을 받나요, 막나요?"
```

### Step 3: 다음 에이전트 호출 시 포함해야 할 정보

메인 Claude가 다음 에이전트를 호출할 때 반드시 포함해야 할 정보:

```
1. 원본 사용자 요청 (original user request)
2. 이전 에이전트 결과 요약 (previous agent result summary)
3. 해결된 P0 항목 (resolved P0 items)
4. 구체적인 다음 작업 내용 (specific task being requested)
```

**예시:**

```
사용자 요청: 사용자 인증 시스템 구현
이전 에이전트: plan-implementation 완료
계획 요약:
  - JWT 기반 인증 (access: 15min, refresh: 7days)
  - User 테이블: id, email, passwordHash, createdAt
  - API: POST /auth/login, POST /auth/refresh, POST /auth/logout
해결된 P0:
  - 세션 방식: stateless JWT (서버 상태 없음)
  - 비밀번호 정책: 8자+ 영문+숫자 필수
다음 작업: 위 계획을 기반으로 TypeScript + Express로 구현
```

---

## 4. DELEGATION_SIGNAL TYPE별 처리 상세

### NEED_USER_INPUT

```
---DELEGATION_SIGNAL---
TYPE: NEED_USER_INPUT
TARGET: (없음)
REASON: P0 모호함 발견 — 데이터 삭제 정책 미정의
CONTEXT:
  QUESTIONS:
    1. 사용자 계정 삭제 시 작성한 게시글을 함께 삭제하나요, 유지하나요?
    2. 소프트 삭제(비활성화)를 사용하나요, 하드 삭제를 사용하나요?
---END_SIGNAL---
```

**처리:** AskUserQuestion으로 QUESTIONS 항목을 사용자에게 전달. 답변 수신 후 체인 재개.

---

### DELEGATE_TO

```
---DELEGATION_SIGNAL---
TYPE: DELEGATE_TO
TARGET: implement-code
REASON: Planning 완료, 구현 준비됨
CONTEXT:
  요구사항 요약: 사용자 인증 API
  기술 스택: TypeScript, Express, Prisma
  데이터 모델: User(id, email, passwordHash, createdAt)
  API 명세: POST /auth/login → JWT 반환
  P1 미결: 로그인 시도 횟수 제한 (기본값 5회로 가정)
---END_SIGNAL---
```

**처리:** `implement-code` 에이전트를 CONTEXT 포함해 즉시 호출.

---

### TASK_COMPLETE

```
---DELEGATION_SIGNAL---
TYPE: TASK_COMPLETE
TARGET: (없음)
REASON: 코드 리뷰 완료, Must Fix 0개, 구현 완료
CONTEXT:
  완료 항목:
    - 사용자 인증 API 구현
    - 단위 테스트 85% 커버리지
    - 보안 스캔 통과
---END_SIGNAL---
```

**처리:** 사용자에게 최종 완료 보고. 체인 종료.

---

## 5. 위임 중단 조건

아래 상황에서 자동 위임을 즉시 중단합니다.

| 조건                                | 이유                                       | 메인 Claude 행동                 |
| ----------------------------------- | ------------------------------------------ | -------------------------------- |
| P0 미해결                           | 핵심 비즈니스 규칙 불명확 상태로 진행 불가 | 사용자에게 P0 질문               |
| 루프 감지 (동일 에이전트 2회+ 호출) | 무한 루프 위험                             | 사용자에게 상황 보고 후 중단     |
| 명시적 완료 신호                    | 체인 종료 시점                             | 최종 보고                        |
| 에러 발생                           | 에이전트 실행 실패                         | 에러 내용과 함께 사용자에게 보고 |

**루프 감지 예시:**

```
1차: plan-implementation 호출 → DELEGATE_TO: plan-implementation (루프!)
→ 메인 Claude: "plan-implementation이 자기 자신을 다시 호출하려 합니다.
   현재 상황을 확인해 주세요: [이전 결과 요약]"
```

---

## 6. 실전 예시: Planning → Dev 위임 흐름

### 사용자 요청

```
사용자: "게시판 CRUD API를 만들어줘"
```

### 흐름

```
Step 1: 메인 Claude → clarify-requirements 호출
  └─ 결과: P0 발견 (삭제 정책 불명확)
     DELEGATION_SIGNAL: NEED_USER_INPUT
     QUESTIONS: ["게시글 삭제 시 소프트 삭제인가요, 하드 삭제인가요?"]

Step 2: 메인 Claude → 사용자에게 질문
  └─ 사용자 답변: "소프트 삭제 (deletedAt 컬럼 사용)"

Step 3: 메인 Claude → plan-implementation 호출 (P0 해결 후)
  └─ 결과: 구현 계획 완성
     DELEGATION_SIGNAL: DELEGATE_TO
     TARGET: implement-code

Step 4: 메인 Claude → implement-code 호출 (이전 계획 포함)
  └─ 결과: 구현 완료
     DELEGATION_SIGNAL: TASK_COMPLETE

Step 5: 메인 Claude → 사용자에게 최종 보고
  "게시판 CRUD API 구현이 완료되었습니다.
   소프트 삭제(deletedAt) 방식으로 구현되었습니다."
```

---

## 7. 체인 관련 Anti-Patterns

```
# 잘못된 예 1: 서브에이전트가 서브에이전트 호출
implement-code 내부에서:
  Task("fix-bugs", ...)  ← 금지! disallowedTools: [Task]

# 잘못된 예 2: P0 모호함 무시하고 DELEGATE_TO
P0: "결제 오류 시 환불 정책 미정의"
→ DELEGATE_TO: implement-code  ← 위험! P0 해결 없이 구현 시작

# 올바른 예: P0 항상 우선
P0 발견 → NEED_USER_INPUT → 답변 수신 → DELEGATE_TO
```
