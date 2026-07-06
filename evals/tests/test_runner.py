"""
evals/run.py 단위 테스트 — claude CLI 호출은 전부 mock/서브프로세스 스텁.

커버리지:
  - frontmatter/본문 파싱
  - expect.json 스키마 검증(--validate 로직)
  - 각 assertion 타입 채점기
  - exit code 규율 (claude 부재 → SKIPPED=2)
  - baseline 비교(후퇴 검출)
  - dry-run이 실제 subprocess를 호출하지 않음
"""

import json
import sys
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import run as runner  # noqa: E402


# ---------------------------------------------------------------------------
# parse_frontmatter
# ---------------------------------------------------------------------------


def test_parse_frontmatter_scalar_and_list():
    content = (
        "---\n"
        "name: fix-bugs\n"
        "model: sonnet\n"
        "tools:\n"
        "  - Read\n"
        "  - Edit\n"
        "  - Bash\n"
        "---\n"
        "# 역할: 버그 수정 전문가\n"
        "본문 내용\n"
    )
    fm, body = runner.parse_frontmatter(content)
    assert fm["name"] == "fix-bugs"
    assert fm["model"] == "sonnet"
    assert fm["tools"] == ["Read", "Edit", "Bash"]
    assert "본문 내용" in body
    assert "---" not in body.split("\n")[0]


def test_parse_frontmatter_block_scalar_description():
    content = (
        "---\n"
        "name: review-code\n"
        "description: |\n"
        "  적대적 코드 리뷰어.\n"
        "  MUST USE when: 리뷰 요청.\n"
        "model: opus\n"
        "---\n"
        "본문\n"
    )
    fm, body = runner.parse_frontmatter(content)
    assert fm["name"] == "review-code"
    assert "적대적 코드 리뷰어" in fm["description"]
    assert fm["model"] == "opus"
    assert body.strip() == "본문"


def test_parse_frontmatter_no_frontmatter_returns_empty():
    fm, body = runner.parse_frontmatter("그냥 본문입니다")
    assert fm == {}
    assert body == "그냥 본문입니다"


def test_parse_frontmatter_unterminated_returns_empty():
    fm, body = runner.parse_frontmatter("---\nname: x\n(닫는 --- 없음)")
    assert fm == {}


# ---------------------------------------------------------------------------
# load_agent (실제 레포 에이전트 정의 파싱)
# ---------------------------------------------------------------------------


def test_load_agent_review_code_resolves_model_and_tools():
    agent = runner.load_agent("review-code")
    assert agent.name == "review-code"
    assert agent.model == "opus"
    assert "Read" in agent.tools
    assert agent.system_prompt  # 본문이 비어있지 않음


def test_load_agent_unknown_raises():
    import pytest as _pytest

    with _pytest.raises(FileNotFoundError):
        runner.load_agent("no-such-agent-xyz")


# ---------------------------------------------------------------------------
# expect.json 스키마 검증
# ---------------------------------------------------------------------------


def test_validate_expect_schema_valid():
    expect = {"assertions": [{"type": "delegation_signal"}]}
    assert runner.validate_expect_schema(expect, "p") == []


def test_validate_expect_schema_missing_assertions():
    errors = runner.validate_expect_schema({}, "p")
    assert any("assertions" in e for e in errors)


def test_validate_expect_schema_unknown_type():
    expect = {"assertions": [{"type": "made_up_type"}]}
    errors = runner.validate_expect_schema(expect, "p")
    assert any("알 수 없는 type" in e for e in errors)


def test_validate_expect_schema_missing_required_field():
    expect = {"assertions": [{"type": "output_regex"}]}
    errors = runner.validate_expect_schema(expect, "p")
    assert any("pattern" in e for e in errors)


def test_validate_expect_schema_judge_enabled_without_rubric():
    expect = {"assertions": [{"type": "delegation_signal"}], "judge": {"enabled": True}}
    errors = runner.validate_expect_schema(expect, "p")
    assert any("rubric" in e for e in errors)


def test_validate_all_scenarios_root_missing(tmp_path):
    errors = runner.validate_all(scenarios_root=tmp_path / "does-not-exist")
    assert errors  # fail-closed: 부재는 항상 오류


