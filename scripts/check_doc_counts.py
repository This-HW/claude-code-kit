#!/usr/bin/env python3
"""문서 카운트 drift 가드 — 단일 소스 (F-023).

verify-done.sh §6(로컬 DoD 게이트)과 .github/workflows/validate.yml(CI)이 **둘 다
이 스크립트를 호출**한다. 카운트 검사 로직을 bash/CI에 각각 두면 반드시 드리프트한다
(원장 F-023) — 정의와 검사 전부를 여기 한 곳에만 둔다.

정의 (SSOT):
  - agent  = plugins/*/agents/ 아래 frontmatter `name:` 보유 .md
             (경로 기반 전체 .md 카운트는 보조 문서가 끼면 부풀므로 사용하지 않음)
  - skill  = plugins/*/skills/**/SKILL.md
  - rule   = plugins/common/rules/*.md

시맨틱 (verify-done §6 계승):
  - 문서에 카운트 주장이 없으면 skip(통과) — 주장 없음은 drift가 아님.
  - 단 README "What's Included" 표 행은 **부재 자체가 실패** — 값이 바뀌면 검사가
    조용히 skip-green되는 self-disable 패턴 차단 (재감사 R2/ATK-001, F-022).

exit 0 = 전부 일치 / exit 1 = drift 또는 표 행 부재.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

OK = "\033[32m✓\033[0m"
NG = "\033[31m✗\033[0m"


def count_actuals(root: Path) -> dict:
    agents = 0
    for f in root.glob("plugins/*/agents/**/*.md"):
        try:
            if re.search(r"^name:", f.read_text(encoding="utf-8"), re.MULTILINE):
                agents += 1
        except OSError:
            pass
    return {
        "agents": agents,
        "skills_common": len(list(root.glob("plugins/common/skills/**/SKILL.md"))),
        "skills_total": len(list(root.glob("plugins/*/skills/**/SKILL.md"))),
        "rules": len(list(root.glob("plugins/common/rules/*.md"))),
    }


def check_claim(root: Path, rel: str, pattern: str, actual: int, label: str) -> bool:
    """첫 매치의 숫자를 실측과 대조. 주장 없음 = skip(통과)."""
    p = root / rel
    if not p.exists():
        print(f"{OK} {label}: 파일 없음 (skip)")
        return True
    m = re.search(pattern, p.read_text(encoding="utf-8"))
    if m is None:
        print(f"{OK} {label}: 주장 없음 (skip)")
        return True
    claim = int(m.group(1))
    if claim == actual:
        print(f"{OK} {label}: {actual} 일치")
        return True
    print(f"{NG} {label}: 문서 주장 {claim} ≠ 실제 {actual} ({rel})")
    return False


def check_included_table(root: Path, a: dict) -> bool:
    """README 'What's Included' 표의 claude-code-kit 행 — 부재 = 실패 (anti self-disable)."""
    p = root / "README.md"
    if not p.exists():
        print(f"{NG} README.md 없음")
        return False
    row = None
    for line in p.read_text(encoding="utf-8").splitlines():
        if re.match(r"^\|\s*.?claude-code-kit.?\s*\|", line):
            row = line
            break
    if row is None:
        print(f"{NG} README What's Included 표 행을 찾지 못함 (형식 변경? 게이트 갱신 필요)")
        return False
    nums = re.findall(r"\d+", row)
    ok = True
    if len(nums) < 2:
        print(f"{NG} README 표 행에서 숫자 2개(agents/skills)를 찾지 못함: {row!r}")
        return False
    if int(nums[0]) != a["agents"]:
        print(f"{NG} README 표 에이전트 셀: {nums[0]} ≠ 실제 {a['agents']}")
        ok = False
    else:
        print(f"{OK} README 표 에이전트 셀: {a['agents']} 일치")
    if int(nums[1]) != a["skills_common"]:
        print(f"{NG} README 표 스킬 셀: {nums[1]} ≠ 실제 {a['skills_common']}")
        ok = False
    else:
        print(f"{OK} README 표 스킬 셀: {a['skills_common']} 일치")
    return ok


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--root", type=Path, default=Path("."), help="repo root (테스트용)")
    args = ap.parse_args()
    root = args.root

    a = count_actuals(root)
    ok = True
    # 루트 CLAUDE.md / README.md (verify-done §6 계승 패턴)
    ok &= check_claim(root, "CLAUDE.md", r"rules \((\d+)\)", a["rules"], "rules(CLAUDE.md)")
    ok &= check_claim(root, "README.md", r"rules \((\d+)\)", a["rules"], "rules(README)")
    ok &= check_claim(root, "CLAUDE.md", r"skills \((\d+)\)", a["skills_common"], "common skills(CLAUDE.md)")
    ok &= check_claim(root, "CLAUDE.md", r"agents \((\d+)\)", a["agents"], "agents(CLAUDE.md)")
    ok &= check_claim(root, "README.md", r"(\d+) skills", a["skills_total"], "total skills(README)")
    ok &= check_claim(root, "README.md", r"(\d+) agents", a["agents"], "agents(README)")
    ok &= check_included_table(root, a)
    # 배포 플러그인 README (2026-07-29 외부 검증에서 stale 발견된 파일 — 이후 상시 검사)
    ok &= check_claim(root, "plugins/common/README.md", r"(\d+) agents", a["agents"], "agents(common/README)")
    ok &= check_claim(root, "plugins/common/README.md", r"(\d+) skills", a["skills_common"], "skills(common/README)")

    if ok:
        print(f"{OK} doc counts: {a['agents']} agents / {a['skills_common']} skills / {a['rules']} rules — 문서와 일치")
        return 0
    print("→ 문서의 수기 카운트가 실측과 drift. 문서를 갱신하세요.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
