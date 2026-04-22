---
name: agent-creator
description: Create Claude Code sub-agents with optimal configuration. Use when users ask to create a new agent, custom agent, specialized assistant, or want to configure task-specific AI workflows.
model: sonnet
effort: medium
---

# Agent Creator

새로운 Claude Code 서브에이전트를 생성하고 최적화합니다.

## 생성 워크플로우

1. **요구사항 수집**
   - 에이전트의 목적
   - 사용 시점 (자동 위임 트리거)
   - 필요한 도구
   - 파일 수정 필요 여부

2. **설정 결정**
   - 모델 선택 (Opus/Sonnet/Haiku)
   - 권한 모드 선택
   - 도구 화이트리스트/블랙리스트

3. **파일 생성**
   - 위치: `plugins/{domain}/agents/{category}/` (플러그인 구조)
   - 또는 `.claude/agents/` (프로젝트 로컬)
   - 파일명: `agent-name.md`

4. **검증**
   - frontmatter 형식 확인
   - 도구 이름 검증
   - plugin.json 등록 확인

## 모델 선택 가이드

| 작업 유형          | 권장 모델 | 이유                 |
| ------------------ | --------- | -------------------- |
| 전략/분석/리뷰     | `opus`    | 복잡한 추론          |
| 코드 구현/수정     | `sonnet`  | 균형잡힌 성능        |
| 탐색/검증/단순작업 | `haiku`   | 빠른 실행, 비용 효율 |

## 권한 모드 선택

| 모드          | 용도                |
| ------------- | ------------------- |
| `default`     | 표준 권한 확인      |
| `acceptEdits` | 파일 편집 자동 허용 |
| `plan`        | 읽기 전용           |

## 출력 형식 (claude-code-kit 플러그인 구조)

```markdown
---
name: [소문자-하이픈]
description: [역할]. MUST USE when: [트리거 조건].
model: [sonnet|opus|haiku]
effort: [low|medium|high|max]
tools:
  - [도구 목록]
permissionMode: [default|acceptEdits|plan]
disallowedTools:
  - Task
---

[시스템 프롬프트]

---DELEGATION_SIGNAL---
TYPE: TASK_COMPLETE | DELEGATE_TO | NEED_USER_INPUT
TARGET: [대상 에이전트]
REASON: [이유]
CONTEXT: [전달 컨텍스트]
---END_SIGNAL---
```

## 플러그인 구조 등록

생성 후 `plugins/{domain}/.claude-plugin/plugin.json`의 `agents` 필드에 등록:

```json
{
  "agents": "agents/"
}
```

에이전트 파일은 `plugins/{domain}/agents/{category}/{name}.md`에 위치.

## 자동 위임 최적화

description에 포함하면 자동 위임 빈도 증가:

- "MUST USE when:"
- "Use PROACTIVELY"
- "Use immediately after"

## 예제

```markdown
---
name: test-runner
description: Test execution specialist. MUST USE when: code changes are made and tests need to be run.
model: haiku
effort: low
tools:
  - Read
  - Bash
  - Grep
  - Glob
disallowedTools:
  - Task
---

You are a test automation expert.

When invoked:

1. Identify changed files
2. Run relevant tests
3. Report results with fix suggestions if failed

---DELEGATION_SIGNAL---
TYPE: TASK_COMPLETE
TARGET: N/A
REASON: Test execution complete
CONTEXT: [test results summary]
---END_SIGNAL---
```
