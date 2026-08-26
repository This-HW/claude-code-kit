#!/usr/bin/env python3
"""Eval 커버리지·기준선 드리프트 가드 (W-018 / S1).

시나리오 디렉토리 집합과 baseline의 (agent, scenario) 집합을 양방향 대조하고,
티어1 에이전트의 최소 시나리오 보유 여부를 검사한다.

`scripts/verify-done.sh` 신설 §와 `.github/workflows/validate.yml`이 **둘 다 이
스크립트를 호출**한다. 로직을 bash/CI에 각각 두면 반드시 드리프트한다(F-023,
`check_doc_counts.py`와 동일 관례) — 정의와 검사 전부를 여기 한 곳에만 둔다.

정책(대상 티어·임계값·기준선 포인터)의 단일 소스는 `evals/policy.json`이다.
숫자·목록을 이 스크립트에 하드코딩하지 않는다.

시나리오 발견 로직(디렉토리 스킵 규칙 포함)은 `evals/run.py::discover_scenario_dirs`를
그대로 재사용한다 — 여기서 별도로 재구현하면 스킵 목록이 갈라질 수 있다.

exit 0 = 커버리지 정합 (tier1 경고는 있을 수 있음, policy로 fail 승격 전까지)
exit 1 = 시나리오⊄기준선 / 기준선⊄시나리오 / baseline.file 부재·파싱 실패 /
         policy.json 부재·파싱 실패 / (승격 시) tier1 미달
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from pathlib import Path
from types import ModuleType

OK = "\033[32m✓\033[0m"
NG = "\033[31m✗\033[0m"
WARN = "\033[33m!\033[0m"


class PolicyError(Exception):
    """policy.json 스키마 위반 — main이 exit 1과 명확한 메시지로 변환한다.

    scripts/build-targets.py의 PolicyError 관례를 그대로 따른다. 이 레포에서
    SSOT/정책 로더마다 서로 다른 예외 관례를 쓰는 것 자체가 부채라는 W-019
    교차 리뷰(Medium) 지적을 반영했다.
    """


def validate_policy_schema(policy: object) -> dict:
    """필수 섹션이 통째로 없거나 형태가 틀리면 명확히 실패한다.

    "검사할 대상이 0개"를 "통과"로 오인하는 게 이 검사의 존재 이유를 무력화하는
    거짓 green이다 — sanddab의 W-019 교차 리뷰가 실측으로 잡았다: evals/policy.json
    에서 'tiers' 키를 지우면 check_eval_coverage.py가 "tier1 전 에이전트(0종) 최소
    시나리오 보유"로 exit 0을 냈다. D1(gate.tier1CoverageEnforceFail 승격)이 막으려던
    것과 정확히 같은 클래스의 결함이 검사 대상 선정 단계에서 재발한 것이다.

    구분 원칙: **섹션 자체(tiers/gate/coverage)가 통째로 없으면** 정책 파일이
    손상됐거나 잘못 편집된 것이므로 즉시 실패한다. 반면 섹션은 있는데 그 **안의
    개별 키**(예: gate.tier1CoverageEnforceFail)가 없는 것은 단계적 롤아웃 중
    정상 상태일 수 있어(예: S1~S3에서 이 플래그가 존재하지 않다가 S4에서 추가됐다)
    안전한 기본값(False = 아직 미승격)을 유지한다 — 이 함수는 그 개별 키까지
    강제하지 않는다.
    """
    if not isinstance(policy, dict):
        raise PolicyError(
            f"policy.json 최상위가 object가 아니다 (실제 타입: {type(policy).__name__})"
        )
    tiers = policy.get("tiers")
    if not isinstance(tiers, dict):
        raise PolicyError("policy.json: 'tiers' 섹션이 없거나 object가 아니다")
    tier1 = tiers.get("tier1")
    if not isinstance(tier1, list) or not tier1:
        raise PolicyError(
            "policy.json: 'tiers.tier1'이 없거나 빈 배열이다 — "
            "검사 대상 0개를 전부 통과로 오인하는 거짓 green을 막기 위해 거부한다"
        )
    if not all(isinstance(a, str) and a for a in tier1):
        raise PolicyError(
            "policy.json: 'tiers.tier1'의 각 원소는 비어있지 않은 문자열이어야 한다"
        )
    if not isinstance(policy.get("gate"), dict):
        raise PolicyError("policy.json: 'gate' 섹션이 없거나 object가 아니다")
    if not isinstance(policy.get("coverage"), dict):
        raise PolicyError("policy.json: 'coverage' 섹션이 없거나 object가 아니다")
    return policy


def _load_run_module(root: Path) -> ModuleType:
    """`evals/run.py`를 경로 기반으로 로드한다(패키지 임포트에 기대지 않음 —
    `--root`로 가짜 레포를 가리킬 때도 그 레포의 run.py를 쓰게 하기 위함,
    scripts/tests/test_eval_forge.py와 동일 관례)."""
    run_py = root / "evals" / "run.py"
    spec = importlib.util.spec_from_file_location("_ckkit_eval_run", run_py)
    if spec is None or spec.loader is None:
        raise ImportError(f"evals/run.py 로드 실패: {run_py}")
    mod = importlib.util.module_from_spec(spec)
    # exec 전에 sys.modules 등록 필요 — run.py의 @dataclass가 클래스 소속 모듈을
    # sys.modules에서 찾는데, 미등록 상태면 3.10+에서 AttributeError로 죽는다.
    sys.modules[spec.name] = mod
    try:
        spec.loader.exec_module(mod)
    finally:
        sys.modules.pop(spec.name, None)
    return mod


def load_policy(root: Path) -> dict:
    return json.loads((root / "evals" / "policy.json").read_text(encoding="utf-8"))


def current_scenarios(root: Path) -> set[tuple[str, str]]:
    run_mod = _load_run_module(root)
    dirs = run_mod.discover_scenario_dirs(root / "evals" / "scenarios")
    return {(d.parent.name, d.name) for d in dirs}


def baseline_scenarios(
    root: Path, policy: dict
) -> tuple[set[tuple[str, str]], list[str]]:
    """baseline.file이 가리키는 파일을 읽어 (agent,scenario) 집합을 돌려준다.
    실패 시 빈 집합 + 에러 메시지 목록 — **조용한 skip 금지**(fail-closed)."""
    errors: list[str] = []
    fname = policy.get("baseline", {}).get("file")
    if not fname:
        errors.append("evals/policy.json: baseline.file 없음")
        return set(), errors
    p = root / "evals" / "baseline" / fname
    if not p.is_file():
        errors.append(f"baseline 파일 없음 — evals/baseline/{fname}")
        return set(), errors
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        errors.append(f"baseline 파일 파싱 실패 — evals/baseline/{fname} ({e})")
        return set(), errors
    results = data.get("results")
    if not isinstance(results, list):
        errors.append(f"baseline 파일 스키마 오류 — 'results' 배열 없음: {p}")
        return set(), errors
    pairs = set()
    for i, r in enumerate(results):
        if not isinstance(r, dict) or "agent" not in r or "scenario" not in r:
            errors.append(f"baseline results[{i}] — agent/scenario 없음: {p}")
            continue
        pairs.add((r["agent"], r["scenario"]))
    return pairs, errors


def check_coverage(root: Path, policy: dict) -> tuple[bool, list[str]]:
    lines: list[str] = []
    baseline_set, errs = baseline_scenarios(root, policy)
    if errs:
        return False, [f"{NG} {e}" for e in errs]

    scenario_set = current_scenarios(root)
    gate = policy.get("gate", {})
    ok = True

    if gate.get("requireBaselineCoversAllScenarios", True):
        extra = scenario_set - baseline_set
        if extra:
            ok = False
            lines.append(
                f"{NG} 기준선에 없는 시나리오(⊄ baseline, 회귀 판정 불가): "
                f"{sorted(f'{a}/{s}' for a, s in extra)}"
            )
        else:
            lines.append(f"{OK} 모든 시나리오 디렉토리가 기준선에 존재")

    if gate.get("requireScenariosCoverBaseline", True):
        missing = baseline_set - scenario_set
        if missing:
            ok = False
            lines.append(
                f"{NG} 기준선에만 있고 시나리오 디렉토리가 사라짐: "
                f"{sorted(f'{a}/{s}' for a, s in missing)}"
            )
        else:
            lines.append(f"{OK} 기준선의 모든 항목이 시나리오 디렉토리로 존재")

    return ok, lines


def check_tier1(root: Path, policy: dict) -> tuple[bool, list[str]]:
    """티어1 각 에이전트가 최소 시나리오를 보유하는지 검사.

    S1에서는 `gate.tier1CoverageEnforceFail`이 false면 미달을 경고로만 출력하고
    전체 판정에는 반영하지 않는다(9종이 아직 비어 있어 영구 red가 되는 것을 피함).
    S4에서 이 플래그를 true로 올리면 동일 코드가 fail로 승격된다(policy 플래그 —
    코드 변경 불필요, decision-log D1).
    """
    lines: list[str] = []
    tier1 = policy.get("tiers", {}).get("tier1", [])
    min_n = policy.get("coverage", {}).get("tier1MinScenariosPerAgent", 1)
    enforce_fail = policy.get("gate", {}).get("tier1CoverageEnforceFail", False)

    counts: dict[str, int] = {}
    for agent, _scenario in current_scenarios(root):
        counts[agent] = counts.get(agent, 0) + 1

    missing = [a for a in tier1 if counts.get(a, 0) < min_n]
    if not missing:
        lines.append(f"{OK} tier1 전 에이전트({len(tier1)}종) 최소 시나리오 보유")
        return True, lines

    if enforce_fail:
        lines.append(
            f"{NG} tier1 커버리지 미달 ({len(missing)}/{len(tier1)}): {missing}"
        )
        return False, lines
    lines.append(
        f"{WARN} tier1 커버리지 미달, 경고만(S4에서 fail 승격 예정) "
        f"({len(missing)}/{len(tier1)}): {missing}"
    )
    return True, lines


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--root", type=Path, default=Path("."), help="repo root (테스트용)")
    args = ap.parse_args(argv)
    root = args.root.resolve()

    policy_path = root / "evals" / "policy.json"
    if not policy_path.is_file():
        print(f"{NG} evals/policy.json 없음")
        return 1
    try:
        policy = load_policy(root)
    except json.JSONDecodeError as e:
        print(f"{NG} evals/policy.json 파싱 실패: {e}")
        return 1

    try:
        validate_policy_schema(policy)
    except PolicyError as e:
        print(f"{NG} {e}")
        return 1

    ok = True
    cov_ok, cov_lines = check_coverage(root, policy)
    ok &= cov_ok
    for line in cov_lines:
        print(line)

    tier_ok, tier_lines = check_tier1(root, policy)
    ok &= tier_ok
    for line in tier_lines:
        print(line)

    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
