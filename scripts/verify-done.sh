#!/usr/bin/env bash
#
# verify-done.sh — Definition of Done 완료 게이트 (Spec 6 / W-010)
#
# "완료"를 판단이 아니라 명령의 출력으로 만든다. 모든 기계 검사를 통합 실행하고,
# 하나라도 FAIL이면 비정상 종료(완료 불가). 수동 DoD 항목은 체크리스트로 출력한다.
#
# 사용: scripts/verify-done.sh
# 종료코드: 0 = 모든 기계 검사 통과, 1 = 하나 이상 실패 (완료 주장 금지)
#
set -uo pipefail

ROOT="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"
cd "$ROOT" || exit 1

# 임시 출력은 예측가능한 /tmp 고정 이름(심링크 선점 위험) 대신 per-run mktemp 디렉토리.
TMPD="$(mktemp -d "${TMPDIR:-/tmp}/ckkit-verify.XXXXXX")" || exit 1
trap 'rm -rf "$TMPD"' EXIT

PASS=0
FAIL=0
green() { printf '  \033[32m✓\033[0m %s\n' "$1"; PASS=$((PASS + 1)); }
red()   { printf '  \033[31m✗ %s\033[0m\n' "$1"; FAIL=$((FAIL + 1)); }
hdr()   { printf '\n\033[1m%s\033[0m\n' "$1"; }

# Python 선택 — pytest 가용 인터프리터 탐색
PYTEST_PY=""
# 후보에 /tmp 경로를 넣지 말 것: world-writable + 예측 가능한 이름이라 아무 로컬
# 사용자나 인터프리터를 심어 게이트 실행자의 권한으로 코드를 돌릴 수 있다. 아래 임시
# 디렉토리를 mktemp로 잡는 것과 같은 이유다 — 실행 대상이면 위험은 오히려 더 크다.
# venv가 레포 밖에 있으면 activate해서 `python3` 후보로 잡히게 하면 된다.
for cand in ".venv/bin/python" "venv/bin/python" "python3"; do
  if "$cand" -c "import pytest" 2>/dev/null; then PYTEST_PY="$cand"; break; fi
done

hdr "1. JSON 유효성"
JSON_FILES=$(find plugins -name 'plugin.json' -o -name 'hooks.json' 2>/dev/null; echo ".claude-plugin/marketplace.json")
for f in $JSON_FILES; do
  [ -f "$f" ] || continue
  if python3 -c "import json;json.load(open('$f'))" 2>/dev/null; then :; else red "JSON invalid: $f"; fi
done
[ "$FAIL" -eq 0 ] && green "all JSON valid"

hdr "2. plugin.json 필수 필드 + agent frontmatter + 금지 필드 (CI 동등)"
python3 - <<'EOF' && green "manifest + frontmatter checks" || red "manifest/frontmatter check failed"
import json, pathlib, re, sys
REQ = ["name","version","description","homepage","repository","license"]
FORB = ["permissionMode","context_cache","output_schema","next_agents","hooks"]
err = []
for f in pathlib.Path("plugins").glob("*/.claude-plugin/plugin.json"):
    d = json.loads(f.read_text())
    err += [f"{f}: missing {k}" for k in REQ if k not in d]
    a = d.get("author", {})
    if not isinstance(a, dict) or "email" not in a: err.append(f"{f}: missing author.email")
for f in pathlib.Path("plugins").rglob("*.md"):
    if "/skills/" in str(f): continue
    c = f.read_text()
    if not c.startswith("---"): continue
    end = c.find("---", 3)
    if end == -1: continue
    fm = c[3:end]
    if "name:" not in fm: err.append(f"{f}: no name")
    if "description:" not in fm: err.append(f"{f}: no description")
    err += [f"{f}: forbidden {x}" for x in FORB if re.search(rf"^{x}:", fm, re.M)]
if err:
    print("\n".join("    " + e for e in err)); sys.exit(1)
EOF

