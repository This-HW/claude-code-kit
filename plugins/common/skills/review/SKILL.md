---
name: review
description: 현재 변경사항 또는 지정된 파일에 대한 코드 리뷰를 수행합니다.
model: opus
effort: high
domain: common
argument-hint: [파일 경로 또는 빈칸(git diff)]
allowed-tools: Read, Glob, Grep, Bash, Task
---

# 코드 리뷰 실행

**즉시 실행하세요. 설명하지 말고 바로 실행합니다.**

## 파이프라인 구조

```
┌──────────────┐   ┌──────────────┐   ┌───────────────┐
│ 리뷰 대상    │ → │ review-code  │ → │ security-scan │
│ 파악 (Main)  │   │ (opus)       │   │ (sonnet)      │
└──────────────┘   └──────────────┘   └───────────────┘
```

---

## 0단계: 정적 분석 (Python 파일 포함 시)

**리뷰 대상에 `.py` 파일이 포함되어 있으면 ruff check를 먼저 실행합니다.**

```bash
# 특정 파일 지정 시
ruff check [대상 파일 또는 디렉토리]

# git diff 대상 시 (변경된 .py 파일 추출 후)
git diff HEAD --name-only | grep '\.py$' | xargs ruff check 2>/dev/null
```

**결과 처리:**

- ruff check 출력이 있으면: 리뷰 컨텍스트에 포함하여 review-code 에이전트에 전달
- ruff check 통과 시: "정적 분석: 통과" 메시지만 출력
- ruff가 설치되지 않은 경우: "스킵됨 (ruff 미설치)" 메시지 출력

**형식:**

```
## 0단계: 정적 분석 (ruff)
- 대상: [파일 목록 또는 "없음 (Python 파일 없음)"]
- 결과: [통과 | N건 발견]
- 발견된 이슈: [있을 때만 출력]
```

---

## 1단계: 리뷰 대상 파악

$ARGUMENTS가 있으면:

- 해당 파일/디렉토리를 읽어서 리뷰

$ARGUMENTS가 없으면:

- `git diff HEAD`로 변경사항 확인
- 변경사항이 없으면 `git diff HEAD~1`로 마지막 커밋 확인

---

## 1.5단계: 자동 범위 판단 (Auto-Scope)

**변경 파일을 분석하여 리뷰 범위를 자동으로 결정합니다.**

### 수동 오버라이드 확인

$ARGUMENTS에 `--quick`이 포함되어 있으면:

- scope = 'quick' (사용자 명시 오버라이드)
- security_scan_needed = false
- "수동으로 quick 모드가 지정되었습니다" 메시지 출력
- 1.5단계 나머지 스킵하고 2단계로 진행

### 자동 범위 판단

변경 파일 목록을 분석하여 scope를 자동 결정:

#### 보안 관련 파일 감지

다음 경로 패턴에 매칭되는 파일이 **1개라도 있으면**:

- `**/auth/**`, `**/security/**`, `**/payment/**`
- `**/middleware/**`, `**/*secret*`, `**/*token*`
- `hooks/*.py`, `**/config.py`

→ **scope = 'adversarial', security_scan_needed = true**

#### Trivial 파일 판정

다음 파일 유형이 **전체의 80% 이상**이면:

- `*.md`, `*.txt`, `docs/**`
- `*.json`, `*.yml`, `*.yaml` (예외: `settings.json`, `project.yaml`)

→ **scope = 'quick', security_scan_needed = false**

#### 기본 (일반 코드)

위 두 조건에 해당하지 않으면:

- `src/**`, `agents/**`, `skills/**`, `scripts/**`

→ **scope = 'adversarial', security_scan_needed = false**

### 판정 결과 출력

```
🔍 Auto-Scope 판정 결과:
- 변경 파일: [N]개
- 보안 관련: [N]개
- Trivial: [N]개
- **Scope: [adversarial | quick]**
- Security Scan: [필요 | 불필요]
```

