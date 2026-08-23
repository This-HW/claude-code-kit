---
name: harness-export
description: Export the kit's host-neutral rules to AGENTS.md so non-Claude-Code harnesses (Codex, OpenCode, Copilot, Pi, Hermes) follow the same discipline. Use when a repo is worked by more than one agent harness, or after changing rules/. Trigger with /harness-export.
model: sonnet
effort: medium
---

# Harness Export — 규범을 하네스 중립으로 내보내기

CCK의 규범(`rules/*.md`)은 **Claude Code의 SessionStart 훅으로만** 주입된다.
그런데 Orca·Paseo 같은 ADE에서는 한 레포에 Claude Code와 Codex·OpenCode·Pi를
**동시에** 붙여 굴린다. 그 순간 레포의 절반은 CCK 규율 밖에서 동작한다.

이 스킬은 규범을 `AGENTS.md`(Codex·OpenCode·Copilot CLI·Cursor가 공통으로 읽는 사실상
표준)로 내보내 그 구멍을 메운다.

## 사용 시점

| 상황 | 실행 |
| --- | --- |
| 레포를 두 개 이상의 하네스가 만진다 | `/harness-export` 1회 → `AGENTS.md` 커밋 |
| `rules/*.md`를 고쳤다 | 재생성 (안 하면 다른 하네스가 옛 규범을 읽는다) |
| CI/게이트에서 최신 여부만 확인 | `--check` |

## 절차

### 소비자(플러그인 설치) 환경 — 기본 경로

구현은 **플러그인 안**에 있다(`<플러그인 루트>/hooks/export_harness.py`).
설치한 프로젝트에는 이 kit의 `scripts/`가 없으므로 이 경로를 쓴다.

> **`$CLAUDE_PLUGIN_ROOT`를 그대로 신뢰하지 마라.** 이 변수는 스킬의 Bash 컨텍스트에
> **설정돼 있지 않을 수 있다**(kit의 `feedback.sh`·`auto-dev`가 같은 이유로 의존을
> 제거했다). 빈 값이면 `python3 "/hooks/export_harness.py"`가 되어 파일 없음으로
> **종료코드 2**가 나고, exit 표상 2는 "SKIPPED"라서 **원인을 오보고**하게 된다.
> 아래처럼 먼저 해석하라.

```bash
# 1) 구현 위치 해석 — 변수가 비면 캐시에서 찾는다
EH="${CLAUDE_PLUGIN_ROOT:-}/hooks/export_harness.py"
[ -f "$EH" ] || EH=$(ls -1 ~/.claude/plugins/cache/*/claude-code-kit/*/hooks/export_harness.py 2>/dev/null | sort -V | tail -1)
[ -f "$EH" ] || { echo "export_harness.py를 찾지 못했다 — 플러그인 설치 확인"; exit 2; }

# 2) 현재 프로젝트(git 최상위)의 AGENTS.md 갱신
python3 "$EH"

# 3) 드리프트 검사만 (기록하지 않음)
python3 "$EH" --check

# 4) 블록 내용만 확인 / 다른 프로젝트 대상
python3 "$EH" --stdout
python3 "$EH" --target /path/to/project
```

`--plugin-root`를 **명시**했는데 그 경로에 `rules/`가 없으면 자동 탐색으로 폴백하지
않고 exit 2다. 지정한 것과 다른 레포의 규범을 내보내고 성공을 보고하는 사고를 막는다.
명시하지 않으면 **스크립트 자기 위치**가 1순위이고(플러그인 캐시에서도 불변),
환경변수는 그 다음이다 — 셸에 남은 다른 플러그인의 값이 남의 규범을 내보내지 않도록.

### kit 레포에서 개발할 때

```bash
./scripts/export-harness.sh          # 내보내기
./scripts/export-harness.sh --check  # 드리프트 검사 (게이트가 쓰는 명령)
```

## exit code

| code | 의미 | 대응 |
| --- | --- | --- |
| 0 | 성공 / 드리프트 없음 | — |
| 1 | 드리프트 · **블록 본문 변조** · 마커 손상 · 분류 미등재/유령 엔트리 · 인코딩 실패 · 트리 밖 심링크 | **stderr의 원인을 읽어라** — 재생성으로 안 고쳐지는 종류가 있다 |
| 2 | SKIPPED — 규범 소스 미탐지 | `--plugin-root` 지정. **0으로 위장하지 말 것** |

## 불변식 [건너뛰기 금지]

1. **마커 블록 밖 불가침.** 대상의 `AGENTS.md`에서 `<!-- cck:begin ... -->` ~
   `<!-- cck:end -->` 밖은 생성기가 절대 건드리지 않는다. 마커가 없는 사용자 파일은
   덮어쓰지 않고 **append**한다. 이 규율을 깨는 수정은 consumer-first 위반이다.
2. **자기신고 sha를 믿지 않는다.** `--check`는 마커의 sha뿐 아니라 **블록 전문**을
   생성 결과와 대조한다. sha만 보면 마커 줄을 그대로 둔 채 안쪽을 지워도 초록이 되고,
   이 도구가 막겠다고 선언한 상황이 그대로 게이트를 통과한다.
3. **요약 금지.** 이식 대상 룰은 **원문 그대로** 실린다. 규범을 요약하면 원문과
   의미가 갈리고, 갈린 규범은 규범이 아니다.
4. **분류 누락도, 유령 엔트리도 실패.** 새 룰을 추가하면 `hooks/export_harness.py`의 `PORTABLE` 또는
   `NOT_PORTABLE`에 **사유와 함께** 등재해야 한다. 반대로 룰을 삭제·개명하면 그 엔트리를
   빼야 한다 — 두면 소비자 AGENTS.md가 존재하지 않는 룰을 영구히 광고한다. 양쪽 다 exit 1.

## 이식되지 않는 것 (정직한 한계)

훅(`protect-sensitive`·`stop-validator`·`auto-format`), 서브에이전트 정의 33종,
그리고 Claude Code 프리미티브에 종속된 룰 5개(`agent-system`·`agent-delegation-chain`·
`parallel-worktree`·`mcp-usage`·`task-resume`)는 이식되지 않는다. 생성물이 그 목록과
사유를 표로 남긴다.

**다른 하네스에서 CCK는 규율 *문서*로 동작하지 강제 *장치*로 동작하지 않는다.**
강제가 필요하면 그 하네스의 네이티브 수단(pre-commit, CI)에 같은 검사를 건다.

## 게이트

이 레포는 스스로 도그푸딩한다 — `scripts/verify-done.sh §11`과 CI가 `./scripts/export-harness.sh --check`를
같은 명령으로 실행한다. `rules/`를 고치고 재생성하지 않으면 완료 게이트가 막힌다.

---

## 다음 단계

```
---DELEGATION_SIGNAL---
TYPE: TASK_COMPLETE
REASON: AGENTS.md 내보내기/검사 완료
CONTEXT: 생성 대상 경로와 sha, 이식 제외 룰 목록
---END_SIGNAL---
```
