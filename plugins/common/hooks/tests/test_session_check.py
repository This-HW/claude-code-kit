"""session-check.py (SessionStart 훅) 회귀 테스트.

이 훅은 세션 시작마다 **모든 소비자 환경**에서 가장 먼저 실행된다. 계약은 두 가지뿐:
  1. 무슨 일이 있어도 exit 0 + 유효한 SessionStart JSON (fail-open — 세션을 막지 않는다)
  2. 관측 가능해야 할 문제는 stderr 경고로 남긴다 (침묵 실패 금지)

특히 python floor 경고는 "구버전 python에서 다른 훅들이 조용히 죽는" 상황을 사용자에게
알리는 유일한 통로다 — 훅이 fail-open이라 그 죽음 자체는 아무 흔적을 남기지 않는다.
"""

import json
import runpy
import subprocess
import sys
from pathlib import Path

import pytest

SETUP_DIR = Path(__file__).resolve().parent.parent.parent / "setup"
SCRIPT = SETUP_DIR / "session-check.py"


def _run_isolated(tmp_path, monkeypatch):
    """격리 환경(HOME·cwd 모두 tmp)에서 스크립트 top-level을 실행한다.

    HOME이 tmp면 `.setup-state.json` 부재 → plugin-only 모드로 판정되어 setup.sh
    관련 경고가 억제되고, cwd가 git 저장소 밖이라 pre-commit 설치 경로도 타지 않는다.
    """
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.chdir(tmp_path)
    with pytest.raises(SystemExit) as exc:
        runpy.run_path(str(SCRIPT), run_name="__ckkit_test__")
    return exc.value.code


def test_exits_zero_with_valid_sessionstart_json(tmp_path, monkeypatch, capsys):
    code = _run_isolated(tmp_path, monkeypatch)
    assert code == 0
    out = json.loads(capsys.readouterr().out)
    # rules 주입은 session-start.py 전담 — 이 훅의 additionalContext는 항상 빈 문자열.
    assert out["hookSpecificOutput"]["hookEventName"] == "SessionStart"
    assert out["hookSpecificOutput"]["additionalContext"] == ""


def test_warns_when_python_below_floor(tmp_path, monkeypatch, capsys):
    """3.9 미만이면 경고 — 없으면 사용자는 훅이 죽은 사실을 영영 모른다."""
    monkeypatch.setattr(sys, "version_info", (3, 8, 10, "final", 0))
    assert _run_isolated(tmp_path, monkeypatch) == 0
    captured = capsys.readouterr()
    assert "3.9+" in captured.err
    assert "3.8" in captured.err
    # 경고를 내면서도 세션은 계속돼야 한다(fail-open).
    assert (
        json.loads(captured.out)["hookSpecificOutput"]["hookEventName"]
        == "SessionStart"
    )