---

## 1.7단계: 사용자 의견 처리 원칙 (조건부)

<!-- Pattern from: superpowers/receiving-code-review -->
**트리거**: $ARGUMENTS에 파일 경로·옵션(`--quick` 등)이 아닌 **자연어 문장이 포함된 경우**에만 실행.

예시:
- `/review src/auth.py 보안이 걱정돼` → **실행** (자연어 의견 포함)
- `/review src/auth.py` → 실행 안 함 (경로만)
- `/review --quick` → 실행 안 함 (옵션만)

### 처리 절차

```
1. Restate  — 의견을 기술적으로 재술 (오해 없게)
2. Verify   — Read/Grep 도구만으로 해당 코드를 직접 확인 (Bash 사용 금지)
3. Evaluate — 기술적 타당성 판단
4. Respond  — 동의 or 근거 있는 반박을 review-code 프롬프트에 반영
```

### 금지

- "맞습니다!" / "좋은 지적이에요!" (검증 없는 동의)
- Verify 없이 의견을 바로 리뷰 방향에 반영

### 처리 예시

```
의견: "이 함수는 성능 문제가 있을 것 같아"
Verify: [Read로 함수 확인 → 중첩 루프 발견]
Evaluate: 타당함 — O(n²) 확인됨
→ review-code 프롬프트에 포함: "사용자 지적 — 성능 이슈 가능성, 검증됨"

의견: "이 부분은 타입 체크가 없어"
Verify: [Grep으로 상위 검증 로직 확인 → strict mode 확인]
Evaluate: 상위에서 처리됨 — 중복 불필요
→ review-code 프롬프트에 반영 안 함. 사용자에게 이유 명시.
```

---

## 2단계: 코드 리뷰 실행

```
Task tool 사용:
subagent_type: review-code
model: opus
prompt: |
  다음 코드를 리뷰해주세요:
  [1단계에서 확인한 코드/diff]

  **정적 분석 결과 (0단계):**
  [0단계 ruff check 결과 - 있으면 포함, 없으면 "정적 분석 통과" 또는 "Python 파일 없음"]

  **Auto-Scope 설정:**
  - scope: [1.5단계에서 결정된 scope]
  - security_scan_needed: [1.5단계 결과]

  scope가 'quick'이면:
  - CRITICAL, HIGH 등급만 스캔
  - MEDIUM, LOW는 필터링
  - 예상 시간: 1-2분

  scope가 'adversarial'이면:
  - 4개 페르소나 전체 공격
  - 모든 등급 보고
  - 예상 시간: 3-5분

  리뷰 형식:
  ## 전체 평가: [A/B/C/D/F]
  ## Scope Used: [adversarial | quick]

  ## Critical (즉시 수정 필요)
  ## Warning (권장 수정)
  ## Suggestion (개선 제안)

  ## 권장 조치
```

---

## 3단계: 보안 검토 (조건부)

**1.5단계에서 security_scan_needed = true인 경우에만 실행**

코드에 보안 관련 파일이 포함되면 security-scan을 실행:

```
Task tool 사용:
subagent_type: security-scan
model: sonnet
prompt: |
  다음 코드의 보안 취약점을 검사해주세요:
  [대상 코드]

  검사 항목:
  - OWASP Top 10 취약점
  - 인증/인가 로직
  - 입력 검증
  - SQL 인젝션
  - XSS
```

**security_scan_needed = false인 경우**:

- 이 단계를 스킵하고 4단계로 진행

---

## 4단계: 결과 요약

리뷰 결과를 사용자에게 요약 보고

### 리뷰 결과

| 항목       | 결과        |
| ---------- | ----------- |
| 전체 평가  | [A/B/C/D/F] |
| Critical   | [N개]       |
| Warning    | [N개]       |
| Suggestion | [N개]       |
| 보안 이슈  | [N개]       |

### 수정 필요 사항

[Critical/Warning 항목 목록]
