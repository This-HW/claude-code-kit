#!/usr/bin/env python3
"""
Agent Evals runner (Spec 2 / W-B, toolkit-improvement-batch).

핵심 에이전트(review-code, fix-bugs, implement-code)의 행동 회귀를 기계로 검증한다.
프롬프트/정의 수정이 품질을 후퇴시켰는지 deterministic 채점(+opt-in LLM-judge)으로
탐지한다. API 비용이 들기 때문에 per-commit CI가 아니라 릴리스 전 필수 게이트로
운영한다(오프라인 스키마 검증만 scripts/verify-done.sh §10에 편입).

stdlib만 사용 — 외부 의존성 추가 금지(zero-debt).

exit code 규율 (false-green 금지 — v2.9.3 교훈):
  0 = 전체 pass (또는 --validate/--dry-run 정상)
  1 = 하나라도 fail, 또는 --compare 시 baseline 대비 후퇴, 또는 스키마 오류
  2 = SKIPPED — claude CLI 부재 등으로 실행 불가. 절대 0으로 위장하지 않는다.

사용:
  python3 evals/run.py --validate              # 오프라인 스키마 검증 (API 불필요)
  python3 evals/run.py --dry-run                # 실행 계획만 출력 (claude 미호출)
  python3 evals/run.py [--agent X] [--scenario Y] [--parallel N] [--timeout SEC]
  python3 evals/run.py --baseline               # 결과를 evals/baseline/<date>.json 저장
  python3 evals/run.py --compare evals/baseline/<date>.json   # 후퇴 시 exit 1

환경 변수:
  CKKIT_EVAL_TIMEOUT   시나리오당 기본 타임아웃(초). 기본 300.
  CKKIT_EVAL_JUDGE=1   opt-in LLM-judge 실행 (deterministic 전부 통과 시에만).
"""

from __future__ import annotations

import argparse
import concurrent.futures
import json
import os
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

EVALS_ROOT = Path(__file__).resolve().parent
REPO_ROOT = EVALS_ROOT.parent
AGENTS_ROOT = REPO_ROOT / "plugins" / "common" / "agents"
SCENARIOS_ROOT = EVALS_ROOT / "scenarios"
REPORTS_DIR = EVALS_ROOT / "reports"
BASELINE_DIR = EVALS_ROOT / "baseline"

DEFAULT_TIMEOUT = int(os.environ.get("CKKIT_EVAL_TIMEOUT", "300"))

EXIT_PASS = 0
EXIT_FAIL = 1
EXIT_SKIPPED = 2

_PYTEST_PY: str | None = None


def resolve_pytest_python() -> str | None:
    """pytest 가용 인터프리터 탐색 (verify-done.sh §4와 동일 순서).

    sys.executable에 pytest가 없을 수 있으므로(시스템 python3) repo venv를
    우선 탐색한다. 없으면 None — 호출부는 이를 '검증 불가'로 명시 처리해야
    하며 green으로 위장해선 안 된다 (false-green 금지).
    """
    global _PYTEST_PY
    if _PYTEST_PY is not None:
        return _PYTEST_PY or None
    for cand in (
        str(REPO_ROOT / ".venv" / "bin" / "python"),
        str(REPO_ROOT / "venv" / "bin" / "python"),
        sys.executable,
        "python3",
        "/tmp/ckkit-venv/bin/python",
    ):
        try:
            r = subprocess.run(
                [cand, "-c", "import pytest"], capture_output=True, timeout=10
            )
            if r.returncode == 0:
                _PYTEST_PY = cand
                return cand
        except (OSError, subprocess.TimeoutExpired):
            continue
    _PYTEST_PY = ""
    return None


# assertion type -> required field names (스키마 검증 + 채점 공용 SSOT)
KNOWN_ASSERTION_TYPES: dict[str, set[str]] = {
    "output_regex": {"pattern"},
    "output_contains_any": {"values"},
    "output_not_contains": {"values"},
    "pytest_green": {"path"},
    "file_contains": {"file", "pattern"},
    "file_unchanged": {"file"},
    "delegation_signal": set(),
}