hdr "3. ruff (레포 전체 — 룰셋은 ruff.toml SSOT)"
# 대상을 나열하지 않는다: `ruff check .` + 루트 ruff.toml(exclude 포함)이 범위의 단일
# 소스다. CI도 동일 커맨드를 쓴다 — 목록을 양쪽에 복제하면 드리프트가 난다(F-023·F-036).
# 설정 파일 자체가 게이트의 전제다 — 사라지면 ruff가 개발자 전역 설정으로 조용히
# 폴백해 "로컬 green·CI red"가 부활한다. 전제 소실을 pass로 넘기지 않는다(F-022).
[ -f ruff.toml ] || red "ruff.toml 없음 — 전역 설정 폴백 위험(린트 SSOT 소실)"
[ -f .ruff-version ] || red ".ruff-version 없음 — CI ruff 설치가 핀을 잃는다"
if command -v ruff >/dev/null 2>&1; then RUFF="ruff"; else RUFF=""; fi  # /tmp 폴백 금지 — §PYTEST_PY 주석 참고
if [ -n "$RUFF" ]; then
  PINNED="$(cat .ruff-version 2>/dev/null || echo "")"
  LOCAL_V="$("$RUFF" --version 2>/dev/null | awk '{print $2}')"
  if [ -n "$PINNED" ] && [ "$LOCAL_V" != "$PINNED" ]; then
    printf '  \033[33m! 로컬 ruff %s ≠ 핀 %s — CI와 판정이 갈릴 수 있다 (pip install ruff==%s)\033[0m\n' \
      "$LOCAL_V" "$PINNED" "$PINNED"
  fi
  if "$RUFF" check . >/dev/null 2>&1; then green "ruff clean (ruff check . / v$LOCAL_V)"; else red "ruff violations (run: $RUFF check .)"; fi
else
  red "ruff unavailable — cannot verify lint"
fi

hdr "3b. shellcheck (셸 스크립트 — 대상·임계값은 scripts/lint-shell.sh SSOT)"
# 번호가 3b인 이유: §4·§7·§10은 CLAUDE.md·validate.yml·run.py 주석에서 참조된다.
# 재번호는 그 참조들을 조용히 깨뜨리므로 삽입 번호를 쓴다.
[ -f .shellcheck-version ] || red ".shellcheck-version 없음 — CI shellcheck 설치가 핀을 잃는다"
if command -v shellcheck >/dev/null 2>&1; then
  SC_PINNED="$(cat .shellcheck-version 2>/dev/null || echo "")"
  SC_LOCAL_V="$(shellcheck --version 2>/dev/null | awk '/^version:/{print $2}')"
  if [ -n "$SC_PINNED" ] && [ -n "$SC_LOCAL_V" ] && [ "$SC_LOCAL_V" != "$SC_PINNED" ]; then
    printf '  \033[33m! 로컬 shellcheck %s ≠ 핀 %s — CI와 판정이 갈릴 수 있다\033[0m\n' \
      "$SC_LOCAL_V" "$SC_PINNED"
  fi
fi
./scripts/lint-shell.sh >"$TMPD/shellcheck" 2>&1
SC_RC=$?
if [ "$SC_RC" -eq 0 ]; then
  green "shellcheck clean (scripts/lint-shell.sh — CI와 동일 커맨드)"
elif [ "$SC_RC" -eq 127 ]; then
  # ruff와 달리 red로 막지 않는다: 셸 린트의 **권위 있는 판정은 CI**(핀된 버전)이고,
  # 로컬은 빠른 피드백용이다. 미설치를 green으로 위장하지도 않는다 — 노란 줄로 남긴다.
  printf '  \033[33m! shellcheck 미설치 — 셸 린트는 CI가 판정 (brew install shellcheck)\033[0m\n'
else
  red "shellcheck 위반 (run: scripts/lint-shell.sh)"
  sed 's/^/    /' "$TMPD/shellcheck" | head -20
fi

