#!/usr/bin/env python3
"""SessionStart hook: 로컬 설정 체크 + 경고 (rules 주입은 session-start.py 전담)"""

import json
import os
import pathlib
import subprocess
import sys

# D-012: __file__ 기반 경로 해결 (cwd 무관, Plugin 캐시 위치 무관)
SETUP_DIR = pathlib.Path(__file__).resolve().parent  # plugins/common/setup/

warnings = []

# ── 1. 설정 체크 / 경고 ──────────────────────────────────────────────────────
try:
    # ATK-005: Plugin-only 사용자(setup.sh 미실행)에게 경고 피로 방지
    setup_state = pathlib.Path.home() / ".claude/.setup-state.json"
    is_plugin_only = not setup_state.exists()

    # 1a. 전역 설정 누락 경고 (풀 모드 전용)
    ruff_dst = pathlib.Path.home() / ".config/ruff/ruff.toml"
    if not ruff_dst.exists() and not is_plugin_only:
        warnings.append("ruff.toml 미설치 — setup.sh를 다시 실행하세요")

    try:
        tpl_result = subprocess.run(
            ["git", "config", "--global", "--get", "init.templateDir"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if tpl_result.returncode == 1 and not is_plugin_only:
            warnings.append("init.templateDir 미설정 — setup.sh를 다시 실행하세요")
    except subprocess.TimeoutExpired:
        warnings.append("git config 조회 시간 초과 (init.templateDir)")

    # 1b. 현재 repo 로컬 설정
    git_toplevel = ""
    try:
        git_toplevel = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            capture_output=True,
            text=True,
            timeout=5,
        ).stdout.strip()
    except subprocess.TimeoutExpired:
        warnings.append("git rev-parse 시간 초과")

    if git_toplevel:
        repo_root = pathlib.Path(git_toplevel)

        # D-015: core.hooksPath 확인 (H-1, IM-04)
        raw_hooks_path = ""
        try:
            hooks_path_result = subprocess.run(
                ["git", "config", "core.hooksPath"],
                capture_output=True,
                text=True,
                cwd=git_toplevel,
                timeout=5,
            )
            raw_hooks_path = hooks_path_result.stdout.strip()
            if hooks_path_result.returncode == 0 and raw_hooks_path:
                p = pathlib.Path(raw_hooks_path)
                candidate = (p if p.is_absolute() else (repo_root / p)).resolve()
                # path traversal 방어: repo_root 상위로 탈출 차단
                try:
                    candidate.relative_to(repo_root.resolve())
                    git_hooks_dir = candidate
                except ValueError:
                    # ATK-008: path traversal 감지 시 경고 메시지 추가
                    warnings.append(
                        f"core.hooksPath가 repo 외부를 가리킵니다: {raw_hooks_path!r}. "
                        "기본 .git/hooks를 사용합니다."
                    )
                    git_hooks_dir = repo_root / ".git/hooks"
            else:
                git_hooks_dir = repo_root / ".git/hooks"
        except subprocess.TimeoutExpired:
            warnings.append("git config core.hooksPath 시간 초과")
            git_hooks_dir = repo_root / ".git/hooks"

        # D-015: dual-load 감지 (CR-07)
        claude_agents = repo_root / ".claude/agents"
        if claude_agents.exists() and any(claude_agents.rglob("*.md")):
            warnings.append(
                ".claude/agents/ + Plugin 동시 감지! 에이전트 중복 로딩 위험. "
                "'setup.sh --migrate' 실행 권장"
            )

except Exception as e:
    print(f"[claude-code-kit] session-check warning (설정 체크): {e}", file=sys.stderr)

# ── 2. pre-commit 설치 (plugin-only 모드) ─────────────────────────────────────
try:
    setup_state = pathlib.Path.home() / ".claude/.setup-state.json"
    is_plugin_only = not setup_state.exists()

    if is_plugin_only and git_toplevel:
        hook_dst = git_hooks_dir / "pre-commit"
        pre_commit_src = SETUP_DIR / "pre-commit"

        # ATK-001: TOCTOU 방어 — atomic write (tempfile + os.replace)
        if (
            not hook_dst.is_symlink()
            and not hook_dst.exists()
            and pre_commit_src.exists()
        ):
            import tempfile

            hook_dst.parent.mkdir(parents=True, exist_ok=True)
            with tempfile.NamedTemporaryFile(
                dir=hook_dst.parent, delete=False, suffix=".tmp"
            ) as tmp:
                tmp_path = pathlib.Path(tmp.name)
                tmp_path.write_bytes(pre_commit_src.read_bytes())
            tmp_path.chmod(0o755)
            os.replace(tmp_path, hook_dst)  # atomic

except Exception as e:
    print(
        f"[claude-code-kit] session-check warning (pre-commit 설치): {e}",
        file=sys.stderr,
    )

# ── 3. 경고 출력 ──────────────────────────────────────────────────────────────
if warnings:
    print(f"[claude-code-kit] ⚠ {'; '.join(warnings)}", file=sys.stderr)

# ── 4. 출력 — additionalContext는 빈 문자열 (session-start.py가 rules 주입 전담) ──
print(
    json.dumps(
        {
            "hookSpecificOutput": {
                "hookEventName": "SessionStart",
                "additionalContext": "",
            }
        }
    )
)

sys.exit(0)  # 항상 허용 (SessionStart = fail-open)