def test_no_python_warning_on_supported_version(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(sys, "version_info", (3, 9, 6, "final", 0))
    assert _run_isolated(tmp_path, monkeypatch) == 0
    assert "3.9+" not in capsys.readouterr().err


# ── stale venv 감지 (프로젝트 디렉토리 이동/복사) ────────────────────────────
#
# venv의 콘솔 스크립트(pytest·pip·ruff …)는 생성 시점의 **절대경로** shebang이 구워진다.
# 프로젝트를 옮기면 `.venv/bin/python`(진짜 바이너리)은 계속 동작하는데 스크립트는 전부
# "bad interpreter"로 죽는다 — 더 나쁜 경우, 옛 경로가 남아 있으면 옛 venv의
# site-packages로 **조용히** 실행된다. 둘 다 침묵 실패라 경고가 유일한 관측 통로다.


def _init_repo(tmp_path):
    """전역 templateDir 영향을 받지 않는 빈 git 저장소를 만든다(테스트 격리)."""
    empty_tpl = tmp_path / "empty-template"
    empty_tpl.mkdir()
    subprocess.run(
        ["git", "init", "-q", f"--template={empty_tpl}", str(tmp_path)],
        capture_output=True,
        timeout=30,
        check=True,
    )


def _make_venv(root, interp, name=".venv"):
    """shebang이 `interp`를 가리키는 콘솔 스크립트 하나를 가진 가짜 venv."""
    bindir = root / name / "bin"
    bindir.mkdir(parents=True)
    script = bindir / "pytest"
    script.write_text(f"#!{interp}\n# -*- coding: utf-8 -*-\n")
    script.chmod(0o755)
    return root / name


def _run_in_repo(tmp_path, monkeypatch):
    _init_repo(tmp_path)
    return _run_isolated(tmp_path, monkeypatch)


def test_warns_when_venv_shebang_points_outside_project(tmp_path, monkeypatch, capsys):
    """디렉토리 이동 후의 stale venv — 경고가 없으면 원인 파악에 한참 걸린다."""
    _make_venv(tmp_path, "/old/path/claude-code-kit/.venv/bin/python")
    assert _run_in_repo(tmp_path, monkeypatch) == 0
    err = capsys.readouterr().err
    assert ".venv" in err
    assert "/old/path/claude-code-kit/.venv/bin/python" in err


def test_no_venv_warning_when_shebang_is_inside_project(tmp_path, monkeypatch, capsys):
    """정상 venv를 stale로 오탐하면 경고가 노이즈가 되어 아무도 안 읽는다."""
    _make_venv(tmp_path, str(tmp_path / ".venv/bin/python"))
    assert _run_in_repo(tmp_path, monkeypatch) == 0
    assert "venv" not in capsys.readouterr().err


def test_stale_venv_warning_keeps_sessionstart_contract(tmp_path, monkeypatch, capsys):
    """경고를 내는 경로에서도 stdout은 유효한 SessionStart JSON이어야 한다."""
    _make_venv(tmp_path, "/old/path/kit/.venv/bin/python")
    assert _run_in_repo(tmp_path, monkeypatch) == 0
    out = json.loads(capsys.readouterr().out)
    assert out["hookSpecificOutput"]["hookEventName"] == "SessionStart"
    assert out["hookSpecificOutput"]["additionalContext"] == ""


def test_detects_stale_venv_in_plain_venv_dir(tmp_path, monkeypatch, capsys):
    """`.venv`뿐 아니라 `venv`도 본다 — 두 이름 다 실제로 쓰인다."""
    _make_venv(tmp_path, "/old/path/kit/venv/bin/python", name="venv")
    assert _run_in_repo(tmp_path, monkeypatch) == 0
    assert "venv 스크립트" in capsys.readouterr().err


def test_malformed_shebang_does_not_abort_later_checks(tmp_path, monkeypatch, capsys):
    """깨진 shebang 하나가 **뒤따르는 검사들을 통째로 삼키면** 안 된다.

    venv 스캔은 설정 체크 블록의 중간에 있다. 여기서 예상 못 한 예외가 나면 같은
    try 안의 후속 검사(dual-load 감지)가 조용히 사라지고, 사용자는 그 사실을
    영영 모른다 — 훅의 침묵 실패를 막으려고 넣은 코드가 새 침묵 실패를 만드는 셈.

    NUL이 박힌 경로는 `os.path.realpath`에서 OSError가 아니라 **ValueError**를 낸다.
    """
    _make_venv(tmp_path, "/old/\x00path/python")
    agents = tmp_path / ".claude/agents"
    agents.mkdir(parents=True)
    (agents / "x.md").write_text("---\nname: x\n---\n")
    assert _run_in_repo(tmp_path, monkeypatch) == 0
    captured = capsys.readouterr()
    # 판정 불가한 shebang은 조용히 건너뛴다 — 예외가 새어나온 흔적이 없어야 한다.
    assert "null" not in captured.err
    # 그리고 뒤따르는 검사(dual-load)는 정상적으로 도달해야 한다.
    assert "동시 감지" in captured.err
    assert (
        json.loads(captured.out)["hookSpecificOutput"]["hookEventName"]
        == "SessionStart"
    )


def test_venv_warning_escapes_control_chars_from_shebang(tmp_path, monkeypatch, capsys):
    """shebang은 파일에서 읽은 값 — 터미널 이스케이프를 그대로 stderr에 흘리지 않는다."""
    _make_venv(tmp_path, "/old/\x1b[2Jpath/python")
    assert _run_in_repo(tmp_path, monkeypatch) == 0
    err = capsys.readouterr().err
    assert ".venv" in err
    assert "\x1b" not in err


def test_no_venv_warning_when_venv_python_is_a_symlink(tmp_path, monkeypatch, capsys):
    """실제 venv의 `bin/python`은 시스템 python으로 가는 **심링크**다.

    shebang 경로를 그대로 resolve()하면 링크를 따라 venv 밖으로 나가버려 멀쩡한 venv를
    전부 stale로 오탐한다(이 프로젝트의 실제 venv에서 재현됨). 판정은 링크를 따라가지
    않는 디렉토리 기준이어야 한다.
    """
    venv = _make_venv(tmp_path, str(tmp_path / ".venv/bin/python"))
    outside = tmp_path / "system-python"
    outside.write_text("#!/bin/sh\n")
    (venv / "bin" / "python").symlink_to(outside)
    assert _run_in_repo(tmp_path, monkeypatch) == 0
    assert "venv" not in capsys.readouterr().err


def test_no_venv_warning_for_relocatable_shebang(tmp_path, monkeypatch, capsys):
    """`#!/bin/sh` 래퍼(uv --relocatable 등)는 절대경로 python이 없다 → 판정 불가 → 침묵."""
    _make_venv(tmp_path, "/bin/sh")
    assert _run_in_repo(tmp_path, monkeypatch) == 0
    assert "venv" not in capsys.readouterr().err


def test_no_venv_warning_when_no_venv_exists(tmp_path, monkeypatch, capsys):
    assert _run_in_repo(tmp_path, monkeypatch) == 0
    assert "venv" not in capsys.readouterr().err


def test_subprocess_run_never_blocks_session(tmp_path):
    """실제 프로세스로도 계약 확인 — in-process 테스트가 놓치는 import-time 오류 포함."""
    r = subprocess.run(
        [sys.executable, str(SCRIPT)],
        capture_output=True,
        text=True,
        timeout=30,
        cwd=str(tmp_path),
        env={"HOME": str(tmp_path), "PATH": "/usr/bin:/bin:/usr/local/bin"},
        check=False,
    )
    assert r.returncode == 0, r.stderr
    assert json.loads(r.stdout)["hookSpecificOutput"]["hookEventName"] == "SessionStart"
