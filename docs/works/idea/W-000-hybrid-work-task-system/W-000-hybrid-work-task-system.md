---
work_id: "W-000"
title: "하이브리드 Work-Task 시스템 구현"
status: idea
current_phase: idea
phases_completed: []
size: Medium
priority: P0
tags: [work-system, task-system, infrastructure, meta]
created_at: "2026-03-29T00:00:00+09:00"
updated_at: "2026-03-29T00:00:00+09:00"
---

# 하이브리드 Work-Task 시스템 구현

> Work ID: W-000
> Status: idea
> 참고: plugins/common/skills/references/hybrid-work-task.md (설계 문서)

## 요약

Work 파일(영구 저장)과 Claude Code Task 시스템(세션 런타임)을 통합하는
하이브리드 추적 시스템. 설계는 완료, 실제 구현 필요.

## 구현 필요 항목

### 인프라

- [ ] `docs/works/` 폴더 구조 확립 (idea / active / completed)
- [ ] Work 파일 템플릿 (W-XXX-{slug}.md, progress.md, decisions.md, planning-results.md, review-results.md)
- [ ] `scripts/work.sh` — Work 상태 관리 CLI (생성, 조회, Phase 전환)

### 스킬 통합

- [ ] `plan-task` 스킬 — Work 파일 생성 + Planning Tasks 자동 생성
- [ ] `auto-dev` 스킬 — Work 파일 로드 + Development Tasks 생성 (병렬 분해)
- [ ] Validation Phase — review + security-scan 병렬 Task 패턴

### 에이전트 통합

- [ ] Task 완료 시 Work 파일 업데이트 규칙 (progress.md, decisions.md)
- [ ] Phase Gate 강제 (Task blocks/blockedBy)
- [ ] Work ID를 Task metadata에 연결하는 규약

### Plugin 완전 통합 (테스트 검증 완료 2026-03-29)

- [ ] `plugins/common/.claude-plugin/plugin.json`에 `hooks` 필드 추가
- [ ] `plugins/common/hooks/hooks.json`에 PreToolUse/PostToolUse 훅 등록
      (protect-sensitive.py, auto-format.py, governance-check.py, log-subagent.py)
- [ ] 훅 커맨드 경로를 `$HOME/.claude/hooks/` 하드코딩 → `${CLAUDE_PLUGIN_ROOT}/hooks/` 로 변경
- [ ] `setup.sh`에서 hooks를 settings.json에 수동 주입하는 로직 제거 (플러그인이 대신)

> 근거: PreToolUse/PostToolUse 모두 plugin hooks.json에서 정상 동작 확인.
> CLAUDE_PLUGIN_ROOT 환경변수 자동 주입됨. hooks/hooks.json 위치 자동 탐색.

### 문서

- [ ] `work-system.md` → 하이브리드 설계 반영 업데이트
- [ ] CLAUDE.md Work 시스템 섹션 추가
- [ ] 에이전트별 Work-Task 통합 가이드

## 다음 단계

W-000 planning 시작 전 W-001(Claude Code 업데이트 적용)을 먼저 이 시스템으로
실행해보며 실전 검증 후 보완.
