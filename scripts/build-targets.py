#!/usr/bin/env python3
"""build-targets.py — 다중 하네스 타겟 매니페스트 생성기 (W-019 / S1-S2).

왜 필요한가
-----------
Codex·Antigravity는 각자 매니페스트 규격(`.codex-plugin/plugin.json`, `plugins/common/
plugin.json`)을 갖는다. 이 값(name·version·description 등)을 손으로 세 곳에 유지하면
`plugins/common/.claude-plugin/plugin.json`(기존 Claude Code SSOT)과 반드시 드리프트한다
— 이 레포가 doc-count·CHECKSUMS·MIRROR·AGENTS.md 게이트를 만든 것과 같은 실패 유형이다
(스펙 §5.2, HANDOFF).

이 스크립트는 SSOT(`plugins/common/.claude-plugin/plugin.json`)와 정책
(`packaging/targets.json`)만으로 타겟 매니페스트를 **재현 가능하게** 계산한다. 필드
매핑·문구는 전부 `packaging/targets.json`에서 읽는다 — 이 파일에 타겟별 값을
하드코딩하지 않는다.

설계 원칙 (export_harness.py와 같은 철학, W-017 선례 참고 — 복제하지 않고 참고함)
--------------------------------------------------------------------------------
1. **결정론적.** 같은 입력(SSOT + targets.json + 컴포넌트 디렉토리 실측)은 항상 같은
   바이트를 만든다 (키 정렬 + 고정 인코딩) — `--check`가 diff 대신 바이트 비교로
   드리프트를 잡을 수 있으려면 이게 전제다.
2. **`enabled`는 "지금 생성 대상" 하나만 의미한다.** S1에서는 `enabled`가 "로드맵에
   있다"와 "지금 만든다"를 겸하게 두었다가, `--write`가 매니페스트를 실제로 쓰면
   그 순간부터 `--check`가 "미생성=drift"로 막혀야 하는데 코드가 그걸 절차 제약(사람이
   "이번엔 쓰지 마라"를 지키는 것)으로만 표현하고 있었다 — S2에서 정책이 고쳐졌다
   (targets.json v1.1.0, `gate.requireGeneratedManifestPresent`). 이제 `enabled:true`는
   "이 실행에서 만들어야 하고, 없으면 드리프트"를 뜻한다. 아직 만들 준비가 안 된 타겟은
   정책에서 `enabled:false`로 두고 준비되면 승격한다(`_enabledPromotion` 참고) — 코드가
   아니라 정책 파일이 단계를 표현한다.
3. **`--check`는 항상 안전(읽기 전용)하지만, `enabled`인데 미생성이면 드리프트다.**
   "매니페스트가 없다"를 "아직 이 단계가 아님"으로 관대히 봐주면, 생성물을 실수로(또는
   악의로) 지워도 게이트가 green이 된다 — 이 레포가 게이트를 만드는 이유 자체를
   무효화하는 침묵 구멍이다(W-018과 같은 실패 유형, 2026-08-26 판정). "존재하지 않는
   파일"은 이제 "드리프트"와 동의어다. 아직 만들 준비가 안 된 타겟은 `enabled:false`로
   두어라 — 그러면 애초에 검사 대상에서 빠진다(원칙 2).
4. **SSOT 부재는 명확한 실패다.** 컴포넌트 디렉토리 부재("skills 없음")는 정상적인
   조건 분기이지만, SSOT 매니페스트 자체가 없으면 계산할 것이 없으므로 즉시, 명확한
   메시지로 실패한다(raw traceback 금지) — 이 도구가 잘못 배치됐다는 신호다.
5. **stdlib only, Python 3.9 floor.** 이 스크립트는 repo-local이라 소비자 환경에서
   돌 필요는 없지만, 이 레포의 게이트(verify-done.sh §4 python39-compat 관례)와 CI가
   3.9로 로드 가능성을 검사한다 — 그 관례를 따른다.

사용:
  python3 scripts/build-targets.py --check              # 전체 enabled 타겟 드리프트 검사
  python3 scripts/build-targets.py --check --only codex # 하나만
  python3 scripts/build-targets.py --write               # 전체 enabled 타겟 기록
  python3 scripts/build-targets.py --write --only codex # 하나만 기록

exit code:
  0 = 성공 (또는 --check 드리프트 없음)
  1 = --check 드리프트(미생성 포함) / SSOT 부재 / 알 수 없는 --only id / 정책 파싱 실패
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_POLICY = REPO_ROOT / "packaging" / "targets.json"


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


def load_ssot(repo_root: Path, policy: dict) -> dict:
    """`packaging/targets.json`의 `source.manifest`가 가리키는 SSOT 매니페스트.

    부재는 조용히 넘기지 않는다 — 계산할 입력 자체가 없다는 뜻이므로 즉시,
    raw traceback 없이 명확한 메시지로 실패한다.
    """
    rel = policy.get("source", {}).get("manifest")
    if not rel:
        raise PolicyError("정책의 source.manifest 필드가 없다.")
    p = repo_root / rel
    try:
        raw = p.read_text(encoding="utf-8")
    except OSError as err:
        raise PolicyError(
            f"SSOT 매니페스트를 읽지 못했다: {p}\n"
            f"  (packaging/targets.json의 source.manifest가 가리키는 파일이다) — {err}"
        ) from err
    try:
        return json.loads(raw)
    except json.JSONDecodeError as err:
        raise PolicyError(f"SSOT 매니페스트 JSON 파싱 실패: {p} ({err})") from err


def _detect_components(repo_root: Path, policy: dict) -> set[str]:
    """`source.pluginRoot` 아래 실재하는 컴포넌트 디렉토리 이름 집합.

    목록을 손으로 유지하지 않는다 — 존재 여부를 실측한다(정책 파일의 `_meta.detection`).
    """
    plugin_root = repo_root / policy["source"]["pluginRoot"]
    candidates = policy["source"]["_meta"]["componentDirs"]
    return {name for name in candidates if (plugin_root / name).is_dir()}


def _find_target(policy: dict, target_id: str) -> dict | None:
    for t in policy.get("targets", []):
        if t.get("id") == target_id:
            return t
    return None


def build_manifest(ssot: dict, target: dict, present_dirs: set[str]) -> dict:
    """타겟 하나의 플러그인 매니페스트 내용을 계산한다. 필드 매핑은 전부 target(정책)이 정한다.

    필드 하드코딩 없음: SSOT에서 뽑을 필드 이름(`requiredFields`/`optionalFields`),
    컴포넌트 필드 매핑(`componentFields`), 인터페이스 문구(`interface`),
    스키마 URL(`schemaUrl`)은 전부 `packaging/targets.json`에서 온다.
    """
    out: dict = {}
    if target.get("schemaUrl"):
        out["$schema"] = target["schemaUrl"]
    for field in target.get("requiredFields", []):
        if field not in ssot:
            raise PolicyError(
                f"타겟 '{target['id']}': SSOT 매니페스트에 필수 필드 '{field}' 없음"
            )
        out[field] = ssot[field]
    for field in target.get("optionalFields", []):
        if field in ssot:
            out[field] = ssot[field]
    for field, rel in target.get("componentFields", {}).items():
        if field in present_dirs:
            out[field] = rel
    if target.get("interface"):
        out["interface"] = target["interface"]
    return out


def build_marketplace(ssot: dict, target: dict, plugin_root_rel: str) -> dict | None:
    """타겟의 마켓플레이스 카탈로그(있는 경우만). codex 전용, antigravity는 None."""
    mk = target.get("marketplace")
    if not mk:
        return None
    entry: dict = {
        "name": f"{ssot['name']}-marketplace",
        "plugins": [
            {
                "name": ssot["name"],
                "source": {"source": "local", "path": f"./{plugin_root_rel}"},
                "policy": {"installation": "AVAILABLE", "authentication": "ON_INSTALL"},
            }
        ],
    }
    iface = target.get("interface", {})
    if iface.get("displayName"):
        entry["interface"] = {"displayName": iface["displayName"]}
    if iface.get("category"):
        entry["plugins"][0]["category"] = iface["category"]
    return entry


def _dumps(d: dict) -> str:
    """결정론적 직렬화 — 키 정렬 + 고정 개행. `--check`의 바이트 비교 전제."""
    return json.dumps(d, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


class Artifact:
    """타겟 하나가 만드는 파일 하나(매니페스트 또는 마켓플레이스)와 그 계산된 내용."""

    def __init__(self, target_id: str, kind: str, rel_path: str, content: dict):
        self.target_id = target_id
        self.kind = kind  # "manifest" | "marketplace"
        self.rel_path = rel_path
        self.content = content
        self.text = _dumps(content)


def artifacts_for(
    repo_root: Path, policy: dict, ssot: dict, target: dict
) -> list[Artifact]:
    present = _detect_components(repo_root, policy)
    out = [
        Artifact(
            target["id"],
            "manifest",
            target["manifestPath"],
            build_manifest(ssot, target, present),
        )
    ]
    mk = build_marketplace(ssot, target, policy["source"]["pluginRoot"])
    if mk is not None:
        out.append(
            Artifact(target["id"], "marketplace", target["marketplace"]["path"], mk)
        )
    return out


def _selected_targets(policy: dict, only: str | None) -> tuple[list[dict], list[str]]:
    """정책의 타겟 목록에서 이번 실행이 다룰 타겟들. (선택됨, 경고 메시지들)을 반환.

    `only`가 없으면 enabled:true 전체 — `--check`·`--write` 둘 다 이 범위를 쓴다(대칭).
    `only`가 있으면 그 하나만 — 존재하지 않으면 PolicyError(명확한 실패), enabled:false면
    빈 목록+경고(조용한 성공이 아니라 "왜 아무것도 안 됐는지"를 보여준다).
    """
    all_targets = policy.get("targets", [])
    if only is None:
        return [t for t in all_targets if t.get("enabled")], []
    t = _find_target(policy, only)
    if t is None:
        known = ", ".join(sorted(x["id"] for x in all_targets)) or "(없음)"
        raise PolicyError(
            f"--only '{only}' 는 정책에 없는 타겟 id다. 알려진 id: {known}"
        )
    if not t.get("enabled"):
        return [], [
            f"'{only}' 는 enabled:false — 건너뜀 ({t.get('_disabledReason', '사유 미기재')})"
        ]
    return [t], []


def cmd_check(repo_root: Path, policy: dict, only: str | None) -> int:
    """드리프트 검사. **항상 읽기 전용.** enabled인데 미생성이면 드리프트다(모듈 docstring 원칙 3)."""
    ssot = load_ssot(repo_root, policy)
    require_present = bool(
        policy.get("gate", {}).get("requireGeneratedManifestPresent")
    )
    targets, warnings = _selected_targets(policy, only)
    for w in warnings:
        print(f"[build-targets] i {w}")
    fail = False
    checked = 0
    for target in targets:
        for art in artifacts_for(repo_root, policy, ssot, target):
            p = repo_root / art.rel_path
            if not p.exists():
                if require_present:
                    print(
                        f"[build-targets] ✗ 미생성 — {art.rel_path} (enabled:true인데 생성물이 없다 → 드리프트)\n"
                        f"  → --write --only {art.target_id} 로 생성하라."
                    )
                    fail = True
                else:
                    print(f"[build-targets] · {art.rel_path} — 미생성 (skip)")
                continue
            checked += 1
            try:
                current = p.read_text(encoding="utf-8")
            except OSError as err:
                print(f"[build-targets] ✗ {art.rel_path} 읽기 실패: {err}")
                fail = True
                continue
            if current != art.text:
                print(
                    f"[build-targets] ✗ 드리프트 — {art.rel_path}\n  → --write --only {art.target_id} 로 재생성하라."
                )
                fail = True
    if fail:
        return 1
    if checked == 0:
        print("[build-targets] ✓ 검사 대상 없음 (enabled 타겟 없음)")
    else:
        print(f"[build-targets] ✓ 생성물 {checked}개 모두 SSOT와 일치")
    return 0


def cmd_write(repo_root: Path, policy: dict, only: str | None) -> int:
    """생성물 기록. enabled 전체(또는 `--only`로 좁힌 하나)를 쓴다(모듈 docstring 원칙 2)."""
    ssot = load_ssot(repo_root, policy)
    targets, warnings = _selected_targets(policy, only)
    for w in warnings:
        print(f"[build-targets] i {w}")
    written = 0
    for target in targets:
        for art in artifacts_for(repo_root, policy, ssot, target):
            p = repo_root / art.rel_path
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(art.text, encoding="utf-8")
            print(f"[build-targets] ✓ 기록: {art.rel_path}")
            written += 1
    if written == 0:
        print("[build-targets] i 기록 대상 없음 (enabled 타겟이 없거나 모두 제외됨)")
    return 0


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--policy",
        default=str(DEFAULT_POLICY),
        help="정책 파일 경로 (기본: packaging/targets.json)",
    )
    ap.add_argument("--repo-root", default=str(REPO_ROOT), help="레포 루트 (테스트용)")
    ap.add_argument(
        "--only",
        default=None,
        help="이 id 하나만 처리 (기본: enabled 전체 — --check·--write 동일)",
    )
    mode = ap.add_mutually_exclusive_group(required=True)
    mode.add_argument(
        "--check", action="store_true", help="드리프트만 검사, 기록하지 않음"
    )
    mode.add_argument("--write", action="store_true", help="생성물 기록")
    args = ap.parse_args(argv)

    repo_root = Path(args.repo_root)
    try:
        policy = load_policy(Path(args.policy))
    except PolicyError as err:
        print(f"[build-targets] ✗ {err}", file=sys.stderr)
        return 1

    try:
        if args.check:
            return cmd_check(repo_root, policy, args.only)
        return cmd_write(repo_root, policy, args.only)
    except PolicyError as err:
        print(f"[build-targets] ✗ {err}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