def test_validate_scenario_unknown_agent(tmp_path):
    sc_dir = tmp_path / "no-such-agent" / "scenario-1"
    (sc_dir / "fixture").mkdir(parents=True)
    (sc_dir / "task.md").write_text("task")
    (sc_dir / "expect.json").write_text(
        json.dumps({"assertions": [{"type": "delegation_signal"}]})
    )
    errors = runner.validate_scenario(
        sc_dir, agents_root=tmp_path / "empty-agents-root"
    )
    assert any("알 수 없는 agent" in e for e in errors)


def test_validate_scenario_missing_files(tmp_path):
    sc_dir = tmp_path / "fix-bugs" / "broken"
    sc_dir.mkdir(parents=True)
    errors = runner.validate_scenario(sc_dir, agents_root=runner.AGENTS_ROOT)
    joined = "\n".join(errors)
    assert "task.md" in joined
    assert "fixture/" in joined
    assert "expect.json" in joined


def test_validate_all_on_repo_scenarios_is_clean():
    # 저장소에 커밋된 11개 시나리오 자체가 스키마를 통과해야 한다.
    errors = runner.validate_all()
    assert errors == []


# ---------------------------------------------------------------------------
# assertion 채점기
# ---------------------------------------------------------------------------


def test_check_assertion_output_regex_match():
    ok, _ = runner.check_assertion(
        {"type": "output_regex", "pattern": r"off-by-one"},
        "found an off-by-one bug",
        Path("."),
    )
    assert ok is True


def test_check_assertion_output_regex_no_match():
    ok, detail = runner.check_assertion(
        {"type": "output_regex", "pattern": r"nope"}, "all good", Path(".")
    )
    assert ok is False
    assert "매치 없음" in detail


def test_check_assertion_output_contains_any_case_insensitive():
    ok, _ = runner.check_assertion(
        {"type": "output_contains_any", "values": ["SQL Injection", "other"]},
        "there is a sql injection risk",
        Path("."),
    )
    assert ok is True


def test_check_assertion_output_not_contains_fails_when_present():
    ok, detail = runner.check_assertion(
        {"type": "output_not_contains", "values": ["secret"]},
        "the secret is here",
        Path("."),
    )
    assert ok is False
    assert "발견됨" in detail


def test_check_assertion_delegation_signal_present():
    stdout = (
        "결과 요약\n---DELEGATION_SIGNAL---\nTYPE: TASK_COMPLETE\n---END_SIGNAL---\n"
    )
    ok, _ = runner.check_assertion({"type": "delegation_signal"}, stdout, Path("."))
    assert ok is True


def test_check_assertion_delegation_signal_missing():
    ok, detail = runner.check_assertion(
        {"type": "delegation_signal"}, "그냥 완료했습니다", Path(".")
    )
    assert ok is False
    assert "마커" in detail


def test_check_assertion_file_contains(tmp_path):
    (tmp_path / "out.py").write_text("def foo():\n    return 42\n")
    ok, _ = runner.check_assertion(
        {"type": "file_contains", "file": "out.py", "pattern": r"return 42"},
        "",
        tmp_path,
    )
    assert ok is True


def test_check_assertion_file_contains_missing_file(tmp_path):
    ok, detail = runner.check_assertion(
        {"type": "file_contains", "file": "nope.py", "pattern": "x"}, "", tmp_path
    )
    assert ok is False
    assert "파일 없음" in detail


def test_check_assertion_pytest_green_pass(tmp_path):
    (tmp_path / "test_ok.py").write_text("def test_trivial():\n    assert 1 == 1\n")
    ok, _ = runner.check_assertion({"type": "pytest_green", "path": "."}, "", tmp_path)
    assert ok is True


def test_check_assertion_pytest_green_fail(tmp_path):
    (tmp_path / "test_bad.py").write_text("def test_trivial():\n    assert 1 == 2\n")
    ok, detail = runner.check_assertion(
        {"type": "pytest_green", "path": "."}, "", tmp_path
    )
    assert ok is False
    assert "exit" in detail


