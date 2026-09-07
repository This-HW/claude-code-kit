---
tier: core
portable: true
portable_reason: 브리프·보고 계약은 호스트 무관 — control-loop·자식 스킬이 공유하는 L0 계약(D-35)
---

# Delegation Contract

4블록: ①전제(선검증) ②범위(IN/OUT+완료기준) ③금지(명령수준:`--check`만)
④보고(下)

보고1행: `[역할] 완료 — <수치>, 커밋 <sha>, 테스트 <n passed>`
정규식: `^\[.+\] 완료 — .+, 커밋 [0-9a-f]{7,40}, 테스트 \d+ passed`

rc 파이프 금지 — 파일/pipefail, 근거없으면재요청.
병합sha=통합브랜치 최종.
