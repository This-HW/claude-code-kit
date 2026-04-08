# Planning Protocol Rules

NEVER implement based on assumption. ALWAYS verify against specs or ask the user.

## 모호함 등급 (P0~P3)

- **P0** — 데이터 무결성·보안·금융·핵심 비즈니스: **즉시 중단 + 질문**
- **P1** — UX 분기·비즈니스 디테일: 기본값 적용 후 나중에 확인
- **P2** — UI 디테일·엣지케이스: TODO 기록
- **P3** — 기술 선택(라이브러리·패턴): 자율 판단

## Dev → Planning 역위임 프로토콜

구현 중 기획 모호함 발견 시 아래 유형으로 분류하고 Planning으로 돌아간다:

- `P0_AMBIGUITY` — AskUserQuestion으로 사용자 확인
- `MISSING_SPEC` — 해당 명세 추가 (여정/규칙)
- `INFEASIBLE` — 대안 검토 후 사용자에게 보고

## 작업 규모 판단

- **Small**: 1개 모듈·1-3파일·~10h → 요구사항만
- **Medium**: 2-3개 모듈·4-10파일·20-50h → +사용자 여정
- **Large**: 4개+ 모듈·10파일+·50h+ → +비즈니스 로직

## Planning 완료 조건

ALWAYS ensure before handing off to Dev:

- P0 모호함 = 0
- 핵심 요구사항 정의·영향 범위 식별·리스크 분석 완료
- Medium+: 사용자 여정·주요 상태 전이·에러 처리 전략 포함
- Large+: 비즈니스 규칙·규칙 간 관계·예외 처리 포함

## P0 질문 형식

P0 발견 시: 즉시 중단 → AskUserQuestion → 답변 기록 → Planning 재진행

```
**맥락**: [상황]  **질문**: [구체적 질문]
**옵션**: 1. [A]  2. [B]
```

## 정보 전달 형식

**Planning → Dev:** 요구사항 요약 / 확인된 사항 / 사용자 여정(해당시) / 비즈니스 규칙(해당시) / 미결정 P1/P2 / 구현 권장사항

**Dev → Planning:** 유형(P0_AMBIGUITY|MISSING_SPEC|INFEASIBLE) / 발생 컨텍스트 / 발견한 문제 / 제안 옵션 / 필요한 결정

## 모호함 감지

NEVER use language: "~할 것 같다", "아마 ~", "보통은 ~", "임시로 ~"

ALWAYS use: "기획에 따르면", "사용자가 요청한", "확인 결과"
