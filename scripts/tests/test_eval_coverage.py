"""Unit tests for scripts/check_eval_coverage.py (W-018 / S1).

**실제 evals/ 트리를 건드리지 않는다** — 매 테스트가 tmp_path에 최소 가짜 레포를
만들고 `--root`로 그곳을 가리킨다. 게이트용 도구의 테스트가 게이트 자산(진짜
baseline/scenarios)을 오염시키면 안 된다(scripts/tests/test_eval_forge.py와 동일 원칙).
"""

from __future__ import annotations

import importlib.util
import json
import shutil
from pathlib import Path
from types import ModuleType

SCRIPTS_DIR = Path(__file__).resolve().parent.parent
REPO_ROOT = SCRIPTS_DIR.parent


def _load_module() -> ModuleType:
    # scripts/에 __init__.py가 없어 일반 import가 안 되므로 경로 기반 로드로
    # 대상을 가져온다 (scripts/tests/test_eval_forge.py와 동일 관례).
    spec = importlib.util.spec_from_file_location(
        "check_eval_coverage", SCRIPTS_DIR / "check_eval_coverage.py"
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


cec = _load_module()


def _base_policy(**gate_overrides) -> dict:
    gate = {
        "requireBaselineCoversAllScenarios": True,
        "requireScenariosCoverBaseline": True,
        "tier1CoverageEnforceFail": False,
    }
    gate.update(gate_overrides)
    return {
        "baseline": {"file": "baseline.json"},
        "tiers": {"tier1": ["fix-bugs", "review-code"]},
        "coverage": {"tier1MinScenariosPerAgent": 1},
        "gate": gate,
    }


def _make_repo(
    tmp_path: Path,
    scenario_pairs: list[tuple[str, str]],
    baseline_pairs: list[tuple[str, str]] | None,
    policy: dict,
) -> Path:
    root = tmp_path / "repo"
    scenarios_root = root / "evals" / "scenarios"
    for agent, scenario in scenario_pairs:
        (scenarios_root / agent / scenario).mkdir(parents=True)

    # 실물 run.py를 그대로 복사 — discover_scenario_dirs 스킵 규칙까지 실물과 동일해야
    # 검사 경로가 의미 있다 (test_eval_forge.py와 동일 관례).
    (root / "evals").mkdir(parents=True, exist_ok=True)
    shutil.copy2(REPO_ROOT / "evals" / "run.py", root / "evals" / "run.py")

    if baseline_pairs is not None:
        baseline_dir = root / "evals" / "baseline"
        baseline_dir.mkdir(parents=True, exist_ok=True)
        results = [{"agent": a, "scenario": s} for a, s in baseline_pairs]
        (baseline_dir / "baseline.json").write_text(
            json.dumps({"results": results}), encoding="utf-8"
        )

    (root / "evals" / "policy.json").write_text(json.dumps(policy), encoding="utf-8")
    return root


# ── 4개 필수 케이스 (STAGE1_LLM.md 완료조건 2) ─────────────────────────────


def test_extra_scenario_not_in_baseline_fails():
    """시나리오 초과 — baseline에 없는 시나리오 디렉토리가 있으면 exit 1."""
    import tempfile

    with tempfile.TemporaryDirectory() as td:
        root = _make_repo(
            Path(td),
            scenario_pairs=[("fix-bugs", "a"), ("review-code", "b")],
            baseline_pairs=[("fix-bugs", "a")],  # review-code/b 없음
            policy=_base_policy(),
        )
        rc = cec.main(["--root", str(root)])
        assert rc == 1


def test_baseline_entry_without_scenario_dir_fails():
    """기준선 초과 — 기준선에만 있고 시나리오 디렉토리가 사라진 항목이 있으면 exit 1."""
    import tempfile

    with tempfile.TemporaryDirectory() as td:
        root = _make_repo(
            Path(td),
            scenario_pairs=[("fix-bugs", "a")],
            baseline_pairs=[("fix-bugs", "a"), ("review-code", "b")],
            policy=_base_policy(),
        )
        rc = cec.main(["--root", str(root)])
        assert rc == 1


def test_missing_baseline_file_fails_not_skips():
    """baseline.file이 가리키는 파일이 없으면 조용히 skip이 아니라 exit 1."""
    import tempfile

    with tempfile.TemporaryDirectory() as td:
        root = _make_repo(
            Path(td),
            scenario_pairs=[("fix-bugs", "a")],
            baseline_pairs=None,  # baseline.json 자체를 만들지 않음
            policy=_base_policy(),
        )
        rc = cec.main(["--root", str(root)])
        assert rc == 1


def test_matching_sets_pass_green():
    """정상 — 시나리오 집합과 기준선 집합이 완전히 일치하면 exit 0."""
    import tempfile

    with tempfile.TemporaryDirectory() as td:
        root = _make_repo(
            Path(td),
            scenario_pairs=[("fix-bugs", "a"), ("review-code", "b")],
            baseline_pairs=[("fix-bugs", "a"), ("review-code", "b")],
            policy=_base_policy(),
        )
        rc = cec.main(["--root", str(root)])
        assert rc == 0


# ── 추가 케이스 — tier1 경고/승격 스위치, 게이트 플래그 off ─────────────────


def test_tier1_gap_warns_only_when_enforce_fail_false():
    import tempfile

    with tempfile.TemporaryDirectory() as td:
        root = _make_repo(
            Path(td),
            scenario_pairs=[("fix-bugs", "a")],  # review-code(tier1) 시나리오 0건
            baseline_pairs=[("fix-bugs", "a")],
            policy=_base_policy(tier1CoverageEnforceFail=False),
        )
        rc = cec.main(["--root", str(root)])
        assert rc == 0  # 커버리지는 정합, tier1 미달은 경고일 뿐


def test_tier1_gap_fails_when_enforce_fail_true():
    import tempfile

    with tempfile.TemporaryDirectory() as td:
        root = _make_repo(
            Path(td),
            scenario_pairs=[("fix-bugs", "a")],
            baseline_pairs=[("fix-bugs", "a")],
            policy=_base_policy(tier1CoverageEnforceFail=True),
        )
        rc = cec.main(["--root", str(root)])
        assert rc == 1  # S4 승격 시나리오


def test_missing_policy_json_fails():
    import tempfile

    with tempfile.TemporaryDirectory() as td:
        root = Path(td) / "repo"
        (root / "evals").mkdir(parents=True)
        rc = cec.main(["--root", str(root)])
        assert rc == 1


def test_real_repo_baseline_covers_scenarios_direction_holds():
    """실물 레포 대조: 이 스크립트가 진짜 evals/를 읽었을 때도 판정 로직 자체가
    죽지 않고 동작함을 확인 — 실제 값의 pass/fail 여부는 단언하지 않는다.
    (2026-08-27 기준 실물은 21/21·tier1 13/13으로 green이지만, 향후 다시
    드리프트가 생기면 fail이 정상 — 이 테스트는 '크래시 없이 판정 가능'만
    검증하고 어느 쪽 결과도 실패로 취급하지 않는다. W-019 교차 리뷰 Low 지적
    — 특정 시점의 pass/fail 사실을 주석에 박아두면 다음 실패 때 오판을 부른다)."""
    rc = cec.main(["--root", str(REPO_ROOT)])
    assert rc in (0, 1)


# ── policy.json 스키마 방어 (W-018/W-019 교차 리뷰 — sanddab 실측 거짓 green) ──
#
# sanddab이 daggertooth의 evals/policy.json에서 "tiers" 키를 통째로 지우고
# check_eval_coverage.py를 돌려 exit 0("tier1 전 에이전트(0종) 최소 시나리오
# 보유")을 재현했다 — 검사 대상 0개를 "전부 통과"로 오인하는 거짓 green이다.
# 아래는 그 정확한 재현을 회귀 테스트로 고정한 것.


def test_policy_missing_tiers_section_fails():
    """tiers 섹션이 통째로 없으면 vacuous pass가 아니라 exit 1이어야 한다."""
    import tempfile

    with tempfile.TemporaryDirectory() as td:
        policy = _base_policy()
        del policy["tiers"]
        root = _make_repo(
            Path(td),
            scenario_pairs=[("fix-bugs", "a")],
            baseline_pairs=[("fix-bugs", "a")],
            policy=policy,
        )
        rc = cec.main(["--root", str(root)])
        assert rc == 1


def test_policy_empty_tier1_list_fails():
    """tiers.tier1이 빈 배열이면(섹션은 있으나 내용 없음) 여전히 exit 1."""
    import tempfile

    with tempfile.TemporaryDirectory() as td:
        policy = _base_policy()
        policy["tiers"] = {"tier1": []}
        root = _make_repo(
            Path(td),
            scenario_pairs=[("fix-bugs", "a")],
            baseline_pairs=[("fix-bugs", "a")],
            policy=policy,
        )
        rc = cec.main(["--root", str(root)])
        assert rc == 1


def test_policy_missing_gate_section_fails():
    """gate 섹션이 통째로 없으면 조용한 기본값(전부 통과) 대신 exit 1."""
    import tempfile

    with tempfile.TemporaryDirectory() as td:
        policy = _base_policy()
        del policy["gate"]
        root = _make_repo(
            Path(td),
            scenario_pairs=[("fix-bugs", "a")],
            baseline_pairs=[("fix-bugs", "a")],
            policy=policy,
        )
        rc = cec.main(["--root", str(root)])
        assert rc == 1


def test_policy_missing_coverage_section_fails():
    """coverage 섹션이 통째로 없으면 조용한 기본값 대신 exit 1."""
    import tempfile

    with tempfile.TemporaryDirectory() as td:
        policy = _base_policy()
        del policy["coverage"]
        root = _make_repo(
            Path(td),
            scenario_pairs=[("fix-bugs", "a")],
            baseline_pairs=[("fix-bugs", "a")],
            policy=policy,
        )
        rc = cec.main(["--root", str(root)])
        assert rc == 1


def test_policy_top_level_not_dict_fails_cleanly():
    """policy.json이 문법상 유효한 JSON이어도 최상위가 dict가 아니면(예: 배열)
    raw AttributeError 트레이스백 대신 명확한 메시지로 exit 1이어야 한다
    (W-019 교차 리뷰 Medium — SSOT 로더가 이런 경우 원인불명으로 죽던 문제와
    같은 클래스)."""
    import tempfile

    with tempfile.TemporaryDirectory() as td:
        root = Path(td) / "repo"
        (root / "evals").mkdir(parents=True)
        (root / "evals" / "policy.json").write_text("[]", encoding="utf-8")
        rc = cec.main(["--root", str(root)])
        assert rc == 1
