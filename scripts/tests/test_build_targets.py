"""Unit tests for scripts/build-targets.py (W-019 / S1).

이 테스트는 **실제 레포의 packaging/targets.json이나 plugins/common을 건드리지 않는다**
— `--repo-root`/`--policy`로 전부 임시 픽스처 레포를 가리킨다 (scripts/tests/test_eval_forge.py의
`_fake_repo` 관례를 따름). "타겟 매니페스트 생성 금지"(S1 금지사항)를 실제 레포 트리
안에서는 절대 어기지 않기 위함이다.
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from types import ModuleType

SCRIPTS_DIR = Path(__file__).resolve().parent.parent


def _load_module() -> ModuleType:
    spec = importlib.util.spec_from_file_location(
        "build_targets", SCRIPTS_DIR / "build-targets.py"
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


_mod = _load_module()

SSOT = {
    "name": "fixture-kit",
    "version": "1.0.0",
    "description": "fixture plugin for build-targets tests",
}

POLICY = {
    "version": "1.0.0",
    "source": {
        "pluginRoot": "plugins/common",
        "manifest": "plugins/common/.claude-plugin/plugin.json",
        "_meta": {"componentDirs": ["skills", "agents", "rules", "hooks"]},
    },
    "targets": [
        {
            "id": "alpha",
            "enabled": True,
            "manifestPath": "plugins/common/.alpha-plugin/plugin.json",
            "requiredFields": ["name", "version"],
            "optionalFields": ["description"],
            "componentFields": {"skills": "./skills/"},
            "interface": {"displayName": "Alpha Target"},
            "marketplace": {"path": ".agents/plugins/marketplace.json"},
        },
        {
            "id": "beta",
            "enabled": False,
            "_disabledReason": "fixture: intentionally disabled",
            "manifestPath": "plugins/common/beta-plugin.json",
            "requiredFields": ["name"],
        },
    ],
}


def _fake_repo(tmp_path: Path, *, with_skills: bool = True) -> Path:
    root = tmp_path / "repo"
    claude_plugin = root / "plugins" / "common" / ".claude-plugin"
    claude_plugin.mkdir(parents=True)
    (claude_plugin / "plugin.json").write_text(json.dumps(SSOT), encoding="utf-8")
    if with_skills:
        (root / "plugins" / "common" / "skills").mkdir(parents=True)
    policy_path = root / "packaging" / "targets.json"
    policy_path.parent.mkdir(parents=True)
    policy_path.write_text(json.dumps(POLICY), encoding="utf-8")
    return root


def _run(root: Path, *extra: str) -> int:
    argv = [
        "--repo-root",
        str(root),
        "--policy",
        str(root / "packaging" / "targets.json"),
        *extra,
    ]
    return _mod.main(argv)


# ── 1. 정상 생성 ─────────────────────────────────────────────────────────────


def test_write_only_creates_expected_manifest(tmp_path):
    root = _fake_repo(tmp_path)
    rc = _run(root, "--write", "--only", "alpha")
    assert rc == 0
    manifest = root / "plugins" / "common" / ".alpha-plugin" / "plugin.json"
    assert manifest.exists()
    data = json.loads(manifest.read_text(encoding="utf-8"))
    assert data["name"] == "fixture-kit"
    assert data["version"] == "1.0.0"
    assert data["description"] == "fixture plugin for build-targets tests"
    assert data["skills"] == "./skills/"
    assert data["interface"] == {"displayName": "Alpha Target"}
    marketplace = root / ".agents" / "plugins" / "marketplace.json"
    assert marketplace.exists()
    mk = json.loads(marketplace.read_text(encoding="utf-8"))
    assert mk["plugins"][0]["name"] == "fixture-kit"


def test_write_omits_component_field_when_dir_absent(tmp_path):
    root = _fake_repo(tmp_path, with_skills=False)
    rc = _run(root, "--write", "--only", "alpha")
    assert rc == 0
    manifest = root / "plugins" / "common" / ".alpha-plugin" / "plugin.json"
    data = json.loads(manifest.read_text(encoding="utf-8"))
    assert "skills" not in data


# ── 2. --check 드리프트 감지 ──────────────────────────────────────────────────


def test_check_detects_drift_then_clean_after_revert(tmp_path, capsys):
    root = _fake_repo(tmp_path)
    assert _run(root, "--write", "--only", "alpha") == 0
    manifest = root / "plugins" / "common" / ".alpha-plugin" / "plugin.json"
    original = manifest.read_text(encoding="utf-8")

    assert _run(root, "--check", "--only", "alpha") == 0

    # 한 글자 훼손
    manifest.write_text(
        original.replace("fixture-kit", "tampered-kit"), encoding="utf-8"
    )
    rc_dirty = _run(root, "--check", "--only", "alpha")
    out_dirty = capsys.readouterr().out
    assert rc_dirty == 1
    assert "드리프트" in out_dirty

    # 원복
    manifest.write_text(original, encoding="utf-8")
    rc_clean = _run(root, "--check", "--only", "alpha")
    assert rc_clean == 0


# ── 3. enabled:false 건너뜀 ───────────────────────────────────────────────────


def test_disabled_target_skipped_by_write_and_default_check(tmp_path, capsys):
    root = _fake_repo(tmp_path)
    rc = _run(root, "--write", "--only", "beta")
    out = capsys.readouterr().out
    assert rc == 0
    assert "건너뜀" in out
    assert not (root / "plugins" / "common" / "beta-plugin.json").exists()

    # 기본 --check(전체 enabled)도 beta를 건드리지 않는다 — 애초에 대상이 아니다.
    rc_check = _run(root, "--check")
    assert rc_check == 0


# ── 4. SSOT 매니페스트 부재 시 명확한 실패 ───────────────────────────────────


def test_missing_ssot_manifest_clean_failure(tmp_path, capsys):
    root = _fake_repo(tmp_path)
    (root / "plugins" / "common" / ".claude-plugin" / "plugin.json").unlink()
    rc = _run(root, "--check")
    err = capsys.readouterr().err
    assert rc == 1
    assert "SSOT" in err
    assert "Traceback" not in err


def test_unknown_only_id_clean_failure(tmp_path, capsys):
    root = _fake_repo(tmp_path)
    rc = _run(root, "--check", "--only", "does-not-exist")
    err = capsys.readouterr().err
    assert rc == 1
    assert "does-not-exist" in err
    assert "Traceback" not in err


# ── 5. --check 는 파일을 쓰지 않는다 ─────────────────────────────────────────


def test_check_never_writes(tmp_path):
    root = _fake_repo(tmp_path)
    manifest = root / "plugins" / "common" / ".alpha-plugin" / "plugin.json"
    before = sorted(p.relative_to(root) for p in root.rglob("*") if p.is_file())
    assert not manifest.exists()

    assert _run(root, "--check", "--only", "alpha") == 0
    assert not manifest.exists()
    after = sorted(p.relative_to(root) for p in root.rglob("*") if p.is_file())
    assert before == after

    # 생성 후에도 --check가 mtime을 건드리지 않는다.
    assert _run(root, "--write", "--only", "alpha") == 0
    mtime_before = manifest.stat().st_mtime_ns
    assert _run(root, "--check", "--only", "alpha") == 0
    assert manifest.stat().st_mtime_ns == mtime_before


# ── 추가: 기본 --write(no --only)는 항상 no-op ────────────────────────────────


def test_bare_write_without_only_is_noop(tmp_path):
    root = _fake_repo(tmp_path)
    rc = _run(root, "--write")
    assert rc == 0
    created = [
        p
        for p in root.rglob("*")
        if p.is_file()
        and "packaging" not in p.parts
        and ".claude-plugin" not in p.parts
    ]
    assert created == []
