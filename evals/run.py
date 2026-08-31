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
  python3 evals/run.py --compare evals/baseline/<date>.json   # 후퇴 시 exit 1 (전량 재실행)
  python3 evals/run.py --compare <baseline> --report evals/reports/<ts>.json  # 재실행 없이 비교

환경 변수:
  CKKIT_EVAL_TIMEOUT   시나리오당 기본 타임아웃(초). override 전용 — 기본값의
                       SSOT는 evals/policy.json의 cost.scenarioTimeoutSeconds다
                       (W-022 R3). 미설정 시 정책 파일 값을 쓴다.
  CKKIT_EVAL_JUDGE=1   opt-in LLM-judge 실행 (deterministic 전부 통과 시에만).
"""

from __future__ import annotations

import argparse
import ast
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
import unicodedata
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


def _policy_default_timeout() -> int:
    """정책 파일의 timeout이 기본값의 SSOT다(W-022 R3) — 환경변수는 override로만
    남긴다. 실행자마다 다른 기본값으로 스위트를 돌리면 "누구는 통과, 누구는
    타임아웃"이 되는 드리프트가 생긴다 — 이 레포가 계속 잡아온 것과 같은 클래스."""
    try:
        policy = json.loads((EVALS_ROOT / "policy.json").read_text(encoding="utf-8"))
        return int(policy.get("cost", {}).get("scenarioTimeoutSeconds", 300))
    except (OSError, ValueError, json.JSONDecodeError):
        return 300


try:
    DEFAULT_TIMEOUT = int(os.environ["CKKIT_EVAL_TIMEOUT"])
except KeyError:
    DEFAULT_TIMEOUT = _policy_default_timeout()
except ValueError:
    print("[eval] CKKIT_EVAL_TIMEOUT 비정수 — 정책 기본값 사용", file=sys.stderr)
    DEFAULT_TIMEOUT = _policy_default_timeout()

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
    global _PYTEST_PY  # noqa: PLW0603 — 프로세스 1회 탐색 결과 메모이제이션
    if _PYTEST_PY is not None:
        return _PYTEST_PY or None
    for cand in (
        str(REPO_ROOT / ".venv" / "bin" / "python"),
        str(REPO_ROOT / "venv" / "bin" / "python"),
        sys.executable,
        "python3",
        # 여기에 /tmp 경로를 후보로 되돌리지 말 것: world-writable + 예측 가능한
        # 이름이라 아무 로컬 사용자나 인터프리터를 심어둘 수 있다. ruff S108이 잡는다.
    ):
        try:
            r = subprocess.run(
                [cand, "-c", "import pytest"],
                capture_output=True,
                timeout=10,
                check=False,
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
    # git 상태 어서션 3종 (W-023 D-5). expect:false로 부정을 표현한다 —
    # *_not_* 타입은 만들지 않는다(타입 표가 읽기 어려워지면 시나리오 작성자가
    # 틀린 타입을 고른다).
    "git_log_contains": {"pattern"},
    "git_branch_exists": {"branch"},
    "git_status_clean": set(),
}

# git.json 연산 어휘 -> 필수 필드 (W-023 D-1, config 제거는 D-1 결정log — 화이트리스트
# **안**의 연산만으로 임의 코드 실행이 성립함이 실증됨: filter.<n>.clean 같은 임의 git
# config 값 + .gitattributes(write) + add 만으로 실행 비트 없이 발화한다). 이 8종이 전부다.
# run/exec/clone/fetch/push/remote/submodule/config 등은 의도적으로 없다(임의 셸 실행
# 통로 금지). validate_git_spec의 스키마 검증과 materialize_git_repo의 실행 분기가 이
# SSOT를 공유한다.
ALLOWED_GIT_OPS: dict[str, set[str]] = {
    "init": set(),
    "write": {"path", "content"},
    "add": {"paths"},
    "commit": {"message"},
    "branch": {"name"},
    "checkout": {"ref"},
    "tag": {"name"},
    "merge": {"ref"},
}

