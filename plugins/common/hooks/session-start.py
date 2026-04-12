#!/usr/bin/env python3
"""
SessionStart hook: rules 주입 + active Work 상태를 additionalContext로 출력.
active Work가 없어도 rules는 항상 주입됨.

공식 output 형식:
  {"hookSpecificOutput": {"additionalContext": "<text>"}}
"""

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Optional

HOOK_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(HOOK_DIR))
try:
    from utils import get_project_root
except ImportError:

    def get_project_root() -> str:
        """Fallback: CLAUDE_PROJECT_DIR 또는 git toplevel."""
        proj = os.environ.get("CLAUDE_PROJECT_DIR", "")
        if proj:
            return proj
        result = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"], capture_output=True, text=True
        )
        return result.stdout.strip() if result.returncode == 0 else os.getcwd()


def parse_frontmatter(filepath: Path) -> dict:
    """Work 파일 YAML frontmatter 파싱 (외부 의존성 없음)."""
    fm: dict = {}
    try:
        lines = filepath.read_text(encoding="utf-8").splitlines()
    except Exception:
        return fm
    if not lines or lines[0].strip() != "---":
        return fm
    for line in lines[1:]:
        if line.strip() == "---":
            break
        if ":" in line:
            k, _, v = line.partition(":")
            fm[k.strip()] = v.strip().strip('"').strip("'")
    return fm


def parse_task_map(progress_path: Path) -> list:
    """
    progress.md Task Map 파싱.
    방어적 파싱 — 공백 변화, 컬럼 너비 변화에 강건함.
    반환: [{"id", "title", "desc", "status", "blocked_by"}, ...]
    """
    tasks = []
    if not progress_path.exists():
        return tasks

    try:
        lines = progress_path.read_text(encoding="utf-8").splitlines()
    except Exception:
        return tasks

    in_task_map = False
    header_found = False

    for line in lines:
        stripped = line.strip()

        if stripped == "## Task Map":
            in_task_map = True
            continue

        # 다른 ## 섹션 진입 시 종료
        if in_task_map and stripped.startswith("## ") and stripped != "## Task Map":
            break

        # ### 서브섹션 진입 시 헤더 리셋 (새 테이블 시작)
        if in_task_map and stripped.startswith("### "):
            header_found = False
            continue

        if not in_task_map or not stripped.startswith("|"):
            continue

        cells = [c.strip() for c in stripped.strip("|").split("|")]

        # 헤더 행 감지 — "Task ID" 포함 행은 항상 스킵
        if any("Task ID" in c for c in cells):
            header_found = True
            continue

        if not header_found:
            continue  # 구분선 등 헤더 전 행 스킵

        # 구분선 스킵 (---|---|...)
        if all(set(c.replace("-", "").replace(":", "").strip()) <= {""} for c in cells):
            continue

        if len(cells) < 4:
            continue

        # placeholder 행 스킵 — T- 로 시작하지 않는 id (예: "(plan-task 완료 후 ...)")
        if not cells[0].startswith("T-"):
            continue

        # 컬럼: Task ID | 제목 | 설명 | 상태 | blockedBy
        if len(cells) >= 5:
            tasks.append(
                {
                    "id": cells[0],
                    "title": cells[1],
                    "desc": cells[2],
                    "status": cells[3].strip(),
                    "blocked_by": cells[4].strip(),
                }
            )
        else:
            tasks.append(
                {
                    "id": cells[0],
                    "title": cells[1],
                    "desc": "",
                    "status": cells[2].strip(),
                    "blocked_by": cells[3].strip(),
                }
            )

    return tasks