# ---------------------------------------------------------------------------
# 에이전트 정의 파싱 (frontmatter + 본문 시스템 프롬프트)
# ---------------------------------------------------------------------------


@dataclass
class AgentDef:
    name: str
    path: Path
    model: str
    tools: list[str]
    disallowed_tools: list[str]
    system_prompt: str


def parse_frontmatter(content: str) -> tuple[dict[str, Any], str]:
    """최소 YAML 서브셋 파서. 에이전트 .md의 frontmatter(scalar + 단순 리스트/블록
    스칼라)만 지원한다 — 범용 YAML 파서가 아니다(stdlib-only 제약, 외부 yaml 금지)."""
    if not content.startswith("---"):
        return {}, content
    end = content.find("\n---", 3)
    if end == -1:
        return {}, content
    fm_text = content[3:end]
    body = content[end + 4 :].lstrip("\n")

    fm: dict[str, Any] = {}
    lines = fm_text.split("\n")
    i = 0
    key_re = re.compile(r"^([A-Za-z_][\w-]*):\s*(.*)$")
    while i < len(lines):
        line = lines[i]
        if not line.strip() or line.lstrip().startswith("#"):
            i += 1
            continue
        m = key_re.match(line)
        if not m:
            i += 1
            continue
        key, val = m.group(1), m.group(2).strip()
        if val and val not in ("|", "|-", ">"):
            fm[key] = val
            i += 1
            continue
        # 블록(리스트 또는 블록 스칼라) — 다음 들여쓰기 줄들을 소비
        j = i + 1
        block_lines: list[str] = []
        is_list = False
        while j < len(lines) and (lines[j].startswith("  ") or not lines[j].strip()):
            sub = lines[j]
            stripped = sub.strip()
            if stripped.startswith("- "):
                is_list = True
                block_lines.append(stripped[2:].strip())
            elif stripped:
                block_lines.append(sub[2:] if sub.startswith("  ") else stripped)
            else:
                block_lines.append("")
            j += 1
        if is_list:
            fm[key] = [b for b in block_lines if b]
        else:
            fm[key] = "\n".join(block_lines).strip("\n")
        i = j
    return fm, body


def _as_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(v) for v in value]
    return [str(value)]


def load_agent(name: str, agents_root: Path = AGENTS_ROOT) -> AgentDef:
    matches = sorted(agents_root.rglob(f"{name}.md"))
    if not matches:
        raise FileNotFoundError(
            f"agent definition not found for '{name}' under {agents_root}"
        )
    path = matches[0]
    content = path.read_text(encoding="utf-8")
    fm, body = parse_frontmatter(content)
    return AgentDef(
        name=name,
        path=path,
        model=str(fm.get("model", "sonnet")),
        tools=_as_list(fm.get("tools")),
        disallowed_tools=_as_list(fm.get("disallowedTools")),
        system_prompt=body.strip(),
    )


# ---------------------------------------------------------------------------
# 시나리오 로딩
# ---------------------------------------------------------------------------


@dataclass
class Scenario:
    agent: str
    scenario_id: str
    path: Path
    task: str
    fixture_dir: Path
    expect: dict[str, Any] = field(default_factory=dict)


def discover_scenario_dirs(
    scenarios_root: Path | None = None,
    agent_filter: str | None = None,
    scenario_filter: str | None = None,
) -> list[Path]:
    # None 기본값 + 모듈 속성을 호출 시점에 읽음 — 테스트가 runner.SCENARIOS_ROOT를
    # monkeypatch할 때도 반영되도록 한다(파라미터 기본값은 정의 시점에 고정되어 버림).
    if scenarios_root is None:
        scenarios_root = SCENARIOS_ROOT
    if not scenarios_root.is_dir():
        return []
    dirs: list[Path] = []
    for agent_dir in sorted(scenarios_root.iterdir()):
        if not agent_dir.is_dir():
            continue
        if agent_filter and agent_dir.name != agent_filter:
            continue
        for sc_dir in sorted(agent_dir.iterdir()):
            if not sc_dir.is_dir():
                continue
            if scenario_filter and sc_dir.name != scenario_filter:
                continue
            dirs.append(sc_dir)
    return dirs