# 재현성 고정값 (D-4) — 사용자 전역 git 설정(user.name 미설정, init.defaultBranch 등)이
# 실체화 결과를 실행자마다 다르게 만들지 않도록 매 git 호출에 고정 환경을 준다.
_GIT_FIXED_IDENTITY = {
    "GIT_AUTHOR_NAME": "eval",
    "GIT_AUTHOR_EMAIL": "eval@example.invalid",
    "GIT_COMMITTER_NAME": "eval",
    "GIT_COMMITTER_EMAIL": "eval@example.invalid",
    "GIT_AUTHOR_DATE": "2026-01-01T00:00:00+00:00",
    "GIT_COMMITTER_DATE": "2026-01-01T00:00:00+00:00",
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
    # git.json 선언적 명세 (W-023 Stage 0). 없으면 None — 기존 시나리오는 회귀 없이 동작한다.
    git_spec: dict[str, Any] | None = None


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
    # 로컬 캐시 부산물(.ruff_cache 등)이 유령 에이전트/시나리오로 잡혀
    # 게이트를 무너뜨리지 않게 dot/캐시 디렉토리는 스킵 (재감사 R1/ATK-004).
    skip = {"__pycache__", ".pytest_cache", ".ruff_cache"}
    dirs: list[Path] = []
    for agent_dir in sorted(scenarios_root.iterdir()):
        if (
            not agent_dir.is_dir()
            or agent_dir.name.startswith(".")
            or agent_dir.name in skip
        ):
            continue
        if agent_filter and agent_dir.name != agent_filter:
            continue
        for sc_dir in sorted(agent_dir.iterdir()):
            if (
                not sc_dir.is_dir()
                or sc_dir.name.startswith(".")
                or sc_dir.name in skip
            ):
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
    git_spec_path = sc_dir / "git.json"
    task = task_path.read_text(encoding="utf-8") if task_path.is_file() else ""
    expect = (
        json.loads(expect_path.read_text(encoding="utf-8"))
        if expect_path.is_file()
        else {}
    )
    git_spec = (
        json.loads(git_spec_path.read_text(encoding="utf-8"))
        if git_spec_path.is_file()
        else None
    )
    return Scenario(
        agent=agent,
        scenario_id=scenario_id,
        path=sc_dir,
        task=task,
        fixture_dir=fixture_dir,
        expect=expect,
        git_spec=git_spec,
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


def validate_git_spec(spec: dict, prefix: str) -> list[str]:
    """git.json 오프라인 스키마 검증 (W-023 D-1/D-2). 실체화(materialize_git_repo) 전에
    구조·화이트리스트·경로 탈출을 잡는다 — `--validate`/게이트 §10이 이 함수로 커버된다.

    `write.path`의 경로 탈출 차단은 여기서도 구조적으로(절대경로·`..`) 걸지만, 유일한
    영구 봉쇄는 materialize_git_repo가 쓰는 _safe_join이다 — 이 함수는 실행 전 조기
    거부일 뿐, 대체하지 않는다 (D-2: 한 번 resolve하고 그 결과를 끝까지 쓴다).
    """
    errors: list[str] = []
    if not isinstance(spec, dict):
        return [f"{prefix}: git.json은 object여야 함"]
    if spec.get("version") != 1:
        errors.append(
            f"{prefix}: git.json 'version'은 1이어야 함 (got {spec.get('version')!r})"
        )
    ops = spec.get("ops")
    if not isinstance(ops, list) or not ops:
        errors.append(f"{prefix}: git.json 'ops'는 비어있지 않은 배열이어야 함")
        ops = []
    for i, op_entry in enumerate(ops):
        if not isinstance(op_entry, dict) or "op" not in op_entry:
            errors.append(f"{prefix}: git.json ops[{i}]에 'op' 없음")
            continue
        op = op_entry["op"]
        if op not in ALLOWED_GIT_OPS:
            errors.append(
                f"{prefix}: git.json ops[{i}] 알 수 없는 op '{op}' (화이트리스트 밖 — "
                f"허용: {sorted(ALLOWED_GIT_OPS)})"
            )
            continue
        for req_field in ALLOWED_GIT_OPS[op]:
            if req_field not in op_entry:
                errors.append(
                    f"{prefix}: git.json ops[{i}] ({op})에 '{req_field}' 없음"
                )
        if op == "write":
            path = op_entry.get("path")
            if isinstance(path, str):
                p = Path(path)
                if p.is_absolute() or ".." in p.parts:
                    errors.append(
                        f"{prefix}: git.json ops[{i}] write.path 경로 탈출/절대경로 "
                        f"금지: {path!r}"
                    )
    return errors


# fixture 모듈 스코프 위험 호출 판정 (AST 우선 + 정규식 폴백)
#
# 판정 원칙: **import 시 실제로 실행되는 위치**만 본다.
#   실행됨   — 모듈 최상위 문장, 클래스 본문, 데코레이터 표현식, 기본 인자 값
#   실행 안 됨 — 함수/메서드 **본문**
# 함수든 클래스든 통째로 스킵하면 위 셋이 전부 새어나간다(2026-08-23 적대적 리뷰가
# 클래스 본문·데코레이터·기본인자 우회를 실증했다).
# 모듈 등급 2단:
#   ANY  — 이 모듈의 **어떤 호출이든** 모듈 스코프에서는 위험 (프로세스/네트워크/동적 import)
#   ATTR — 위험한 **속성 이름일 때만** 위험. `os.path.join`·`shutil.which`·`urlparse` 같은
#          정상 사용을 막지 않기 위해 필요하다(1단 블록리스트는 이들을 오탐했다).
_ANY_CALL_DANGER = frozenset({"subprocess", "socket", "requests", "importlib"})
_ATTR_CALL_DANGER = frozenset({"os", "shutil", "urllib"})
_DANGER_MODULES = _ANY_CALL_DANGER | _ATTR_CALL_DANGER
# 이름만으로 위험한 호출 (from-import 되어 모듈 접두어가 사라진 경우)
_DANGER_NAMES = frozenset(
    {
        "system",
        "popen",
        "execv",
        "execve",
        "execl",
        "execlp",
        "spawnv",
        "spawnl",
        "remove",
        "unlink",
        "rmdir",
        "removedirs",
        "rmtree",
        "kill",
        "urlopen",
    }
)
# 빌트인: 임의 실행·동적 해석 통로만. `open`/`input`/`compile`은 **넣지 않는다** —
# 모듈 스코프에서 데이터를 읽는 정상 fixture를 막아버린다(오탐으로 실증됨).
_DANGER_BUILTINS = frozenset({"eval", "exec", "__import__", "getattr", "setattr"})
_DANGER_DYNAMIC = frozenset({"importlib"})
_DANGER_RE = re.compile(
    r"^(?!\s)(?:.*\b(?:os\.system|subprocess\.|socket\.|eval\(|exec\(|__import__)\b)"
)


def _danger_ref(node: ast.AST) -> tuple[str | None, str | None]:
    """참조 표현식에서 (최상위 이름, 마지막 속성)을 뽑는다.

    `os.system` → ("os", "system") · `os.path.join` → ("os", "join") · `f` → ("f", None)
    `getattr(os,"x")("id")` 처럼 호출이 중첩되면 안쪽으로 내려간다.
    """
    f = node.func if isinstance(node, ast.Call) else node
    last = f.attr if isinstance(f, ast.Attribute) else None
    while isinstance(f, ast.Attribute):
        f = f.value
    if isinstance(f, ast.Name):
        return f.id, last
    if isinstance(f, ast.Call):
        root, inner = _danger_ref(f)
        return root, last or inner
    return None, last


def _collect_aliases(tree: ast.AST) -> tuple[dict, dict, list]:
    """import 별칭과 위험 재바인딩을 추적한다.

    `import os as x` / `from os import system` / `f = os.system` / `from os import *`
    — 전부 모듈 접두어를 지우거나 바꿔서 단순 부분문자열 검사를 무력화하는 경로다.
    """
    alias_mod: dict[str, str] = {}  # 별칭 → 원본 모듈
    alias_name: dict[str, str] = {}  # 별칭 → "module.name"
    star_imports: list[str] = []  # `from X import *` 의 X
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for a in node.names:
                alias_mod[a.asname or a.name.split(".")[0]] = a.name.split(".")[0]
        elif isinstance(node, ast.ImportFrom):
            mod = (node.module or "").split(".")[0]
            for a in node.names:
                if a.name == "*":
                    star_imports.append(mod)
                else:
                    alias_name[a.asname or a.name] = f"{mod}.{a.name}"
        elif isinstance(node, ast.Assign):
            # `f = os.system` 재바인딩 — 대입 자체는 Call이 아니라 별도로 잡는다.
            target = node.targets[0] if node.targets else None
            if isinstance(target, ast.Name) and isinstance(node.value, ast.Attribute):
                base = node.value.value
                if isinstance(base, ast.Name):
                    origin = alias_mod.get(base.id, base.id)
                    if origin in _DANGER_MODULES or node.value.attr in _DANGER_NAMES:
                        alias_name[target.id] = f"{origin}.{node.value.attr}"
    return alias_mod, alias_name, star_imports


def _executed_at_import(tree: ast.Module) -> list[ast.AST]:
    """import 시 실제로 평가되는 노드만 모은다."""
    out: list[ast.AST] = []
    stack: list[ast.AST] = list(tree.body)
    while stack:
        node = stack.pop()
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            # 본문은 실행되지 않지만 데코레이터와 기본 인자 값은 실행된다.
            out.extend(node.decorator_list)
            out.extend(d for d in node.args.defaults if d is not None)
            out.extend(
                d for d in getattr(node.args, "kw_defaults", []) if d is not None
            )
            continue
        if isinstance(node, ast.ClassDef):
            # 클래스 **본문은 import 시 실행된다**.
            out.extend(node.decorator_list)
            out.extend(node.bases)
            stack.extend(node.body)
            continue
        out.append(node)
    return out


def _module_scope_danger(src: str) -> list[str]:
    """모듈 스코프(=import 시 실행되는 위치)의 위험 호출 목록."""
    try:
        tree = ast.parse(src)
    except (SyntaxError, ValueError):
        # 파싱 불가 = 검사 불가. 통과로 삼지 않는다 (NUL 바이트는 ValueError를 던진다 —
        # 이걸 안 잡으면 --validate 전체가 트레이스백으로 죽는다).
        return [ln.strip()[:60] for ln in src.splitlines() if _DANGER_RE.match(ln)] or [
            "구문 오류로 AST 검사 불가"
        ]

    alias_mod, alias_name, star_imports = _collect_aliases(tree)
    hits: list[str] = []

    # `from os import *` 는 이름이 통째로 쏟아져 들어와 추적이 불가능하다 — 거부한다.
    for mod in star_imports:
        if mod in _DANGER_MODULES:
            hits.append(f"from {mod} import * (별칭 추적 불가 — 명시 import를 쓰라)")

    for node in _executed_at_import(tree):
        for sub in ast.walk(node):
            # 데코레이터는 `@os.popen` 처럼 **Call이 아닌 참조**로도 쓰이고, 그때도
            # import 시 평가·적용된다. Call만 보면 이 경로가 통째로 샌다.
            if not isinstance(sub, (ast.Call, ast.Attribute, ast.Name)):
                continue
            if isinstance(sub, (ast.Attribute, ast.Name)) and not _is_decorator(
                sub, node
            ):
                continue
            root, last = _danger_ref(sub)
            if root is None:
                continue
            if _is_dangerous(root, last, alias_mod, alias_name):
                hits.append(f"line {getattr(sub, 'lineno', '?')}: {root}(...)")
    return hits


def _is_decorator(node: ast.AST, parent: ast.AST) -> bool:
    """`_executed_at_import`가 데코레이터 표현식을 그대로 넘겨준다 — 그 자신인지 확인."""
    return node is parent


def _is_dangerous(
    root: str, last: str | None, alias_mod: dict, alias_name: dict
) -> bool:
    origin = alias_mod.get(root)
    imported = alias_name.get(root)
    if root in _DANGER_BUILTINS or root in _DANGER_DYNAMIC or origin in _DANGER_DYNAMIC:
        return True
    if origin in _ANY_CALL_DANGER:
        return True
    if origin in _ATTR_CALL_DANGER:
        # `os.path.join`은 통과, `os.system`은 차단.
        return last in _DANGER_NAMES
    if imported is not None:
        head, tail = imported.split(".")[0], imported.split(".")[-1]
        if head in _ANY_CALL_DANGER:
            return True
        return tail in _DANGER_NAMES
    return False


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
        # 모듈 스코프 부작용 차단 (재감사 R2/ATK-003): fixture는 stop-validator
        # 검증에서 제외되므로, import-time에 실행되는 위험 호출을 여기서 거부한다.
        #
        # 1차는 AST다. 이전에는 정규식 부분문자열 블록리스트뿐이었고, 그건 **별칭으로
        # 뚫린다** — `import os as x; x.system("id")`, `from os import system;
        # system("id")`가 전부 통과했다(2026-08-23 보안 점검 실증). AST는 import 별칭을
        # 따라가므로 그 경로를 닫는다. 정규식은 파싱 불가(SyntaxError) 파일에 대한
        # 2차 방어로 남긴다 — 검사 불가를 통과로 삼지 않기 위해서다.
        for py in sorted(fixture_dir.rglob("*.py")):
            src = py.read_text(encoding="utf-8", errors="replace")
            for hit in _module_scope_danger(src):
                errors.append(
                    f"{prefix}: fixture 모듈 스코프에 위험 호출 금지 ({py.name}: {hit})"
                )
    # scenario 디렉토리에 fixture 밖 .py 금지 (재감사 R2/ATK-005): stop-validator의
    # evals/scenarios/ 제외가 실코드를 은닉하는 통로가 되지 않게 구조로 강제.
    for stray in sorted(sc_dir.glob("*.py")):
        errors.append(
            f"{prefix}: 시나리오 루트에 .py 금지 ({stray.name}) — 코드는 fixture/ 안에만"
        )
    if not expect_path.is_file():
        errors.append(f"{prefix}: expect.json 없음")
        return errors

    try:
        expect = json.loads(expect_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        errors.append(f"{prefix}: expect.json 파싱 실패 ({e})")
        return errors

    errors += validate_expect_schema(expect, prefix)

    git_spec_path = sc_dir / "git.json"
    if git_spec_path.is_file():
        try:
            git_spec = json.loads(git_spec_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as e:
            errors.append(f"{prefix}: git.json 파싱 실패 ({e})")
        else:
            errors += validate_git_spec(git_spec, prefix)

    if not list(agents_root.rglob(f"{agent_name}.md")):
        errors.append(
            f"{prefix}: 알 수 없는 agent '{agent_name}' ({agents_root} 하위에 대응 .md 없음)"
        )

    return errors


def validate_all(
    scenarios_root: Path | None = None,
    agents_root: Path | None = None,
    agent_filter: str | None = None,
    scenario_filter: str | None = None,
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
    dirs = discover_scenario_dirs(
        scenarios_root, agent_filter=agent_filter, scenario_filter=scenario_filter
    )
    if not dirs:
        return [f"scenarios root에 시나리오 없음(필터 포함): {scenarios_root}"]
    errors: list[str] = []
    for sc_dir in dirs:
        errors += validate_scenario(sc_dir, agents_root)
    return errors


# ---------------------------------------------------------------------------
# git.json 실체화 (W-023 Stage 0 — D-1~D-4)
# ---------------------------------------------------------------------------


def _git_env() -> dict[str, str]:
    """고정 커밋 작성자/시각(D-4) — 사용자 전역 git 설정에 결과가 좌우되지 않는다."""
    env = os.environ.copy()
    env.update(_GIT_FIXED_IDENTITY)
    return env


def _run_git(work_dir: Path, args: list[str]) -> None:
    """`git -C work_dir` 고정 — cwd 상대경로에 의존하지 않는다 (D-2).

    gpgsign은 명령별로 끈다(-c commit.gpgsign=false) — 사용자 전역 설정이
    commit.gpgsign=true면 서명 프롬프트로 실체화가 멈춘다 (D-4).
    """
    r = subprocess.run(
        ["git", "-C", str(work_dir), "-c", "commit.gpgsign=false", *args],
        capture_output=True,
        text=True,
        env=_git_env(),
        check=False,
    )
    if r.returncode != 0:
        raise RuntimeError(
            f"git {' '.join(args)} 실패 (exit {r.returncode}): {r.stderr.strip()[:300]}"
        )


def materialize_git_repo(work_dir: Path, spec: dict) -> None:
    """git.json 선언적 명세를 work_dir(temp fixture 작업 디렉토리)에 실체화한다.

    화이트리스트(ALLOWED_GIT_OPS) 밖의 op는 이 함수가 아니라 validate_git_spec이
    먼저 걸러야 정상이지만, 방어적으로 여기서도 거부한다(fail-closed, D-3) —
    검증을 거치지 않고 이 함수를 직접 호출하는 경로(단위 테스트 등)가 있을 수 있다.

    `write.path`는 반드시 _safe_join(work_dir, path)을 통과해야 한다 — 한 번
    resolve하고 그 결과(target)를 끝까지 쓴다. 검사와 사용이 각각 resolve하면
    그 틈이 TOCTOU다 (D-2, CLAUDE.md "설정값으로 경로를 만들면 반드시 봉쇄한다").

    실패하면 예외를 던진다 — 호출부(run_scenario)가 'error'로 분리해 어서션
    채점에 들어가지 않게 한다 (D-3 fail-closed).
    """
    for op_entry in spec.get("ops", []):
        op = op_entry.get("op")
        if op == "init":
            default_branch = op_entry.get("defaultBranch", "main")
            _run_git(work_dir, ["init", "-q", "-b", str(default_branch)])
        elif op == "write":
            raw_path = op_entry["path"]
            target = _safe_join(work_dir, raw_path)
            if target is None:
                raise RuntimeError(f"git.json write.path 경로 탈출 차단: {raw_path!r}")
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(op_entry["content"], encoding="utf-8")
        elif op == "add":
            _run_git(work_dir, ["add", *[str(p) for p in op_entry["paths"]]])
        elif op == "commit":
            _run_git(work_dir, ["commit", "-q", "-m", str(op_entry["message"])])
        elif op == "branch":
            _run_git(work_dir, ["branch", str(op_entry["name"])])
        elif op == "checkout":
            _run_git(work_dir, ["checkout", "-q", str(op_entry["ref"])])
        elif op == "tag":
            _run_git(work_dir, ["tag", str(op_entry["name"])])
        elif op == "merge":
            _run_git(work_dir, ["merge", "--no-edit", str(op_entry["ref"])])
        else:
            raise RuntimeError(f"git.json 알 수 없는 op '{op}' (화이트리스트 밖)")


# ---------------------------------------------------------------------------
# 채점 (deterministic assertions)
# ---------------------------------------------------------------------------


def _norm(s: str) -> str:
    # NFC 정규화 — NFD(자모 분해) 출력과 NFC expect 값의 코드포인트 불일치로 인한
    # 한글 false-red 방지 (재감사 R1/ATK-006). stdlib unicodedata — zero-debt.
    return unicodedata.normalize("NFC", s).lower()


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
                check=False,
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
        # MULTILINE 기본 적용 (W-018 S3 실측): 이게 없으면 '^'/'$'가 파일 전체의
        # 시작/끝에만 매치해, frontmatter처럼 구분선 뒤에 오는 필드를 앵커링하는
        # 흔한 패턴이 실제로 false-fail을 냈다(2026-08-26 실측). 인라인 `(?m)`
        # 워크어라운드가 이미 있던 시나리오는 중복 지정이라도 무해하다.
        ok = re.search(assertion["pattern"], content, re.MULTILINE) is not None
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
    if t in ("git_log_contains", "git_branch_exists", "git_status_clean"):
        return _check_git_assertion(assertion, t, fixture_dir)
    return False, f"알 수 없는 assertion type: {t}"


def _check_git_assertion(assertion: dict, t: str, fixture_dir: Path) -> tuple[bool, str]:
    """git 상태 어서션 3종 채점 (W-023 D-5). fixture_dir은 run_scenario가 넘기는
    실행 후 temp work_dir — materialize_git_repo가 이미 저장소를 만들어 둔 상태다.

    ref/branch는 author 제어 문자열이다. `-`로 시작하는 값은 git이 옵션으로
    오인할 수 있어(옵션 주입) 거부한다 — shell=True는 쓰지 않지만 리스트 인자
    자체가 신뢰 경계다.
    """
    expect_ok = bool(assertion.get("expect", True))
    timeout_s = int(assertion.get("timeout", 30))

    if t == "git_log_contains":
        ref = assertion.get("ref", "HEAD")
        if not isinstance(ref, str) or ref.startswith("-"):
            return False, f"git_log_contains — 유효하지 않은 ref(옵션 주입 의심): {ref!r}"
        args = ["log", "--format=%B", ref]
    elif t == "git_branch_exists":
        branch = assertion["branch"]
        if not isinstance(branch, str) or branch.startswith("-"):
            return (
                False,
                f"git_branch_exists — 유효하지 않은 branch(옵션 주입 의심): {branch!r}",
            )
        args = ["branch", "--list", "--format=%(refname:short)"]
    else:  # git_status_clean
        args = ["status", "--porcelain"]

    try:
        r = subprocess.run(
            ["git", "-C", str(fixture_dir), *args],
            capture_output=True,
            text=True,
            timeout=timeout_s,
            check=False,
        )
    except subprocess.TimeoutExpired:
        # 무한대기 하나가 전체 런을 크래시시키지 않게 fail로 강등 (ATK-003 관례).
        return False, f"{t} — git 명령 타임아웃"

    if r.returncode != 0:
        # 비-저장소(또는 다른 git 실패)는 항상 명시적 fail이다. "porcelain이 비어
        # 있으니 clean"으로 오독하면 저장소 없는 상태가 통과로 위장되는 거짓
        # green이 된다 — 이 분기가 그 오독을 막는다.
        return (
            False,
            f"{t} — git 명령 실패(비-저장소 가능성, exit {r.returncode}): "
            f"{r.stderr.strip()[:200]}",
        )

    if t == "git_log_contains":
        matched = re.search(assertion["pattern"], r.stdout, re.MULTILINE) is not None
    elif t == "git_branch_exists":
        branches = {ln.strip() for ln in r.stdout.splitlines() if ln.strip()}
        matched = assertion["branch"] in branches
    else:  # git_status_clean
        matched = r.stdout.strip() == ""

    ok = matched == expect_ok
    return ok, t + ("" if ok else f" — expect={expect_ok} actual={matched}")


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
            check=False,
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


def build_claude_command(agent: AgentDef, task: str) -> list[str]:
    """CLI 인자만 조립한다. 타임아웃은 호출부의 subprocess.run(timeout=)이 강제한다
    (여기서 받던 timeout 인자는 어디에도 쓰이지 않는 죽은 파라미터였다)."""
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

        if scenario.git_spec is not None:
            try:
                materialize_git_repo(work_dir, scenario.git_spec)
            # 실체화 실패 = error, 어서션 채점에 들어가지 않는다 (D-3 fail-closed).
            # 저장소 없는 상태로 조용히 넘어가 "검사했는데 통과"가 나오는 것이 최악이다.
            except Exception as e:  # noqa: BLE001
                return _result(
                    agent.name,
                    scenario,
                    "error",
                    [
                        {
                            "type": "git_materialize",
                            "ok": False,
                            "detail": f"git.json 실체화 실패: {e!r}",
                        }
                    ],
                    0.0,
                )

        cmd = build_claude_command(agent, scenario.task)
        start = time.time()
        try:
            r = subprocess.run(
                cmd,
                cwd=str(work_dir),
                capture_output=True,
                text=True,
                timeout=timeout,
                check=False,
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
            # 채점기 예외 = fail (크래시로 전체 런 유실 금지, ATK-003)
            except Exception as e:  # noqa: BLE001
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
    # 실행 경로에서는 필터 범위만 검증 — 무관한 WIP 시나리오가 건강한 시나리오의
    # 실행/dry-run을 막지 않게 (재감사 R1/ATK-002). 전체 검증은 --validate/verify-done §10.
    schema_errors = validate_all(
        agent_filter=agent_filter, scenario_filter=scenario_filter
    )
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
            cmd = build_claude_command(agent, sc.task)
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
        base_summary = {k: v for k, v in base_summary.items() if k == agent_filter}
    regressions = []
    for agent, cur in current_summary.items():
        base = base_summary.get(agent)
        if not base:
            continue
        if base.get("pass_rate") is None:
            regressions.append(
                f"{agent}: baseline 항목에 pass_rate 없음 (손상된 baseline)"
            )
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
    p.add_argument(
        "--report",
        metavar="REPORT_JSON",
        help="이미 기록된 리포트로 --compare 수행 (재실행하지 않음 — API 비용 0)",
    )
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)

    if args.validate:
        # --agent/--scenario는 --validate에도 적용된다. 예전에는 조용히 무시돼서,
        # "내 시나리오 하나만 검증"이 불가능했다 — 무관한 기존 시나리오의 결함이
        # 신규 생성 도구(eval-forge)의 판정을 오염시키는 원인이었다.
        errors = validate_all(agent_filter=args.agent, scenario_filter=args.scenario)
        if errors:
            for e in errors:
                print(f"  [FAIL] {e}")
            print(f"\n{len(errors)}건 검증 실패")
            return EXIT_FAIL
        print("[validate] 모든 시나리오 스키마 OK")
        return EXIT_PASS

    if args.report:
        # 이미 실행한 리포트를 재사용해 비교만 한다.
        #   --compare는 항상 전체를 **다시 실행**했다. 방금 전량 실행을 마친 직후에도
        #   후퇴 여부를 보려면 API 비용을 한 번 더 내야 했다(2026-08-23 릴리스 작업에서
        #   실측). 실행과 판정은 분리 가능한 관심사다.
        if not args.compare:
            print("[report] --report 는 --compare 와 함께 써야 한다.", file=sys.stderr)
            return EXIT_FAIL
        try:
            prev = json.loads(Path(args.report).read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as e:
            print(f"[report] 리포트 읽기 실패: {e}", file=sys.stderr)
            return EXIT_FAIL
        summary = prev.get("summary")
        if not summary:
            print(f"[report] summary 없음: {args.report}", file=sys.stderr)
            return EXIT_FAIL
        print_console_summary(summary)
        try:
            regressions = compare_baseline(
                summary, args.compare, agent_filter=args.agent
            )
        except (OSError, json.JSONDecodeError) as e:
            print(f"[compare] baseline 읽기 실패: {e}", file=sys.stderr)
            return EXIT_FAIL
        if regressions:
            print("\n[compare] baseline 대비 후퇴 감지:")
            for r in regressions:
                print(f"  - {r}")
            return EXIT_FAIL
        print("\n[compare] baseline 대비 후퇴 없음")
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
        if args.agent or args.scenario:
            # 부분 실행을 기준선으로 저장하면 이후 compare가 미포함 에이전트의
            # 회귀를 영구히 못 본다 — 침묵 커버리지 은닉 차단 (재감사 R1/ATK-001).
            print(
                "[eval] baseline 저장 거부 — 필터(--agent/--scenario)가 걸린 부분 실행은 기준선이 될 수 없음"
            )
        elif exit_code != EXIT_PASS:
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