def summarize_work(work_dir: Path) -> Optional[str]:
    """Work 하나의 요약 문자열 생성."""
    md_files = sorted(work_dir.glob("W-*.md"))
    if not md_files:
        return None

    fm = parse_frontmatter(md_files[0])
    work_id = fm.get("work_id", work_dir.name)
    title = fm.get("title", work_dir.name)
    phase = fm.get("current_phase", "?")

    tasks = parse_task_map(work_dir / "progress.md")
    done = sum(1 for t in tasks if "✅" in t["status"])
    total = len(tasks)

    in_progress = [t for t in tasks if "⏳" in t["status"]]

    # blockedBy 없는 pending Task (완료 Task에만 의존하거나 의존 없음)
    done_ids = {t["id"] for t in tasks if "✅" in t["status"]}
    pending_unblocked = []
    for t in tasks:
        if "⬜" not in t["status"]:
            continue
        deps = [
            d.strip()
            for d in t["blocked_by"].split(",")
            if d.strip() and d.strip() != "-"
        ]
        if all(d in done_ids for d in deps):
            pending_unblocked.append(t)

    lines = [f"[{work_id}] {title}"]
    lines.append(f"  Phase: {phase} | 완료: {done}/{total} Tasks")

    if in_progress:
        lines.append("  진행 중:")
        for t in in_progress[:2]:
            lines.append(f"    ⏳ {t['id']}: {t['title']}")

    if pending_unblocked:
        lines.append("  실행 가능 (블록 없음):")
        for t in pending_unblocked[:3]:
            lines.append(f"    ⬜ {t['id']}: {t['title']}")

    return "\n".join(lines)


ALWAYS_RULES = [
    "agent-system.md",
    "tool-usage-priority.md",
    "planning-protocol.md",
    "planning-check.md",
    "agent-delegation-chain.md",
    "code-quality.md",
    "ssot.md",
    "mcp-usage.md",
]


def load_rules(plugin_root: Path, include_task_resume: bool) -> str:
    """
    plugin_root/rules/ 디렉토리의 rule 파일들을 읽어 섹션 문자열로 반환.
    파일이 없거나 읽기 실패해도 무시 (fail-open).
    반환값: '=== RULES ===' 섹션 전체 문자열 (파일 없으면 빈 문자열)
    """
    rules_dir = plugin_root / "rules"
    if not rules_dir.exists():
        return ""

    rule_files = list(ALWAYS_RULES)
    if include_task_resume:
        rule_files.append("task-resume.md")

    sections = []
    for filename in rule_files:
        rule_path = rules_dir / filename
        try:
            content = rule_path.read_text(encoding="utf-8").strip()
        except Exception:
            continue
        sections.append(content)

    if not sections:
        return ""

    return "=== RULES ===\n" + "\n---\n".join(sections) + "\n=== END RULES ==="


def main() -> None:
    project_root = Path(get_project_root())
    works_active = project_root / "docs" / "works" / "active"

    # Active Work 스캔
    active_work_text = ""
    has_active_work = False

    if works_active.exists():
        active_dirs = sorted(d for d in works_active.iterdir() if d.is_dir())
        if active_dirs:
            summaries = []
            for work_dir in active_dirs:
                summary = summarize_work(work_dir)
                if summary:
                    summaries.append(summary)

            if summaries:
                has_active_work = True
                # 상태 표시만 — 사용자가 재개 의사를 표현할 때까지 Task 재생성 안 함
                active_work_text = (
                    "=== ACTIVE WORK ===\n"
                    + "\n\n".join(summaries)
                    + "\n\n"
                    + "작업 재개 시 progress.md Task Map을 읽고 Task 재생성 알고리즘을 실행하세요.\n"
                    + "(규칙: task-resume.md 참고)\n"
                    + "=== END ACTIVE WORK ==="
                )

    # Rules 주입
    plugin_root_env = os.environ.get("CLAUDE_PLUGIN_ROOT", "")
    rules_text = ""
    if plugin_root_env:
        rules_text = load_rules(
            Path(plugin_root_env), include_task_resume=has_active_work
        )

    # context 조합
    parts = []
    if active_work_text:
        parts.append(active_work_text)
    if rules_text:
        parts.append(rules_text)

    context = "\n\n".join(parts) if parts else ""
    print(
        json.dumps(
            {
                "hookSpecificOutput": {
                    "hookEventName": "SessionStart",
                    "additionalContext": context,
                }
            }
        )
    )


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        # SessionStart는 fail-open — 오류가 세션을 막으면 안 됨
        print(f"[claude-code-kit] session-start warning: {e}", file=sys.stderr)
        print(
            json.dumps(
                {
                    "hookSpecificOutput": {
                        "hookEventName": "SessionStart",
                        "additionalContext": "",
                    }
                }
            )
        )
    sys.exit(0)