def load_scenario(sc_dir: Path) -> Scenario:
    agent = sc_dir.parent.name
    scenario_id = sc_dir.name
    task_path = sc_dir / "task.md"
    expect_path = sc_dir / "expect.json"
    fixture_dir = sc_dir / "fixture"
    task = task_path.read_text(encoding="utf-8") if task_path.is_file() else ""
    expect = (
        json.loads(expect_path.read_text(encoding="utf-8"))
        if expect_path.is_file()
        else {}
    )
    return Scenario(
        agent=agent,
        scenario_id=scenario_id,
        path=sc_dir,
        task=task,
        fixture_dir=fixture_dir,
        expect=expect,
    )


# ---------------------------------------------------------------------------
# 오프라인 스키마 검증 (--validate / verify-done §10)
# ---------------------------------------------------------------------------


def validate_expect_schema(expect: dict, prefix: str) -> list[str]:
    errors: list[str] = []
    if not isinstance(expect, dict):
        return [f"{prefix}: expect.json은 object여야 함"]
    assertions = expect.get("assertions")
    if not isinstance(assertions, list) or not assertions:
        errors.append(
            f"{prefix}: expect.json 'assertions'는 비어있지 않은 배열이어야 함"
        )
        assertions = []
    for i, a in enumerate(assertions):
        if not isinstance(a, dict) or "type" not in a:
            errors.append(f"{prefix}: assertions[{i}]에 'type' 없음")
            continue
        t = a["type"]
        if t not in KNOWN_ASSERTION_TYPES:
            errors.append(f"{prefix}: assertions[{i}] 알 수 없는 type '{t}'")
            continue
        for req_field in KNOWN_ASSERTION_TYPES[t]:
            if req_field not in a:
                errors.append(f"{prefix}: assertions[{i}] ({t})에 '{req_field}' 없음")
    judge = expect.get("judge")
    if judge is not None:
        if not isinstance(judge, dict):
            errors.append(f"{prefix}: 'judge'는 object여야 함")
        elif judge.get("enabled") and "rubric" not in judge:
            errors.append(f"{prefix}: judge.enabled=true인데 'rubric' 없음")
    return errors


