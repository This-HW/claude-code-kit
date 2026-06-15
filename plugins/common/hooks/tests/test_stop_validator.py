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


# ── TC2a: lint_auto_fixed (stderr 정보 메시지 + exit 0) ───────────
def test_lint_auto_fixed_reports_on_stderr_and_exits_zero(monkeypatch, capsys):
    monkeypatch.setattr(_mod, "get_modified_py_files", lambda: ["file.py"])
    monkeypatch.setattr(_mod, "check_lint", lambda files: (False, "E501 line too long"))
    monkeypatch.setattr(_mod, "auto_fix_lint", lambda files: (True, ["file.py"], ""))
    monkeypatch.setattr(_mod, "check_tests", lambda: (True, ""))

    with pytest.raises(SystemExit) as exc_info:
        _mod.main()

    assert exc_info.value.code == 0
    # 정보성 메시지는 stderr로 — stdout은 decision 프로토콜 전용.
    assert "자동 수정" in capsys.readouterr().err


# ── TC2b: lint_auto_fixed (수정 파일이 stderr에 보고) ────────────
def test_lint_auto_fixed_lists_files_on_stderr(monkeypatch, capsys):
    monkeypatch.setattr(_mod, "get_modified_py_files", lambda: ["file.py"])
    monkeypatch.setattr(_mod, "check_lint", lambda files: (False, "E501 error"))
    monkeypatch.setattr(_mod, "auto_fix_lint", lambda files: (True, ["file.py"], ""))
    monkeypatch.setattr(_mod, "check_tests", lambda: (True, ""))

    with pytest.raises(SystemExit):
        _mod.main()

    assert "file.py" in capsys.readouterr().err


# ── TC3: test_failure (decision:block + exit 0) ──────────────────
def test_test_failure_emits_block_decision(monkeypatch, capsys):
    monkeypatch.setattr(_mod, "get_modified_py_files", lambda: ["app.py"])
    monkeypatch.setattr(_mod, "check_lint", lambda files: (True, ""))
    monkeypatch.setattr(
        _mod, "check_tests", lambda: (False, "FAILED test_foo - AssertionError")
    )

    with pytest.raises(SystemExit) as exc_info:
        _mod.main()

    # 네이티브 스키마: decision 필드가 차단 제어, exit 0.
    assert exc_info.value.code == 0
    payload = _extract_json(capsys.readouterr().out)
    assert payload["decision"] == "block"
    assert "test_failure" in payload["reason"]
    assert "FAILED test_foo" in payload["reason"]


# ── TC4: marker_skip ─────────────────────────────────────────────
def test_marker_skip_exits_zero_and_consumes_marker(monkeypatch):
    _mod.VALIDATED_MARKER.touch()

    with pytest.raises(SystemExit) as exc_info:
        _mod.main()

    assert exc_info.value.code == 0
    assert not _mod.VALIDATED_MARKER.exists(), "마커 파일이 소비(삭제)되지 않았습니다."


# ── TC5: lint_error (auto-fix 실패 → decision:block) ─────────────
def test_lint_error_when_auto_fix_fails_emits_block(monkeypatch, capsys):
    monkeypatch.setattr(_mod, "get_modified_py_files", lambda: ["bad.py"])
    monkeypatch.setattr(_mod, "check_lint", lambda files: (False, "E999 SyntaxError"))
    monkeypatch.setattr(
        _mod, "auto_fix_lint", lambda files: (False, [], "E999 SyntaxError remains")
    )

    with pytest.raises(SystemExit) as exc_info:
        _mod.main()

    assert exc_info.value.code == 0
    payload = _extract_json(capsys.readouterr().out)
    assert payload["decision"] == "block"
    assert "lint_error" in payload["reason"]


# ── TC6: max_retries 도달 → block이 아니라 allow (무한 루프 방지) ──
def test_max_retries_exceeded_allows_not_blocks(monkeypatch, capsys):
    """cap 도달 시 block()하면 test_failure↔max_retries 무한 루프가 된다.
    cap = '검증 중단·턴 종료'이므로 allow(exit 0, decision JSON 없음)여야 한다.
    """
    monkeypatch.setattr(_mod, "get_modified_py_files", lambda: ["app.py"])
    _mod.RETRY_COUNTER.write_text(str(_mod.MAX_RETRIES), encoding="utf-8")

    with pytest.raises(SystemExit) as exc_info:
        _mod.main()

    assert exc_info.value.code == 0
    out = capsys.readouterr().out
    assert '"decision"' not in out, "cap에서 차단(block) JSON을 내면 안 된다."
    assert not _mod.RETRY_COUNTER.exists(), (
        "max_retries 후 카운터가 리셋되지 않았습니다."
    )


# ── TC7: stop_hook_active=true → 즉시 통과 (네이티브 무한 루프 가드) ──
def test_stop_hook_active_short_circuits(monkeypatch, capsys):
    monkeypatch.setattr(_mod, "_read_input", lambda: {"stop_hook_active": True})
    # 변경 파일/카운터가 차단 조건이어도 stop_hook_active가 우선해 통과해야 한다.
    monkeypatch.setattr(_mod, "get_modified_py_files", lambda: ["app.py"])
    _mod.RETRY_COUNTER.write_text("1", encoding="utf-8")

    with pytest.raises(SystemExit) as exc_info:
        _mod.main()

    assert exc_info.value.code == 0
    assert '"decision"' not in capsys.readouterr().out


# ── TC8: _read_input — TTY hang 가드 + JSON 파싱 ──────────────────
def test_read_input_returns_empty_on_tty(monkeypatch):
    """수동 실행(TTY)에서 stdin.read()로 멈추지 않고 빈 dict 반환."""

    class _FakeStdin:
        def isatty(self):
            return True

        def read(self):  # 호출되면 안 됨 (호출 시 hang을 의미)
            raise AssertionError("TTY에서 read()를 호출하면 안 된다")

    monkeypatch.setattr("sys.stdin", _FakeStdin())
    assert _mod._read_input() == {}


def test_read_input_parses_json(monkeypatch):
    import io

    monkeypatch.setattr("sys.stdin", io.StringIO('{"stop_hook_active": true}'))
    assert _mod._read_input() == {"stop_hook_active": True}
