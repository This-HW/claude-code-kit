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


def stale_venv_interp(venv_dir):
    """venv 콘솔 스크립트의 shebang이 이 venv 밖 python을 가리키면 그 경로를 반환한다.

    venv 스크립트(pytest·pip·ruff …)에는 생성 시점의 **절대경로** shebang이 구워진다.
    프로젝트 디렉토리를 옮기거나 복사하면 그 경로가 이전 위치에 고정된 채 남는데,
    `bin/python`은 진짜 바이너리(shebang 없음)라 계속 동작한다. 그래서 증상이
    "python은 되는데 pytest만 bad interpreter"로 쪼개져 원인 파악이 오래 걸리고,
    옛 경로가 아직 살아 있으면 **옛 venv의 site-packages로 조용히** 실행된다.

    판정 불가(절대경로 python shebang이 하나도 없는 relocatable venv 등)면 None —
    오탐 경고는 노이즈가 되어 전체 경고를 안 읽게 만든다. 침묵이 낫다.
    스캔은 bin 앞쪽 40개로 제한한다(SessionStart 지연 방지).
    """
    bindir = venv_dir / ("Scripts" if os.name == "nt" else "bin")
    if not bindir.is_dir():
        return None
    try:
        bindir_real = os.path.realpath(bindir)
        entries = sorted(bindir.iterdir())[:40]
    except OSError:
        return None
    for entry in entries:
        try:
            with open(entry, "rb") as fh:
                first = fh.readline(512)
        except OSError:
            continue  # 디렉토리·깨진 심링크·권한 — 다음 후보로
        if not first.startswith(b"#!"):
            continue  # 바이너리(bin/python 본체 포함) 또는 shebang 없는 파일
        tokens = first[2:].decode("utf-8", "replace").strip().split()
        if not tokens:
            continue
        interp = tokens[0]
        if not os.path.isabs(interp):
            continue  # `#!/usr/bin/env python` 류 — venv 귀속을 판정할 수 없다
        if not os.path.basename(interp).startswith("python"):
            continue  # `#!/bin/sh` 래퍼(uv --relocatable 등)
        # 링크를 **따라가지 않고** 디렉토리 기준으로 비교한다. venv의 `bin/python`은
        # 보통 시스템 python으로 가는 심링크라, shebang 경로 자체를 resolve()하면
        # 멀쩡한 venv도 전부 "밖을 가리킨다"로 오탐한다.
        try:
            if os.path.realpath(os.path.dirname(interp)) != bindir_real:
                return interp
        except OSError:
            continue
        return None  # 정상 shebang 확인 — 더 볼 필요 없다
    return None


# ── 1. 설정 체크 / 경고 ──────────────────────────────────────────────────────
try:
    # 1z. python floor — 훅은 이 인터프리터로 실행된다. 3.9 미만이면 다른 훅들이
    # import 시점에 죽는데, 훅은 fail-open이라 **아무 메시지 없이 조용히** 사라진다.
    # 침묵 대신 한 줄 경고로 관측 가능하게 만든다 (이 파일 자체는 구버전에서도 로드됨).
    if sys.version_info < (3, 9):
        warnings.append(
            "python3 %d.%d 감지 — kit 훅은 3.9+ 필요. auto-format·stop-validator 등이 "
            "동작하지 않습니다 (python3 업그레이드 또는 PATH 확인)"
            % (sys.version_info[0], sys.version_info[1])
        )

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
            check=False,
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
            check=False,
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
                check=False,
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

        # 1c. stale venv 감지 — 프로젝트 디렉토리 이동/복사 후의 침묵 실패 (stale_venv_interp 참고)
        for venv_name in (".venv", "venv"):
            stale_interp = stale_venv_interp(repo_root / venv_name)
            if stale_interp:
                warnings.append(
                    # !r — shebang은 파일에서 읽은 값이다. 터미널 이스케이프가 섞여도
                    # 그대로 렌더되지 않도록 repr로 감싼다(core.hooksPath 경고와 동일 관례).
                    f"{venv_name} 스크립트의 shebang이 프로젝트 밖 python을 가리킵니다 "
                    f"({stale_interp!r}) — 디렉토리 이동/복사 후 stale 상태입니다. "
                    f"재생성: rm -rf {venv_name} && python3 -m venv {venv_name} (의존성 재설치)"
                )
                break

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
