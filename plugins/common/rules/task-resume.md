# Task 재생성 규칙

> 세션 재시작 후 active Work의 Task를 복원하는 알고리즘

---

## 트리거 조건

세션 컨텍스트에 `=== ACTIVE WORK ===` 블록이 있을 때:

1. 사용자가 작업 재개를 명시하면 (예: "계속해줘", "재개", "W-XXX 작업해줘")
   → Task 재생성 알고리즘 즉시 실행
2. 단순 질문/조회이면
   → "W-XXX 작업이 진행 중입니다. 재개할까요?" 안내 후 대기

자동으로 Task를 생성하거나 코드를 수정하지 않는다.

---

## Task 재생성 알고리즘

### Step 1: 준비

```
ToolSearch("select:TaskCreate,TaskUpdate,TaskList") — 스키마 fetch
TaskList → 이미 Task 있으면 재생성 스킵 (중복 방지)
```

### Step 2: progress.md 읽기

해당 Work의 `progress.md` Task Map을 읽어:

- `complete` = ✅ 상태인 Task ID 집합
- `incomplete` = ⬜·⏳ 상태인 Task 목록 (순서 유지)

### Step 3: Task 생성 (순서대로)

```
id_map = {}   ← T-N 레이블 → 실제 TaskCreate ID 매핑

incomplete을 순서대로 처리:
  실제_blockedBy = [
    id_map[dep]
    for dep in task.blocked_by.split(",")
    if dep.strip() not in complete    ← 완료 Task는 의존성 제거
       and dep.strip() in id_map      ← 이미 생성된 Task만
  ]

  new_id = TaskCreate(
    subject=f"[W-XXX][Phase] {task.title}",
    description=task.desc,
    metadata={"work_id": "W-XXX", "phase": "<phase>"}
  )
  id_map[task.id] = new_id

  if 실제_blockedBy:
    TaskUpdate(new_id, addBlockedBy=실제_blockedBy)
```

### Step 4: in_progress 복원

```
⏳이었던 Task → TaskUpdate(new_id, status="in_progress")
```

### Step 5: 실행 재개

blockedBy 없는 Task부터 실행 시작.
2개 이상이면 Agent 동시 dispatch.

---

## 예시

**progress.md 상태:**

```
T-1 ✅, T-2 ✅, T-3 ✅ (완료)
T-4 ⏳ blockedBy T-3
T-5 ⬜ blockedBy T-3
T-6 ⬜ blockedBy T-4, T-5
```

**재생성 결과:**

```
complete = {T-1, T-2, T-3}
incomplete = [T-4, T-5, T-6]

T-4: blockedBy=[T-3✅] → 제거 → blockedBy=[] → TaskCreate → id=51
T-5: blockedBy=[T-3✅] → 제거 → blockedBy=[] → TaskCreate → id=52
T-6: blockedBy=[T-4→51, T-5→52] → blockedBy=[51,52] → TaskCreate → id=53

T-4(⏳) → TaskUpdate(51, in_progress)
T-5, T-6 → pending

실행: 51(T-4)과 52(T-5) 동시 dispatch (둘 다 blockedBy 없음)
```

---

## Task 생성 규칙

- subject: `[W-XXX][Phase] 제목` 형식
- metadata: `{"work_id": "W-XXX", "phase": "planning|development|validation"}`
- 완료된 Task(✅)는 절대 재생성하지 않음
- blockedBy에서 완료 Task 의존성은 제거

---

## 고급: CLAUDE_CODE_TASK_LIST_ID

`work.sh resume W-XXX`로 시작한 세션은 이전 Task가 그대로 유지된다.
이 경우 `TaskList`만 실행해도 기존 상태 확인 가능 — 재생성 불필요.