hdr "4. pytest (hook tests)"
# ruff와 동일한 이유로 러너 버전도 핀한다(§3 참고): pytest는 메이저마다 수집·fixture·
# deprecation 처리가 바뀌어, 핀이 없으면 CI만 최신으로 떠내려가 "코드 변경 없이 red"가 난다.
[ -f .pytest-version ] || red ".pytest-version 없음 — CI pytest 설치가 핀을 잃는다"
if [ -n "$PYTEST_PY" ]; then
  PY_PINNED="$(cat .pytest-version 2>/dev/null || echo "")"
  PY_LOCAL_V="$("$PYTEST_PY" -m pytest --version 2>/dev/null | awk '{print $2}')"
  if [ -n "$PY_PINNED" ] && [ -n "$PY_LOCAL_V" ] && [ "$PY_LOCAL_V" != "$PY_PINNED" ]; then
    printf '  \033[33m! 로컬 pytest %s ≠ 핀 %s — CI와 판정이 갈릴 수 있다 (pip install pytest==%s)\033[0m\n' \
      "$PY_LOCAL_V" "$PY_PINNED" "$PY_PINNED"
  fi
  # 수집 대상은 **pytest.ini의 testpaths가 단일 소스**다 (F-023). 여기서도 CI에서도
  # 인자 없이 호출한다 — 목록을 양쪽에 적어두면 새 테스트 디렉토리를 한쪽만 등록해
  # "로컬은 돌고 CI는 안 도는" 구멍이 생긴다. 실제로 scripts/tests/ 추가 때 발생했다.
  [ -f pytest.ini ] || red "pytest.ini 없음 — 수집 대상 단일소스 소실 (F-023)"
  # SSOT는 옳지만, 그 SSOT를 한 줄 지우면 테스트 디렉토리 하나가 통째로 사라지면서
  # 로컬·CI 둘 다 green이 된다(self-disable). 실재하는 테스트 디렉토리가 전부
  # testpaths에 덮이는지 검사한다 — check_doc_counts의 "표 행 부재 = 실패"와 같은 방어.
  if [ -f pytest.ini ]; then
    UNCOVERED=$(python3 - <<'PYEOF'
import pathlib, re, subprocess, sys

# testpaths 파싱은 INI 연속 줄 규칙을 그대로 따른다: `testpaths =` 다음의 **들여쓴 줄**만
# 값이고, 들여쓰지 않은 줄에서 끝난다. 주석은 제거한다.
#   예전 정규식(`(.*?)(?=^\w|\Z)`)은 `#`가 \w가 아니라 주석 블록에서 멈추지 않았고,
#   주석의 낱말("evals" 같은)이 .split()으로 경로가 됐다. 그 결과 `evals/tests` 한 줄을
#   지워도 "덮였다"고 판정 — 테스트 50건이 조용히 사라지는데 게이트는 초록이었다.
#   (2026-08-23 적대적 리뷰가 잡은 self-disable. 이 검사 자체가 false-green이었다.)
paths = set()
in_block = False
for raw in pathlib.Path("pytest.ini").read_text(encoding="utf-8").splitlines():
    line = raw.split("#", 1)[0].rstrip()
    if not line:
        continue
    if re.match(r"^testpaths\s*=", line):
        in_block = True
        rest = line.split("=", 1)[1].strip()
        paths.update(rest.split())
        continue
    if in_block:
        if raw[:1].isspace():
            paths.update(line.split())
        else:
            break
if not paths:
    print("PARSE-FAILED")
    sys.exit(0)

out = subprocess.run(
    ["git", "ls-files", "-z", "--", "*test_*.py", "*_test.py"],
    capture_output=True, text=True, check=False,
).stdout
missing = set()
for f in out.split("\0"):
    if not f or f.startswith("evals/scenarios/"):
        continue  # 의도적으로 실패하는 fixture — 수집 대상이 아니다
    d = str(pathlib.PurePosixPath(f).parent)
    if not any(d == p or d.startswith(p.rstrip("/") + "/") for p in paths):
        missing.add(d)
print(" ".join(sorted(missing)))
PYEOF
) || UNCOVERED="PARSE-FAILED"
    # 검사 스크립트가 죽어도 빈 문자열 → green이 되던 착시를 막는다: 파싱 실패는 red다.
    if [ "$UNCOVERED" = "PARSE-FAILED" ]; then
      red "pytest.ini testpaths 파싱 실패 — 커버리지 검사 불가 (검사 불가를 통과로 세지 않는다)"
    elif [ -n "$UNCOVERED" ]; then
      red "pytest testpaths 미포함 테스트 디렉토리: $UNCOVERED (수집되지 않아 조용히 미실행)"
    else
      green "pytest testpaths 커버리지: 모든 테스트 디렉토리 포함"
    fi
  fi
  "$PYTEST_PY" -m pytest >"$TMPD/pytest" 2>&1; PYTEST_RC=$?
  # exit 5 = 수집 0. 테스트가 상존하는 레포에서 수집 0은 경로 붕괴 신호이므로 실패다
  # (CI와 fail-closed 방향 통일).
  if [ "$PYTEST_RC" -eq 0 ]; then
    green "pytest: $(grep -oE '[0-9]+ passed' "$TMPD/pytest" | tail -1) (pytest.ini testpaths)"
  elif [ "$PYTEST_RC" -eq 5 ]; then
    red "pytest 수집 0 — testpaths 붕괴 (pytest.ini 확인)"
  else
    red "pytest failed (see: $PYTEST_PY -m pytest)"
  fi
