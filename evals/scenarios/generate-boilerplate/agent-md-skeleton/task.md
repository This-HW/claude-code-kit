# 과제

`agents/dev/existing-example.md`를 구조 레퍼런스로 삼아, 새 에이전트 보일러플레이트
`agents/dev/format-code.md`를 생성하라.

요구사항:
- frontmatter: `name: format-code`, `model: haiku`, `tools`에 `Read`와 `Bash` 포함.
- `description`에 `MUST USE when:` 트리거 문구 최소 1개.
- 본문에 `# 역할:` 섹션.
- 파일 끝에 표준 3-마커 델리게이션 시그널 블록(`---DELEGATION_SIGNAL---` /
  `TYPE:` / `---END_SIGNAL---`)을 포함한다 — 이건 보일러플레이트 자체가 담아야 할
  계약이지, 너의 최종 응답 형식과는 별개다.
- `existing-example.md`는 참조만 하고 수정하지 않는다.
