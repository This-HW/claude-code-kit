#!/usr/bin/env python3
"""SessionStart hook: rules additionalContext 주입 + 로컬 설정 체크 + 경고"""
import json
import pathlib
import subprocess
import sys

try:
    # D-012: __file__ 기반 경로 해결 (cwd 무관, Plugin 캐시 위치 무관)
    SETUP_DIR = pathlib.Path(__file__).resolve().parent   # plugins/common/setup/
    PLUGIN_DIR = SETUP_DIR.parent                          # plugins/common/
    RULES_DIR = PLUGIN_DIR / "rules"

    warnings = []

    # ATK-005: Plugin-only 사용자(setup.sh 미실행)에게 경고 피로 방지
    setup_state = pathlib.Path.home() / ".claude/.setup-state.json"
    is_plugin_only = not setup_state.exists()

    # 1. 전역 설정 누락 경고 (풀 모드 전용)
    ruff_dst = pathlib.Path.home() / ".config/ruff/ruff.toml"
    if not ruff_dst.exists() and not is_plugin_only:
        warnings.append("ruff.toml 미설치 — setup.sh를 다시 실행하세요")

    tpl_result = subprocess.run(
        ["git", "config", "--global", "--get", "init.templateDir"],
        capture_output=True, text=True
    )
    if tpl_result.returncode == 1 and not is_plugin_only:
        warnings.append("init.templateDir 미설정 — setup.sh를 다시 실행하세요")

    # 2. 현재 repo 로컬 설정
    git_toplevel = subprocess.run(
        ["git", "rev-parse", "--show-toplevel"],
        capture_output=True, text=True
    ).stdout.strip()

    if git_toplevel:
        repo_root = pathlib.Path(git_toplevel)

        # D-015: core.hooksPath 확인 (H-1, IM-04)
        hooks_path_result = subprocess.run(
            ["git", "config", "core.hooksPath"],
            capture_output=True, text=True, cwd=git_toplevel
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
                git_hooks_dir = repo_root / ".git/hooks"
        else:
            git_hooks_dir = repo_root / ".git/hooks"

        # 2a. pre-commit: core.hooksPath 경로에 설치
        import shutil
        hook_dst = git_hooks_dir / "pre-commit"
        pre_commit_src = SETUP_DIR / "pre-commit"
        if not hook_dst.exists() and pre_commit_src.exists():
            hook_dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(pre_commit_src, hook_dst)
            hook_dst.chmod(0o755)

        # D-015: dual-load 감지 (CR-07)
        claude_agents = repo_root / ".claude/agents"
        if claude_agents.exists() and any(claude_agents.rglob("*.md")):
            warnings.append(
                ".claude/agents/ + Plugin 동시 감지! 에이전트 중복 로딩 위험. "
                "'setup.sh --migrate' 실행 권장"
            )

    # 3. 경고 출력
    if warnings:
        print(f"[claude-code-kit] ⚠ {'; '.join(warnings)}", file=sys.stderr)

    # 4. rules additionalContext 주입
    RULE_FILES = [
        "agent-system.md",
        "tool-usage-priority.md",
        "ssot.md",
        "mcp-usage.md",
        "code-quality.md",
    ]

    sections = []
    for fname in RULE_FILES:
        fpath = RULES_DIR / fname
        try:
            content = fpath.read_text(encoding="utf-8").strip()
            sections.append(f"## {fname}\n{content}")
        except Exception:
            pass  # 조용히 스킵

    if sections:
        rules_content = "<claude-code-kit-rules>\n" + "\n\n".join(sections) + "\n</claude-code-kit-rules>"
        print(json.dumps({
            "hookSpecificOutput": {
                "additionalContext": rules_content
            }
        }))

except Exception as e:
    print(f"[claude-code-kit] session-check warning: {e}", file=sys.stderr)

sys.exit(0)  # 항상 허용 (SessionStart = fail-open)
