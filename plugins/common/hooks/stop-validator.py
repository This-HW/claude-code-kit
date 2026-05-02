#!/usr/bin/env python3
"""
Stop hook: last-resort safety net for ad-hoc coding sessions.
Runs ruff + pytest when Python files are modified. Blocks on failure.
Skips if auto-dev pipeline already ran validation (marker file present).

Failure taxonomy:
  lint_error    → auto-fix with ruff, re-validate. If fixed: inform Claude.
  test_failure  → structured error output, block (NOT auto-fixable)
  no_py_changes → skip entirely (no Python files modified)

To disable: in plugins/common/hooks/hooks.json, replace the Stop section with
the prompt-based hook (see CHANGELOG.md [2.2.0]) or remove it entirely.
"""

import hashlib
import json
import subprocess
import sys
from pathlib import Path


# ── 프로젝트 루트 결정 ───────────────────────────────────────────
def _get_project_root() -> Path:
    """git rev-parse로 stable한 프로젝트 루트를 반환. git 없으면 cwd fallback."""
    try:
        r = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if r.returncode == 0 and r.stdout.strip():
            return Path(r.stdout.strip())
    except Exception:
        pass
    return Path(".").resolve()


PROJECT_ROOT = _get_project_root()
_hash = hashlib.md5(str(PROJECT_ROOT).encode()).hexdigest()[:8]
VALIDATED_MARKER = Path(f"/tmp/.claude_validated_{_hash}")
RETRY_COUNTER = Path(f"/tmp/.claude_stop_retries_{_hash}")
MAX_RETRIES = 2
_MAX_FILE_SIZE = 1_048_576  # 1MB: auto_fix_lint에서 파일 읽기 상한

# 검색 제외 디렉토리
EXCLUDE_DIRS = {
    ".venv",
    "venv",
    "__pycache__",
    ".git",
    "node_modules",
    ".mypy_cache",
    ".pytest_cache",
    "dist",
    "build",
}


# ── 유틸 ────────────────────────────────────────────────────────
def get_retry_count() -> int:
    try:
        return int(RETRY_COUNTER.read_text(encoding="utf-8").strip())
    except Exception:
        return 0


def increment_retry() -> int:
    count = get_retry_count() + 1
    RETRY_COUNTER.write_text(str(count), encoding="utf-8")
    return count


def reset_retry():
    RETRY_COUNTER.unlink(missing_ok=True)


def allow(message: str = ""):
    """정상 종료: Claude Code가 stop을 허용."""
    if message:
        print(message)
    reset_retry()
    sys.exit(0)


