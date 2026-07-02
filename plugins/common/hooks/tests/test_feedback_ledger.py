"""Unit tests for feedback_ledger.py (Spec 3 / W-007)."""

import importlib.util
from pathlib import Path
from types import ModuleType


HOOKS_DIR = Path(__file__).resolve().parent.parent


def _load_module() -> ModuleType:
    spec = importlib.util.spec_from_file_location(
        "feedback_ledger", HOOKS_DIR / "feedback_ledger.py"
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


_mod = _load_module()


# ── upsert: 신규 추가 ─────────────────────────────────────────────
def test_upsert_adds_new_entry(tmp_path):
    result = _mod.upsert("lint", "low", "unused import", root=tmp_path)
    assert result == "added"
    entries = _mod.parse_ledger(_mod.ledger_path(tmp_path))
    assert len(entries) == 1
    assert entries[0]["category"] == "lint"
    assert entries[0]["frequency"] == 1


# ── upsert: 중복 → frequency 증가 (dedupe) ───────────────────────
def test_upsert_increments_on_duplicate(tmp_path):
    _mod.upsert("security", "high", "Hardcoded API key", root=tmp_path)
    # 대소문자/공백 차이는 같은 패턴으로 정규화되어야 함
    result = _mod.upsert("security", "high", "hardcoded   api  key", root=tmp_path)
    assert result == "incremented"
    entries = _mod.parse_ledger(_mod.ledger_path(tmp_path))
    assert len(entries) == 1
    assert entries[0]["frequency"] == 2


# ── decay: 상한 초과 시 하위 제거 ────────────────────────────────
def test_decay_enforces_cap(tmp_path, monkeypatch):
    monkeypatch.setattr(_mod, "CAP", 3)
    for i in range(5):
        _mod.upsert("convention", "low", f"pattern number {i}", root=tmp_path)
    entries = _mod.parse_ledger(_mod.ledger_path(tmp_path))
    assert len(entries) <= 3


# ── decay: 고빈도 엔트리는 상한에서 보존 ─────────────────────────
def test_decay_keeps_high_frequency(tmp_path, monkeypatch):
    monkeypatch.setattr(_mod, "CAP", 2)
    # high-freq 엔트리
    for _ in range(5):
        _mod.upsert("test", "medium", "flaky timing assertion", root=tmp_path)
    # low-freq 엔트리들
    _mod.upsert("lint", "low", "trailing whitespace", root=tmp_path)
    _mod.upsert("lint", "low", "long line", root=tmp_path)
    entries = _mod.parse_ledger(_mod.ledger_path(tmp_path))
    patterns = [e["pattern"] for e in entries]
    assert any("flaky timing" in p for p in patterns), "고빈도 엔트리가 감쇠로 제거됨"


# ── load_digest: 상위 K + 빈도 표시 ──────────────────────────────
def test_load_digest_returns_top_k(tmp_path):
    for _ in range(3):
        _mod.upsert("security", "critical", "SQL injection risk", root=tmp_path)
    _mod.upsert("lint", "low", "unused var", root=tmp_path)
    digest = _mod.load_digest(top_k=5, root=tmp_path)
    assert "SQL injection risk" in digest
    assert "x3" in digest


# ── fail-open: ledger 부재 시 빈 digest ──────────────────────────
def test_load_digest_empty_when_no_ledger(tmp_path):
    assert _mod.load_digest(root=tmp_path) == ""


# ── invalid category → convention으로 폴백 ───────────────────────
def test_invalid_category_falls_back(tmp_path):
    _mod.upsert("nonsense", "low", "weird thing", root=tmp_path)
    entries = _mod.parse_ledger(_mod.ledger_path(tmp_path))
    assert entries[0]["category"] == "convention"


# ── '|' 포함 패턴: 테이블 깨짐 없이 저장·dedupe ──────────────────
def test_pipe_in_pattern_is_sanitized(tmp_path):
    # review 결함에 '|'가 흔함 (예: 'string | null')
    _mod.upsert(
        "architecture", "high", "prefer composition | over inheritance", root=tmp_path
    )
    entries = _mod.parse_ledger(_mod.ledger_path(tmp_path))
    assert len(entries) == 1, "'|'로 행이 깨져 엔트리가 유실됨"
    assert entries[0]["frequency"] == 1
    assert "|" not in entries[0]["pattern"]
    # 재upsert 시 dedupe 되어야 함 (중복 누적 방지)
    result = _mod.upsert(
        "architecture", "high", "prefer composition | over inheritance", root=tmp_path
    )
    assert result == "incremented"
    entries = _mod.parse_ledger(_mod.ledger_path(tmp_path))
    assert len(entries) == 1
    assert entries[0]["frequency"] == 2


# ── 개행 포함 패턴: 단일 행 유지 ─────────────────────────────────
def test_newline_in_pattern_collapsed(tmp_path):
    _mod.upsert("test", "low", "line one\nline two", root=tmp_path)
    entries = _mod.parse_ledger(_mod.ledger_path(tmp_path))
    assert len(entries) == 1
    assert "\n" not in entries[0]["pattern"]


# ── digest 문자 상한 ─────────────────────────────────────────────
def test_digest_char_cap(tmp_path, monkeypatch):
    monkeypatch.setattr(_mod, "DIGEST_CHAR_CAP", 80)
    for i in range(10):
        _mod.upsert(
            "architecture",
            "high",
            f"very long architectural smell pattern {i}",
            root=tmp_path,
        )
    digest = _mod.load_digest(top_k=10, root=tmp_path)
    assert len(digest) <= 82  # cap + " …"


# ── 동시 upsert: lost-update / F-id 충돌 방지 (W-011) ─────────────
def test_concurrent_upserts_preserve_all_entries(tmp_path):
    """auto-dev가 T-review/T-security를 병렬 실행하며 둘 다 upsert하는 시나리오.

    CLI 프로세스 N개를 동시에 띄워 서로 다른 패턴을 upsert — 락이 없으면
    read-modify-write 레이스로 일부 기록이 소실되고 F-id가 중복 채번된다.
    """
    import subprocess as sp
    import sys

    n = 8
    env = {**__import__("os").environ, "CLAUDE_PROJECT_DIR": str(tmp_path)}
    script = str(HOOKS_DIR / "feedback_ledger.py")
    procs = [
        sp.Popen(
            [sys.executable, script, "upsert", "lint", "low", f"concurrent pattern {i}"],
            env=env,
            stdout=sp.DEVNULL,
            stderr=sp.DEVNULL,
        )
        for i in range(n)
    ]
    for p in procs:
        assert p.wait(timeout=30) == 0

    entries = _mod.parse_ledger(_mod.ledger_path(tmp_path))
    patterns = {e["pattern"] for e in entries}
    ids = [e["id"] for e in entries]
    assert len(entries) == n, f"동시 upsert 중 기록 소실: {n}개 중 {len(entries)}개만 보존"
    assert patterns == {f"concurrent pattern {i}" for i in range(n)}
    assert len(ids) == len(set(ids)), f"F-id 중복 채번: {sorted(ids)}"


def test_write_ledger_leaves_no_tmp_files(tmp_path):
    """원자 교체 후 tmp 파일이 잔존하지 않는다."""
    _mod.upsert("lint", "low", "atomic write check", root=tmp_path)
    leftovers = list(_mod.ledger_path(tmp_path).parent.glob("*.tmp.*"))
    assert leftovers == []
