"""Unit tests for scripts/audit-version-strings.py (W-022 / Track B S1).

`scripts/tests/test_bump_version.py`가 이 도구를 `bump-version.sh`를 통해
간접적으로도 검증하지만(완료 조건 2: 감사가 실제로 낡은 문자열을 찾아냄), 여기서는
모듈을 직접 import해 경계 조건(v 접두사, exclude, 잘못된 패턴)을 격리 검증한다.
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from types import ModuleType

SCRIPTS_DIR = Path(__file__).resolve().parent.parent


def _load_module() -> ModuleType:
    spec = importlib.util.spec_from_file_location(
        "audit_version_strings", SCRIPTS_DIR / "audit-version-strings.py"
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


_mod = _load_module()

POLICY = {
    "pattern": r"\bv?(2\.\d+\.\d+)\b",
    "excludeDirs": [".git", "cache_dir"],
    "excludePathPrefixes": ["CHANGELOG.md", "docs/specs/"],
}


def _write_policy(tmp_path: Path, policy: dict) -> Path:
    p = tmp_path / "version-audit.json"
    p.write_text(json.dumps(policy), encoding="utf-8")
    return p


def test_finds_stale_version_not_matching_current(tmp_path):
    (tmp_path / "README.md").write_text("released as 2.14.2\n", encoding="utf-8")
    hits = _mod.find_stale(tmp_path, POLICY, "2.16.0")
    assert len(hits) == 1
    rel, lineno, line = hits[0]
    assert rel == "README.md"
    assert lineno == 1
    assert "2.14.2" in line


def test_current_version_is_not_reported_even_with_v_prefix(tmp_path):
    (tmp_path / "NOTES.md").write_text(
        "See v2.16.0 release and also 2.16.0 plain.\n", encoding="utf-8"
    )
    hits = _mod.find_stale(tmp_path, POLICY, "2.16.0")
    assert hits == []  # 둘 다 현재 버전 — v 접두사 여부와 무관하게 flagged 안 됨


def test_v_prefixed_stale_version_is_still_caught(tmp_path):
    (tmp_path / "NOTES.md").write_text("as of v2.14.2 this worked\n", encoding="utf-8")
    hits = _mod.find_stale(tmp_path, POLICY, "2.16.0")
    assert len(hits) == 1
    assert "2.14.2" in hits[0][2]


def test_excluded_path_prefix_is_skipped(tmp_path):
    (tmp_path / "CHANGELOG.md").write_text("## [2.10.0]\n", encoding="utf-8")
    hits = _mod.find_stale(tmp_path, POLICY, "2.16.0")
    assert hits == []


def test_excluded_dir_is_not_descended_into(tmp_path):
    d = tmp_path / "cache_dir"
    d.mkdir()
    (d / "stale.txt").write_text("2.9.0\n", encoding="utf-8")
    hits = _mod.find_stale(tmp_path, POLICY, "2.16.0")
    assert hits == []


def test_main_rejects_pattern_without_exactly_one_capture_group(tmp_path, capsys):
    policy_path = _write_policy(
        tmp_path, {**POLICY, "pattern": r"2\.\d+\.\d+"}
    )  # 0 groups
    rc = _mod.main(
        [
            "--repo-root",
            str(tmp_path),
            "--policy",
            str(policy_path),
            "--current",
            "2.16.0",
        ]
    )
    err = capsys.readouterr().err
    assert rc == 1
    assert "캡처 그룹" in err


def test_main_clean_repo_reports_zero_and_exits_zero(tmp_path, capsys):
    (tmp_path / "README.md").write_text("no versions here\n", encoding="utf-8")
    policy_path = _write_policy(tmp_path, POLICY)
    rc = _mod.main(
        [
            "--repo-root",
            str(tmp_path),
            "--policy",
            str(policy_path),
            "--current",
            "2.16.0",
        ]
    )
    out = capsys.readouterr().out
    assert rc == 0
    assert "낡은 버전 문자열 없음" in out
