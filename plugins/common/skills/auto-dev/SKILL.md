---
name: auto-dev
description: Work 기반 자동 개발 파이프라인. Planning 완료 Work를 Development → Validation까지 실행.
model: sonnet
effort: high
domain: common
---

# Auto-Dev 스킬

Work 파일과 Task 시스템을 통합하여 Development → Validation 파이프라인을 자동 실행합니다.

---

## Step 0: Work 컨텍스트 + Task 시스템 초기화 [건너뛰기 금지]

### Work ID가 제공된 경우 (예: `/auto-dev W-042`)

1. Work 파일 위치 탐색: `docs/works/idea/` 또는 `docs/works/active/`
2. `W-XXX-{slug}/W-XXX-{slug}.md` 와 `planning-results.md` 읽기
3. frontmatter `status`, `current_phase`, `phases_completed` 확인

**idea 상태면 자동 전환:**

```bash
./scripts/work.sh start W-042
# idea/ → active/ 이동, status: active, started_at 기록
```

**current_phase에 따른 시작 위치:**

| current_phase | 시작 위치       |
| ------------- | --------------- |
| `planning`    | Step 1부터 전체 |
| `development` | Step 2부터 재개 |
| `validation`  | Step 3부터 재개 |

### Work ID가 없는 경우 (예: `/auto-dev 로그인 기능 추가`)

`docs/works/` 폴더 존재 여부 확인:

- **존재하면** → `work.sh new`로 새 Work 생성 후 Step 1부터 진행:
  ```bash
  ./scripts/work.sh new "<요청 제목>"
  ```
- **없으면** → Step 4 fallback

### Task 시스템 초기화 [건너뛰기 금지]

Work ID 확보 후 반드시 실행:

1. `ToolSearch("select:TaskCreate,TaskUpdate,TaskList")` — 스키마 fetch
2. `TaskList` 실행 → subject가 `[W-XXX]`로 시작하는 Task 있으면 상태 확인 후 재개 (재생성 스킵, W-XXX는 현재 Work ID)
3. Task 없으면 → Step 1: Development Tasks 생성으로 이동

---

## Step 1: Development Tasks 생성

`planning-results.md`의 구현 계획 항목 분석 + **소스코드 직접 탐색**:

1. 구현 계획 항목 목록화
2. 코드베이스 직접 탐색 (에이전트 위임 아님):
   - 이미 구현된 파일/함수 확인
   - 해당 항목은 ✅ 완료로 마킹 (Task 생성 스킵)
3. 미완료 항목만 TaskCreate:

**분리 기준:**

- 독립적으로 구현 가능한 항목 → 별도 Task (병렬 실행)
- 다른 항목에 의존하는 항목 → `addBlockedBy` 설정

**Task 네이밍:** `[W-XXX][Dev] {구현 항목명}`

**TaskCreate 시 모든 Task에 metadata 포함:**

```json
{ "work_id": "W-XXX", "phase": "development" }
```

**예시 구조:**

```
T-dev-1: [W-042][Dev] 데이터 모델 정의       ← 독립 (병렬)
T-dev-2: [W-042][Dev] API 엔드포인트 구현    ← blockedBy: T-dev-1
T-dev-3: [W-042][Dev] 프론트엔드 컴포넌트   ← blockedBy: T-dev-1
T-dev-4: [W-042][Dev] 테스트 작성            ← blockedBy: T-dev-2, T-dev-3
```

`progress.md` Task Map 생성/갱신 (description 컬럼 포함).

---

## Step 2: Development 실행

각 Task를 `implement-code` 에이전트에 위임 (isolation: worktree):

**병렬 실행 원칙:**

blockedBy 없는 Task가 2개 이상이면 동일 응답에서 동시 dispatch:

```
Agent(task_A) ─┐
Agent(task_B) ─┼─ 동일 응답에서 동시 dispatch
Agent(task_C) ─┘
```

**Task 완료 시 매번 의무:**

1. `TaskUpdate(id, status="completed")`
2. `progress.md` Task Map: 해당 행 상태 ✅로 수정
3. `progress.md` Task 업데이트 로그에 완료 시각 기록
4. Work frontmatter `updated_at` 갱신
5. `TaskList`로 unblocked Task 확인 → 즉시 실행

모든 Dev Task 완료 후:

```bash
./scripts/work.sh next-phase W-042
# current_phase: development → validation
# phases_completed에 development 추가
```

---

## Step 3: Validation Tasks 생성 및 실행

Dev 완료 직후 두 Task를 동시 생성 후 **병렬 실행**:

```
T-review:   [W-042][Validation/A] 코드 리뷰   — blockedBy: 모든 Dev Tasks
T-security: [W-042][Validation/B] 보안 스캔   — blockedBy: 모든 Dev Tasks
```

TaskCreate 시 metadata:

```json
{ "work_id": "W-XXX", "phase": "validation" }
```

**병렬 실행:**

- `T-review` → `review-code` 에이전트
- `T-security` → `security-scan` 에이전트

두 Task 모두 완료 후 결과 통합 Task 생성:

```
T-merge: [W-042][Validation] 결과 통합   — blockedBy: T-review, T-security
```

`T-merge` 실행:

1. T-review, T-security 결과를 `review-results.md`에 통합 기록
2. 이슈 여부 판단:
   - **이슈 없음**: 사용자에게 완료 보고 후 Work 완료 처리
     ```bash
     ./scripts/work.sh complete W-042
     # active/ → completed/ 이동
     ```
   - **이슈 있음**: 이슈 목록과 권고사항을 사용자에게 보고, 파이프라인 중단

3. `TaskUpdate(T-merge, status="completed")`

---

## Fallback: Work 시스템 없는 경우

`docs/works/` 폴더가 없거나 Work ID 없이 요청된 경우:

Work 관련 작업(상태 전환, progress.md, decisions.md) 전부 생략하고 파이프라인만 실행:

1. **탐색**: 코드베이스 파악 (직접 탐색)
2. **계획**: 구현 계획 수립 (`plan-implementation` 에이전트)
3. **구현**: 코드 작성 (`implement-code` 에이전트, isolation: worktree)
4. **테스트**: 테스트 작성 (`write-tests` 에이전트)
5. **검증**: 코드 리뷰 + 보안 스캔 (병렬)
6. **보고**: 결과를 대화창에 출력

---

## 참고 문서

| 문서              | 경로                                              |
| ----------------- | ------------------------------------------------- |
| Work 시스템 전체  | `plugins/common/skills/references/work-system.md` |
| Planning 프로토콜 | `plugins/common/rules/planning-protocol.md`       |
