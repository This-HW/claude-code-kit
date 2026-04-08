# MCP 서버 활용 가이드

> 이 문서는 Claude Code에서 사용 가능한 MCP 서버들의 용도와 올바른 선택 방법을 설명합니다.

---

## 1. MCP 서버 7개 상세 설명

| MCP 서버                | 주요 용도                            | 사용 시점                             | 장점                                  | 단점/주의사항              |
| ----------------------- | ------------------------------------ | ------------------------------------- | ------------------------------------- | -------------------------- |
| **Context7**            | 라이브러리·프레임워크 공식 문서 조회 | API 문법, 설정 방법, 버전별 차이 확인 | 최신 문서 보장, 훈련 데이터 오류 방지 | 버전을 반드시 명시해야 함  |
| **Exa**                 | 시맨틱 코드/기술 검색                | 특정 기술 구현 패턴, 코드 예시 탐색   | 코드 컨텍스트 이해, 정밀한 기술 검색  | 일반 검색보다 느릴 수 있음 |
| **Tavily**              | 종합 리서치, 팩트 체킹, 기술 비교    | 라이브러리 비교, 보안 취약점 조사     | 광범위한 정보 수집, 출처 다양         | 정확도 검증 필요           |
| **Playwright**          | 동적 페이지 스크래핑, E2E 테스트     | JS 렌더링 필요 페이지, UI 자동화      | JavaScript 실행 가능, 브라우저 제어   | 정적 페이지엔 오버킬       |
| **Sequential Thinking** | 복잡한 다단계 설계·문제 분해         | 아키텍처 설계, 복잡한 알고리즘 계획   | 단계적 추론, 논리 체계화              | 단순 작업엔 불필요         |
| **PostgreSQL**          | DB 쿼리, 스키마 탐색, 쿼리 최적화    | 데이터 분석, 스키마 확인, 성능 튜닝   | 직접 DB 접근, 실시간 데이터           | SSH 터널 선행 필요         |
| **Magic (21st.dev)**    | 자연어 → UI 컴포넌트 생성            | 빠른 UI 프로토타이핑, 컴포넌트 제안   | 빠른 컴포넌트 생성                    | 프로덕션 코드 검토 필요    |

---

## 2. MCP vs 기본 도구 선택 플로우차트

```
작업 유형은 무엇인가?
         │
         ├─ 라이브러리/API 문서 확인
         │        │
         │        └─ Context7 사용
         │           (NEVER WebFetch — 훈련 데이터가 오래됨)
         │
         ├─ 코드/기술 검색
         │        │
         │        ├─ 정밀한 기술 쿼리? → Exa 사용
         │        └─ 일반 검색? → WebSearch 사용
         │
         ├─ 웹 페이지 접근
         │        │
         │        ├─ JS 렌더링 필요? → Playwright 사용
         │        └─ 정적 HTML? → WebFetch 사용
         │
         ├─ 리서치/팩트 체킹
         │        │
         │        └─ Tavily 사용
         │
         ├─ DB 조회
         │        │
         │        └─ PostgreSQL MCP 사용
         │           (반드시 db-tunnel.sh start 먼저)
         │
         └─ 복잡한 설계 문제
                  │
                  └─ Sequential Thinking 사용
```

---

## 3. 작업 유형별 MCP 선택 가이드

| 작업                           | 잘못된 선택              | 올바른 선택         | 이유                            |
| ------------------------------ | ------------------------ | ------------------- | ------------------------------- |
| Next.js App Router API 확인    | WebFetch (공식 문서 URL) | Context7            | 훈련 데이터가 구 버전일 수 있음 |
| React Hook 사용법              | WebSearch                | Context7            | 공식 문서가 가장 정확           |
| "zustand vs jotai 비교" 리서치 | WebSearch                | Tavily              | 종합적인 비교 분석에 적합       |
| SPA 페이지 데이터 스크래핑     | WebFetch                 | Playwright          | WebFetch는 JS 미실행            |
| 정적 블로그 포스트 읽기        | Playwright               | WebFetch            | Playwright는 오버킬             |
| DB 스키마 확인                 | Bash (psql 명령)         | PostgreSQL MCP      | MCP가 더 편리하고 안전          |
| 마이크로서비스 아키텍처 설계   | 즉시 구현                | Sequential Thinking | 단계적 설계가 먼저              |

