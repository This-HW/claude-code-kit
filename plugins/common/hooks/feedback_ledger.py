#!/usr/bin/env python3
"""
Feedback Ledger — validation/review에서 반복 발견되는 결함 패턴을 누적하고,
session-start가 주입할 digest를 제공하는 학습 루프의 SSOT (Spec 3 / W-007).

핵심 안티-부채 장치는 Claude 재량이 아니라 코드에 있다:
  - 상한(CAP): 엔트리 수 제한
  - 중복제거(dedupe): category+pattern 정규화 키로 upsert (freq++)
  - 감쇠(decay): 상한 초과 시 frequency·recency 하위 제거

사용:
  - session-start.py가 load_digest()를 import해 주입 (읽기)
  - auto-dev T-merge가 CLI로 upsert (쓰기):
      python3 feedback_ledger.py upsert <category> <severity> <pattern...>
      python3 feedback_ledger.py digest [K]

ledger 경로: <project_root>/docs/works/feedback/ledger.md
ledger 부재/파싱 실패 시 전 구간 무동작 (fail-open, opt-in).
"""

import fcntl
import os
import subprocess
import sys
import time
from contextlib import contextmanager
from datetime import date
from pathlib import Path

CAP = 50  # 최대 엔트리 수
DEFAULT_DIGEST_K = 5  # 주입할 상위 교훈 수
DIGEST_CHAR_CAP = 1200  # digest 문자 상한 (토큰 예산 보호)
VALID_CATEGORIES = {"lint", "security", "architecture", "test", "convention"}
VALID_SEVERITIES = {"critical", "high", "medium", "low"}
_LOCK_TIMEOUT_SECONDS = 5  # 락 획득 데드라인 — 초과 시 무락 진행(fail-open)

_HEADER = (
    "# Feedback Ledger\n\n"
    "> 자동 생성 (Spec 3 / W-007). validation·review에서 잡힌 결함 패턴 누적.\n"
    f"> 상한 {CAP}개, frequency·recency 기준 감쇠. 수동 편집 가능하나 형식 유지 필요.\n\n"
    "| id | category | pattern | frequency | last_seen | severity |\n"
    "| -- | -------- | ------- | --------- | --------- | -------- |\n"
)


def _project_root() -> Path:
    proj = os.environ.get("CLAUDE_PROJECT_DIR", "")
    if proj:
        return Path(proj)
    try:
        r = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if r.returncode == 0 and r.stdout.strip():
            return Path(r.stdout.strip())
    except Exception:
        pass
    return Path(".").resolve()


def ledger_path(root: Path | None = None) -> Path:
    root = root or _project_root()
    return root / "docs" / "works" / "feedback" / "ledger.md"


def _sanitize(pattern: str) -> str:
    """pattern을 ledger 셀에 안전하게 — '|'(테이블 구분자)·개행 제거, 공백 정규화.

    review 결함에 '|'(예: 'string | null', 'A | B')가 포함되면 마크다운 행이
    깨져 파싱 시 엔트리가 유실되고 dedupe가 무력화된다 (안티-부채 설계 붕괴 방지).
    """
    return " ".join(pattern.replace("|", "/").split())


def _normalize(category: str, pattern: str) -> str:
    """dedupe 키 — category + 소문자/sanitize된 pattern."""
    return f"{category}::{_sanitize(pattern).lower()}"


def parse_ledger(path: Path) -> list[dict]:
    """ledger.md 테이블을 파싱. 부재/실패 시 빈 리스트 (fail-open)."""
    entries: list[dict] = []
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except Exception:
        return entries
    for line in lines:
        s = line.strip()
        if not s.startswith("|"):
            continue
        cells = [c.strip() for c in s.strip("|").split("|")]
        if len(cells) < 6:
            continue
        if cells[0].lower() == "id" or set(cells[0]) <= {"-", ":"}:
            continue  # 헤더/구분선
        try:
            freq = int(cells[3])
        except ValueError:
            continue
        entries.append(
            {
                "id": cells[0],
                "category": cells[1],
                "pattern": cells[2],
                "frequency": freq,
                "last_seen": cells[4],
                "severity": cells[5],
            }
        )
    return entries


def _decay(entries: list[dict]) -> list[dict]:
    """상한 초과 시 frequency↑, last_seen↑(최근) 우선 보존, 하위 제거."""
    entries.sort(key=lambda e: (e["frequency"], e["last_seen"]), reverse=True)
    return entries[:CAP]


@contextmanager
def _ledger_lock(path: Path):
    """ledger read-modify-write 직렬화 (W-011).

    auto-dev가 T-review/T-security를 병렬 실행하며 둘 다 upsert를 호출하는
    시나리오가 스킬 설계에 내장돼 있다 — 락 없이는 lost-update(한쪽 기록 소실)와
    F-id 중복 채번이 발생한다. 별도 락 파일에 flock 배타 락을 잡는다.

    fcntl.flock은 darwin/linux 전용(kit 대상 플랫폼). 락 파일 생성/획득 실패 시
    무락으로 진행한다 — ledger는 학습 보조 데이터라 가용성 우선(fail-open).

    - 락 파일은 O_NOFOLLOW로 연다 — 심링크로 선점돼 있으면 열지 않는다(CWE-59).
    - 블로킹 flock 대신 LOCK_NB + 재시도(_LOCK_TIMEOUT_SECONDS 데드라인) —
      락 보유 프로세스가 정지해도 파이프라인이 무한 대기하지 않는다.
    """
    lock_file = path.with_name(path.name + ".lock")
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        fd = os.open(str(lock_file), os.O_WRONLY | os.O_CREAT | os.O_NOFOLLOW, 0o600)
        fh = os.fdopen(fd, "w")
    except Exception:
        yield
        return
    locked = False
    try:
        deadline = time.monotonic() + _LOCK_TIMEOUT_SECONDS
        while True:
            try:
                fcntl.flock(fh, fcntl.LOCK_EX | fcntl.LOCK_NB)
                locked = True
                break
            except OSError:
                if time.monotonic() >= deadline:
                    break  # 데드라인 초과 → 무락 진행(fail-open)
                time.sleep(0.05)
        yield
    finally:
        try:
            if locked:
                fcntl.flock(fh, fcntl.LOCK_UN)
        finally:
            fh.close()