def validate_scenario(sc_dir: Path, agents_root: Path = AGENTS_ROOT) -> list[str]:
    errors: list[str] = []
    agent_name = sc_dir.parent.name
    scenario_id = sc_dir.name
    prefix = f"{agent_name}/{scenario_id}"

    task_path = sc_dir / "task.md"
    fixture_dir = sc_dir / "fixture"
    expect_path = sc_dir / "expect.json"

    if not task_path.is_file():
        errors.append(f"{prefix}: task.md 없음")
    if not fixture_dir.is_dir():
        errors.append(f"{prefix}: fixture/ 없음")
    else:
        # 보안(ATK-002 보강): pytest는 수집 시 conftest.py를 자동 실행한다 —
        # fixture에 conftest가 있으면 채점 단계에서 임의 코드 실행이 가능해 금지.
        for bad in fixture_dir.rglob("conftest.py"):
            errors.append(f"{prefix}: fixture에 conftest.py 금지 ({bad.name})")
    if not expect_path.is_file():
        errors.append(f"{prefix}: expect.json 없음")
        return errors

    try:
        expect = json.loads(expect_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        errors.append(f"{prefix}: expect.json 파싱 실패 ({e})")
        return errors

    errors += validate_expect_schema(expect, prefix)

    if not list(agents_root.rglob(f"{agent_name}.md")):
        errors.append(
            f"{prefix}: 알 수 없는 agent '{agent_name}' ({agents_root} 하위에 대응 .md 없음)"
        )

    return errors


def validate_all(
    scenarios_root: Path | None = None, agents_root: Path | None = None
) -> list[str]:
    # None 기본값 + 모듈 속성을 호출 시점에 읽음 — patch.object(runner, "SCENARIOS_ROOT", ...)
    # 로 테스트가 오버라이드할 때도 반영되도록 한다.
    if scenarios_root is None:
        scenarios_root = SCENARIOS_ROOT
    if agents_root is None:
        agents_root = AGENTS_ROOT
    if not scenarios_root.is_dir():
        # fail-closed — evals/ 부재를 조용한 green으로 위장하지 않는다.
        return [f"scenarios root 없음: {scenarios_root}"]
    dirs = discover_scenario_dirs(scenarios_root)
    if not dirs:
        return [f"scenarios root에 시나리오 없음: {scenarios_root}"]
    errors: list[str] = []
    for sc_dir in dirs:
        errors += validate_scenario(sc_dir, agents_root)
    return errors


# ---------------------------------------------------------------------------
# 채점 (deterministic assertions)
# ---------------------------------------------------------------------------


def _norm(s: str) -> str:
    return s.lower()


def _safe_join(base: Path, rel: str) -> Path | None:
    """author-제어 상대경로를 base 밖으로 못 나가게 정규화 (ATK-012 경로 탈출 가드)."""
    p = (base / rel).resolve()
    return p if p.is_relative_to(base.resolve()) else None


def check_assertion(
    assertion: dict,
    stdout: str,
    fixture_dir: Path,
    source_fixture: Path | None = None,
) -> tuple[bool, str]:
    t = assertion.get("type")
    if t == "output_regex":
        flags = 0
        for ch in assertion.get("flags", ""):
            flags |= {"i": re.IGNORECASE, "s": re.DOTALL, "m": re.MULTILINE}.get(ch, 0)
        pattern = assertion["pattern"]
        ok = re.search(pattern, stdout, flags) is not None
        return ok, f"output_regex '{pattern}'" + ("" if ok else " — 매치 없음")
    if t == "output_contains_any":
        values = assertion.get("values", [])
        low = _norm(stdout)
        ok = any(_norm(v) in low for v in values)
        return ok, f"output_contains_any {values}" + ("" if ok else " — 하나도 없음")
    if t == "output_not_contains":
        values = assertion.get("values", [])
        low = _norm(stdout)
        hit = [v for v in values if _norm(v) in low]
        ok = not hit
        return ok, "output_not_contains" + ("" if ok else f" — 발견됨 {hit}")
    if t == "pytest_green":
        rel = assertion.get("path", ".")
        target = _safe_join(fixture_dir, rel)
        if target is None:
            return False, f"pytest_green — 경로 탈출 차단: {rel}"
        py = resolve_pytest_python()
        if py is None:
            # pytest 부재 = 검증 불가. green 위장 금지 — 명시적 실패로 드러낸다.
            return (
                False,
                "pytest_green — pytest 인터프리터 없음 (검증 불가, .venv 확인)",
            )
        try:
            r = subprocess.run(
                [py, "-m", "pytest", str(target), "-q", "-p", "no:cacheprovider"],
                cwd=str(fixture_dir),
                capture_output=True,
                text=True,
                timeout=int(assertion.get("timeout", 120)),
            )
        except subprocess.TimeoutExpired:
            # 무한루프 fixture 하나가 전체 런을 크래시시키지 않게 fail로 강등 (ATK-003).
            return False, "pytest_green — pytest 타임아웃"
        ok = r.returncode == 0
        return ok, "pytest_green" + (
            "" if ok else f" — exit {r.returncode}: {r.stdout[-400:]} {r.stderr[-200:]}"
        )
    if t == "file_contains":
        f = _safe_join(fixture_dir, assertion["file"])
        if f is None:
            return False, f"file_contains — 경로 탈출 차단: {assertion['file']}"
        if not f.is_file():
            return False, f"file_contains — 파일 없음 {assertion['file']}"
        content = f.read_text(encoding="utf-8")
        ok = re.search(assertion["pattern"], content) is not None
        return ok, "file_contains" + ("" if ok else " — 패턴 없음")
    if t == "file_unchanged":
        # 채점 게이밍 방지(ATK-006): 에이전트가 테스트 파일을 고쳐 green을 만드는
        # 우회를 차단 — 실행 후 파일이 원본 fixture와 byte-동일해야 통과.
        rel_f = assertion["file"]
        cur = _safe_join(fixture_dir, rel_f)
        if cur is None:
            return False, f"file_unchanged — 경로 탈출 차단: {rel_f}"
        if source_fixture is None:
            return False, "file_unchanged — 원본 fixture 참조 없음 (러너 버그)"
        orig = _safe_join(source_fixture, rel_f)
        if orig is None or not orig.is_file():
            return False, f"file_unchanged — 원본에 없는 파일 {rel_f}"
        if not cur.is_file():
            return False, f"file_unchanged — 실행 후 파일 삭제됨 {rel_f}"
        ok = cur.read_bytes() == orig.read_bytes()
        return ok, "file_unchanged" + ("" if ok else f" — {rel_f} 변조됨 (게이밍 의심)")
    if t == "delegation_signal":
        markers = ("---DELEGATION_SIGNAL---", "TYPE:", "---END_SIGNAL---")
        ok = all(m in stdout for m in markers)
        return ok, "delegation_signal" + ("" if ok else " — 형식 마커 없음")
    return False, f"알 수 없는 assertion type: {t}"


# ---------------------------------------------------------------------------
# LLM-judge (opt-in, deterministic 전부 통과 시에만)
# ---------------------------------------------------------------------------


def run_judge(stdout: str, judge_cfg: dict, timeout: int) -> dict:
    rubric = judge_cfg.get("rubric", "")
    threshold = judge_cfg.get("threshold", 7)
    prompt = (
        "다음은 AI 에이전트의 출력입니다. 아래 rubric에 따라 0~10점으로 채점하고 "
        "응답 첫 줄에 정확히 'SCORE: <정수>' 형식으로만 점수를 적으세요.\n\n"
        f"Rubric: {rubric}\n\n--- 에이전트 출력 ---\n{stdout}\n"
    )
    try:
        r = subprocess.run(
            ["claude", "-p", prompt, "--model", "sonnet", "--output-format", "text"],
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        return {"ok": None, "score": None, "note": "judge timeout"}
    m = re.search(r"SCORE:\s*(\d+)", r.stdout)
    if not m:
        return {
            "ok": None,
            "score": None,
            "note": "judge 점수 파싱 실패 (deterministic만으로 판정)",
        }
    score = int(m.group(1))
    return {"ok": score >= threshold, "score": score, "threshold": threshold}


# ---------------------------------------------------------------------------
# 실행
# ---------------------------------------------------------------------------


def build_claude_command(agent: AgentDef, task: str, timeout: int) -> list[str]:  # noqa: ARG001
    cmd = [
        "claude",
        "-p",
        task,
        "--model",
        agent.model,
        "--append-system-prompt",
        agent.system_prompt,
        "--permission-mode",
        "bypassPermissions",
        "--output-format",
        "text",
    ]
    if agent.tools:
        cmd += ["--allowedTools", *agent.tools]
    if agent.disallowed_tools:
        cmd += ["--disallowedTools", *agent.disallowed_tools]
    return cmd


def _result(
    agent: str,
    scenario: Scenario,
    status: str,
    checks: list[dict],
    duration: float,
    judge=None,
) -> dict:
    return {
        "agent": agent,
        "scenario": scenario.scenario_id,
        "status": status,
        "checks": checks,
        "judge": judge,
        "duration_s": round(duration, 2),
    }


def run_scenario(agent: AgentDef, scenario: Scenario, timeout: int) -> dict:
    # fail-closed 가드: assertions 0개 = 채점 불가 = fail (적대적 리뷰 B / ATK-001).
    # "검사 0건"이 pass로 합산되면 baseline 희석·후퇴 은폐가 생긴다 (v2.9.3 P0 계열).
    assertions = scenario.expect.get("assertions", [])
    if not assertions:
        return _result(
            agent.name,
            scenario,
            "fail",
            [
                {
                    "type": "schema",
                    "ok": False,
                    "detail": "assertions 비어있음/누락 — 채점 불가 (fail-closed)",
                }
            ],
            0.0,
        )

    with tempfile.TemporaryDirectory(
        prefix=f"ckkit-eval-{agent.name}-{scenario.scenario_id}-"
    ) as td:
        work_dir = Path(td) / "fixture"
        if scenario.fixture_dir.is_dir():
            shutil.copytree(
                scenario.fixture_dir,
                work_dir,
                ignore=shutil.ignore_patterns("__pycache__", ".pytest_cache"),
            )
        else:
            work_dir.mkdir(parents=True)

        cmd = build_claude_command(agent, scenario.task, timeout)
        start = time.time()
        try:
            r = subprocess.run(
                cmd, cwd=str(work_dir), capture_output=True, text=True, timeout=timeout
            )
            stdout = r.stdout
        except subprocess.TimeoutExpired:
            return _result(
                agent.name,
                scenario,
                "fail",
                [{"type": "timeout", "ok": False, "detail": f"{timeout}s 초과"}],
                time.time() - start,
            )

        # 인프라 실패(비정상 exit)는 품질 fail과 구분해 'error'로 기록하되,
        # 집계에서는 pass가 아니므로 동일하게 게이트를 막는다 (ATK-004).
        if r.returncode != 0:
            return _result(
                agent.name,
                scenario,
                "error",
                [
                    {
                        "type": "claude_exit",
                        "ok": False,
                        "detail": f"claude exit {r.returncode}: {r.stderr[-300:]}",
                    }
                ],
                time.time() - start,
            )

        checks = []
        all_ok = True
        for a in assertions:
            try:
                ok, detail = check_assertion(
                    a, stdout, work_dir, source_fixture=scenario.fixture_dir
                )
            except (
                Exception
            ) as e:  # 채점기 예외 = fail (크래시로 전체 런 유실 금지, ATK-003)
                ok, detail = False, f"{a.get('type')} — 채점 예외: {e!r}"
            checks.append({"type": a.get("type"), "ok": ok, "detail": detail})
            all_ok = all_ok and ok

        judge_result = None
        judge_cfg = scenario.expect.get("judge") or {}
        if (
            all_ok
            and judge_cfg.get("enabled")
            and os.environ.get("CKKIT_EVAL_JUDGE") == "1"
        ):
            judge_result = run_judge(stdout, judge_cfg, timeout)
            if judge_result is not None:
                # advisory-only: 최종 판정에 영향 없음을 리포트에 명시 (ATK-009).
                judge_result["advisory"] = True

        status = "pass" if all_ok else "fail"
        return _result(
            agent.name,
            scenario,
            status,
            checks,
            time.time() - start,
            judge=judge_result,
        )


def summarize(results: list[dict]) -> dict:
    summary: dict[str, dict] = {}
    for r in results:
        s = summary.setdefault(r["agent"], {"pass": 0, "fail": 0, "total": 0})
        s["total"] += 1
        s["pass" if r["status"] == "pass" else "fail"] += 1
    for s in summary.values():
        s["pass_rate"] = s["pass"] / s["total"] if s["total"] else 0.0
    return summary


def _shdisplay(cmd: list[str]) -> str:
    parts = []
    for c in cmd:
        shown = c if len(c) < 60 else c[:57] + "..."
        parts.append(shlex.quote(shown))
    return " ".join(parts)


def run_all(
    agent_filter: str | None,
    scenario_filter: str | None,
    parallel: int,
    timeout: int,
    dry_run: bool = False,
) -> tuple[dict, int]:
    # 실행 전 스키마 검증 강제 (ATK-001): 유령 디렉토리/깨진 expect.json이
    # "검사 0건 pass"로 흘러드는 경로를 실행 경로 자체에서 차단한다.
    schema_errors = validate_all()
    if schema_errors:
        for e in schema_errors:
            print(f"[eval] 스키마 오류: {e}", file=sys.stderr)
        return {"results": [], "summary": {}}, EXIT_FAIL

    sc_dirs = discover_scenario_dirs(
        agent_filter=agent_filter, scenario_filter=scenario_filter
    )
    if not sc_dirs:
        print("[eval] 매치되는 시나리오 없음", file=sys.stderr)
        return {"results": [], "summary": {}}, EXIT_FAIL

    scenarios = [load_scenario(d) for d in sc_dirs]
    agents_cache: dict[str, AgentDef] = {}
    plan: list[tuple[AgentDef, Scenario]] = []
    for sc in scenarios:
        if sc.agent not in agents_cache:
            try:
                agents_cache[sc.agent] = load_agent(sc.agent)
            except FileNotFoundError as e:
                print(f"[eval] {e}", file=sys.stderr)
                return {"results": [], "summary": {}}, EXIT_FAIL
        plan.append((agents_cache[sc.agent], sc))

    if dry_run:
        for agent, sc in plan:
            cmd = build_claude_command(agent, sc.task, timeout)
            print(f"[dry-run] {sc.agent}/{sc.scenario_id} model={agent.model}")
            print(f"          cmd: {_shdisplay(cmd)}")
        return {"results": [], "summary": {}}, EXIT_PASS

    if shutil.which("claude") is None:
        print("[eval] SKIPPED — claude CLI를 PATH에서 찾을 수 없음", file=sys.stderr)
        return {"results": [], "summary": {}}, EXIT_SKIPPED

    results: list[dict] = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=max(1, parallel)) as ex:
        futs = [ex.submit(run_scenario, agent, sc, timeout) for agent, sc in plan]
        for fut in concurrent.futures.as_completed(futs):
            results.append(fut.result())

    summary = summarize(results)
    exit_code = EXIT_PASS if all(r["status"] == "pass" for r in results) else EXIT_FAIL
    return {"results": results, "summary": summary}, exit_code


def compare_baseline(
    current_summary: dict, baseline_path: str, agent_filter: str | None = None
) -> list[str]:
    baseline = json.loads(Path(baseline_path).read_text(encoding="utf-8"))
    base_summary = baseline.get("summary", {})
    # --agent 필터 실행 시 baseline도 그 에이전트로 좁힌다 — 필터로 실행하지 않은
    # 에이전트를 "커버리지 소실"로 오탐하는 것을 방지 (최종 재감사 ATK-004).
    if agent_filter is not None:
        base_summary = {
            k: v for k, v in base_summary.items() if k == agent_filter
        }
    regressions = []
    for agent, cur in current_summary.items():
        base = base_summary.get(agent)
        if not base:
            continue
        if cur["pass_rate"] < base["pass_rate"]:
            regressions.append(
                f"{agent}: pass_rate {cur['pass_rate']:.2f} < baseline {base['pass_rate']:.2f}"
            )
        # 커버리지 감소도 후퇴 (ATK-007): 시나리오 삭제로 pass_rate를 유지하는
        # 우회를 차단 — 개수가 줄면 그 자체로 회귀 취급.
        if (
            cur.get("total") is not None
            and base.get("total") is not None
            and cur["total"] < base["total"]
        ):
            regressions.append(
                f"{agent}: 시나리오 수 감소 {cur['total']} < baseline {base['total']}"
            )
    # baseline에 있던 에이전트가 통째로 사라진 경우 (ATK-007)
    for agent in base_summary:
        if agent not in current_summary:
            regressions.append(
                f"{agent}: baseline에 있으나 현재 결과에 없음 (커버리지 소실)"
            )
    return regressions


def print_console_summary(summary: dict) -> None:
    print("\n=== Agent Evals Summary ===")
    if not summary:
        print("  (결과 없음)")
        return
    for agent, s in sorted(summary.items()):
        print(f"  {agent}: {s['pass']}/{s['total']} pass ({s['pass_rate'] * 100:.0f}%)")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def build_arg_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="claude-code-kit agent evals runner")
    p.add_argument(
        "--validate",
        action="store_true",
        help="오프라인 스키마 검증만 수행 (API 불필요)",
    )
    p.add_argument(
        "--dry-run", action="store_true", help="claude 호출 없이 실행 계획만 출력"
    )
    p.add_argument("--agent", help="에이전트 이름으로 필터")
    p.add_argument("--scenario", help="시나리오 id로 필터")
    p.add_argument(
        "--parallel", type=int, default=1, help="동시 실행 시나리오 수 (기본 1)"
    )
    p.add_argument(
        "--timeout", type=int, default=DEFAULT_TIMEOUT, help="시나리오당 타임아웃(초)"
    )
    p.add_argument(
        "--baseline",
        action="store_true",
        help="결과를 evals/baseline/<date>.json에 저장",
    )
    p.add_argument(
        "--compare", metavar="BASELINE_JSON", help="baseline 대비 pass-rate 후퇴 검출"
    )
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)

    if args.validate:
        errors = validate_all()
        if errors:
            for e in errors:
                print(f"  [FAIL] {e}")
            print(f"\n{len(errors)}건 검증 실패")
            return EXIT_FAIL
        print("[validate] 모든 시나리오 스키마 OK")
        return EXIT_PASS

    report, exit_code = run_all(
        args.agent, args.scenario, args.parallel, args.timeout, dry_run=args.dry_run
    )

    if args.dry_run:
        return exit_code
    if exit_code == EXIT_SKIPPED:
        return exit_code

    print_console_summary(report["summary"])

    # 리포트를 compare보다 먼저 기록 — compare 크래시로 실측 결과가 유실되지 않게 (ATK-011).
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    report_path = REPORTS_DIR / f"{ts}.json"
    report_path.write_text(
        json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print(f"\n[eval] report written: {report_path}")

    if args.compare:
        try:
            regressions = compare_baseline(
                report["summary"], args.compare, agent_filter=args.agent
            )
        except (OSError, json.JSONDecodeError) as e:
            print(f"[compare] baseline 읽기 실패: {e}", file=sys.stderr)
            return EXIT_FAIL
        if regressions:
            print("\n[compare] baseline 대비 후퇴 감지:")
            for r in regressions:
                print(f"  - {r}")
            exit_code = EXIT_FAIL
        else:
            print("\n[compare] baseline 대비 후퇴 없음")

    if args.baseline:
        if exit_code != EXIT_PASS:
            # 실패 런을 기준선으로 저장하면 이후 compare가 오염된다 (ATK-010).
            print("[eval] baseline 저장 거부 — 실패한 런은 기준선이 될 수 없음")
        else:
            BASELINE_DIR.mkdir(parents=True, exist_ok=True)
            date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
            baseline_path = BASELINE_DIR / f"{date_str}.json"
            if baseline_path.exists():
                baseline_path.replace(baseline_path.with_suffix(".json.bak"))
                print(f"[eval] 기존 baseline 백업: {baseline_path}.bak")
            baseline_path.write_text(
                json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8"
            )
            print(f"[eval] baseline written: {baseline_path}")

    return exit_code


if __name__ == "__main__":
    sys.exit(main())