else
  red "pytest unavailable — install pytest to verify tests"
fi

hdr "5. 시크릿 스캔 (기본)"
# 결과를 변수로 수집해 판정한다 — `... | head -1 | grep -q`는 매치가 많을 때
# 상류 grep이 SIGPIPE(141)로 죽고 pipefail이 파이프라인을 비정상 종료로 만들어,
# 시크릿이 있어도 else(green)로 빠지던 false-green(적대적 리뷰 P0)을 유발했다.
SECRET_HITS=$(git ls-files | xargs grep -nIE '(api[_-]?key|secret|password|token)[[:space:]]*[:=][[:space:]]*["'"'"'][A-Za-z0-9/+]{16,}' 2>/dev/null | grep -v -E 'test|example|placeholder|YOUR_|xxx' || true)
if [ -n "$SECRET_HITS" ]; then
  red "잠재 시크릿 발견 (수동 확인 필요)"
else
  green "no obvious secrets"
fi

hdr "6. 문서 카운트/버전 sync"
# plugin.json 버전 ↔ CHANGELOG 최상단 버전 일치 (릴리스 체크리스트: 버전 범프 시
# CHANGELOG 누락 방지 — 캐시가 버전으로 키잉되므로 불일치는 릴리스 사고).
PJ_VER=$(grep -oE '"version"[[:space:]]*:[[:space:]]*"[0-9.]+"' plugins/common/.claude-plugin/plugin.json 2>/dev/null | grep -oE '[0-9.]+' | head -1)
CL_VER=$(grep -oE '^## \[[0-9.]+\]' CHANGELOG.md 2>/dev/null | grep -oE '[0-9.]+' | head -1)
if [ -z "$PJ_VER" ] || [ -z "$CL_VER" ]; then
  red "버전 sync: 파싱 실패 (plugin.json='$PJ_VER' CHANGELOG='$CL_VER')"
elif [ "$PJ_VER" = "$CL_VER" ]; then
  green "버전 sync: plugin.json = CHANGELOG = $PJ_VER"
else
  red "버전 sync: plugin.json $PJ_VER ≠ CHANGELOG 최상단 $CL_VER (릴리스 체크리스트 위반)"
fi
# 카운트 검사는 scripts/check_doc_counts.py 가 단일 소스 (F-023) — CI(validate.yml)와
# 동일 스크립트를 호출한다. bash 재구현 금지(로직 이중화 = 드리프트).
if python3 scripts/check_doc_counts.py; then
  green "doc counts 일치 (check_doc_counts.py — CI와 단일 소스)"
else
  red "doc counts drift (상세는 위 check_doc_counts.py 출력)"
fi
# 릴리스 태그 sync — CHANGELOG의 **과거** 릴리스는 전부 태그가 있어야 한다.
# 최상단(=지금 작업 중인 버전)은 아직 커밋 전일 수 있으므로 제외한다.
# 실제로 v2.10.4 이후 20개 릴리스가 무태그로 방치됐다(2026-08-17 소급 부여) —
# 관례가 조용히 끊긴 것을 아무도 몰랐던 게 문제라 산문 대신 기계 검사로 못박는다.
# 로컬 전용 검사다(CI의 shallow checkout은 태그를 안 가져온다).
MISSING_TAGS=""; _skip_top=1
for v in $(grep -oE '^## \[[0-9]+\.[0-9]+\.[0-9]+\]' CHANGELOG.md | grep -oE '[0-9]+\.[0-9]+\.[0-9]+'); do
  if [ "$_skip_top" -eq 1 ]; then _skip_top=0; continue; fi
  git rev-parse -q --verify "refs/tags/v$v" >/dev/null 2>&1 || MISSING_TAGS="$MISSING_TAGS v$v"
