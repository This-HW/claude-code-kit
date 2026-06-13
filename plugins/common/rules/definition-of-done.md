# Definition of Done — 완료 게이트 (Spec 6 / W-010)

"완료/끝/통과"는 **판단이 아니라 명령의 출력**이다. verification-before-completion의
확장 — 코드뿐 아니라 **완료 주장 자체**를 게이트한다.

## Iron Law of Completion

> "완료"를 주장하기 전:
> 1. `scripts/verify-done.sh`를 실행한다 (fresh run).
> 2. 출력을 전부 읽는다.
> 3. 기계 검사 FAIL이 하나라도 있으면 → "완료"라 하지 않는다. 실제 상태를 증거와 함께 보고.
> 4. 수동 DoD 항목은 명시적으로 attest(체크)한다 — 건너뛰면 "완료" 아님.
> **명령을 실행하지 않고 완료를 주장하는 것은 오류다.**

## 금지 어휘 규율

검증 전에는 "완료/끝났다/done/통과"를 쓰지 않는다. 대신 정확히 말한다:
"구현 + self-validation 완료, 미결: [홀리스틱 검증 / 문서 sync / 통합]".
"완료"라는 단어는 DoD 체크리스트가 전부 green일 때만 쓴다.

## Definition of Done (모든 Work 공통)

### 기계 검사 (verify-done.sh가 강제 — FAIL 시 완료 불가)
- [ ] JSON 유효 (모든 plugin.json + hooks.json + marketplace.json)
- [ ] plugin.json 필수 필드 + agent frontmatter + 금지 필드 (CI 동등)
- [ ] ruff clean
- [ ] pytest green
- [ ] 시크릿 스캔 clean
- [ ] 문서 카운트 sync (rules / skills 수가 문서 주장과 일치)
- [ ] stale 참조 0 (삭제된 컴포넌트가 활성 참조로 남지 않음)

### 수동 attest (사람/Claude이 증거와 함께 명시)
- [ ] 스펙·계획의 모든 항목 구현 (누락 없음 — spec ↔ 코드 대조)
- [ ] 적대적 리뷰 1회 (버그·엣지케이스·문서 sync 능동 탐색)
- [ ] Work 라이프사이클 상태 정확히 보고 (active/validation vs completed, 통합 여부 명시)
- [ ] CHANGELOG·README·CLAUDE.md 영향 반영

## 루프 종료 조건 (loop-engineering 연계)

배치 루프의 완료 조건 = **verify-done.sh green + 수동 DoD attest 완료 + Work 상태 해소**.
"마지막 스텝 도달"은 완료 조건이 아니다. (`rules/loop-engineering.md` 참조)
