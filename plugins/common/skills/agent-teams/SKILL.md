---
name: agent-teams
description: |
  Agent Teams를 활용하여 대규모 작업을 병렬 처리합니다.
  Team Lead가 Teammates를 조율하여 독립 작업을 병렬 실행합니다.
  Opus 4.6 필수, 환경변수 CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1 필요.
model: opus
effort: high
---

# Agent Teams 스킬

> ⚠️ 실험적 기능 — `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1` 환경변수 필요
> Opus 4.6의 Agent Teams로 대규모 작업을 병렬 처리

---

## 사용 시점

```
✅ 사용:
- Large 작업 (10개 이상 파일 변경)
- 병렬 가능한 독립 작업 (테스트 + 문서 + 구현)
- 장기 실행 작업 (1시간 이상)

❌ 사용하지 않음:
- Small 작업 (기존 Task tool 사용)
- 순차 의존 작업 (A 완료 후 B 시작)
- Sonnet/Haiku 모델 사용 시
```

---

## 사전 조건

```bash
# 환경변수 설정 필수
export CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1

# 설정 여부 확인
echo $CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS
```

---

## 실행 방법

### 1. 팀 구성

```
TeamCreate(
  team_name: "feature-team",
  description: "기능 구현 팀",
  agent_type: "facilitator-teams"  # Lead 에이전트
)
```

### 2. Teammates 할당

```
# 병렬로 Teammates 생성
Task(subagent_type="implement-code", team_name="feature-team",
     name="implementer", prompt="...")

Task(subagent_type="write-tests", team_name="feature-team",
     name="tester", prompt="...")

Task(subagent_type="review-code", team_name="feature-team",
     name="reviewer", prompt="...")
```

### 3. Lead가 조율

```
# Lead(facilitator-teams)가 자동으로:
- Teammate 진행 상황 모니터링
- 결과 통합 (synthesizer 역할)
- 충돌 해결 (consensus-builder 역할)
- 최종 보고서 생성
```

---

## 역할 배분 가이드

### 권장 팀 구성

| 작업 유형       | Lead              | Teammates                                             |
| --------------- | ----------------- | ----------------------------------------------------- |
| **기능 구현**   | facilitator-teams | implement-code, write-tests, sync-docs                |
| **리팩토링**    | facilitator-teams | plan-refactor, implement-code, verify-code            |
| **다관점 리뷰** | facilitator-teams | 관점별 에이전트 (/multi-perspective-review 사용 권장) |

### Teammate 수 제한

```
권장: 3-5개 Teammates
최대: 8개 (그 이상은 조율 오버헤드 증가)
```

---

## multi-perspective-review와의 관계

MPR 스킬은 CALC-001 점수 >= 9일 때 자동으로 Agent Teams 모드를 사용합니다.
이 스킬은 MPR 외의 **일반 작업**에서 Agent Teams를 직접 사용할 때 활용합니다.

| 상황             | 사용 스킬                                           |
| ---------------- | --------------------------------------------------- |
| 다관점 리뷰      | `/multi-perspective-review` (Agent Teams 자동 선택) |
| 대규모 기능 구현 | `/agent-teams` (이 스킬)                            |
| 대규모 리팩토링  | `/agent-teams` (이 스킬)                            |

---

## 제약사항

- **모델**: Opus 4.6 필수
- **환경변수**: `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1`
- **비용**: 여러 세션 동시 실행으로 토큰 비용 증가
- **안정성**: 실험적 기능 (프로덕션 주의)
- **POL-002**: 토큰 한도 300K (Subagent 모드의 2배)

---

## 참조

| 문서                        | 위치                                                    |
| --------------------------- | ------------------------------------------------------- |
| facilitator-teams 에이전트  | plugins/common/agents/meta/facilitator-teams.md         |
| MPR 스킬 (Agent Teams 모드) | plugins/common/skills/multi-perspective-review/SKILL.md |
| Phase Gate 패턴             | docs/architecture/phase-gate-pattern.md                 |