done
if [ -n "$MISSING_TAGS" ]; then
  red "릴리스 태그 누락:$MISSING_TAGS — 릴리스 후 'git tag -a vX <릴리스 커밋>' + push --tags"
else
  green "릴리스 태그 sync: 과거 릴리스 전부 태그 존재"
fi

hdr "7. stale 참조 (hooks.json + rules/agents가 가리키는 스크립트 존재)"
MISSING=0
for s in $(grep -oE '\$\{CLAUDE_PLUGIN_ROOT\}/[A-Za-z0-9_./-]+\.py' plugins/common/hooks/hooks.json 2>/dev/null | sed 's|${CLAUDE_PLUGIN_ROOT}|plugins/common|'); do
  [ -f "$s" ] || { red "hooks.json → 없는 스크립트: $s"; MISSING=1; }
done
# rules/agents 산문이 가리키는 ./scripts/<name>.sh 가 실재하는지 검증 — always-injected
# 룰의 죽은 스크립트 참조(예: 존재하지 않는 db-tunnel.sh)가 매 세션 주입되던 문제 방지.
for ref in $(grep -rhoE '(\./)?scripts/[A-Za-z0-9_/-]+\.sh' plugins/common/rules plugins/common/agents 2>/dev/null | sed 's|^\./||' | sort -u); do
  [ -f "$ref" ] || { red "rules/agents → 없는 스크립트 참조: $ref"; MISSING=1; }
done
[ "$MISSING" -eq 0 ] && green "hooks.json + rules/agents 참조 스크립트 모두 존재"
# rules 무결성 매니페스트 강제 — 해시 일치 + **집합 동등성**(매니페스트에 없는
# 신규 파일도 red — 나열-파일만 검사하는 -c의 맹점 보완, 재감사 ATK-002/007)
if command -v shasum >/dev/null 2>&1; then _SHA="shasum -a 256"; elif command -v sha256sum >/dev/null 2>&1; then _SHA="sha256sum"; else _SHA=""; fi
if [ -z "$_SHA" ]; then
  red "rules CHECKSUMS: 해시 도구 부재(shasum/sha256sum) — 검증 불가"
elif (cd plugins/common/rules && $_SHA *.md 2>/dev/null | grep -v CHECKSUMS | diff -q - CHECKSUMS.sha256 >/dev/null 2>&1); then
  green "rules CHECKSUMS 일치 (집합 동등)"
else
  red "rules CHECKSUMS 불일치/신규 파일 — 재생성: (cd plugins/common/rules && $_SHA *.md | grep -v CHECKSUMS > CHECKSUMS.sha256)"
fi
# 룰 해설본 미러 동기 — 검사 로직은 scripts/sync-rule-mirror.sh 가 단일 소스.
# docs/architecture/rules/ 가 주입 룰보다 뒤처지면 FAIL (실제로 3건 드리프트했었다).
if ./scripts/sync-rule-mirror.sh >"$TMPD/mirror" 2>&1; then
  green "rules 해설본 미러 동기 (docs/architecture/rules ↔ plugins/common/rules)"
else
  red "rules 해설본 미러 드리프트 (run: scripts/sync-rule-mirror.sh)"
  sed 's/^/    /' "$TMPD/mirror" | head -10
fi
# 배포 에이전트 MCP 미배선 가드 (W-015): frontmatter tools에 mcp__ 금지 + description/body가
# Context7/Tavily/mcp__를 자기 능력으로 지시 금지(web-research 스킬 위임 문맥은 허용).
# 미설치 소비자 환각(CC #13898) 방지 — frontmatter-only 가드의 산문 맹점 보완(적대리뷰 ATK-004).
MCP_VIOL=0
# `< <(find -print0)`: 파이프가 아니라 프로세스 치환이어야 한다 — `find | while`로 쓰면
# 루프가 서브셸에서 돌아 red()의 FAIL 증가와 MCP_VIOL 대입이 통째로 버려진다(false-green).
while IFS= read -r -d '' f; do
  fm=$(awk 'NR==1&&/^---/{fr=1;next} fr&&/^---/{exit} fr{print}' "$f")
  printf '%s' "$fm" | grep -q "mcp__" && { red "MCP: frontmatter에 mcp__ — $f"; MCP_VIOL=1; }
  # 산문이 Context7/Tavily/mcp__를 언급하면서 web-research 위임 문맥이 없으면 위반
  # ("Exa"는 "example" 오탐이라 제외)
  if grep -qE "Context7|Tavily|mcp__" "$f" && ! grep -q "web-research" "$f"; then
    red "MCP: 에이전트 산문이 MCP를 자기 능력으로 지시(스킬 위임 아님) — $f"; MCP_VIOL=1
  fi
