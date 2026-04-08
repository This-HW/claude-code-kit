# Planning Check Rules

NEVER implement based on assumption. ALWAYS stop and verify specs first.

## 기획 확인이 필요한 상황

1. **요구사항 불명확**: "~할 것 같다", "보통은 ~" → 즉시 기획 문서 확인
2. **엣지 케이스**: 빈 값·오류·권한 없음 동작 → 기획서 확인, 없으면 사용자에게 질문
3. **다중 해석**: 표현이 모호한 요구사항 → 명확한 정의 확인
4. **비즈니스 로직**: 할인 계산·권한 체계·상태 전이 → 반드시 기획서/명세 기반 구현

## 기획 확인 워크플로우

1. 불확실성 감지 즉시 멈춤
2. `docs/planning/`, Notion MCP, Figma MCP, GitHub Issues 순으로 검색
3. 정보 부재 시 AskUserQuestion으로 옵션 A/B 제시
4. 결정 내용과 근거를 코드 주석에 기록

## 질문 형식 (기획 부재 시)

```
[기능명]에 대해 확인이 필요합니다.
상황: [현재 구현하려는 것]
불명확한 점: [구체적인 질문]
옵션: A) [해석 1]  B) [해석 2]
```

## 체크리스트

**구현 전:** 요구사항 문서 존재 / 성공·실패·로딩·빈 값 상태 정의 / 엣지 케이스 명시

**구현 중:** NEVER guess / NEVER deviate from spec / NEVER add unspecified features

**구현 후:** 구현 결과가 기획과 일치 / 모든 케이스가 기획대로 동작
