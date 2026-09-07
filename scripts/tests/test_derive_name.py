"""Unit tests for scripts/derive-name.py (D-3 / W-027 27-2).

`scripts/tests/test_build_targets.py` 와 같은 관례를 따른다 — 실제 레포의
`packaging/name-targets.json`이나 `plugins/common`을 건드리지 않고, `--repo-root`/
`--policy`로 전부 임시 픽스처 레포를 가리킨다.
"""

from __future__ import annotations

import json
from pathlib import Path
from types import ModuleType

from module_loader import load_module_by_path

SCRIPTS_DIR = Path(__file__).resolve().parent.parent


def _load_module() -> ModuleType:
    return load_module_by_path(SCRIPTS_DIR / "derive-name.py", "derive_name")


_mod = _load_module()

SSOT = {"name": "fixture-kit", "version": "1.0.0"}


def _fake_repo(tmp_path: Path, *, last_applied: str = "fixture-kit") -> Path:
    root = tmp_path / "repo"
    claude_plugin = root / "plugins" / "common" / ".claude-plugin"
    claude_plugin.mkdir(parents=True)
    (claude_plugin / "plugin.json").write_text(json.dumps(SSOT), encoding="utf-8")

    (root / "README.md").write_text(
        "# fixture-kit\n\ninstall: fixture-kit@fixture-community\n", encoding="utf-8"
    )
    plugins_common = root / "plugins" / "common"
    plugins_common.mkdir(parents=True, exist_ok=True)
    (plugins_common / "README.md").write_text(
        "fixture-kit common readme\n", encoding="utf-8"
    )
    (root / "CLAUDE.md").write_text("# fixture-kit conventions\n", encoding="utf-8")

    content = root / "site" / "content"
    content.mkdir(parents=True)
    (content / "_index.md").write_text("welcome to fixture-kit\n", encoding="utf-8")
    posts = content / "posts"
    posts.mkdir()
    (posts / "post-1.md").write_text("fixture-kit shipped a thing\n", encoding="utf-8")
    # 이름을 언급하지 않는 문서도 있을 수 있다 — check가 이걸로 false-fail하면 안 된다.
    (posts / "post-2.md").write_text("no product name here\n", encoding="utf-8")

    policy = {
        "source": {
            "manifest": "plugins/common/.claude-plugin/plugin.json",
            "field": "name",
        },
        "lastAppliedName": last_applied,
        "files": ["README.md", "plugins/common/README.md", "CLAUDE.md"],
        "directories": ["site/content"],
    }
    policy_path = root / "packaging" / "name-targets.json"
    policy_path.parent.mkdir(parents=True)
    policy_path.write_text(json.dumps(policy), encoding="utf-8")
    return root


def _run(root: Path, *extra: str) -> int:
    argv = [
        "--repo-root",
        str(root),
        "--policy",
        str(root / "packaging" / "name-targets.json"),
        *extra,
    ]
    return _mod.main(argv)


# ── 1. discover_targets — files + directories 실측, 손으로 나열하지 않음 ────────


def test_discover_targets_includes_files_and_recursive_md(tmp_path):
    root = _fake_repo(tmp_path)
    targets = _mod.discover_targets(
        root, json.loads((root / "packaging" / "name-targets.json").read_text())
    )
    rels = sorted(str(t.relative_to(root.resolve())) for t in targets)
    assert rels == [
        "CLAUDE.md",
        "README.md",
        "plugins/common/README.md",
        "site/content/_index.md",
        "site/content/posts/post-1.md",
        "site/content/posts/post-2.md",
    ]


# ── 2. --check clean when lastAppliedName already matches SSOT ─────────────────


def test_check_green_when_name_unchanged(tmp_path, capsys):
    root = _fake_repo(tmp_path)
    rc = _run(root, "--check")
    out = capsys.readouterr().out
    assert rc == 0
    assert "정합" in out


# ── 3. --write is a no-op when SSOT name hasn't moved ───────────────────────────