---

## 4. 에이전트별 MCP 설정 예시 (frontmatter)

에이전트는 필요한 MCP만 허용하고 나머지는 비활성화합니다. 미사용 MCP를 열어두면 컨텍스트 윈도우를 낭비합니다.

```yaml
# 코드 구현 에이전트 — Context7, Exa만 허용
---
name: implement-code
model: sonnet
disallowedTools:
  - Task
  - mcp__tavily__tavily_search
  - mcp__tavily__tavily_research
  - mcp__playwright__browser_navigate
  - mcp__magic__ui_generate
  # Context7, Exa는 허용 (라이브러리 문서 참조 필요)
---
# 코드 리뷰 에이전트 — 모든 MCP 비활성화
---
name: review-code
model: opus
disallowedTools:
  - Task
  - mcp__context7__resolve-library-id
  - mcp__context7__query-docs
  - mcp__exa__web_search_exa
  - mcp__exa__get_code_context_exa
  - mcp__tavily__tavily_search
  - mcp__tavily__tavily_research
  - mcp__playwright__browser_navigate
  - mcp__magic__ui_generate
  - mcp__sequential-thinking__sequentialthinking
  # 리뷰는 코드만 읽으면 됨 — 외부 도구 불필요
---
# web-research 스킬 — 모든 MCP 허용
---
name: web-research
# disallowedTools 없음 — 모든 MCP 활용
---
```

---

## 5. Context7 사용 시 버전 명시 규칙

Context7는 버전별로 다른 문서를 반환합니다. 버전을 생략하면 잘못된 API가 반환될 수 있습니다.

```
# 잘못된 예 — 버전 없음
"use context7 for Next.js App Router"
→ 어떤 버전인지 모름, 잘못된 문서 반환 가능

# 올바른 예 — 버전 명시
"use context7 for Next.js 15 App Router"
"use context7 for React 18 Hooks"
"use context7 for Prisma 5 Schema"
"use context7 for TypeScript 5.4 satisfies operator"
```

**버전 확인 방법:**

```bash
# package.json에서 버전 확인
cat package.json | grep '"next"\|"react"\|"typescript"'
```

---

## 6. PostgreSQL MCP 사용 전 필수 절차

```bash
# 반드시 먼저 실행
./scripts/db-tunnel.sh start

# 그 후 PostgreSQL MCP 사용
# (MCP가 localhost:5432로 연결)

# 작업 완료 후
./scripts/db-tunnel.sh stop
```

**터널 없이 PostgreSQL MCP 사용 시:** 연결 오류 발생.

---

## 7. Context Window 최적화 가이드

MCP 도구는 컨텍스트를 소비합니다. 아래 원칙으로 효율을 높입니다.

| 원칙                     | 방법                                              |
| ------------------------ | ------------------------------------------------- |
| 미사용 MCP 비활성화      | `disallowedTools`에 사용하지 않는 MCP 명시        |
| 필요한 문서만 조회       | Context7에서 전체 문서 대신 특정 API만 검색       |
| 검색 결과 캐시 활용      | 같은 라이브러리 문서를 세션 내 반복 조회 금지     |
| 와일드카드 비활성화 불가 | `mcp__*` 와일드카드는 지원 안 됨 — 개별 명시 필요 |

---

## 8. NotebookLM 활용 규칙

NotebookLM을 사용할 때는 Source 관리에 주의가 필요합니다.

```
작업 전: notebook_get → 현재 Source 수 확인
         Source 수 < 50개? → Source 추가 가능
         Source 수 = 50개? → 기존 Source 정리 후 추가

Source vs Note 구분:
  Source = 원본 증거 자료 (PDF, 문서, URL)
  Note   = 처리된 출력물 (요약, 분석 결과)
  → 혼동하면 Source 한도 계산 오류 발생
```