def _write_ledger(path: Path, entries: list[dict]) -> None:
    """tmp 파일 작성 후 os.replace로 원자 교체 — 부분 쓰기 상태 노출 방지."""
    path.parent.mkdir(parents=True, exist_ok=True)
    rows = [
        f"| {e['id']} | {e['category']} | {e['pattern']} | "
        f"{e['frequency']} | {e['last_seen']} | {e['severity']} |"
        for e in entries
    ]
    tmp = path.with_name(f"{path.name}.tmp.{os.getpid()}")
    tmp.unlink(missing_ok=True)
    # O_EXCL|O_NOFOLLOW: 예측 가능한 tmp 경로가 심링크로 선점돼 있어도 따라가지 않는다.
    fd = os.open(str(tmp), os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(_HEADER + "\n".join(rows) + ("\n" if rows else ""))
        os.replace(tmp, path)
    finally:
        tmp.unlink(missing_ok=True)


def upsert(category: str, severity: str, pattern: str, root: Path | None = None) -> str:
    """결함 패턴을 추가하거나 기존 freq를 증가. 반환: 'added' | 'incremented'.

    parse→수정→write 전체가 _ledger_lock 안에서 실행된다 — 병렬 upsert에서도
    양쪽 기록이 모두 보존되고 F-id가 중복 채번되지 않는다.
    """
    if category not in VALID_CATEGORIES:
        category = "convention"
    # severity도 화이트리스트 강제 — pattern만 sanitize하는 비대칭은 '|'/개행 주입으로
    # 테이블 행을 깨뜨려 엔트리 유실·세션 주입 벡터가 된다 (ATK-006/M-2).
    # 화이트리스트 밖 값은 ''로 비워 기존 semantics 유지(빈 값 = 기존 severity 보존,
    # 신규 엔트리는 medium 기본값).
    severity = (severity or "").strip().lower()
    if severity not in VALID_SEVERITIES:
        severity = ""
    pattern = _sanitize(pattern)
    path = ledger_path(root)
    today = date.today().isoformat()
    with _ledger_lock(path):
        entries = parse_ledger(path)
        key = _normalize(category, pattern)
        for e in entries:
            if _normalize(e["category"], e["pattern"]) == key:
                e["frequency"] += 1
                e["last_seen"] = today
                e["severity"] = severity or e["severity"]
                _write_ledger(path, _decay(entries))
                return "incremented"
        # id 충돌 방지: 기존 최대 번호 + 1
        nums = [
            int(e["id"][2:])
            for e in entries
            if e["id"].startswith("F-") and e["id"][2:].isdigit()
        ]
        next_id = f"F-{(max(nums) + 1) if nums else len(entries) + 1:03d}"
        entries.append(
            {
                "id": next_id,
                "category": category,
                "pattern": pattern,
                "frequency": 1,
                "last_seen": today,
                "severity": severity or "medium",
            }
        )
        _write_ledger(path, _decay(entries))
        return "added"


def load_digest(top_k: int = DEFAULT_DIGEST_K, root: Path | None = None) -> str:
    """주입용 digest 문자열. ledger 부재/빈 경우 빈 문자열 (fail-open)."""
    entries = parse_ledger(ledger_path(root))
    if not entries:
        return ""
    entries.sort(key=lambda e: (e["frequency"], e["last_seen"]), reverse=True)
    top = entries[:top_k]
    lines = ["과거 validation에서 반복된 결함 — 구현/리뷰 시 우선 점검:"]
    for e in top:
        lines.append(
            f"  - [{e['category']}/{e['severity']}] {e['pattern']} (x{e['frequency']})"
        )
    digest = "\n".join(lines)
    if len(digest) > DIGEST_CHAR_CAP:
        digest = digest[:DIGEST_CHAR_CAP].rstrip() + " …"
    return digest


def _main(argv: list[str]) -> int:
    if not argv:
        print(
            "usage: feedback_ledger.py upsert <category> <severity> <pattern> | digest [K]",
            file=sys.stderr,
        )
        return 2
    cmd = argv[0]
    if cmd == "upsert":
        if len(argv) < 4:
            print("usage: upsert <category> <severity> <pattern...>", file=sys.stderr)
            return 2
        result = upsert(argv[1], argv[2], " ".join(argv[3:]))
        print(result)
        return 0
    if cmd == "digest":
        k = int(argv[1]) if len(argv) > 1 and argv[1].isdigit() else DEFAULT_DIGEST_K
        print(load_digest(k))
        return 0
    print(f"unknown command: {cmd}", file=sys.stderr)
    return 2


if __name__ == "__main__":
    try:
        sys.exit(_main(sys.argv[1:]))
    except Exception as e:  # fail-open: 학습 루프 오류가 본 작업을 막으면 안 됨
        print(f"[feedback_ledger] warning: {e}", file=sys.stderr)
        sys.exit(0)
