#!/bin/bash
# setup.sh: 새 환경 초기 셋업 (전역 설정 + Plugin 설치)
# D-016: 상태 추적 + 멱등성 + 외부 도구 버전 체크
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
STATE_FILE="$HOME/.claude/.setup-state.json"

# D-016: 상태 관리 함수 (ATK-002: sys.argv로 shell injection 방지)
_step_done() {
    python3 - "$1" "$STATE_FILE" <<'PYEOF'
import json, pathlib, sys
step, state_file = sys.argv[1], sys.argv[2]
p = pathlib.Path(state_file)
try:
    s = json.loads(p.read_text()) if p.exists() else {}
    sys.exit(0 if step in s.get('completed', []) else 1)
except Exception as e:
    print(f"[setup] _step_done error: {e}", file=sys.stderr)
    sys.exit(1)
PYEOF
}
_mark_done() {
    python3 - "$1" "$STATE_FILE" <<'PYEOF'
import json, pathlib, sys
step, state_file = sys.argv[1], sys.argv[2]
p = pathlib.Path(state_file)
try:
    p.parent.mkdir(parents=True, exist_ok=True)
    s = json.loads(p.read_text()) if p.exists() else {'completed': []}
    if step not in s['completed']:
        s['completed'].append(step)
    p.write_text(json.dumps(s, indent=2))
except Exception as e:
    print(f"[setup] _mark_done error: {e}", file=sys.stderr)
PYEOF
}

# D-016: 옵션 파서 (ATK-004: while-loop, 복합 옵션 조합 지원)
OPT_FORCE=false
OPT_ALL=false
OPT_FULL=false
OPT_LIST=false
OPT_STATUS=false
OPT_MIGRATE=false

while [[ $# -gt 0 ]]; do
    case "$1" in
        --force)   OPT_FORCE=true; shift;;
        --all)     OPT_ALL=true; shift;;
        --full)    OPT_FULL=true; shift;;
        --list)    OPT_LIST=true; shift;;
        --status)  OPT_STATUS=true; shift;;
        --migrate) OPT_MIGRATE=true; shift;;
        *) echo "Unknown option: $1"; exit 1;;
    esac
done

if $OPT_STATUS; then
    python3 - "$STATE_FILE" <<'PYEOF'
import pathlib, sys
p = pathlib.Path(sys.argv[1])
print(p.read_text() if p.exists() else 'No setup state found')
PYEOF
    exit 0
fi

if $OPT_MIGRATE; then # D-015: dual-load 해소
    [ -d .claude/agents ] && mv .claude/agents .claude/agents.bak && echo "✓ .claude/agents → .claude/agents.bak"
    [ -d .claude/skills ] && mv .claude/skills .claude/skills.bak && echo "✓ .claude/skills → .claude/skills.bak"
    exit 0
fi

if $OPT_FORCE; then rm -f "$STATE_FILE"; echo "State reset."; fi

echo "=== claude-code-kit 초기 셋업 ==="

# D-016 (IM-09): 외부 도구 최소 버전 체크 (ATK-007: 실제 버전 비교 구현)
_check_version() {
    local cmd="$1" min_ver="$2"
    if ! command -v "$cmd" &>/dev/null; then
        echo "  ⚠ $cmd 미설치 — $min_ver 이상 설치 권장"
        return 1
    fi
    local cur_ver
    cur_ver=$("$cmd" --version 2>/dev/null | grep -oE '[0-9]+\.[0-9]+\.[0-9]+' | head -1)
    if [ -z "$cur_ver" ]; then
        echo "  ? $cmd 버전 확인 불가 (설치는 됨)"
        return 0
    fi
    local IFS=.
    local cur=($cur_ver) min=($min_ver)
    for i in 0 1 2; do
        local c="${cur[$i]:-0}" m="${min[$i]:-0}"
        if (( c > m )); then echo "  ✓ $cmd $cur_ver"; return 0; fi
        if (( c < m )); then echo "  ⚠ $cmd $cur_ver < 권장 $min_ver — 업그레이드 권장"; return 1; fi
    done
    echo "  ✓ $cmd $cur_ver"
}
_check_version "ruff" "0.4.0"
_check_version "gitleaks" "8.18.0"

# 1. Plugin 설치 (common 필수)
echo "[1/4] Plugin 설치..."
if ! _step_done "plugin-common"; then
    claude plugin install claude-code-kit@stable --scope user
    _mark_done "plugin-common"
