"""Unit tests for checklist.py (W-013 — Durable Executor Checklist)."""

import importlib.util
import json
from pathlib import Path
from types import ModuleType


HOOKS_DIR = Path(__file__).resolve().parent.parent


def _load_module() -> ModuleType:
    spec = importlib.util.spec_from_file_location(
        "checklist", HOOKS_DIR / "checklist.py"
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


_mod = _load_module()


def _item(iid, verify="true"):
    return {
        "id": iid,
        "description": f"desc {iid}",
        "acceptance": f"accept {iid}",
        "verify": verify,
    }


# ── init: default-FAIL 계약 ───────────────────────────────────────
def test_init_forces_passes_false(tmp_path):
    payload = json.dumps([{**_item("a"), "passes": True}])  # passes:true 주입 시도
    assert _mod.cmd_init(tmp_path, payload) == 0
    items = json.loads((tmp_path / "checklist.json").read_text())
    assert items[0]["passes"] is False  # 주입 무시, 강제 false


def test_init_rejects_missing_field(tmp_path):
    bad = json.dumps([{"id": "a", "description": "x"}])  # acceptance/verify 누락
    assert _mod.cmd_init(tmp_path, bad) == 2
    assert not (tmp_path / "checklist.json").exists()


def test_init_rejects_duplicate_id(tmp_path):
    dup = json.dumps([_item("a"), _item("a")])
    assert _mod.cmd_init(tmp_path, dup) == 2


def test_init_rejects_empty_or_nonlist(tmp_path):
    assert _mod.cmd_init(tmp_path, "[]") == 2
    assert _mod.cmd_init(tmp_path, '{"id":"a"}') == 2
    assert _mod.cmd_init(tmp_path, "not json") == 2


# ── status: exit code 계약 ────────────────────────────────────────
def test_status_no_checklist_returns_3(tmp_path):
    assert _mod.cmd_status(tmp_path) == 3


def test_status_pending_returns_1(tmp_path):
    _mod.cmd_init(tmp_path, json.dumps([_item("a")]))
    assert _mod.cmd_status(tmp_path) == 1


def test_status_all_pass_returns_0(tmp_path):
    _mod.cmd_init(tmp_path, json.dumps([_item("a", verify="true")]))
    assert _mod.cmd_pass(tmp_path, "a") == 0
    assert _mod.cmd_status(tmp_path) == 0


def test_status_corrupt_file_fails_not_skips(tmp_path):
    # 적대적 리뷰 false-green: 손상 파일이 3(skip)이 아니라 1(FAIL)이어야 게이트 우회 차단
    (tmp_path / "checklist.json").write_text("not json {{{", encoding="utf-8")
    assert _mod.cmd_status(tmp_path) == 1


def test_status_empty_list_file_fails_not_skips(tmp_path):
    # `echo '[]' > checklist.json` 변조 → 존재하는 빈 리스트는 FAIL(1), skip 아님
    (tmp_path / "checklist.json").write_text("[]", encoding="utf-8")
    assert _mod.cmd_status(tmp_path) == 1


# ── pass: verify 실행형 기계 게이트 (self-mark 차단) ─────────────
def test_pass_flips_only_when_verify_exits_zero(tmp_path):
    _mod.cmd_init(tmp_path, json.dumps([_item("ok", verify="true")]))
    assert _mod.cmd_pass(tmp_path, "ok") == 0
    items = json.loads((tmp_path / "checklist.json").read_text())
    assert items[0]["passes"] is True
    assert "verify exit 0" in items[0]["evidence"]


def test_pass_refused_when_verify_fails(tmp_path):
    _mod.cmd_init(tmp_path, json.dumps([_item("no", verify="false")]))
    assert _mod.cmd_pass(tmp_path, "no") == 1
    items = json.loads((tmp_path / "checklist.json").read_text())
    assert items[0]["passes"] is False  # 실패한 verify는 절대 flip 안 함


def test_pass_unknown_id_returns_2(tmp_path):
    _mod.cmd_init(tmp_path, json.dumps([_item("a")]))
    assert _mod.cmd_pass(tmp_path, "zzz") == 2


def test_init_rejects_empty_verify(tmp_path):
    # 빈/공백 verify는 영구 미완이 되므로 init에서 차단(pass 이전에)
    assert _mod.cmd_init(tmp_path, json.dumps([_item("a", verify="   ")])) == 2
    assert not (tmp_path / "checklist.json").exists()


def test_pass_refuses_empty_verify_written_directly(tmp_path):
    # 방어층: init을 우회해 빈 verify가 파일에 들어와도 cmd_pass는 거부
    _mod._write(
        tmp_path / "checklist.json",
        [
            {
                "id": "a",
                "description": "d",
                "acceptance": "x",
                "verify": "",
                "passes": False,
            }
        ],
    )
    assert _mod.cmd_pass(tmp_path, "a") == 2


# ── 원자 쓰기: 손상 없이 상태 보존 ───────────────────────────────
def test_write_read_roundtrip_preserves_order(tmp_path):
    ids = ["c", "a", "b"]
    _mod.cmd_init(tmp_path, json.dumps([_item(i) for i in ids]))
    items = json.loads((tmp_path / "checklist.json").read_text())
    assert [it["id"] for it in items] == ids  # 삽입 순서 보존


def test_pass_persists_across_reads(tmp_path):
    _mod.cmd_init(tmp_path, json.dumps([_item("a", "true"), _item("b", "true")]))
    _mod.cmd_pass(tmp_path, "a")
    # 재읽기 시 a만 pass, b는 pending
    items = json.loads((tmp_path / "checklist.json").read_text())
    by_id = {it["id"]: it["passes"] for it in items}
    assert by_id == {"a": True, "b": False}
