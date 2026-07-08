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
for cand in ".venv/bin/python" "venv/bin/python" "python3" "/tmp/ckkit-venv/bin/python"; do
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

hdr "3. ruff (hooks)"
if command -v ruff >/dev/null 2>&1; then RUFF="ruff"; elif [ -x /tmp/ckkit-venv/bin/ruff ]; then RUFF="/tmp/ckkit-venv/bin/ruff"; else RUFF=""; fi
if [ -n "$RUFF" ]; then
  RUFF_TARGETS="plugins/common/hooks/"
  [ -d evals ] && RUFF_TARGETS="$RUFF_TARGETS evals/"
  # shellcheck disable=SC2086
  if "$RUFF" check $RUFF_TARGETS >/dev/null 2>&1; then green "ruff clean ($RUFF_TARGETS)"; else red "ruff violations (run: $RUFF check $RUFF_TARGETS)"; fi
else
  red "ruff unavailable — cannot verify lint"
fi

hdr "4. pytest (hook tests)"
if [ -n "$PYTEST_PY" ]; then
  # evals 러너 테스트도 게이트에 포함 (최종 재감사 ATK-003: 러너 보안가드 회귀 방지).
  PYTEST_TARGETS="plugins/common/hooks/tests/"
  [ -d evals/tests ] && PYTEST_TARGETS="$PYTEST_TARGETS evals/tests/"
  # shellcheck disable=SC2086
  if "$PYTEST_PY" -m pytest $PYTEST_TARGETS -q >"$TMPD/pytest" 2>&1; then
    green "pytest: $(grep -oE '[0-9]+ passed' "$TMPD/pytest" | tail -1) ($PYTEST_TARGETS)"
  else
    red "pytest failed (see: $PYTEST_PY -m pytest $PYTEST_TARGETS)"
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
RULES_ACTUAL=$(ls plugins/common/rules/*.md 2>/dev/null | wc -l | tr -d ' ')
SKILLS_C_ACTUAL=$(find plugins/common/skills -name SKILL.md 2>/dev/null | wc -l | tr -d ' ')
SKILLS_T_ACTUAL=$(find plugins -name SKILL.md 2>/dev/null | wc -l | tr -d ' ')
check_count() { # claim_regex file actual label
  local claim
  claim=$(grep -oE "$1" "$2" 2>/dev/null | grep -oE '[0-9]+' | head -1)
  if [ -z "$claim" ]; then green "$4: 주장 없음 (skip)"; elif [ "$claim" = "$3" ]; then green "$4: $3 일치"; else red "$4: 문서 주장 $claim ≠ 실제 $3 ($2)"; fi
}
check_count 'rules \([0-9]+\)' CLAUDE.md "$RULES_ACTUAL" "rules(CLAUDE.md)"
check_count 'rules \([0-9]+\)' README.md "$RULES_ACTUAL" "rules(README)"
check_count 'skills \([0-9]+\)' CLAUDE.md "$SKILLS_C_ACTUAL" "common skills(CLAUDE.md)"
check_count '[0-9]+ skills' README.md "$SKILLS_T_ACTUAL" "total skills(README)"
# What's Included 표 행(| agents | skills |) 검증 — 매직 33 리터럴 커플링 제거
# (재감사 R2/ATK-001: 33이 바뀌면 검사가 조용히 skip-green되던 self-disable 차단)
AGENTS_ACTUAL=$(find plugins/common/agents -name '*.md' 2>/dev/null | wc -l | tr -d ' ')
TBL_ROW=$(grep -E '^\| .claude-code-kit. \|' README.md | head -1)
if [ -z "$TBL_ROW" ]; then
  red "README What's Included 표 행을 찾지 못함 (형식 변경? 게이트 갱신 필요)"
else
  TBL_AGENTS=$(echo "$TBL_ROW" | grep -oE '[0-9]+' | sed -n 1p)
  TBL_SKILLS=$(echo "$TBL_ROW" | grep -oE '[0-9]+' | sed -n 2p)
  [ "$TBL_AGENTS" = "$AGENTS_ACTUAL" ] && green "README 표 에이전트 셀: $TBL_AGENTS 일치" || red "README 표 에이전트 셀: $TBL_AGENTS ≠ 실제 $AGENTS_ACTUAL"
  [ "$TBL_SKILLS" = "$SKILLS_C_ACTUAL" ] && green "README 표 스킬 셀: $TBL_SKILLS 일치" || red "README 표 스킬 셀: $TBL_SKILLS ≠ 실제 $SKILLS_C_ACTUAL"
fi
check_count '[0-9]+ agents' README.md "$AGENTS_ACTUAL" "agents(README)"

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
# 배포 에이전트 MCP 미배선 가드 (W-015): frontmatter tools에 mcp__ 금지 + description/body가
# Context7/Tavily/mcp__를 자기 능력으로 지시 금지(web-research 스킬 위임 문맥은 허용).
# 미설치 소비자 환각(CC #13898) 방지 — frontmatter-only 가드의 산문 맹점 보완(적대리뷰 ATK-004).
MCP_VIOL=0
for f in $(find plugins/common/agents -name "*.md" 2>/dev/null); do
  fm=$(awk 'NR==1&&/^---/{fr=1;next} fr&&/^---/{exit} fr{print}' "$f")
  printf '%s' "$fm" | grep -q "mcp__" && { red "MCP: frontmatter에 mcp__ — $f"; MCP_VIOL=1; }
  # 산문이 Context7/Tavily/mcp__를 언급하면서 web-research 위임 문맥이 없으면 위반
  # ("Exa"는 "example" 오탐이라 제외)
  if grep -qE "Context7|Tavily|mcp__" "$f" && ! grep -q "web-research" "$f"; then
    red "MCP: 에이전트 산문이 MCP를 자기 능력으로 지시(스킬 위임 아님) — $f"; MCP_VIOL=1
  fi
done
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
