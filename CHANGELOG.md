# Changelog

All notable changes to claude-code-kit are documented here.

Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

---

## [2.7.0] — 2026-06-14

### Removed — Core-only consolidation

테스트 0개, v2.0.0 이후 실질 변경이 없던 **5개 도메인 플러그인을 제거**하고 단일 core로 집중. 잘 테스트된 core를 들고 가는 게 미검증 플러그인 5개를 배포·버전관리하는 것보다 zero-debt다.

- 제거: `claude-code-kit-frontend`, `-infra`, `-ops`, `-data`, `-integration` (총 33 agents, 10 skills, **0 tests**)
- `marketplace.json`을 core 1개만 노출하도록 정리
- `setup.sh` 도메인 선택/설치 로직 제거 (`--all`/`--list` 플래그 삭제)
- README·CLAUDE.md를 단일 플러그인 구조(2-tier)로 갱신
- **복구 지점**: 제거 직전 상태를 `v2.6.0-with-domains` 태그로 보존 (git 히스토리로 언제든 복원 가능)

### Changed

- core `claude-code-kit` 버전 2.6.0 → 2.7.0
- **배포 모드: 상대경로 → `git-subdir`** — `marketplace.json`의 플러그인 source를 `./plugins/common`(로컬 경로)에서 `git-subdir`(모노레포 서브디렉토리 sparse-clone)로 전환. 이제 진짜 리모트/버전 관리 플러그인으로 동작하며 `/plugin`의 "Update now"가 작동한다. (단일 플러그인이 되어 가능해짐)

---

## [2.6.0] — 2026-06-13

네이티브 프리미티브 최대 활용 + 자체 재구현 제거 (Spec 1~5, W-005~009).
설계 스펙: `docs/specs/2026-06-13-*.md`. 전부 하위호환 (fail-open / graceful degradation).

### Added

- **Feedback memory loop** (Spec 3) — `hooks/feedback_ledger.py`로 validation·review 결함을 누적(상한·중복제거·감쇠 SSOT)하고, session-start가 상위 빈도 교훈을 `=== LESSONS ===`로 주입. 캡처 진입점은 `scripts/feedback.sh`(work.sh와 동일한 ./scripts 관례, `CLAUDE_PLUGIN_ROOT` 의존 없음). `rules/feedback-loop.md`.
- **Loop engineering** (Spec 5) — `rules/loop-engineering.md`로 게이트(설계·사람 멈춤) vs 루프(실행·자율 완주)를 분리. auto-dev 배치 드라이버 + 종료 가드.
- **Plugin dependencies** (Spec 1) — 도메인 5종 매니페스트에 `dependencies: ["claude-code-kit"]` 선언 (네이티브가 common 강제 활성화).
- **Architecture & Concepts** README 섹션 (Spec 4) — 네 갈래 융합(네이티브·superpowers·Hermes·Work) + Harness×Loop engineering narrative.
- **Definition of Done 완료 게이트** (Spec 6) — `scripts/verify-done.sh`(JSON·CI필드·ruff·pytest·시크릿·카운트 sync·stale 참조 통합 게이트, FAIL 시 비정상 종료) + `rules/definition-of-done.md`(Iron Law of Completion + 금지 어휘). "완료"를 판단이 아니라 명령의 출력으로 강제. loop-engineering 종료 조건과 연계.

### Changed

- **Hooks exec form** (Spec 1) — `hooks.json`를 `command`+`args[]` exec form으로 전환, `${CLAUDE_PLUGIN_ROOT}` 경로 인용 문제 제거.
- **Stop hook** (Spec 1) — `stop-validator.py`가 실패 시 네이티브 `{"decision":"block","reason":...}`를 emit해 Claude가 수정 턴을 이어가도록 개선.
- **Orchestration model** (Spec 2) — "main만 조율"에서 "스케일별 네이티브 프리미티브"로 재서술. Small/Medium은 스킬 주도 플랫, Large는 네이티브 `ultracode`. `agent-teams` 스킬을 네이티브 workflow 가이드로 재정의.
- delegation-signal 표준 포맷을 `rules/agent-delegation-chain.md`에 SSOT로 명문화.
- **superpowers interop** — `using-claude-code-kit`을 additive-only로 슬림화. 범용 스킬 규율(1% 룰·red flags)은 `superpowers:using-superpowers`와 공유하고 kit 전용 델타(에이전트맵·Work·체인·native/loop/DoD)만 유지. 둘 다 활성 시 중복 0, kit standalone도 자급. interop 가이드 섹션 추가.

### Removed

- **`agent-lifecycle.py`** (Spec 1) — 순수 로깅 훅 삭제. 서브에이전트 관측은 네이티브 OpenTelemetry(`agent_id`/`parent_agent_id` 스팬)로 위임. `SubagentStart`/`SubagentStop`/`PreCompact` 등록 제거.

### Notes

- 네이티브 dynamic workflow(`ultracode`)·`/goal`은 대화형 전용이라 스킬에서 프로그래밍 트리거 불가(2026.6 검증) → 자동 위임은 검증된 Task 시스템 + 스킬 루프로 구현(자체 데몬 없음).
- 버전: common 2.3.0→2.6.0, 도메인 플러그인 5종 2.0.0→2.1.0.

