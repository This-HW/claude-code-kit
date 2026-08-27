#!/usr/bin/env python3
"""audit-version-strings.py — 낡은 버전 문자열 감사 (W-022 / R8).

`scripts/bump-version.sh`가 버전 갱신 직후 호출한다. 정책(정규식 패턴 + 제외
디렉토리/경로)의 단일 소스는 `packaging/version-audit.json`이다 — 값을 여기
하드코딩하지 않는다(`packaging/targets.json`과 같은 관례, "정책은 데이터다").

**이 도구는 보고 전용이다 — hard gate가 아니다.** exit 코드 관례(0=매치 없음,
1=매치 있음)는 이 레포의 다른 검사 스크립트와 통일해 두지만, `bump-version.sh`는
이 exit code로 자신을 중단시키지 않는다. 이유: 이 레포는 코드 주석에도 과거
사고를 버전 번호로 회고하는 관례가 있다(예: `.github/workflows/validate.yml`의
"2.12.0 실사고" — F-036/F-037 설명). "이 파일이 그 버전이라고 주장한다"와
"이 파일이 그 버전 시절 사고를 회고한다"는 문자열 매칭만으로 구분할 수 없다 —
완벽한 판별에는 의미 이해가 필요하다. 기계적 감사가 할 수 있는 최선은 "사람이
검토할 후보를 정확히 보여주는 것"이므로, 발견을 숨기지 않고 전부 출력하되
릴리스를 막지는 않는다. 확실히 역사 기록인 파일(CHANGELOG·specs·research·works)만
`excludePathPrefixes`로 미리 뺀다.

사용:
  python3 scripts/audit-version-strings.py --current 2.16.0
  python3 scripts/audit-version-strings.py --current 2.16.0 --repo-root /path/to/repo

exit code:
  0 = 낡은 버전 문자열 없음
  1 = 낡은 버전 문자열 후보 발견 (보고만 — bump-version.sh는 이걸로 중단하지 않는다)
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path

DEFAULT_POLICY = (
    Path(__file__).resolve().parent.parent / "packaging" / "version-audit.json"
)


def load_policy(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def find_stale(
    root: Path, policy: dict, current_version: str
) -> list[tuple[str, int, str]]:
    """`current_version`과 다른, 정책 패턴에 매치되는 문자열을 전부 찾는다.

    `excludeDirs`는 `os.walk`의 `dirnames`를 그 자리에서 잘라 **아예 내려가지
    않는다** — `.git` 같은 큰 디렉토리를 나열 후 걸러내는 것보다 빠르고,
    거기서 우연히 매치될 여지 자체를 없앤다.

    정책 패턴은 **캡처 그룹 1개**를 가져야 한다 — 순수 버전 숫자(예: `2.16.0`)만
    감싼 그룹. `v2.16.0`처럼 접두사가 붙는 표기(실제로 `CLAUDE.md`에 있다)도
    잡아야 하는데, 매치 전체(`v2.16.0`)를 `current_version`("2.16.0")과 비교하면
    **현재 버전을 가리키는 정당한 표기까지 전부 "낡음"으로 오탐**한다. 그룹만
    비교해 접두사 유무와 무관하게 순수 숫자만 대조한다.
    """
    pattern = re.compile(policy["pattern"])
    exclude_dirs = set(policy.get("excludeDirs", []))
    exclude_prefixes = tuple(policy.get("excludePathPrefixes", []))
    hits: list[tuple[str, int, str]] = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in exclude_dirs]
        for fname in filenames:
            f = Path(dirpath) / fname
            rel = f.relative_to(root).as_posix()
            if rel.startswith(exclude_prefixes):
                continue
            try:
                text = f.read_text(encoding="utf-8")
            except (UnicodeDecodeError, OSError):
                continue  # 바이너리/읽기불가 — 버전 문자열이 있을 수 없다고 취급
            for lineno, line in enumerate(text.splitlines(), start=1):
                for m in pattern.finditer(line):
                    if m.group(1) != current_version:
                        hits.append((rel, lineno, line.strip()))
    return sorted(hits)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--repo-root", type=Path, default=Path("."), help="레포 루트 (테스트용)"
    )
    ap.add_argument(
        "--policy", type=Path, default=DEFAULT_POLICY, help="정책 파일 경로"
    )
    ap.add_argument(
        "--current",
        required=True,
        help="현재(신규) 버전 — 이 값과 정확히 일치하는 매치는 낡은 것으로 세지 않는다",
    )
    args = ap.parse_args(argv)

    root = args.repo_root.resolve()
    try:
        policy = load_policy(args.policy)
    except (OSError, json.JSONDecodeError) as err:
        print(
            f"[audit-version] ✗ 정책 로드 실패: {args.policy} ({err})", file=sys.stderr
        )
        return 1
    try:
        pattern_groups = re.compile(policy["pattern"]).groups
    except re.error as err:
        print(
            f"[audit-version] ✗ 정책의 pattern이 정규식으로 컴파일되지 않는다: {err}",
            file=sys.stderr,
        )
        return 1
    if pattern_groups != 1:
        print(
            f"[audit-version] ✗ 정책의 pattern은 캡처 그룹이 정확히 1개여야 한다"
            f" (순수 버전 숫자만 감싼 그룹) — 지금은 {pattern_groups}개: {policy['pattern']!r}",
            file=sys.stderr,
        )
        return 1

    hits = find_stale(root, policy, args.current)
    if not hits:
        print(f"[audit-version] ✓ 낡은 버전 문자열 없음 (현재: {args.current})")
        return 0

    print(
        f"[audit-version] ! 낡은 버전 문자열 후보 {len(hits)}건 (현재: {args.current})"
        " — 과거 사고 회고 같은 정당한 인용이면 무시해도 된다:"
    )
    for rel, lineno, line in hits:
        print(f"    {rel}:{lineno}: {line}")
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