def test_check_assertion_unknown_type():
    ok, detail = runner.check_assertion({"type": "bogus"}, "", Path("."))
    assert ok is False
    assert "알 수 없는" in detail


# ---------------------------------------------------------------------------
# exit code 규율 — claude CLI 부재 → SKIPPED(2), 절대 0 위장 금지
# ---------------------------------------------------------------------------


def test_run_all_skipped_when_claude_missing(tmp_path):
    scenarios_root = tmp_path / "scenarios"
    sc_dir = scenarios_root / "fix-bugs" / "s1"
    (sc_dir / "fixture").mkdir(parents=True)
    (sc_dir / "task.md").write_text("do it")
    (sc_dir / "expect.json").write_text(
        json.dumps({"assertions": [{"type": "delegation_signal"}]})
    )

    with (
        patch.object(runner, "SCENARIOS_ROOT", scenarios_root),
        patch("shutil.which", return_value=None),
    ):
        report, exit_code = runner.run_all(None, None, 1, 5, dry_run=False)
    assert exit_code == runner.EXIT_SKIPPED
    assert report["results"] == []


def test_run_all_no_scenarios_matched_is_fail(tmp_path):
    report, exit_code = runner.run_all(
        "no-such-agent",
        None,
        1,
        5,
        dry_run=False,
    )
    assert exit_code == runner.EXIT_FAIL


def test_dry_run_does_not_invoke_subprocess(tmp_path):
    scenarios_root = tmp_path / "scenarios"
    sc_dir = scenarios_root / "fix-bugs" / "s1"
    (sc_dir / "fixture").mkdir(parents=True)
    (sc_dir / "task.md").write_text("do it")
    (sc_dir / "expect.json").write_text(
        json.dumps({"assertions": [{"type": "delegation_signal"}]})
    )

    with (
        patch.object(runner, "SCENARIOS_ROOT", scenarios_root),
        patch("subprocess.run") as mock_run,
    ):
        report, exit_code = runner.run_all(None, None, 1, 5, dry_run=True)
    mock_run.assert_not_called()
    assert exit_code == runner.EXIT_PASS
    assert report["results"] == []


# ---------------------------------------------------------------------------
# baseline 비교(후퇴 검출)
# ---------------------------------------------------------------------------


def test_compare_baseline_detects_regression(tmp_path):
    baseline_path = tmp_path / "baseline.json"
    baseline_path.write_text(json.dumps({"summary": {"fix-bugs": {"pass_rate": 1.0}}}))
    current = {"fix-bugs": {"pass_rate": 0.5}}
    regressions = runner.compare_baseline(current, str(baseline_path))
    assert regressions
    assert "fix-bugs" in regressions[0]


def test_compare_baseline_no_regression_when_improved(tmp_path):
    baseline_path = tmp_path / "baseline.json"
    baseline_path.write_text(json.dumps({"summary": {"fix-bugs": {"pass_rate": 0.5}}}))
    current = {"fix-bugs": {"pass_rate": 1.0}}
    regressions = runner.compare_baseline(current, str(baseline_path))
    assert regressions == []


def test_summarize_pass_rate():
    results = [
        {"agent": "fix-bugs", "status": "pass"},
        {"agent": "fix-bugs", "status": "fail"},
        {"agent": "review-code", "status": "pass"},
    ]
    summary = runner.summarize(results)
    assert summary["fix-bugs"]["pass_rate"] == 0.5
    assert summary["review-code"]["pass_rate"] == 1.0


# ---------------------------------------------------------------------------
# CLI main() — validate 모드
# ---------------------------------------------------------------------------


def test_main_validate_exit_zero_on_repo_scenarios():
    assert runner.main(["--validate"]) == runner.EXIT_PASS


def test_main_validate_exit_one_on_bad_scenarios(tmp_path):
    scenarios_root = tmp_path / "scenarios"
    sc_dir = scenarios_root / "fix-bugs" / "broken"
    sc_dir.mkdir(parents=True)
    with patch.object(runner, "SCENARIOS_ROOT", scenarios_root):
        assert runner.main(["--validate"]) == runner.EXIT_FAIL


