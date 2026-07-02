# Parallel Worktree Rules

병렬 dispatch에서 파일을 수정하는 에이전트는 worktree로 "격리 진입"하고, 검증
통과 후에만 "복귀(병합)"한다. 격리는 필요조건일 뿐이다 — 병합 규범이 없으면
충돌은 사라지는 게 아니라 병합 시점으로 이연된다. (W-011)

## 진입 (Isolation)

- ALWAYS: 소스 파일을 수정하는 에이전트는 frontmatter `isolation: worktree` + tools에 `ExitWorktree`.
  대상: implement-code, fix-bugs, write-tests, write-api-tests, implement-api, generate-boilerplate, sync-docs, optimize-logic
- NEVER: read-only 에이전트(explore-codebase, review-code, plan-implementation 등)에 isolation 설정.
- git-workflow는 의도적으로 비격리 — 병합·충돌 해결은 메인 워크스페이스에서 일어나야 한다.

## 파일 소유권 (dispatch 전)

- ALWAYS: 병렬 dispatch 전에 청크 간 수정 대상 파일이 겹치지 않는지 확인. 겹치면 해당 청크들은 순차로 강등.
- 공유 파일(설정, 배럴 export, 라우트 등록부 등)은 병렬 청크에 배정하지 않고 마지막에 메인 세션이 단독 수정.

## 복귀 (ExitWorktree)

- ALWAYS: worktree 안에서 검증(린트 + 관련 테스트)이 그린일 때만 ExitWorktree 호출. 레드 상태로 병합 금지.
- ALWAYS: 여러 worktree 결과는 순차 병합 — 하나 병합 → 검증 → 다음. 동시 병합 금지.
- 병합 순서: 의존성 상류(공유 타입/유틸) 먼저, 하류(사용처) 나중.

## 충돌 에스컬레이션

- NEVER: 충돌 시 에이전트가 임의로 ours/theirs 선택. 반드시 `DELEGATE_TO: git-workflow`로 위임 —
  git-workflow가 충돌 파일/내용을 보고하고 NEED_USER_INPUT(ours/theirs/manual)으로 사용자에게 선택지를 제시한다.
- 같은 지점에서 충돌 2회 반복 = 청크 분해 오류 신호 → plan-implementation으로 에스컬레이션.

## 공유 상태 파일

- NEVER: worktree 안에서 `docs/works/**`(progress.md, feedback ledger 등) 갱신 —
  병합 전까지 메인 저장소에 반영되지 않아 상태가 유실/분기된다. Work 상태 갱신은 메인 세션(오케스트레이터)의 몫.
