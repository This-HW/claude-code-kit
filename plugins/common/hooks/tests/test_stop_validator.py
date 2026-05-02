"""Unit tests for stop-validator.py"""

import json
from pathlib import Path
from types import ModuleType

import pytest

HOOKS_DIR = Path(__file__).resolve().parent.parent


def _load_module() -> ModuleType:
    """stop-validator.py는 하이픈 이름이라 import 불가."""
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "stop_validator", HOOKS_DIR / "stop-validator.py"
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


_mod = _load_module()


@pytest.fixture(autouse=True)
def _isolate_tmp_files(tmp_path, monkeypatch):
    """마커/카운터를 tmp_path 기준 경로로 교체 — 실제 /tmp 및 동시 세션 간섭 방지."""
    fake_marker = tmp_path / "claude_validated"
    fake_counter = tmp_path / "claude_stop_retries"
    monkeypatch.setattr(_mod, "VALIDATED_MARKER", fake_marker)
    monkeypatch.setattr(_mod, "RETRY_COUNTER", fake_counter)


def _extract_json(output: str) -> dict:
    """stdout에서 첫 번째 JSON 객체를 추출."""
    start = output.find("{")
    assert start != -1, "stdout에 JSON 출력이 없습니다."
    depth, end = 0, start
    for i, ch in enumerate(output[start:], start=start):
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                end = i
                break
    return json.loads(output[start : end + 1])


# ── TC1: no_py_changes ───────────────────────────────────────────
def test_no_py_changes_exits_zero(monkeypatch):
    monkeypatch.setattr(_mod, "get_modified_py_files", lambda: [])

    with pytest.raises(SystemExit) as exc_info:
        _mod.main()

    assert exc_info.value.code == 0


# ── TC2a: lint_auto_fixed (stdout 확인) ──────────────────────────
def test_lint_auto_fixed_prints_json_and_exits_zero(monkeypatch, capsys):
    monkeypatch.setattr(_mod, "get_modified_py_files", lambda: ["file.py"])
    monkeypatch.setattr(_mod, "check_lint", lambda files: (False, "E501 line too long"))
    monkeypatch.setattr(_mod, "auto_fix_lint", lambda files: (True, ["file.py"], ""))
    monkeypatch.setattr(_mod, "check_tests", lambda: (True, ""))

    with pytest.raises(SystemExit) as exc_info:
        _mod.main()

    assert exc_info.value.code == 0
    assert "auto_fixed" in capsys.readouterr().out


# ── TC2b: lint_auto_fixed (JSON 구조 확인) ───────────────────────
def test_lint_auto_fixed_json_structure(monkeypatch, capsys):
    monkeypatch.setattr(_mod, "get_modified_py_files", lambda: ["file.py"])
    monkeypatch.setattr(_mod, "check_lint", lambda files: (False, "E501 error"))
    monkeypatch.setattr(_mod, "auto_fix_lint", lambda files: (True, ["file.py"], ""))
    monkeypatch.setattr(_mod, "check_tests", lambda: (True, ""))

    with pytest.raises(SystemExit):
        _mod.main()

    payload = _extract_json(capsys.readouterr().out)
    assert payload["action"] == "auto_fixed"
    assert "file.py" in payload["fixed_files"]


# ── TC3: test_failure ────────────────────────────────────────────
def test_test_failure_exits_two_with_correct_json(monkeypatch, capsys):
    monkeypatch.setattr(_mod, "get_modified_py_files", lambda: ["app.py"])
    monkeypatch.setattr(_mod, "check_lint", lambda files: (True, ""))
    monkeypatch.setattr(
        _mod, "check_tests", lambda: (False, "FAILED test_foo - AssertionError")
    )

    with pytest.raises(SystemExit) as exc_info:
        _mod.main()

    assert exc_info.value.code == 2
    payload = _extract_json(capsys.readouterr().out)
    assert payload["failure_type"] == "test_failure"
    assert "FAILED test_foo" in payload["details"]["output"]


# ── TC4: marker_skip ─────────────────────────────────────────────
def test_marker_skip_exits_zero_and_consumes_marker(monkeypatch):
    _mod.VALIDATED_MARKER.touch()

    with pytest.raises(SystemExit) as exc_info:
        _mod.main()

    assert exc_info.value.code == 0
    assert not _mod.VALIDATED_MARKER.exists(), "마커 파일이 소비(삭제)되지 않았습니다."


# ── TC5: lint_error (auto-fix 실패) ──────────────────────────────
def test_lint_error_when_auto_fix_fails_exits_two(monkeypatch, capsys):
    monkeypatch.setattr(_mod, "get_modified_py_files", lambda: ["bad.py"])
    monkeypatch.setattr(_mod, "check_lint", lambda files: (False, "E999 SyntaxError"))
    monkeypatch.setattr(
        _mod, "auto_fix_lint", lambda files: (False, [], "E999 SyntaxError remains")
    )

    with pytest.raises(SystemExit) as exc_info:
        _mod.main()

    assert exc_info.value.code == 2
    payload = _extract_json(capsys.readouterr().out)
    assert payload["failure_type"] == "lint_error"


# ── TC6: max_retries_exceeded ─────────────────────────────────────
def test_max_retries_exceeded_exits_two(monkeypatch, capsys):
    monkeypatch.setattr(_mod, "get_modified_py_files", lambda: ["app.py"])
    _mod.RETRY_COUNTER.write_text(str(_mod.MAX_RETRIES), encoding="utf-8")

    with pytest.raises(SystemExit) as exc_info:
        _mod.main()

    assert exc_info.value.code == 2
    payload = _extract_json(capsys.readouterr().out)
    assert payload["failure_type"] == "max_retries_exceeded"
    assert not _mod.RETRY_COUNTER.exists(), (
        "max_retries 후 카운터가 리셋되지 않았습니다."
    )
