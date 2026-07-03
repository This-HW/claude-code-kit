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
FORB = ["permissionMode","context_cache","output_schema","next_agents"]
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
  if "$RUFF" check plugins/common/hooks/ >/dev/null 2>&1; then green "ruff clean"; else red "ruff violations (run: $RUFF check plugins/common/hooks/)"; fi
else
  red "ruff unavailable — cannot verify lint"
fi

hdr "4. pytest (hook tests)"
if [ -n "$PYTEST_PY" ]; then
  if "$PYTEST_PY" -m pytest plugins/common/hooks/tests/ -q >"$TMPD/pytest" 2>&1; then
    green "pytest: $(grep -oE '[0-9]+ passed' "$TMPD/pytest" | tail -1)"
  else
    red "pytest failed (see: $PYTEST_PY -m pytest plugins/common/hooks/tests/)"
  fi
else
  red "pytest unavailable — install pytest to verify tests"
fi

hdr "5. 시크릿 스캔 (기본)"
if git ls-files | xargs grep -nIE '(api[_-]?key|secret|password|token)[[:space:]]*[:=][[:space:]]*["'"'"'][A-Za-z0-9/+]{16,}' 2>/dev/null | grep -v -E 'test|example|placeholder|YOUR_|xxx' | head -1 | grep -q .; then
  red "잠재 시크릿 발견 (수동 확인 필요)"
else
  green "no obvious secrets"
fi

hdr "6. 문서 카운트 sync"
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

hdr "7. stale 참조 (hooks.json이 가리키는 스크립트 존재)"
MISSING=0
for s in $(grep -oE '\$\{CLAUDE_PLUGIN_ROOT\}/[A-Za-z0-9_./-]+\.py' plugins/common/hooks/hooks.json 2>/dev/null | sed 's|${CLAUDE_PLUGIN_ROOT}|plugins/common|'); do
  [ -f "$s" ] || { red "hooks.json → 없는 스크립트: $s"; MISSING=1; }
done
[ "$MISSING" -eq 0 ] && green "hooks.json 참조 스크립트 모두 존재"

hdr "8. Durable checklist 완료 게이트 (active Work, W-013)"
# checklist.json이 완료 상태의 단일 authority. active Work에 passes:false 잔존 시 FAIL,
# checklist 부재 시 스킵(회귀 없음). status의 exit: 0=전항목pass 1=미완 3=없음/빈.
CL_HELPER="plugins/common/hooks/checklist.py"
CL_FOUND=0
if [ -f "$CL_HELPER" ]; then
  for cl in docs/works/active/*/checklist.json; do
    [ -f "$cl" ] || continue
    CL_FOUND=1
    wd="$(dirname "$cl")"
    python3 "$CL_HELPER" status "$wd" >"$TMPD/checklist" 2>&1
    rc=$?
    if [ "$rc" -eq 0 ]; then
      green "checklist 전항목 pass: $(basename "$wd")"
    elif [ "$rc" -eq 3 ]; then
      : # 빈 checklist → skip
    else
      red "checklist 미완: $(basename "$wd") — $(tr '\n' ' ' <"$TMPD/checklist")"
    fi
  done
fi
[ "$CL_FOUND" -eq 0 ] && green "active checklist 없음 (skip)"

hdr "9. test-ratchet (테스트/assert 삭제 방지, W-013)"
# diff에서 test/assert가 allow-marker 없이 순감소하면 FAIL. 산문 규율이 아닌 기계 체크.
python3 - <<'EOF' && green "test-ratchet: 테스트 감소 없음" || red "test-ratchet: allow-marker 없이 테스트/assert 순감소 (의도적이면 diff에 TEST-RATCHET-ALLOW 명시)"
import re
import subprocess
import sys


def sh(*a):
    return subprocess.run(a, capture_output=True, text=True).stdout


base = sh("git", "merge-base", "main", "HEAD").strip() or "HEAD"
diff = sh("git", "diff", "--unified=0", base)
if not diff.strip() or "TEST-RATCHET-ALLOW" in diff:
    sys.exit(0)
pat = re.compile(r"(def\s+test_|\bassert\b|\bit\(|\btest\(|\bexpect\()")
# 테스트 파일 경로만 집계 — prod 코드의 방어적 assert 삭제가 오탐 FAIL 내지 않도록.
test_path = re.compile(r"(^|/)(test_|[^/]*_test\.|[^/]*\.test\.|[^/]*\.spec\.|conftest)")


def _is_test(p):
    p = p.strip()
    if p in ("", "/dev/null"):
        return False
    for pre in ("a/", "b/"):
        if p.startswith(pre):
            p = p[2:]
            break
    return bool(test_path.search(p))


added = removed = 0
old_test = in_test = False
for ln in diff.splitlines():
    if ln.startswith("--- "):  # 삭제측(구 파일) — 테스트 파일 통째 삭제도 잡도록
        old_test = _is_test(ln[4:])
        continue
    if ln.startswith("+++ "):  # 추가측(신 파일). 헤더 쌍이 끝나며 in_test 확정
        in_test = old_test or _is_test(ln[4:])
        continue
    if not in_test:
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
