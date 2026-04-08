    ---
    work_id: "W-005"
    title: "auto-dev 리뷰 루프 강화"
    status: idea
    size: Medium
    priority: P2
    tags: [auto-dev, plan-task, review, quality]
    created_at: "2026-04-09T00:00:00Z"
    ---

    # auto-dev 리뷰 루프 강화

    ## 배경

    superpowers subagent-driven-development 패턴 분석 결과,
    우리 auto-dev에는 태스크 완료 후 2단계 리뷰 루프가 없음.

    ## 현재 vs 목표

    | | 현재 auto-dev | 목표 |
    |---|---|---|
    | 태스크 완료 후 | Stop hook prompt만 | spec reviewer + quality reviewer dispatch |
    | 이슈 발견 시 | 없음 | implementer 재수정 → 재검토 사이클 |
    | 컨텍스트 오염 | Agent가 전체 이력 공유 | 태스크별 fresh subagent |

    ## 개선 항목

    **auto-dev (skill.md):**
    - 각 태스크 완료 후 review-code 에이전트 자동 dispatch
    - DONE / DONE_WITH_CONCERNS / NEEDS_CONTEXT / BLOCKED 상태 신호 처리
    - spec compliance 확인 → quality 확인 순서 강제

    **plan-task (skill.md):**
    - Phase 3 Validation에 "spec compliance 확인" 단계 추가

    ## 설계 주의사항

    superpowers 패턴을 그대로 복사하지 않고
    우리 DELEGATION_SIGNAL 체계와 통합하는 설계 필요.
