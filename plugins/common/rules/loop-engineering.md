# Loop Engineering Rule (Spec 5 / W-009)

**Harness Engineering**(어디서·무엇으로 행동하는가)의 상보 개념. Loop Engineering은
**얼마나 오래·끈질기게** 행동하는가를 다룬다. 승인된 계획을 P0·완료·가드 도달 전까지
자율로 완주한다.

## 게이트 vs 루프 — 절대 혼동 금지

| | 게이트 (설계) | 루프 (실행) |
| --- | --- | --- |
| 목적 | 사람 승인 — 무엇을 만들지 | 자율 완주 — 끝까지 어떻게 |
| 멈춤 | **의도적 멈춤** (brainstorming/plan-task HARD-GATE) | **멈추지 않음** (P0·완료·가드 제외) |
| 예 | 설계 승인, 스펙 검토 | auto-dev 배치 실행, Task dispatch |

- 설계 게이트는 유지한다 — 루프가 게이트를 우회하지 않는다.
- **게이트 통과 후에는** 매 단계 확인을 구하지 않는다. 승인된 배치는 완주한다.

## 실행 루프 드라이버 (네이티브/기존 인프라만)

> `/goal`·`ultracode`는 대화형 전용이라 스킬에서 프로그래밍 트리거 불가(2026.6).
> 따라서 드라이버는 검증된 Task 시스템 + 스킬 루프로 구성한다 (자체 데몬 없음).

```
승인된 배치 (여러 Work/Task)
  while (미완료 Work/Task 존재):
    1. TaskList → unblocked Task 선택
    2. 실행 (dispatch / 직접 구현)
    3. 완료 → progress.md 래칫 → TaskUpdate(completed)
    4. 종료 가드 점검 (아래)
    5. 다음 unblocked로 — 사람 확인 없이 전진
  → 완료 보고
```

## 종료 가드 (안티-런어웨이 = 필수)

루프는 **반드시** 아래에서 멈춘다:

- **P0 도달**: 데이터/보안/결제/핵심로직 모호함 → 즉시 `AskUserQuestion`.
- **완료**: `scripts/verify-done.sh` green + 수동 DoD attest 완료 + 배치의 모든 Work/Task 상태 해소. "마지막 스텝 도달"은 완료가 아니다 (`rules/definition-of-done.md`).
- **max_iterations**: 한 배치에서 진전 없는 반복이 상한(기본 동일 Task 2회/배치 누적 과다) 초과 → 사람 에스컬레이션.
- **루프 감지**: 동일 Task/에이전트가 진전 없이 2회+ → 중단 보고.
- **검증 실패 잔존**: validation이 가드(continueOnBlock) 재시도 후에도 실패 → 보고.

## 적용

- `auto-dev`: 배치 모드에서 한 Work 완료 시 다음 unblocked Work로 자동 전진(위 드라이버).
- 단발 실행(`/auto-dev W-XXX` 단일)은 기존 동작 유지 — 루프는 배치에만.
- opt-in·하위호환: 루프 실패가 본 작업을 막지 않는다.