# ---------------------------------------------------------------------------
# pytest 인터프리터 해석 (baseline 0% 사건 — 시스템 python3에 pytest 부재)
# ---------------------------------------------------------------------------


def test_pytest_green_fails_explicitly_when_no_pytest(tmp_path):
    """pytest 인터프리터 부재 시 green 위장 없이 명시적 실패해야 한다."""
    with patch.object(runner, "resolve_pytest_python", return_value=None):
        ok, detail = runner.check_assertion(
            {"type": "pytest_green", "path": "."}, "무관한 출력", tmp_path
        )
    assert ok is False
    assert "pytest" in detail and "없" in detail


def test_resolve_pytest_python_caches_and_probes(monkeypatch):
    """탐색 결과는 캐시되고, import pytest 성공 후보를 반환한다."""
    runner._PYTEST_PY = None
    calls = []

    class R:
        def __init__(self, rc):
            self.returncode = rc

    def fake_run(cmd, **kw):
        calls.append(cmd[0])
        # 첫 후보만 성공
        return R(0 if len(calls) == 1 else 1)

    monkeypatch.setattr(runner.subprocess, "run", fake_run)
    first = runner.resolve_pytest_python()
    assert first == calls[0]
    # 캐시 — 추가 probe 없음
    n = len(calls)
    assert runner.resolve_pytest_python() == first
    assert len(calls) == n
    runner._PYTEST_PY = None


# ---------------------------------------------------------------------------
# run_scenario 채점 코어 (적대적 리뷰 B / ATK-001·003·004·008)
# ---------------------------------------------------------------------------


def _agent(tmp_path):
    return runner.AgentDef(
        name="fix-bugs",
        path=tmp_path / "fix-bugs.md",
        model="sonnet",
        tools=["Read", "Edit", "Bash"],
        disallowed_tools=["Task"],
        system_prompt="테스트용",
    )


def _scenario(tmp_path, expect):
    fx = tmp_path / "fixture"
    fx.mkdir(exist_ok=True)
    return runner.Scenario(
        agent="fix-bugs",
        scenario_id="s1",
        path=tmp_path,
        task="과제",
        fixture_dir=fx,
        expect=expect,
    )


def test_run_scenario_empty_assertions_fails_closed(tmp_path):
    """assertions 0개 = 채점 불가 = fail (유령 pass 금지)."""
    res = runner.run_scenario(_agent(tmp_path), _scenario(tmp_path, {}), timeout=5)
    assert res["status"] == "fail"
    assert res["checks"][0]["type"] == "schema"


def test_run_scenario_claude_nonzero_exit_is_error(tmp_path, monkeypatch):
    """claude 비정상 종료(인프라 실패)는 error로 분류되고 pass가 아니어야 한다."""

    class R:
        returncode = 1
        stdout = "부분 출력 injection parameterize"  # 우연히 키워드 포함해도
        stderr = "auth expired"

    monkeypatch.setattr(runner.subprocess, "run", lambda *a, **k: R())
    sc = _scenario(
        tmp_path, {"assertions": [{"type": "output_contains_any", "values": ["injection"]}]}
    )
    res = runner.run_scenario(_agent(tmp_path), sc, timeout=5)
    assert res["status"] == "error"
    assert "claude exit 1" in res["checks"][0]["detail"]


def test_run_scenario_assertion_exception_degrades_to_fail(tmp_path, monkeypatch):
    """채점기 예외는 크래시가 아니라 해당 assertion fail로 강등."""

    class R:
        returncode = 0
        stdout = "ok"
        stderr = ""

    monkeypatch.setattr(runner.subprocess, "run", lambda *a, **k: R())

    def boom(*a, **k):
        raise RuntimeError("scorer bug")

    monkeypatch.setattr(runner, "check_assertion", boom)
    sc = _scenario(tmp_path, {"assertions": [{"type": "output_regex", "pattern": "x"}]})
    res = runner.run_scenario(_agent(tmp_path), sc, timeout=5)
    assert res["status"] == "fail"
    assert "채점 예외" in res["checks"][0]["detail"]