done < <(find plugins/common/agents -name "*.md" -print0 2>/dev/null)
[ "$MCP_VIOL" -eq 0 ] && green "MCP: 배포 에이전트 frontmatter·산문 모두 MCP 미배선(스킬 위임)"

hdr "8. Durable checklist 완료 게이트 (active Work, W-013)"
# checklist.json이 완료 상태의 단일 authority. active Work에 passes:false 잔존 시 FAIL.
# status exit: 0=전항목pass 1=미완/손상 3=진짜 부재(skip). helper가 없는데 checklist는
# 있으면 fail-closed(적대적 리뷰: helper 삭제 시 미완이 green 되던 false-green 차단).
CL_HELPER="plugins/common/hooks/checklist.py"
CL_FOUND=0
for cl in docs/works/active/*/checklist.json; do
  [ -f "$cl" ] || continue
  CL_FOUND=1
  wd="$(dirname "$cl")"
  if [ ! -f "$CL_HELPER" ]; then
    red "checklist 존재하나 helper($CL_HELPER) 없음 → 검증 불가(fail-closed): $(basename "$wd")"
    continue
  fi
  python3 "$CL_HELPER" status "$wd" >"$TMPD/checklist" 2>&1
  rc=$?
  if [ "$rc" -eq 0 ]; then
    green "checklist 전항목 pass: $(basename "$wd")"
  elif [ "$rc" -eq 3 ]; then
    : # 진짜 부재 → skip (loop 도중 파일 생성 전)
  else
    red "checklist 미완/손상: $(basename "$wd") — $(tr '\n' ' ' <"$TMPD/checklist")"
  fi
done
[ "$CL_FOUND" -eq 0 ] && green "active checklist 없음 (skip)"

hdr "9. test-ratchet (테스트/assert 삭제 방지, W-013)"
# diff에서 test/assert가 allow-marker 없이 순감소하면 FAIL. 산문 규율이 아닌 기계 체크.
python3 - <<'EOF' && green "test-ratchet: 테스트 감소 없음" || red "test-ratchet: allow-marker 없이 테스트/assert 순감소 (의도적이면 diff에 TEST-RATCHET-ALLOW 명시)"
import re
import subprocess
import sys


def sh(*a):
    r = subprocess.run(a, capture_output=True, text=True)
    return r.stdout.strip(), r.returncode


# 비교 기준(base) 선택 — 적대적 리뷰 F4: `merge-base main HEAD`는 HEAD가 main일 때
# HEAD와 같아져(=빈 diff) 커밋된 테스트 삭제를 못 본다. 또 main이 없으면 조용히 green.
# → fork point가 degenerate하면 origin/main → HEAD~1 로 폴백하고, 어디에도 없으면
#   조용한 green이 아니라 [warn] 후 skip.
base, mrc = sh("git", "merge-base", "main", "HEAD")
head, _ = sh("git", "rev-parse", "HEAD")
if mrc != 0 or not base or base == head:
    omb, orc = sh("git", "merge-base", "origin/main", "HEAD")
    if orc == 0 and omb and omb != head:
        base = omb
    else:
        h1, h1rc = sh("git", "rev-parse", "--verify", "--quiet", "HEAD~1")
        if h1rc == 0 and h1:
            base = "HEAD~1"
        else:
            # fresh/단일-커밋 저장소: HEAD를 base로 두면 최소한 워킹트리 미커밋
            # 테스트 삭제는 잡는다(조용한 skip보다 낫다, 적대적 리뷰 P2).
            base = "HEAD"
r = subprocess.run(
    ["git", "diff", "--unified=0", base], capture_output=True, text=True
)
if r.returncode != 0:
    print(f"    [warn] test-ratchet: git diff 실패({base}) — skip")
    sys.exit(0)
diff = r.stdout
if not diff.strip() or "TEST-RATCHET-ALLOW" in diff:
    sys.exit(0)
pat = re.compile(r"(def\s+test_|\bassert\b|\bit\(|\btest\(|\bexpect\()")
# 테스트 파일 경로만 집계 — prod 코드의 방어적 assert 삭제가 오탐 FAIL 내지 않도록.
test_path = re.compile(
    r"(^|/)(test_|[^/]*_test\.|[^/]*\.test\.|[^/]*\.spec\.|conftest|(tests?|specs?|__tests__)/)"
)


def _is_test(p):
    p = p.strip()
    if p in ("", "/dev/null"):
        return False
    for pre in ("a/", "b/"):
        if p.startswith(pre):
            p = p[2:]
            break
    return bool(test_path.search(p))


# --unified=0에서 삭제된 내용줄 '-- x'는 '--- x'로, 추가줄 '++ x'는 '+++ x'로 보여
# 파일 헤더로 오인될 수 있다(적대적 리뷰). diff --git/@@ 로 헤더 영역 vs 내용 영역을
# 명확히 분리해, --- /+++ 는 hunk 시작(@@) 전에만 헤더로 해석한다.
added = removed = 0
old_test = in_test = in_hunk = False
for ln in diff.splitlines():
    if ln.startswith("diff --git"):
        in_hunk = False
        old_test = in_test = False
        continue
    if ln.startswith("@@"):
        in_hunk = True
        continue
    if not in_hunk and ln.startswith("--- "):
        old_test = _is_test(ln[4:])
        continue
    if not in_hunk and ln.startswith("+++ "):
        in_test = old_test or _is_test(ln[4:])
        continue
    if not in_hunk or not in_test:
        continue
    if ln.startswith("+") and pat.search(ln):
        added += 1
    elif ln.startswith("-") and pat.search(ln):
        removed += 1
if removed - added > 0:
    print(f"    테스트 삭제 {removed} > 추가 {added} (net -{removed - added})")
    sys.exit(1)
sys.exit(0)
EOF

hdr "10. Agent evals 스키마 (오프라인, W-B / toolkit-improvement-batch)"
# 행동 eval 자체(claude -p 실제 호출)는 API 비용이 들어 여기 넣지 않는다 —
# release-gate는 scripts/run-evals.sh의 몫(README §exit code 참고). 여기서는
# expect.json 스키마 + 시나리오-에이전트 참조 무결성만 오프라인 검증한다.
# evals/ 부재는 fail-closed(조용한 skip 금지) — run.py의 validate_all()이 이를 강제한다.
if [ -f evals/run.py ]; then
  if python3 evals/run.py --validate >"$TMPD/evals_validate" 2>&1; then
    green "evals --validate: $(tail -1 "$TMPD/evals_validate")"
  else
    red "evals --validate 실패 — $(tail -3 "$TMPD/evals_validate" | tr '\n' ' ')"
  fi
else
  red "evals/run.py 없음 (fail-closed — W-B 산출물 누락)"
fi

hdr "13. Eval 커버리지·기준선 게이트 (W-018 / S1)"
# 시나리오 디렉토리 ⇄ 기준선 (agent,scenario) 집합의 양방향 대조 + tier1 최소
# 커버리지. 로직 단일 소스는 scripts/check_eval_coverage.py — CI(validate.yml)가
# 동일 스크립트를 호출한다(F-023 관례). 에이전트 호출 0건(비용 없음), 매 커밋 가능.
if [ -f scripts/check_eval_coverage.py ]; then
  if python3 scripts/check_eval_coverage.py >"$TMPD/eval_coverage" 2>&1; then
    green "eval 커버리지 정합 (baseline ⇄ scenarios)"
    sed 's/^/    /' "$TMPD/eval_coverage"
  else
    red "eval 커버리지 드리프트 — 상세는 check_eval_coverage.py 출력"
    sed 's/^/    /' "$TMPD/eval_coverage"
  fi
else
  red "scripts/check_eval_coverage.py 없음 (W-018 S1 산출물 누락)"
fi

hdr "12. 에이전트 출력 계약 위치 (W-017)"
# CLAUDE.md는 "모든 에이전트는 구조화된 delegation signal로 **끝난다**"고 규정한다.
# 그런데 3종에서 계약이 문서 중간에 있었고(뒤로 186~496줄), 뒤따르는 참고 자료가
# 컨텍스트의 끝을 차지해 **리뷰 리포트가 실제로 유실됐다**(2026-08-23 실측 2회).
# 산문 규정만 두면 또 밀린다 — 위치를 기계로 강제한다 (F-027: 규율에는 감지 장치를).
if python3 - <<'PYEOF'
import pathlib, sys
BAD_TAIL = 50  # 계약 언급 뒤에 이만큼 넘게 남으면 끝이 아니다
bad = []
for f in sorted(pathlib.Path("plugins").glob("*/agents/**/*.md")):
    lines = f.read_text(encoding="utf-8").splitlines()
    idx = [i for i, l in enumerate(lines) if "DELEGATION_SIGNAL" in l or "출력 계약" in l]
    if not idx:
        bad.append(f"{f} (계약 없음)")
        continue
    tail = len(lines) - (idx[-1] + 1)
    if tail > BAD_TAIL:
        bad.append(f"{f} (뒤에 {tail}줄 남음)")