---

## [2.2.0] — 2026-05-03

### ⚠️ Behavior Change — Stop Hook

The `Stop` hook has been replaced with an automated validator (`stop-validator.py`).

**What changed:** Previously, the Stop hook asked Claude to self-evaluate completion. Now it runs `ruff` and `pytest` automatically and **blocks the session from stopping if either fails.**

**Who is affected:** All users with Python files modified in the current session.

**How to disable** (per-session or globally):

```json
// plugins/common/hooks/hooks.json → restore the prompt-based hook:
"Stop": [
  {
    "hooks": [
      {
        "type": "prompt",
        "prompt": "개발 작업이 완료된 경우 ...",
        "timeout": 30
      }
    ]
  }
]
```

Or remove the `Stop` section entirely to disable all stop validation.

**How it works:**
- No Python files modified → instant pass (no ruff/pytest run)
- `ruff` not installed → warning to stderr, pass
- `pytest` not installed → warning to stderr, pass
- auto-dev pipeline already validated → marker file detected, skip (no double-validation)
- Max 2 auto-fix retries before giving up

### Added

- **`stop-validator.py`** — automated Stop hook: detects Python changes, runs ruff (with auto-fix) and pytest, blocks on failure with structured JSON output
- **7 unit tests** for `stop-validator.py` (`hooks/tests/test_stop_validator.py`):
  - `test_no_py_changes_exits_zero`
  - `test_lint_auto_fixed_prints_json_and_exits_zero`
  - `test_lint_auto_fixed_json_structure`
  - `test_test_failure_exits_two_with_correct_json`
  - `test_marker_skip_exits_zero_and_consumes_marker`
  - `test_lint_error_when_auto_fix_fails_exits_two`
  - `test_max_retries_exceeded_exits_two`
- **auto-dev SKILL.md** — T-merge step now creates a validation marker to prevent double-validation when auto-dev pipeline already ran lint/test

### Fixed

- Stop hook `PROJECT_ROOT` now derived from `git rev-parse --show-toplevel` (stable regardless of harness cwd)
- git-relative paths resolved against `PROJECT_ROOT` before passing to ruff (fixes silent lint skip when hook cwd ≠ project root)
- TOCTOU race condition in marker file check replaced with atomic `try/except unlink()`

---

## [2.0.0] — 2026-04-22

### Breaking Changes

- **Removed from all agent frontmatter** (non-standard fields, unsupported by the official plugin spec):
  - `permissionMode` — removed from 6 agents
  - `context_cache` — removed from all agents
  - `output_schema` — removed from all agents
  - `next_agents` — removed from all agents
  - Inline `hooks:` blocks — removed from all agents (covered by plugin-level `hooks/hooks.json`)
- **Removed from all skill frontmatter**:
  - `domain`, `argument-hint`, `allowed-tools` — non-standard, not supported by official spec

If you extended agents by adding these fields in project-local overrides, remove them to stay compliant.

### Added

- **Manifest compliance** — all 6 `plugin.json` files now include `homepage`, `repository`, `license`, `author.email` for official registry submission
- **`maxTurns` field** — added to 11 agents to prevent infinite loops:
  - Implementation agents (`implement-code`, `fix-bugs`, `write-tests`, `plan-implementation`, `write-api-tests`): `maxTurns: 20`
  - Exploration/review agents (`review-code`, `verify-code`, `verify-integration`, `explore-codebase`, `analyze-dependencies`, `security-scan`): `maxTurns: 10`
- **New lifecycle hooks** in `hooks/hooks.json`:
  - `SubagentStart` — logs agent invocation start
  - `SubagentStop` — logs agent invocation completion
  - `PreCompact` — saves state summary before context compaction
- **`agent-lifecycle.py`** — new hook script handling the three lifecycle events above
- **91 unit tests** for all hook scripts:
  - `tests/test_session_start.py` — 19 tests (frontmatter parsing, task map parsing, rules loading, main output format)
  - `tests/test_protect_sensitive.py` — 33 tests (file path blocking, content scanning, integration)
  - `tests/test_auto_format.py` — 19 tests (path validation, ESLint config detection, pipeline execution)
  - `tests/test_utils.py` — 21 tests (safe_path, debug_log, is_debug_mode, get_project_root)
- **CI strengthened** (`.github/workflows/validate.yml`):
  - `Check plugin.json required fields` step
  - `Check agent frontmatter — no forbidden fields` step
  - `Run hook unit tests` step (`pytest plugins/common/hooks/tests/ -v`)
- **English skill descriptions** — all 14 skill `description` fields converted from Korean to English for correct Claude auto-invocation behavior

### Fixed

- `agent-creator` skill template: removed `permissionMode` from the generated agent template (it was showing a now-unsupported field)
- All `hooks/hooks.json` paths already used `${CLAUDE_PLUGIN_ROOT}` — verified correct

---

## [1.1.5] — 2026-04-21

### Fixed

- W-007 validation issues: T-merge guard, confidence wording, Bash scope

---

## [1.1.4] — 2026-04-14

### Fixed

- GitHub Actions gitleaks failure
- Documentation updates

---

## [1.1.3] and earlier

Initial releases establishing the 33-agent + 12-skill core structure across 6 plugin domains.
