# MCP 서버 활용 가이드

> MCP(Model Context Protocol) 서버를 상황에 맞게 활용하여 최신 정보와 전문 도구를 사용합니다.

## MCP 서버 목록

| MCP                     | 용도                 | 사용 시점                             |
| ----------------------- | -------------------- | ------------------------------------- |
| **Context7**            | 라이브러리 최신 문서 | 라이브러리 API, 버전별 기능 확인      |
| **Magic** (21st.dev)    | 자연어 → UI 컴포넌트 | 프론트엔드 컴포넌트, 디자인 시스템    |
| **Exa**                 | AI 시맨틱 검색       | 코드 예제, 기술 문서 정밀 검색        |
| **Tavily**              | 리서치 특화 검색     | 종합 조사, 팩트체크, 기술 비교        |
| **Playwright**          | 브라우저 자동화      | 동적 페이지, E2E 테스트, 스크래핑     |
| **Sequential Thinking** | 단계별 추론          | 복잡한 설계, 다단계 문제 분해         |
| **PostgreSQL**          | DB 직접 쿼리         | 데이터 분석, 스키마 탐색, 쿼리 최적화 |

**PostgreSQL 사전 요구사항:** `./scripts/db-tunnel.sh start`

## MCP 선택 가이드

| 작업 유형        | 1순위 MCP               | 2순위 MCP |
| ---------------- | ----------------------- | --------- |
| 라이브러리 문서  | **Context7**            | Exa       |
| UI 컴포넌트 생성 | **Magic**               | Context7  |
| 기술 검색        | **Exa**                 | Tavily    |
| 종합 리서치      | **Tavily**              | Exa       |
| 웹 스크래핑      | **Playwright**          | -         |
| 복잡한 설계      | **Sequential Thinking** | -         |
| DB 분석          | **PostgreSQL**          | -         |

### MCP vs 기본 도구

| 상황                 |   MCP 사용    | 기본 도구 사용 |
| -------------------- | :-----------: | :------------: |
| 라이브러리 최신 문서 |  Context7 ✅  |  WebFetch ❌   |
| 단순 웹 검색         |       -       |  WebSearch ✅  |
| 의미 기반 검색       |    Exa ✅     |  WebSearch ❌  |
| 정적 페이지 조회     |       -       |  WebFetch ✅   |
| 동적 페이지 조회     | Playwright ✅ |  WebFetch ❌   |
| DB 쿼리              | PostgreSQL ✅ | Bash(psql) ❌  |

## MCP 활용 원칙

1. **최신 정보 우선**: 기억에 의존하지 말고 MCP로 확인 (`use context7 for React 19`)
2. **토큰 효율성**: MCP는 필터링된 결과 반환 — WebFetch 전체 페이지 로드 지양
3. **버전 명시**: `"use context7 for Next.js 15 App Router"` (버전 생략 ❌)

## NotebookLM 운영 규칙

- `Source` = 원문 근거, `Note` = 가공 산출물
- **Source 최대 50개** 제한 (노트북당)
- 50개 초과 시 추가 불가 — 추가 전 반드시 `notebook_get`으로 현재 Source 수 확인

## MCP 환경변수 설정

MCP 서버 사용을 위해 필요한 환경변수:

| MCP                  | 환경변수         | 설정 위치                                            |
| -------------------- | ---------------- | ---------------------------------------------------- |
| **Tavily**           | `TAVILY_API_KEY` | `~/.claude/settings.json` → `env` 또는 shell profile |
| **Exa**              | `EXA_API_KEY`    | `~/.claude/settings.json` → `env` 또는 shell profile |
| **Context7**         | 별도 키 불필요   | —                                                    |
| **Magic (21st.dev)** | `MAGIC_API_KEY`  | `~/.claude/settings.json` → `env`                    |
| **PostgreSQL**       | `DATABASE_URL`   | 프로젝트별 `.env`                                    |

`~/.claude/settings.json` 설정 예시:

```json
{
  "env": {
    "TAVILY_API_KEY": "YOUR_TAVILY_API_KEY",
    "EXA_API_KEY": "YOUR_EXA_API_KEY"
  }
}
```

## Context Window 최적화

MCP 툴 설명이 context를 과도하게 소비하는 경우 `disallowedTools`로 비활성화:

```yaml
# 에이전트 frontmatter 예시
disallowedTools:
  - mcp__magic__21st_magic_component_builder # 이 에이전트에서 Magic MCP 비활성화
  - mcp__tavily__tavily_research # 무거운 research MCP 비활성화
```

### 가이드라인

- 코드 구현 에이전트: Context7, Exa만 허용 (Tavily/Magic 비활성화)
- 리뷰 에이전트: MCP 전부 비활성화 (`disallowedTools: [mcp__*]` 형태는 미지원 → 개별 명시)
- web-research 스킬: 모든 MCP 허용 (용도 특화)
