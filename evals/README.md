# Agent Evals

핵심 에이전트(`review-code`, `fix-bugs`, `implement-code`)의 **행동 회귀**를
기계로 검증하는 하네스. 에이전트 정의(`.md` frontmatter + 시스템 프롬프트)를
수정했을 때 품질이 후퇴했는지 감지하기 위한 것이다.

`plugins/` 밖(레포 루트)에 둔다 — 플러그인 설치 용량에 영향을 주지 않기 위함.

## 철학

- **Deterministic-first.** 채점은 규칙(정규식/파일 검사/pytest 실행)으로 하며,
  LLM-judge는 opt-in 보조 수단이다. deterministic 검사를 전부 통과한 시나리오만
  judge를 태운다.
- **False-green 금지 (v2.9.3 교훈).** 실행 불가(claude CLI 부재 등)를 성공으로
  위장하지 않는다 — 반드시 별도 exit code(`SKIPPED=2`)로 구분한다.
- **릴리스 전 필수 게이트이지 per-commit CI가 아니다.** 실제 행동 eval은
  `claude -p`를 호출해 API 비용이 든다. 그래서:
  - `--validate`(스키마 오프라인 검증)만 `scripts/verify-done.sh` §10에 편입한다.
  - 전체 행동 eval(`scripts/run-evals.sh`, 인자 없이)은 릴리스 전에 수동/온디맨드로
    실행한다.

## 디렉토리 구조

```
evals/
  run.py                 러너 (stdlib만, 단일 파일)
  scenarios/<agent>/<scenario-id>/
    task.md              에이전트에게 줄 과제 프롬프트
    fixture/             대상 코드 (버그를 심거나 TODO로 비워둔 상태)
    expect.json          채점 기준 (deterministic assertions + opt-in judge rubric)
  baseline/<date>.json    --baseline으로 저장된 기준선 (git 추적)
  reports/<timestamp>.json  매 실행 리포트 (gitignore 대상, 로컬 전용)
```

## 사용법

```bash
# 오프라인 스키마 검증 (API 불필요, verify-done.sh §10과 동일)
./scripts/run-evals.sh --validate

# claude 미호출, 실행 계획만 확인
./scripts/run-evals.sh --dry-run

# 특정 에이전트/시나리오만 실행 (API 비용 발생)
./scripts/run-evals.sh --agent fix-bugs
./scripts/run-evals.sh --agent review-code --scenario sql-injection

# 병렬 실행 (기본 1)
./scripts/run-evals.sh --parallel 4

# 기준선 저장 (릴리스 시점 1회)
./scripts/run-evals.sh --baseline

# 기준선 대비 후퇴 검출 (pass-rate 하락 시 exit 1)
./scripts/run-evals.sh --compare evals/baseline/2026-07-07.json
```

환경 변수:

| 변수 | 설명 | 기본값 |
| --- | --- | --- |
| `CKKIT_EVAL_TIMEOUT` | 시나리오당 타임아웃(초) | 300 |
| `CKKIT_EVAL_JUDGE` | `1`이면 deterministic 전부 통과 시 LLM-judge 실행 | (미실행) |

## exit code

| code | 의미 |
| --- | --- |
| 0 | 전체 pass (또는 `--validate`/`--dry-run` 정상) |
| 1 | 하나 이상 fail, 또는 `--compare` 시 baseline 대비 후퇴, 또는 스키마 오류 |
| 2 | **SKIPPED** — `claude` CLI를 PATH에서 찾을 수 없어 실행 불가. 절대 0으로 위장하지 않는다 |

## 채점 기준 (`expect.json`)

```json
{
  "assertions": [
    { "type": "output_regex", "pattern": "off-by-one", "flags": "i" },
    { "type": "output_contains_any", "values": ["sql injection", "parameterize"] },
    { "type": "output_not_contains", "values": ["secret-key"] },
    { "type": "pytest_green", "path": "." },
    { "type": "file_contains", "file": "stats.py", "pattern": "range\\(len" },
    { "type": "delegation_signal" }
  ],
  "judge": {
    "enabled": false,
    "rubric": "채점 기준 서술",
    "threshold": 7
  }
}
```

- `output_contains_any`/`output_not_contains`는 대소문자 무시 부분 문자열 매칭이다
  — 동의어를 넉넉히 나열해 brittleness를 낮춘다.
