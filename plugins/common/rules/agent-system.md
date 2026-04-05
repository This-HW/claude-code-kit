# 에이전트 시스템

## 3-Tier 아키텍처

```
Tier 1: plugins/common/    → 모든 프로젝트 공통 (33개)
Tier 2: plugins/{domain}/  → 도메인별 (33개)
Tier 3: agents/project/   → 프로젝트 전용 (4개)
```

스킬도 동일 구조: `skills/common/` (Tier 1) → `skills/domain/` → `skills/project/`

## 모델 선택 기준

| 모델       | 용도           | 예시                                        |
| ---------- | -------------- | ------------------------------------------- |
| **Opus**   | 전략/분석/리뷰 | clarify-requirements, review-code, diagnose |
| **Sonnet** | 코드 구현/수정 | implement-code, fix-bugs, write-tests       |
| **Haiku**  | 탐색/검증/단순 | explore-codebase, verify-code, monitor      |

## 위임 신호 (Delegation Signal)

```
---DELEGATION_SIGNAL---
TYPE: DELEGATE_TO | TASK_COMPLETE | NEED_USER_INPUT
TARGET: [대상 에이전트]
REASON: [이유]
CONTEXT: [전달 컨텍스트]
---END_SIGNAL---
```

## 점진적 에이전트 선택

```
Step 1: agents/common/index.json 읽기 (~6K 토큰)
Step 2: description 매칭으로 에이전트 식별
Step 3: 필요한 에이전트만 전체 로드
Step 4: 병렬 실행 → 75% 토큰 절약
```

**인덱스 갱신:** `python scripts/build-agent-index.py`

## 에이전트 선택 강제 규칙

### ⚠️ 필수: Task tool 호출 전 반드시 확인

1. **agents/common/index.json 읽기** (76개 에이전트 목록)
2. **description 키워드 매칭**으로 적합한 에이전트 찾기
3. **subagent_type 명시적 지정** (general-purpose 폴백 금지)

**general-purpose 사용 제한:**

- ✅ 특화 에이전트가 없는 작업 / ✅ 다중 도메인 혼합 작업
- ❌ 특화 에이전트가 있는데 찾지 못한 경우 (절대 금지)

### 키워드 매칭 가이드

| 작업 키워드         | 매칭 에이전트           |
| ------------------- | ----------------------- |
| "조사", "리서치"    | **research-external**   |
| "계획", "설계"      | **plan-implementation** |
| "구현", "코드 작성" | **implement-code**      |
| "리뷰", "검토"      | **review-code**         |
| "탐색", "파악"      | **explore-codebase**    |
| "테스트"            | **write-tests**         |
| "수정", "버그"      | **fix-bugs**            |

## 에이전트 Frontmatter 신규 필드 (v2.1.49+)

### `isolation: "worktree"` — 격리 실행

서브에이전트를 임시 git worktree에서 격리하여 실행합니다. 파일 시스템 충돌 방지 및 안전한 실험에 활용됩니다.

| 적용 기준          | 적용 대상                                                              | 비적용 대상                                        |
| ------------------ | ---------------------------------------------------------------------- | -------------------------------------------------- |
| 파일 수정 에이전트 | implement-code, fix-bugs, write-tests, write-api-tests, write-ui-tests | explore-codebase, review-code, plan-implementation |

```yaml
---
name: implement-code
model: sonnet
isolation: worktree # 임시 worktree에서 격리 실행
---
```

### `background: true` — 백그라운드 강제 실행

에이전트가 항상 백그라운드 Task로 실행됩니다. 장시간 실행 + 사용자 대기 불필요한 운영 에이전트에 적용합니다.

| 적용 기준                | 적용 대상                                                  |
| ------------------------ | ---------------------------------------------------------- |
| 모니터링/스케줄 에이전트 | health-check, schedule-task, trigger-pipeline, notify-team |

```yaml
---
name: health-check
model: haiku
background: true # 항상 백그라운드 실행
---
```

**Ctrl+F**: 실행 중인 백그라운드 에이전트 일괄 종료 (2회 확인)

## disallowedTools 정책

서브에이전트는 다른 서브에이전트를 호출할 수 없습니다. 메인 Claude만 에이전트 조율을 담당합니다.

| 에이전트 유형                                       | disallowedTools                      |
| --------------------------------------------------- | ------------------------------------ |
| **Meta 에이전트** (facilitator, synthesizer 등 4개) | `[Bash]`                             |
| **일반 에이전트** (implement-code, fix-bugs 등)     | `[Task]`                             |
| **스킬**                                            | 없음 (메인 Claude가 실행, Task 필요) |

## Phase Gate 패턴

Phase Gate = 메인 Claude의 판단 기준 (자동 시스템 아님)
Stop hook(prompt type)이 작업 완료 시 자동 품질 검증 담당.

```
Phase 1: Planning  → P0 모호함 100% 제거
Phase 2: Development → Planning artifacts 기반 구현
Phase 3: Validation → 리뷰, 보안 검사 (병렬)
```

### Exit Gate 판단 기준

**Planning → Dev:**

- P0 모호함 = 0
- 핵심 비즈니스 규칙 정의됨
- 데이터 모델 정의됨
- 주요 사용자 흐름 명확

**Dev → Validation:**

- 빌드 성공 (verify-code 통과)
- 핵심 로직 테스트 존재 (80%+)
- 린트/타입 통과

**Validation → Complete:**

- review-code Must Fix = 0
- Critical 보안 이슈 = 0
- 통합 테스트 통과

**상세:** docs/architecture/phase-gate-pattern.md