fi
echo "  ℹ 훅(protect-sensitive, auto-format 등)은 플러그인이 자동으로 처리합니다"

# D-016 (IM-06): 도메인 선택 UI에 설명 추가
if $OPT_LIST; then
    echo "frontend    — UI 컴포넌트, React/Vue (4 agents, 1 skill)"
    echo "infra       — Terraform, Docker, K8s (7 agents, 1 skill)"
    echo "ops         — 배포, 모니터링, 인시던트 (14 agents, 4 skills)"
    echo "data        — DB 설계, 쿼리 최적화 (4 agents, 3 skills)"
    echo "integration — Webhook, Slack, CI/CD 연동 (4 agents)"
    exit 0
fi

if $OPT_ALL; then
    DOMAINS="frontend infra ops data integration"
elif [ -n "${DOMAINS:-}" ]; then
    : # 환경변수에서 직접 지정
elif [ -t 0 ] && [ "${CI:-}" != "true" ]; then
    echo "도메인 플러그인 선택 (원하는 도메인을 space로 구분하여 입력, 없으면 Enter):"
    echo "  frontend    — UI 컴포넌트, React/Vue (4 agents)"
    echo "  infra       — Terraform, Docker, K8s (7 agents)"
    echo "  ops         — 배포, 모니터링, 인시던트 (14 agents)"
    echo "  data        — DB 설계, 쿼리 최적화 (4 agents)"
    echo "  integration — Webhook, CI/CD 연동 (4 agents)"
    read -r -p "선택: " DOMAINS
else
    DOMAINS=""  # 비대화형: common만
fi

ALLOWED_DOMAINS=(frontend infra ops data integration)
for domain in $DOMAINS; do
    # 화이트리스트 검증 (command injection 방지)
    valid=false
    for allowed in "${ALLOWED_DOMAINS[@]}"; do
        [[ "$domain" == "$allowed" ]] && valid=true && break
    done
    if ! $valid; then
        echo "  ⚠ Unknown domain: '$domain', 스킵됨"
        continue
    fi
    if ! _step_done "plugin-$domain"; then
        claude plugin install "claude-code-kit-${domain}@stable" --scope user
        _mark_done "plugin-$domain"
    fi
done

# 2. ruff.toml 전역 설치
echo "[2/4] ruff.toml 설치..."
RUFF_DST="$HOME/.config/ruff/ruff.toml"
if [ ! -f "$RUFF_DST" ]; then
    mkdir -p "$(dirname "$RUFF_DST")"
    cp "$SCRIPT_DIR/plugins/common/setup/ruff.toml" "$RUFF_DST"
    echo "  ✓ $RUFF_DST 설치됨"
else
    echo "  - 이미 존재, 스킵"
fi

# 3. init.templateDir 설정
echo "[3/4] git init.templateDir 설정..."
CURRENT_TPL="$(git config --global init.templateDir 2>/dev/null || true)"
if [ -z "$CURRENT_TPL" ]; then
    TPL_DIR="$HOME/.claude/git-templates/hooks"
    mkdir -p "$TPL_DIR"
    cp "$SCRIPT_DIR/plugins/common/setup/pre-commit" "$TPL_DIR/pre-commit"
    chmod 755 "$TPL_DIR/pre-commit"
    git config --global init.templateDir "$HOME/.claude/git-templates"
    echo "  ✓ init.templateDir 설정됨"
elif [ "$CURRENT_TPL" != "$HOME/.claude/git-templates" ]; then
    echo "  ⚠ 이미 다른 templateDir 설정됨: $CURRENT_TPL"
    echo "    수동으로 pre-commit을 해당 디렉토리에 복사하세요."
fi

# 4. 현재 repo pre-commit 설치
echo "[4/4] 현재 repo pre-commit 설치..."
GIT_DIR="$(git rev-parse --git-dir 2>/dev/null || true)"
if [ -n "$GIT_DIR" ] && [ ! -f "$GIT_DIR/hooks/pre-commit" ]; then
    cp "$SCRIPT_DIR/plugins/common/setup/pre-commit" "$GIT_DIR/hooks/pre-commit"
    chmod 755 "$GIT_DIR/hooks/pre-commit"
    echo "  ✓ pre-commit 설치됨"
fi

echo ""
echo "=== 셋업 완료 ==="
echo "도메인 플러그인 목록: ./setup.sh --list"
