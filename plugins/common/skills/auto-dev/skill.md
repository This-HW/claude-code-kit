---
name: auto-dev
description: Work 기반 자동 개발 파이프라인. Planning 완료 Work를 Development → Validation까지 실행.
model: sonnet
effort: high
disable-model-invocation: true
---

# Auto-Dev 스킬

Work 파일과 Task 시스템을 통합하여 Development → Validation 파이프라인을 자동 실행합니다.

---

## Step 1: Work 컨텍스트 로드

### Work ID가 제공된 경우 (예: `/auto-dev W-042`)

1. `./scripts/work.sh show W-042` 실행 — 현재 상태 확인
2. Work 파일 위치 탐색: `docs/works/idea/` 또는 `docs/works/active/`
3. `W-XXX-{slug}/W-XXX-{slug}.md` 와 `planning-results.md` 읽기
4. frontmatter `status`, `current_phase`, `phases_completed` 확인

**idea 상태면 자동 전환:**

```bash
./scripts/work.sh start W-042
# idea/ → active/ 이동, status: active, started_at 기록
```

**current_phase에 따른 시작 위치:**

| current_phase | 시작 위치       |
| ------------- | --------------- |
| `planning`    | Step 2부터 전체 |
| `development` | Step 3부터 재개 |
| `validation`  | Step 4부터 재개 |

### Work ID가 없는 경우 (예: `/auto-dev 로그인 기능 추가`)

`docs/works/` 폴더 존재 여부 확인:

- **존재하면** → `work.sh new`로 새 Work 생성 후 Step 2부터 진행:
  ```bash
  ./scripts/work.sh new "<요청 제목>"
  ```
- **없으면** → Step 5 fallback

---

## Step 2: Development Tasks 생성

`planning-results.md`의 구현 계획 항목을 분석해서 Tasks 생성.

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

---

## Step 3: Development 실행

각 Task를 `implement-code` 에이전트에 위임 (isolation: worktree):

1. blockedBy 없는 Task부터 실행 시작
2. 각 Task 완료 시:
   - Task → `completed` 마킹
   - `progress.md` 업데이트 (해당 항목 체크박스 체크)
   - Work frontmatter `updated_at` 갱신
3. 의존 Task는 선행 Task 완료 후 순서대로 실행

모든 Dev Task 완료 후:

```bash
./scripts/work.sh next-phase W-042
# current_phase: development → validation
# phases_completed에 development 추가
```

---

## Step 4: Validation Tasks 생성 및 실행

Dev 완료 직후 두 Task를 동시 생성:

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

---

## Step 5: Validation 결과 통합 및 완료

`T-merge` 실행:

1. T-review, T-security 결과를 `review-results.md`에 통합 기록
2. 이슈 여부 판단:
   - **이슈 없음**: 사용자에게 완료 보고 후 Work 완료 처리
     ```bash
     ./scripts/work.sh complete W-042
     # active/ → completed/ 이동, progress.md/decisions.md 병합
     ```
   - **이슈 있음**: 이슈 목록과 권고사항을 사용자에게 보고, 파이프라인 중단

3. T-merge → `completed` 마킹

---

## Fallback: Work 시스템 없는 경우

`docs/works/` 폴더가 없거나 Work ID 없이 요청된 경우:

Work 관련 작업(상태 전환, progress.md, decisions.md) 전부 생략하고 파이프라인만 실행:

1. **탐색**: 코드베이스 파악 (`explore-codebase` 에이전트)
2. **계획**: 구현 계획 수립 (`plan-implementation` 에이전트)
3. **구현**: 코드 작성 (`implement-code` 에이전트, isolation: worktree)
4. **테스트**: 테스트 작성 (`write-tests` 에이전트)
5. **검증**: 코드 리뷰 + 보안 스캔 (병렬)
6. **보고**: 결과를 대화창에 출력

---

## 참고 문서

| 문서              | 경로                                                   |
| ----------------- | ------------------------------------------------------ |
| Work 통합 상세    | `plugins/common/skills/references/work-integration.md` |
| Work 시스템 전체  | `plugins/common/skills/references/work-system.md`      |
| Planning 프로토콜 | `plugins/common/rules/planning-protocol.md`            |