def block(failure_type: str, reason: str, details: dict | None = None):
    """
    Stop을 차단: Claude Code가 Claude에게 재응답을 요청.
    stdout에 출력된 내용이 Claude의 컨텍스트에 주입된다.
    """
    payload = {
        "failure_type": failure_type,
        "reason": reason,
        "details": details or {},
        "retry_count": get_retry_count(),
        "action_required": _get_action_hint(failure_type),
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    sys.exit(2)


def _get_action_hint(failure_type: str) -> str:
    hints = {
        "lint_error": "남은 린트 오류를 수동으로 수정하세요.",
        "test_failure": "실패한 테스트를 확인하고 코드를 수정하세요.",
        "max_retries_exceeded": "자동 수정 한계 초과. 수동 확인이 필요합니다.",
    }
    return hints.get(failure_type, "확인이 필요합니다.")


# ── 변경 파일 감지 ───────────────────────────────────────────────
def get_modified_py_files() -> list[str]:
    """
    수정/추가된 Python 파일 목록을 반환.
    1) git diff HEAD      — tracked 파일 중 수정된 것
    2) git diff --cached  — staged 파일
    3) git ls-files --others --exclude-standard — untracked 새 파일
    git 없는 환경이면 빈 리스트 (검증 스킵).
    """
    try:
        files: set[str] = set()
        git_opts = {
            "capture_output": True,
            "text": True,
            "timeout": 5,
            "cwd": str(PROJECT_ROOT),
        }

        r1 = subprocess.run(["git", "diff", "--name-only", "HEAD"], **git_opts)
        files.update(f for f in r1.stdout.splitlines() if f.endswith(".py"))

        r2 = subprocess.run(["git", "diff", "--cached", "--name-only"], **git_opts)
        files.update(f for f in r2.stdout.splitlines() if f.endswith(".py"))

        r3 = subprocess.run(
            ["git", "ls-files", "--others", "--exclude-standard"], **git_opts
        )
        files.update(f for f in r3.stdout.splitlines() if f.endswith(".py"))

        return list(files)
    except Exception:
        return []


# ── 린트 ────────────────────────────────────────────────────────
def _resolve_paths(target_files: list[str]) -> list[str]:
    """git-relative 경로를 PROJECT_ROOT 기준 절대 경로로 변환.
    이미 절대 경로면 그대로 반환. 존재하지 않는 파일은 제외.
    """
    resolved = []
    for f in target_files:
        p = Path(f)
        abs_p = p if p.is_absolute() else PROJECT_ROOT / p
        if abs_p.exists():
            resolved.append(str(abs_p))
    return resolved


def check_lint(target_files: list[str]) -> tuple[bool, str]:
    existing = _resolve_paths(target_files)
    if not existing:
        return True, ""
    try:
        result = subprocess.run(
            ["ruff", "check"] + existing,
            capture_output=True,
            text=True,
            timeout=30,
        )
        return result.returncode == 0, result.stdout + result.stderr
    except FileNotFoundError:
        print("[WARN] ruff not found — lint check skipped", file=sys.stderr)
        return True, ""
    except subprocess.TimeoutExpired:
        print("[WARN] ruff timeout — lint check skipped", file=sys.stderr)
        return True, ""


def auto_fix_lint(target_files: list[str]) -> tuple[bool, list[str], str]:
    """
    Returns: (now_passing, fixed_files, remaining_errors)
    1MB 초과 파일은 비교 대상에서 제외 (OOM 방지).
    """
    try:
        existing = [
            f
            for f in _resolve_paths(target_files)
            if Path(f).stat().st_size < _MAX_FILE_SIZE
        ]
        before = {
            f: Path(f).read_text(encoding="utf-8", errors="replace") for f in existing
        }
        subprocess.run(
            ["ruff", "check", "--fix"] + existing,
            capture_output=True,
            text=True,
            timeout=30,
        )
        after = {
            f: Path(f).read_text(encoding="utf-8", errors="replace") for f in existing
        }
        fixed_files = [f for f in existing if before.get(f) != after.get(f)]

        passed, errors = check_lint(target_files)
        return passed, fixed_files, errors
    except FileNotFoundError:
        print("[WARN] ruff not found — auto-fix skipped", file=sys.stderr)
        return True, [], ""
    except subprocess.TimeoutExpired:
        print("[WARN] ruff --fix timeout — auto-fix skipped", file=sys.stderr)
        return True, [], ""


# ── 테스트 ───────────────────────────────────────────────────────
def find_test_files() -> list[str]:
    """EXCLUDE_DIRS를 제외하고 테스트 파일 탐색."""
    test_files = []
    for pattern in ("test_*.py", "*_test.py"):
        for p in PROJECT_ROOT.rglob(pattern):
            try:
                relative_parts = p.relative_to(PROJECT_ROOT).parts
            except ValueError:
                continue
            if not any(part in EXCLUDE_DIRS for part in relative_parts):
                test_files.append(str(p))
    return test_files


def check_tests() -> tuple[bool, str]:
    test_files = find_test_files()
    if not test_files:
        return True, ""
    try:
        result = subprocess.run(
            ["python3", "-m", "pytest", "--tb=short", "-q", "--no-header"],
            capture_output=True,
            text=True,
            timeout=60,
            cwd=str(PROJECT_ROOT),
        )
        # exit 5 = no tests collected — 통과로 처리
        return result.returncode in (0, 5), result.stdout + result.stderr
    except FileNotFoundError:
        print("[WARN] pytest not found — test check skipped", file=sys.stderr)
        return True, ""
    except subprocess.TimeoutExpired:
        return False, "테스트 실행 시간 초과 (60초)"


# ── 메인 ────────────────────────────────────────────────────────
def main():
    # 1. auto-dev Phase 5 마커 확인 → 이중 검증 방지 (원자 연산으로 TOCTOU 방지)
    try:
        VALIDATED_MARKER.unlink()
        allow("auto-dev validation marker found. Skipping stop-validator.")
    except FileNotFoundError:
        pass

    # 2. Python 파일 변경 없음 → 스킵
    modified_files = get_modified_py_files()
    if not modified_files:
        allow()

    # 3. max retries guard
    retry_count = get_retry_count()
    if retry_count >= MAX_RETRIES:
        reset_retry()
        block(
            "max_retries_exceeded",
            f"자동 수정 {MAX_RETRIES}회 시도 후에도 문제가 남아있습니다.",
            {"modified_files": modified_files},
        )

    # 4. 린트 검사
    lint_passed, lint_errors = check_lint(modified_files)
    if not lint_passed:
        fixed, fixed_files, remaining = auto_fix_lint(modified_files)
        if fixed:
            print(
                json.dumps(
                    {
                        "action": "auto_fixed",
                        "fixed_files": fixed_files,
                        "message": f"ruff가 {len(fixed_files)}개 파일을 자동 수정했습니다. "
                        f"수정된 파일: {', '.join(fixed_files)}",
                    },
                    ensure_ascii=False,
                )
            )
        else:
            increment_retry()
            block(
                "lint_error",
                "자동 수정 후에도 린트 오류가 남아있습니다.",
                {"errors": remaining[:2000], "files": modified_files},
            )

    # 5. 테스트 검사 (test_failure는 자동 수정 불가 → 바로 block)
    tests_passed, test_output = check_tests()
    if not tests_passed:
        increment_retry()
        block(
            "test_failure",
            "테스트가 실패했습니다. 코드를 수정하세요.",
            {"output": test_output[:3000]},
        )

    allow()


if __name__ == "__main__":
    main()