- `pytest_green`은 fixture의 임시 복사본에서 `python3 -m pytest <path>`를 실행해
  exit 0인지 확인한다.
- `delegation_signal`은 표준 3-마커(`---DELEGATION_SIGNAL---` / `TYPE:` /
  `---END_SIGNAL---`) 존재 여부만 확인한다.
- `judge`는 opt-in이다. `enabled: true`면 `rubric` 필수. deterministic이 전부
  통과하고 `CKKIT_EVAL_JUDGE=1`일 때만 실행되며, judge 실패는 경고로만 기록된다
  (deterministic 통과 시 최종 판정은 pass 유지).

## 시나리오 추가 가이드

1. `evals/scenarios/<agent-name>/<scenario-id>/` 디렉토리 생성.
   `<agent-name>`은 `plugins/common/agents/**/<name>.md`에 실재해야 한다.
2. `fixture/`에 대상 코드를 둔다 — review-code는 버그가 심긴 코드, fix-bugs는
   버그 코드 + 실패하는 pytest 테스트, implement-code는 `TODO`/`NotImplementedError`
   상태의 코드 + red 상태 pytest 테스트.
3. `task.md`에 에이전트에게 줄 과제를 한국어로 명확히 서술한다.
4. `expect.json`에 assertions를 정의한다 — 최소 1개 이상, deterministic 우선.
5. `python3 evals/run.py --validate`로 스키마를 확인한다.
6. `python3 evals/run.py --dry-run --agent <name> --scenario <id>`로 계획을
   확인한 뒤, 필요 시 `--agent <name> --scenario <id>`로 실제 1회 실행해 본다
   (API 비용 발생 — 로컬에서 최소 횟수로).

## 릴리스 체크리스트 연동

- `scripts/verify-done.sh` §10이 `--validate`를 자동 실행한다(오프라인, fail-closed).
- 실제 행동 eval(`scripts/run-evals.sh`, 필터 없이 전체)은 릴리스 전 수동 1회
  실행해 `--baseline`으로 기준선을 남기고, 이후 프롬프트 수정 PR에서는
  `--compare`로 후퇴 여부를 확인한다.

## 보안 경계 (적대적 리뷰 B 반영)

- 실측 실행(`run-evals.sh`)은 에이전트를 `--permission-mode bypassPermissions`로
  돌린다 — temp 작업 디렉토리는 **샌드박스가 아니다**. 따라서 **이 레포에 커밋된,
  리뷰를 통과한 시나리오만 실행**하라. 외부 기여 시나리오는 fixture/task.md의
  프롬프트 인젝션 여부를 사람이 검토한 뒤 병합한다.
- fixture 내 `conftest.py`는 금지 — pytest 수집 시 자동 실행되므로 `--validate`가
  fail 처리한다.
- 채점 경로(`path`/`file`)는 fixture 밖 탈출이 차단된다(`_safe_join`).

## 운영 규칙

- **judge는 advisory-only**: 최종 pass/fail에 영향을 주지 않고 리포트에만 기록된다
  (`advisory: true`). 게이트는 deterministic assertions가 전담한다.
- **실패한 런은 baseline이 되지 못한다**: exit≠0이면 `--baseline` 저장을 거부한다.
  같은 날짜 재실행 시 기존 baseline은 `.bak`으로 백업 후 교체된다.
- **커버리지 후퇴도 후퇴다**: `--compare`는 pass_rate 하락뿐 아니라 에이전트/시나리오
  수 감소도 회귀로 판정한다.
- **fix-bugs 게이밍 차단**: `file_unchanged` assertion이 테스트 파일 변조(테스트를
  고쳐서 green 만들기)를 fail 처리한다.

## 추가 주의사항 (재감사 반영)

- **reports/의 민감정보 가능성**: 에이전트(Read/Grep 보유)가 호스트 파일 내용을 출력에
  포함하면 `evals/reports/*.json`에 평문으로 남는다 (로컬 전용·gitignore — 원격 유출
  채널은 없지만 리포트 공유 전 확인하라).
- **baseline 백업은 1세대만**: 같은 날 재실행 시 `.bak`이 덮어써진다 — 보존이 필요하면
  재실행 전에 커밋하라.
- **부분 실행은 baseline이 될 수 없다**: `--agent`/`--scenario` 필터가 걸린 실행에서
  `--baseline`은 저장을 거부한다 (부분 기준선이 커버리지를 침묵 은닉하는 것 차단).
