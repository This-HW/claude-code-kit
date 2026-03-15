#!/usr/bin/env python3
"""SessionStart hook: 로컬 설정 체크 + 전역 누락 경고 + 무결성 검증"""
import sys, shutil, pathlib, subprocess, hashlib


# ATK-001: 함수 정의를 try 블록 이전에 위치 (호출 전 반드시 정의되어야 함)
def _verify_checksums(rules_dir, checksums_file):
    """CHECKSUMS.sha256 파일로 rules 무결성 검증 (D-013)"""
    if not checksums_file.exists():
        return True  # 체크섬 파일 없으면 스킵 (하위 호환)
    expected = {}
    for line in checksums_file.read_text().splitlines():
        if line.strip():
            h, name = line.split(None, 1)
            expected[name] = h
    for name, expected_hash in expected.items():
        fpath = rules_dir / name
        if fpath.exists():
            actual = hashlib.sha256(fpath.read_bytes()).hexdigest()
            if actual != expected_hash:
                return False
    return True


def _version_gt(a, b):
    """시맨틱 버전 비교: a > b (D-013)"""
    try:
        return tuple(int(x) for x in a.split(".")) > tuple(int(x) for x in b.split("."))
    except (ValueError, AttributeError):
        return False


try:
    # D-012: __file__ 기반 경로 해결 (cwd 무관, Plugin 캐시 위치 무관)
    SETUP_DIR = pathlib.Path(__file__).resolve().parent   # plugins/common/setup/
    PLUGIN_DIR = SETUP_DIR.parent                          # plugins/common/
    RULES_SRC = PLUGIN_DIR / "rules"
    warnings = []

    # 1. 전역 설정 누락 경고
    # ATK-005: Plugin-only 사용자(setup.sh 미실행)에게 경고 피로 방지
    setup_state = pathlib.Path.home() / ".claude/.setup-state.json"
    is_plugin_only = not setup_state.exists()

    hooks_dir = pathlib.Path.home() / ".claude/hooks"
    if not hooks_dir.exists() or not (hooks_dir / "protect-sensitive.py").exists():
        if is_plugin_only:
            # Plugin-only 모드: 첫 세션 1회만 안내 (이후 억제)
            warned_file = pathlib.Path.home() / ".claude/.setup-hint-shown"
            if not warned_file.exists():
                warnings.append("보안 훅 미설치 — ./setup.sh 실행으로 추가 보안을 강화할 수 있습니다")
                warned_file.touch()
        else:
            # 풀 모드인데 훅이 없으면: 실제 문제 (매 세션 경고)
            warnings.append("보안 훅 미설치 — setup.sh를 다시 실행하세요 (--resume)")

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
        git_hooks_dir = (
            pathlib.Path(hooks_path_result.stdout.strip())
            if hooks_path_result.returncode == 0
            else repo_root / ".git/hooks"
        )

        # 2a. pre-commit: core.hooksPath 경로에 설치
        hook_dst = git_hooks_dir / "pre-commit"
        pre_commit_src = SETUP_DIR / "pre-commit"
        if not hook_dst.exists() and pre_commit_src.exists():
            hook_dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(pre_commit_src, hook_dst)
            hook_dst.chmod(0o755)

        # D-015: dual-load 감지 (CR-07)
        claude_agents = repo_root / ".claude/agents"
        if claude_agents.exists() and any(claude_agents.glob("*.md")):
            warnings.append(
                ".claude/agents/ + Plugin 동시 감지! 에이전트 중복 로딩 위험. "
                "'setup.sh --migrate' 실행 권장"
            )

        # D-013: rules 복사 + 무결성 검증 (CR-06, H-4, IM-02)
        rules_dst = repo_root / ".claude/rules"
        if RULES_SRC.exists():
            checksums_file = RULES_SRC / "CHECKSUMS.sha256"
            version_src = RULES_SRC / "VERSION"

            if not rules_dst.exists():
                # 최초 복사: 체크섬 검증 후 복사
                if _verify_checksums(RULES_SRC, checksums_file):
                    shutil.copytree(
                        RULES_SRC, rules_dst,
                        symlinks=False,  # ATK-012: 실제 파일만 복사
                        ignore=shutil.ignore_patterns("VERSION", "CHECKSUMS.sha256")
                    )
                else:
                    warnings.append("rules 체크섬 불일치 — 수동 확인 필요")
            elif version_src.exists():
                # 업데이트 안내: VERSION 비교
                version_dst = rules_dst / "VERSION"
                src_ver = version_src.read_text().strip()
                dst_ver = version_dst.read_text().strip() if version_dst.exists() else "0.0.0"
                if _version_gt(src_ver, dst_ver):
                    warnings.append(f"rules 업데이트 가능 ({dst_ver} → {src_ver})")
        elif not RULES_SRC.exists():
            warnings.append("Plugin rules 경로를 찾을 수 없음 — Plugin 재설치 권장")

    # 3. 경고 출력
    if warnings:
        print(f"[claude-code-kit] ⚠ {'; '.join(warnings)}", file=sys.stderr)

except Exception as e:
    print(f"[claude-code-kit] session-check warning: {e}", file=sys.stderr)

sys.exit(0)  # 항상 허용 (SessionStart = fail-open)