def test_write_is_noop_when_name_unchanged(tmp_path):
    root = _fake_repo(tmp_path)
    readme = root / "README.md"
    before = readme.read_text(encoding="utf-8")
    rc = _run(root, "--write")
    assert rc == 0
    assert readme.read_text(encoding="utf-8") == before


# ── 4. drift: SSOT renamed, --write not run yet → --check fails ────────────────


def test_check_fails_when_ssot_renamed_and_stale_name_remains(tmp_path, capsys):
    root = _fake_repo(tmp_path, last_applied="old-kit")
    rc = _run(root, "--check")
    out = capsys.readouterr().out
    assert rc == 1
    assert "lastAppliedName" in out or "≠" in out


# ── 5. rename propagation: --write replaces the literal old name everywhere ────


def test_write_propagates_rename_across_all_targets(tmp_path):
    root = _fake_repo(tmp_path, last_applied="old-kit")
    # 파일들은 실제로 옛 이름을 담고 있어야 치환 대상이 된다.
    for rel in ["README.md", "plugins/common/README.md", "CLAUDE.md"]:
        p = root / rel
        p.write_text(
            p.read_text(encoding="utf-8").replace("fixture-kit", "old-kit"),
            encoding="utf-8",
        )
    idx = root / "site" / "content" / "_index.md"
    idx.write_text(
        idx.read_text(encoding="utf-8").replace("fixture-kit", "old-kit"),
        encoding="utf-8",
    )

    rc_write = _mod.main(
        [
            "--repo-root",
            str(root),
            "--policy",
            str(root / "packaging" / "name-targets.json"),
            "--write",
        ]
    )
    assert rc_write == 0
    assert "fixture-kit" in (root / "README.md").read_text(encoding="utf-8")
    assert "old-kit" not in (root / "README.md").read_text(encoding="utf-8")
    assert "fixture-kit" in idx.read_text(encoding="utf-8")

    policy = json.loads((root / "packaging" / "name-targets.json").read_text())
    assert policy["lastAppliedName"] == "fixture-kit"

    rc_check = _mod.main(
        [
            "--repo-root",
            str(root),
            "--policy",
            str(root / "packaging" / "name-targets.json"),
            "--check",
        ]
    )
    assert rc_check == 0


# ── 6. missing target file → --check fails ──────────────────────────────────────


def test_check_fails_when_target_file_missing(tmp_path, capsys):
    root = _fake_repo(tmp_path)
    (root / "CLAUDE.md").unlink()
    rc = _run(root, "--check")
    out = capsys.readouterr().out
    assert rc == 1
    assert "없음" in out


# ── 7. missing SSOT manifest → clean failure, no traceback ─────────────────────


def test_missing_ssot_manifest_clean_failure(tmp_path, capsys):
    root = _fake_repo(tmp_path)
    (root / "plugins" / "common" / ".claude-plugin" / "plugin.json").unlink()
    rc = _run(root, "--check")
    err = capsys.readouterr().err
    assert rc == 1
    assert "SSOT" in err
    assert "Traceback" not in err


# ── 8. path containment — shared adversarial table (D-15) ──────────────────────


def test_resolve_in_repo_shared_adversarial_table(tmp_path):
    from resolve_in_repo_contract import assert_resolve_in_repo_contract

    assert_resolve_in_repo_contract(_mod._resolve_in_repo, tmp_path)


def test_directory_escape_via_policy_is_blocked(tmp_path, capsys):
    root = _fake_repo(tmp_path)
    policy_path = root / "packaging" / "name-targets.json"
    policy = json.loads(policy_path.read_text())
    policy["directories"] = ["../outside"]
    policy_path.write_text(json.dumps(policy), encoding="utf-8")

    outside = root.parent / "outside"
    outside.mkdir()
    (outside / "evil.md").write_text("fixture-kit\n", encoding="utf-8")

    rc = _run(root, "--check")
    err = capsys.readouterr().err
    assert rc == 1
    assert "레포 루트 밖" in err