def test_pytest_green_timeout_is_fail(tmp_path, monkeypatch):
    """pytest 타임아웃은 전체 런 크래시가 아니라 fail."""
    monkeypatch.setattr(runner, "resolve_pytest_python", lambda: "python3")

    def timeout_run(*a, **k):
        raise runner.subprocess.TimeoutExpired(cmd="pytest", timeout=1)

    monkeypatch.setattr(runner.subprocess, "run", timeout_run)
    ok, detail = runner.check_assertion(
        {"type": "pytest_green", "path": "."}, "", tmp_path
    )
    assert ok is False and "타임아웃" in detail


def test_file_unchanged_detects_test_tampering(tmp_path):
    """테스트 파일 변조(채점 게이밍)를 잡는다."""
    src = tmp_path / "src_fixture"
    work = tmp_path / "work"
    src.mkdir()
    work.mkdir()
    (src / "test_x.py").write_text("assert True\n")
    (work / "test_x.py").write_text("assert True  # tampered\n")
    ok, detail = runner.check_assertion(
        {"type": "file_unchanged", "file": "test_x.py"}, "", work, source_fixture=src
    )
    assert ok is False and "변조" in detail
    (work / "test_x.py").write_text("assert True\n")
    ok, _ = runner.check_assertion(
        {"type": "file_unchanged", "file": "test_x.py"}, "", work, source_fixture=src
    )
    assert ok is True


def test_safe_join_blocks_traversal(tmp_path):
    assert runner._safe_join(tmp_path, "../../etc/passwd") is None
    assert runner._safe_join(tmp_path, "sub/file.py") is not None


def test_compare_baseline_flags_coverage_loss(tmp_path):
    """시나리오 수 감소·에이전트 소실도 후퇴로 판정 (ATK-007)."""
    baseline = {
        "summary": {
            "fix-bugs": {"pass": 4, "fail": 0, "total": 4, "pass_rate": 1.0},
            "review-code": {"pass": 4, "fail": 0, "total": 4, "pass_rate": 1.0},
        }
    }
    bp = tmp_path / "b.json"
    bp.write_text(json.dumps(baseline))
    current = {"fix-bugs": {"pass": 1, "fail": 0, "total": 1, "pass_rate": 1.0}}
    regs = runner.compare_baseline(current, str(bp))
    joined = "\n".join(regs)
    assert "시나리오 수 감소" in joined
    assert "review-code" in joined and "커버리지 소실" in joined


def test_compare_baseline_agent_filter_no_false_coverage_loss(tmp_path):
    """--agent 필터 실행 시 미실행 에이전트를 커버리지 소실로 오탐하지 않는다 (ATK-004)."""
    baseline = {
        "summary": {
            "fix-bugs": {"pass": 4, "fail": 0, "total": 4, "pass_rate": 1.0},
            "review-code": {"pass": 4, "fail": 0, "total": 4, "pass_rate": 1.0},
        }
    }
    bp = tmp_path / "b.json"
    bp.write_text(json.dumps(baseline))
    current = {"fix-bugs": {"pass": 4, "fail": 0, "total": 4, "pass_rate": 1.0}}
    assert runner.compare_baseline(current, str(bp), agent_filter="fix-bugs") == []
    # 필터 없으면 여전히 소실 검출
    regs = runner.compare_baseline(current, str(bp))
    assert any("review-code" in r for r in regs)


# ---------------------------------------------------------------------------
# v2.10.1 재감사 하드닝 회귀 고정 (R1/R2 발견)
# ---------------------------------------------------------------------------


def test_discover_skips_cache_and_dot_dirs(tmp_path):
    """.ruff_cache 등 로컬 부산물이 유령 시나리오로 잡히지 않는다 (R1/ATK-004)."""
    (tmp_path / ".ruff_cache" / "0.15").mkdir(parents=True)
    (tmp_path / "fix-bugs" / "__pycache__").mkdir(parents=True)
    (tmp_path / "fix-bugs" / "real-scenario").mkdir()
    dirs = runner.discover_scenario_dirs(scenarios_root=tmp_path)
    assert [d.name for d in dirs] == ["real-scenario"]


