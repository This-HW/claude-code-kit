---
tier: core
portable: true
---

# Planning Check Rules

NEVER implement based on assumption. ALWAYS stop and verify specs first — 요구사항
불명확, 엣지 케이스(빈 값·오류·권한 없음), 다중 해석 가능한 표현, 비즈니스 로직
(할인·권한·상태 전이)은 반드시 기획서/명세 기반으로 확인한다.

## 기획 확인 워크플로우

불확실성 감지 즉시 멈춤 → `docs/planning/` → (설치돼 있으면) Notion·Figma MCP → GitHub
Issues 순으로 검색(MCP 없으면 건너뛴다 — 설치를 가정하지 않는다) → 정보 부재 시
사용자에게 옵션 A/B를 제시하고 답을 받는다(호스트가 제공하는 수단으로, 상황·불명확한
점·옵션을 명시) → 결정 내용과 근거를 코드 주석에 기록.

체크리스트 — 구현 전: 요구사항 문서·상태 정의(성공/실패/로딩/빈 값)·엣지 케이스 명시.
구현 중: NEVER guess/deviate from spec/add unspecified features. 구현 후: 결과가
기획과 전 케이스 일치.