if bad:
    print("  " + "\n  ".join(bad))
    sys.exit(1)
print(f"에이전트 33종 모두 출력 계약이 문서 끝({BAD_TAIL}줄 이내)에 있음")
PYEOF
then
  green "에이전트 출력 계약 위치 정상"
else
  red "출력 계약이 문서 끝에 없는 에이전트 — 뒤따르는 내용에 밀려 반환값이 유실된다"
fi

hdr "11. AGENTS.md 하네스 이식 드리프트 (W-017)"
# rules/ 를 고치고 AGENTS.md를 재생성하지 않으면, Codex·OpenCode 등 다른 하네스에서
# 도는 에이전트는 **옛 규범**을 읽는다. 같은 레포에서 하네스마다 규율이 갈리는 상태를
# 침묵으로 두지 않는다. exit 2(SKIPPED)는 소스 미탐지 — green으로 세지 않는다.
if [ -f scripts/export-harness.sh ] && [ -f plugins/common/hooks/export_harness.py ]; then
  ./scripts/export-harness.sh --check >"$TMPD/agents_md" 2>&1
  EH_RC=$?
  if [ "$EH_RC" -eq 0 ]; then
    green "AGENTS.md 최신 (rules 원문 + 블록 본문 일치)"
  elif [ "$EH_RC" -eq 2 ]; then
    red "export-harness SKIPPED — 규범 소스 미탐지"
    sed 's/^/      /' "$TMPD/agents_md" | head -6
  else
    # exit 1은 드리프트만이 아니다 — 분류 미등재/유령 엔트리, 마커 손상, 본문 변조,
    # 인코딩 실패가 모두 여기 모인다. 원인을 안 보여주면 "재생성하라"가 무한루프가 된다
    # (분류 문제는 재생성으로 안 고쳐진다).
    red "AGENTS.md 검사 실패 — 아래 원인 확인 (재생성으로 안 고쳐지는 경우가 있다)"
    sed 's/^/      /' "$TMPD/agents_md" | head -10
  fi
else
  red "export-harness 산출물 누락 (scripts/export-harness.sh 또는 hooks/export_harness.py) — W-017"
fi

# ── 결과 ──────────────────────────────────────────────────────────
hdr "═══ 기계 검사 결과: ${PASS} pass / ${FAIL} fail ═══"
hdr "수동 DoD attest (증거와 함께 명시 — 자동 검사 불가)"
cat <<'EOF'
  [ ] 스펙·계획의 모든 항목 구현 (spec ↔ 코드 대조, 누락 없음)
  [ ] 적대적 리뷰 1회 (버그·엣지케이스·문서 sync 능동 탐색)
  [ ] Work 라이프사이클 상태 정확히 보고 (active/validation vs completed)
  [ ] CHANGELOG·README·CLAUDE.md 영향 반영
EOF

if [ "$FAIL" -gt 0 ]; then
  printf '\n\033[31m완료 불가 — 기계 검사 %d건 실패. "완료"를 주장하지 말 것.\033[0m\n' "$FAIL"
  exit 1
fi
printf '\n\033[32m기계 검사 전부 통과. 위 수동 attest를 증거와 함께 확인한 뒤에만 "완료" 선언.\033[0m\n'
exit 0