def test_norm_nfc_normalization():
    """NFD 출력과 NFC expect 값이 일치 판정된다 (R1/ATK-006)."""
    import unicodedata

    nfd = unicodedata.normalize("NFD", "인젝션")
    assert runner._norm("인젝션") in runner._norm(f"이 코드엔 {nfd} 위험이 있다")


def test_compare_baseline_malformed_entry_flagged_not_crash(tmp_path):
    """pass_rate 누락 baseline 항목은 크래시가 아니라 회귀로 플래그 (R1/ATK-008)."""
    bp = tmp_path / "b.json"
    bp.write_text(json.dumps({"summary": {"fix-bugs": {"pass": 1}}}))
    current = {"fix-bugs": {"pass": 4, "fail": 0, "total": 4, "pass_rate": 1.0}}
    regs = runner.compare_baseline(current, str(bp))
    assert regs and "pass_rate 없음" in regs[0]


def test_main_refuses_baseline_with_filter(tmp_path, monkeypatch):
    """--agent 필터 + --baseline 은 기준선 저장을 거부한다 (R1/ATK-001)."""
    report = {
        "results": [{"agent": "fix-bugs", "scenario": "s", "status": "pass",
                     "checks": [], "judge": None, "duration_s": 0.1}],
        "summary": {"fix-bugs": {"pass": 1, "fail": 0, "total": 1, "pass_rate": 1.0}},
    }
    monkeypatch.setattr(runner, "run_all", lambda *a, **k: (report, runner.EXIT_PASS))
    monkeypatch.setattr(runner, "BASELINE_DIR", tmp_path / "baseline")
    monkeypatch.setattr(runner, "REPORTS_DIR", tmp_path / "reports")
    rc = runner.main(["--agent", "fix-bugs", "--baseline"])
    assert rc == runner.EXIT_PASS
    assert not list((tmp_path / "baseline").glob("*.json")) if (tmp_path / "baseline").exists() else True
    # 필터 없으면 정상 저장
    rc = runner.main(["--baseline"])
    assert rc == runner.EXIT_PASS
    assert list((tmp_path / "baseline").glob("*.json"))


def test_run_scenario_pass_path_judge_advisory(tmp_path, monkeypatch):
    """전 assertion 통과 → pass, judge 결과는 advisory로만 기록 (R1/ATK-005)."""

    class R:
        returncode = 0
        stdout = "수정 완료 injection 지적"
        stderr = ""

    monkeypatch.setattr(runner.subprocess, "run", lambda *a, **k: R())
    monkeypatch.setenv("CKKIT_EVAL_JUDGE", "1")
    monkeypatch.setattr(
        runner, "run_judge", lambda *a, **k: {"ok": False, "score": 2}
    )
    sc = _scenario(
        tmp_path,
        {
            "assertions": [{"type": "output_contains_any", "values": ["injection"]}],
            "judge": {"enabled": True, "rubric": "r"},
        },
    )
    res = runner.run_scenario(_agent(tmp_path), sc, timeout=5)
    assert res["status"] == "pass"  # judge 실패해도 advisory — 판정 불변
    assert res["judge"]["advisory"] is True


def test_validate_scenario_rejects_module_scope_danger(tmp_path):
    """fixture 모듈 스코프의 위험 호출과 시나리오 루트 .py를 거부 (R2/ATK-003·005)."""
    sc = tmp_path / "fix-bugs" / "evil"
    fx = sc / "fixture"
    fx.mkdir(parents=True)
    (sc / "task.md").write_text("t")
    (sc / "expect.json").write_text(
        json.dumps({"assertions": [{"type": "pytest_green", "path": "."}]})
    )
    (fx / "mod.py").write_text("import os\nos.system('echo pwned')\n")
    (sc / "helper.py").write_text("x = 1\n")
    agents_root = tmp_path / "agents"
    agents_root.mkdir()
    (agents_root / "fix-bugs.md").write_text("---\nname: fix-bugs\n---\nbody")
    errors = runner.validate_scenario(sc, agents_root)
    joined = "\n".join(errors)
    assert "위험 호출" in joined and "시나리오 루트에 .py 금지" in joined
