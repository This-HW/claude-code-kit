# Changelog

All notable changes to claude-code-kit are documented here.

Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

---

## [2.7.2] — 2026-06-22

### Fixed — stop-validator 테스트 타임아웃 오탐 (대형 레포) + 전체 스위트 실행 제거

전체 테스트 스위트가 60초를 넘는 레포에서 `.py`를 편집할 때마다, 코드가 전부
통과하는데도 `test_failure: 테스트 실행 시간 초과 (60초)`로 Stop이 거짓 차단되던
문제를 수정. 근본 원인은 매 턴 종료마다 도는 Stop 훅이 **전체 pytest 스위트**를
실행한 것 — 지연이 스위트 크기에 비례해 대형 레포에서 항상 타임아웃났다.

- **전체 스위트 실행 제거(근본 차단)**: `check_tests()`는 이제 이번 세션이 편집한
  `test_*.py`/`*_test.py`만 실행한다(lint의 스코프 철학과 동일). 소스만 편집했으면
  테스트 검증을 스킵한다. 전체 회귀 검증은 CI(`validate.yml`)·`/test`·
  `verify-done.sh`의 몫. 이로써 대형 레포 타임아웃 오탐이 **구조적으로 불가능**해진다.
- **타임아웃 ≠ 실패**: 남는 단일 느린 테스트를 위해 `TimeoutExpired`는 차단이 아니라
  비차단 `[WARN]`으로 강등(통과 반환). 실제 실패 테스트는 여전히 차단된다.
- **타임아웃 설정 가능**: `CLAUDE_STOP_TEST_TIMEOUT` 환경변수로 한도 조절(기본 60초).
- **죽은 코드 제거**: 전체 스위트 탐색용 `find_test_files()`·`EXCLUDE_DIRS` 삭제.
- **부수**: `scripts/verify-done.sh`가 pytest 인터프리터 탐색 시 프로젝트
  `.venv`/`venv`를 우선하도록 정렬(훅의 `_pytest_python()`과 일관).

---

## [2.7.1] — 2026-06-15

### Fixed — stop-validator 무한 루프 + pytest 오탐

턴 종료 시 도는 `stop-validator.py`가 외부 dirty `.py`(병렬 세션 미커밋 등)를 만나면
무한 차단 루프에 빠지던 문제를 수정. 하니스의 연속 차단 cap이 강제 종료할 때까지 반복됐다.

- **무한 루프 근본 차단**: `max_retries_exceeded` 분기가 `block()` + 카운터 reset 하던 것을
  `allow()`로 전환. cap은 "검증 중단·턴 종료"가 정상인데 정반대로 동작해
  `test_failure ↔ max_retries` 사이클을 영원히 돌렸다.
- **pytest 오탐(#332)**: `check_tests()`가 시스템 `python3`로 pytest를 실행해
  모듈 부재 시 `No module named pytest` → `test_failure`로 차단했다. 이제 프로젝트
  `.venv`/`venv` 인터프리터를 우선 사용하고, 모듈 부재는 차단이 아니라 스킵으로 처리.
- **`stop_hook_active` 존중**: stdin을 읽어 stop-hook 재진입(`stop_hook_active=true`) 시
  즉시 통과 — 네이티브 무한 루프 가드.
- **세션별 파일 스코핑(1차 트리거 제거)**: 기존엔 `git diff HEAD`로 레포 전체 dirty
  `.py`를 검증 대상으로 삼아, *이 세션이 안 건드린* 병렬 세션 미커밋 `.py`에도 매 턴
  pytest를 돌렸다(사건 1차 트리거). 이제 Stop 훅 `transcript_path`를 파싱해 이 세션이
  Edit/Write로 실제 편집한 파일만 검증한다. transcript 부재 시 전체 검증으로 폴백.
- **TTY hang 가드**: `_read_input()`이 수동 실행 시 `stdin.read()` EOF 대기로 멈추지
  않도록 `isatty()` 체크 추가.

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
