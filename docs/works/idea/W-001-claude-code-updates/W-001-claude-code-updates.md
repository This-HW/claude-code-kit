---
work_id: "W-001"
title: "Claude Code v2.1.74~v2.1.86 업데이트 적용"
status: idea
current_phase: idea
phases_completed: []
size: Medium
priority: P2
tags: [claude-code, hooks, skills, agents, mcp, ci]
created_at: "2026-03-29T00:00:00+09:00"
updated_at: "2026-03-29T00:00:00+09:00"
---

# Claude Code v2.1.74~v2.1.86 업데이트 적용

> Work ID: W-001
> Status: idea
> 참고: memory/ideas_claude_code_updates.md (13개 항목 상세 목록)

## 요약

2026-03-29 기준 최근 2주 Claude Code 업데이트 중 이 프로젝트에 적용 가능한 13개 항목 식별.
하이브리드 Work-Task 시스템 설계 완료 후 이 Work 아이템을 통해 구체화 진행 예정.

## 적용 항목 (13개)

### HIGH (4개)

1. Conditional Hooks (`if` 필드) — `hooks.json`
2. `ExitWorktree` 툴 — worktree 에이전트 5개 frontmatter
3. Skills에 `effort` frontmatter 추가
4. `/plan` description 인자 문서화

### MEDIUM (6개)

5. `/loop` 스킬 추가 (ops 도메인)
6. Computer Use 옵션 문서화 (webapp-testing)
7. `rate_limits` 상태바 설정 (setup.sh)
8. `autoMemoryDirectory` 설정 (setup.sh)
9. `--bare` 플래그 CI 통합 (validate.yml)
10. `source: 'settings'` 경량 설치 옵션

### LOW (3개)

11. MCP 환경변수 문서화
12. Plugin Freshness 재검토
13. Context Window 최적화 문서화

## 다음 단계

하이브리드 Work-Task 시스템 설계 완료 후 planning 단계로 전환.
