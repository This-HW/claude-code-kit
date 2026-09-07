#!/usr/bin/env python3
"""derive-name.py — 이름 SSOT 파생 생성기 + 드리프트 검사 (D-3 / W-027 27-2).

왜 필요한가
-----------
`git grep -l "claude-code-kit"` 는 문서·사이트 전역에서 수십 개 파일을 찾는다.
개명 비용이 그 파일 수에 비례하는 것 자체가 부채다(설계 SSOT §1.3). `build-targets.py`
는 이미 매니페스트 3종을 `plugins/common/.claude-plugin/plugin.json` 의 `name` 에서
파생시킨다 — 이 스크립트는 같은 SSOT를 문서(`README.md`·`CLAUDE.md`)와 사이트 콘텐츠
(`site/content/`)에도 적용한다.

`build-targets.py` 와 다른 점 (의도적)
--------------------------------------
`build-targets.py` 의 산출물은 사람이 손으로 편집하지 않는 순수 생성물(JSON 매니페스트)
이라 SSOT + 정책만으로 **바이트 단위 전체 재생성**이 안전하다. 이 스크립트의 대상
(`README.md`·`CLAUDE.md`·`site/content/**`)은 반대로 사람이 상시 편집하는 산문이다.
전체를 템플릿에서 재생성하면 이름과 무관한 편집마다 템플릿도 같이 고쳐야 하는 **이중
SSOT**가 생긴다 — 이 킷이 반복해서 잡아온 결함 클래스 그 자체다(`docs/conventions/`).

그래서 이 스크립트는 파일 전체를 재생성하지 않는다. `packaging/name-targets.json` 의
`lastAppliedName`(직전 파생 실행 시점의 SSOT 이름)을 기억해 두고, **`lastAppliedName`
→ 현재 SSOT 이름의 리터럴 문자열 치환**만 수행한다. 산문의 나머지는 손대지 않는다.

알려진 한계 (탐지할 수 없는 것은 탐지한다고 주장하지 않는다 — warning-signal.md)
--------------------------------------------------------------------------------
리터럴 치환은 위치·문맥을 모른다. 대상 파일에 SSOT와 다른 이름이 수기로 잘못
박히는 사고(오타 등)는 `--check` 가 잡지 못한다. `--check` 가 탐지하는 것은 정확히
하나다: **SSOT 이름이 바뀌었는데 `--write` 를 안 돌린 상태** — 정책의
`lastAppliedName` 이 현재 SSOT 이름과 다르거나, 그 상태에서 대상 파일에 구 이름이
여전히 남아 있는 경우.

사용:
  python3 scripts/derive-name.py --check   # 드리프트만 검사, 기록하지 않음
  python3 scripts/derive-name.py --write   # 구 이름 → 현재 SSOT 이름으로 치환 + 정책 갱신

exit code: 0 = 성공(또는 드리프트 없음) / 1 = 드리프트·정책 오류
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_POLICY = REPO_ROOT / "packaging" / "name-targets.json"


class PolicyError(Exception):
    """정책·SSOT 파싱 실패 — main이 exit 1과 명확한 메시지로 변환한다."""


def load_policy(path: Path) -> dict:
    try:
        raw = path.read_text(encoding="utf-8")
    except OSError as err:
        raise PolicyError(f"정책 파일을 읽지 못했다: {path} ({err})") from err
    try:
        return json.loads(raw)
    except json.JSONDecodeError as err:
        raise PolicyError(f"정책 파일 JSON 파싱 실패: {path} ({err})") from err


def _resolve_in_repo(
    container_root: Path, rel_path: str
) -> tuple[Path | None, str | None]:
    """`rel_path`(정책 파일의 문자열)를 `container_root` 안으로만 한정해 해석한다.

    `scripts/build-targets.py::_resolve_in_repo` 와 시그니처가 **동일**하다(D-15:
    구현은 여러 벌, 계약만 하나 — 파라미터 이름까지 통일해 둔다). 공유 적대적 케이스
    표는 `scripts/tests/resolve_in_repo_contract.py`.
    """
    real = (container_root / rel_path).resolve()
    try:
        real.relative_to(container_root.resolve())
    except ValueError:
        return None, f"레포 루트 밖을 가리킨다 → {real}"
    return real, None


def load_ssot_name(repo_root: Path, policy: dict) -> str:
    src = policy.get("source", {})
    rel = src.get("manifest")
    field = src.get("field")
    if not rel or not field:
        raise PolicyError("정책의 source.manifest 또는 source.field 필드가 없다.")
    p, err = _resolve_in_repo(repo_root, rel)
    if p is None:
        raise PolicyError(f"SSOT 매니페스트 경로가 레포 밖을 가리킨다: {rel} ({err})")
    try:
        raw = p.read_text(encoding="utf-8")
    except OSError as err:
        raise PolicyError(f"SSOT 매니페스트를 읽지 못했다: {p} ({err})") from err
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as err:
        raise PolicyError(f"SSOT 매니페스트 JSON 파싱 실패: {p} ({err})") from err
    if field not in data:
        raise PolicyError(f"SSOT 매니페스트에 '{field}' 필드가 없다: {p}")
    return data[field]


def discover_targets(repo_root: Path, policy: dict) -> list[Path]:
    """정책의 `files`·`directories` 로부터 이름 파생 대상 파일 목록을 실측한다.

    `directories` 는 재귀적으로 `*.md` 전체를 스캔한다 — 대상을 손으로 나열하지
    않는다(D-23 원칙: 검사 대상이 아닌 것은 결코 red가 되지 않는다). 새 문서가
    추가되면 자동으로 파생 대상에 포함된다.
    """
    real_root = repo_root.resolve()
    out: list[Path] = []
    errs: list[str] = []
    for rel in policy.get("files", []):
        p, err = _resolve_in_repo(repo_root, rel)
        if p is None:
            errs.append(f"{rel}: {err}")
            continue
        out.append(p)
    for rel in policy.get("directories", []):
        d, err = _resolve_in_repo(repo_root, rel)
        if d is None:
            errs.append(f"{rel}: {err}")
            continue
        if not d.is_dir():
            continue
        for f in sorted(d.rglob("*.md")):
            real_f = f.resolve()
            try:
                real_f.relative_to(real_root)
            except ValueError:
                errs.append(f"{f}: 레포 루트 밖을 가리킨다(심링크 의심) → {real_f}")
                continue
            out.append(real_f)
    if errs:
        raise PolicyError("경로 탈출 차단 — " + "; ".join(errs))
    return sorted(set(out))


def cmd_check(repo_root: Path, policy_path: Path, policy: dict) -> int:
    ssot_name = load_ssot_name(repo_root, policy)
    last = policy.get("lastAppliedName")
    targets = discover_targets(repo_root, policy)
    fail = False
    missing = 0
    for t in targets:
        if not t.exists():
            print(
                f"[derive-name] ✗ 대상 파일 없음: {t.relative_to(repo_root.resolve())}"
            )
            fail = True
            missing += 1
    if last != ssot_name:
        print(
            f"[derive-name] ✗ 정책 lastAppliedName('{last}') ≠ SSOT 이름('{ssot_name}')"
            " — --write 로 파생을 다시 실행하라"
        )
        fail = True
        if last:
            for t in targets:
                if not t.exists():
                    continue
                text = t.read_text(encoding="utf-8")
                if last in text:
                    print(
                        f"  ✗ {t.relative_to(repo_root.resolve())} 에 구 이름 '{last}' 잔존"
                    )
    if fail:
        return 1
    print(
        f"[derive-name] ✓ 대상 {len(targets)}개 파일 모두 SSOT 이름('{ssot_name}')과 정합"
    )
    return 0


def _dumps(d: dict) -> str:
    return json.dumps(d, indent=2, ensure_ascii=False) + "\n"


def cmd_write(repo_root: Path, policy_path: Path, policy: dict) -> int:
    ssot_name = load_ssot_name(repo_root, policy)
    last = policy.get("lastAppliedName")
    targets = discover_targets(repo_root, policy)
    changed = 0
    if last and last != ssot_name:
        for t in targets:
            text = t.read_text(encoding="utf-8")
            new_text = text.replace(last, ssot_name)
            if new_text != text:
                t.write_text(new_text, encoding="utf-8")
                changed += 1
                print(f"[derive-name] ✓ 갱신: {t.relative_to(repo_root.resolve())}")
    if last != ssot_name:
        policy["lastAppliedName"] = ssot_name
        policy_path.write_text(_dumps(policy), encoding="utf-8")
        print(f"[derive-name] ✓ 정책 lastAppliedName → '{ssot_name}'")
    print(
        f"[derive-name] 파생 대상 {len(targets)}개 확인, {changed}개 파일 갱신,"
        f" SSOT 이름='{ssot_name}'"
    )
    return 0


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--policy",
        default=str(DEFAULT_POLICY),
        help="정책 파일 경로 (기본: packaging/name-targets.json)",
    )
    ap.add_argument("--repo-root", default=str(REPO_ROOT), help="레포 루트 (테스트용)")
    mode = ap.add_mutually_exclusive_group(required=True)
    mode.add_argument(
        "--check", action="store_true", help="드리프트만 검사, 기록하지 않음"
    )
    mode.add_argument("--write", action="store_true", help="파생 실행 + 정책 갱신")
    args = ap.parse_args(argv)

    repo_root = Path(args.repo_root)
    policy_path = Path(args.policy)
    try:
        policy = load_policy(policy_path)
        if args.check:
            return cmd_check(repo_root, policy_path, policy)
        return cmd_write(repo_root, policy_path, policy)
    except PolicyError as err:
        print(f"[derive-name] ✗ {err}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
