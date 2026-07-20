# Changelog

All notable changes to claude-code-kit are documented here.

Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

---

## [2.11.0] — 2026-07-20

### Added — Interoperability as a first-class goal (memory MCP interop)

- **`using-claude-code-kit` 스킬**: "메모리 MCP와 함께 쓸 때" 섹션 신설 — 세션에
  메모리형 MCP 툴(`recall`/`search`/`remember` 류, 서버 이름 불문)이 있으면
  **계획 전 recall → 완료 후 remember** 패턴으로 활용, 없으면 완전 스킵
  (fail-open, consumer-first). 특정 서버 가정·하드코딩 없음.
- **CLAUDE.md**: 상호운용성을 명시적 설계 목표로 승격 — never assume / never
  conflict / leverage generically 3원칙. MCP 활용 가이드는 스킬에만, 에이전트
  `tools:` 허용목록엔 금지(기존 규칙 재확인).
- **README**: "Works with your MCPs" 섹션 추가 — 메모리 MCP(basic-memory,
  agentcairn, 사내/개인 서버 등)와의 일반화된 결합 방식 안내.

### Added — review: 복잡도 하이브리드 가드 (advisory 전용)

- **`review` 스킬 0.5단계 신설**: 결정론 flag(`ruff check --select C901`, mccabe
  기본 임계 10) → review-code 에이전트가 **모듈 경계·IN/OUT 계약 분리 타당성**
  관점으로만 판단하는 2단 하이브리드. 복잡도 수치·줄수 단독 리젝 금지, 응집적이면
  flag 기각(근거 명시). 어떤 경우에도 리뷰를 실패시키지 않는 advisory —
  전역 blocking lint(E,F)·stop-validator 무접촉(소비자 기존 코드 차단 없음),
  ruff 미설치 시 스킵(fail-open). CLI `--select`가 프로젝트 lint 설정과 독립임을
  실측 검증(select=E,F 프로젝트에서 C901 flag + blocking 경로 통과 확인).

## [2.10.5] — 2026-07-17

### Fixed — protect-sensitive: env 템플릿 과차단 예외 (소비자 보고, W-016)

- **env 템플릿 허용**: `.env.example` / `.env.sample` / `.env.template` / `.env.dist`
  (중간 변형 `.env.local.example` 포함)를 정확-suffix 매치(`ENV_TEMPLATE_RE`)로만
  보호 대상에서 제외 — placeholder 전용·git-tracked이 정상인 템플릿 파일의
  Read/Edit까지 차단하던 false positive 해소 (소비자 프로젝트 보고).
  `.env.example.backup` 같은 뒤붙임 변형과 실제 `.env*`는 계속 차단.
- **symlink 방어 무회귀 (ATK-007)**: 예외를 `check_protected()` 내부에 배치해
  main()의 원본 경로 → realpath 2단 검사가 예외에도 일관 적용 — 템플릿 이름의
  symlink가 실제 `.env`를 가리키면 realpath 검사가 차단 (회귀 테스트 고정).
- **예외 역이용 완화 (best-effort)**: 템플릿 경로에 대한 쓰기(Edit/MultiEdit/Write/
  NotebookEdit) 콘텐츠를 형식-확정 패턴(`HIGH_CONFIDENCE_CONTENT_PATTERNS`:
  sk-/sk-ant-/sk_live·test_/AIza/AKIA/ghp_/PEM/JWT/DB URI 등)으로 스캔해 실제 형식의
  시크릿 기록을 차단. placeholder(`API_KEY=your_key_here`)는 통과 — 휴리스틱 할당
  패턴은 이 스캔에서 제외. 형식-확정 패턴 밖 시크릿의 **최종 방어선은 커밋 시
  gitleaks**(이 스캔은 best-effort 사전 차단). message/broadcast 스캔은 기존 전체
  패턴 그대로 (동작 불변, 합집합 구성 테스트로 고정).
- **적대적 검증 반영**: 예외 정규식 좌측 `(^|/)` 앵커(ATK-001 —
  `credentials.env.example`류 보호 파일명 재개방 차단), 쓰기 스캔 payload `str()`
  강제(ATK-002 — 비-str payload의 fail-open 우회 차단), 스캔의 realpath 게이트
  (symlink 경유 쓰기 우회 차단).
- 회귀 테스트 30건 추가 — protect-sensitive 64건, hooks 스위트 220 passed.

## [2.10.4] — 2026-07-09

### Fixed — MCP 이식성: MCP는 스킬에, 배포 에이전트는 빌트인만 (소비자 환각 차단)

- **research-external**: MCP(Context7/Exa/Tavily)를 자기 능력으로 지시하던 죽은 산문 제거 —
  이 에이전트의 `tools:` allowlist는 MCP를 부여하지 않으므로 실행 불가한 지시였다. MCP
  리서치는 `web-research` 스킬로 위임하도록 명시.
- **web-research 스킬**: MCP 부재/미인증/타임아웃 시 WebSearch/WebFetch로 폴백하는 규율
  추가 — MCP 상시존재 가정 제거, 결과 날조 금지.
- **rules/mcp-usage.md**: "MCP는 스킬에 산다" 원칙 명문화 — 배포 에이전트 `tools:`에
  `mcp__*` 금지(미설치 project-scoped MCP는 환각/hard-fail, CC #13898). "ALWAYS MCP"
  문구를 "가용 시 우선 + 폴백"으로 완화(MCP Servers·Required Rules 절 포함).
- **저장소 전역 정합**(적대 리뷰 CONDITIONAL 리메디에이션): `implement-api.md`의 죽은
  Context7 지시 제거→스킬 위임, `docs/architecture/rules/mcp-usage.md` 미러 동기화(에이전트
  frontmatter MCP 배선 예시·부재 `db-tunnel.sh` 참조·`NEVER WebFetch` 제거), `planning-check.md`
  Notion/Figma MCP 조건부화, agent-system 미러 스테일 카운트(16 skills/13 rules) 정정.
- **verify-done.sh 산문 가드 추가**: 에이전트 frontmatter뿐 아니라 description/body가 MCP를
  자기 능력으로 지시하는 것도 검출(frontmatter-only 가드의 맹점 보완).

### Added — 거버넌스: 소비자-우선 north-star + 이종 fan-out 규율

- **CLAUDE.md · README**: "Who this is for" 설계 north-star + Contributing 체크리스트 게이트
  (소비자 환경 작동 검증 · 에이전트 allowlist `mcp__*` 금지) — 소비자 cwd에서 깨지는
  설계를 리뷰에서 차단.
- **rules/agent-system.md**(+ docs/architecture 미러): 적대적 병렬 검증은 general-purpose
  복제가 아니라 이종 전용 에이전트(review-code + devils-advocate + verify-integration)
  fan-out 규율 추가 — 관점 다양성(편향 방지) 보존.
- feedback ledger에 general-purpose-over-specialized 사건 frequency=1 기록 — 인포스먼트
  (신규 에이전트/훅)는 재발 2회+에서만 재검토(과적합 방지).

## [2.10.3] — 2026-07-07

### Added — 태스크 잔존의 기계적 재발 감지 (프롬프트 규율의 안전망)

- session-start `load_stale_tasks()` 신설 + 재감사 A/B(H1·M7·L6) 전건 반영:
  - **스코프 분류**: 세션↔프로젝트를 `~/.claude/projects/<slug>/<sess>.jsonl`로 판정 —
    이 프로젝트 잔존만 상세(예시 3건, 첫 보고 1줄 요약 규정), 타 프로젝트는 집계
    1줄(능동 보고 금지) — "판단 불가 조건" 노이즈 제거 (재감사 B/M1·M2)
  - **인젝션 방어**: subject는 비신뢰 텍스트 — 제어문자/개행 제거·`===` 마커 무력화·
    인용 인코딩, 방어 프레이밍을 예시 앞에 배치, E2E 무력화 실증 (재감사 A/H1)
  - **나이 필터**(기본 14일, `CKKIT_STALE_TASKS_DAYS`) + mtime 최신 우선 선별 +
    세션/파일 상한 — best-effort 명시 (재감사 A/M3, B/M2)
  - 설계 게이트 대기(brainstorming) 태스크는 정상 in_progress 예외 명시 + task-resume에
    고아 태스크 재개/정리 경로 신설 (재감사 B/M3)
  - fail-open, 현재 세션 제외(디렉토리명=session_id 실측 검증), `CKKIT_STALE_TASKS=0`
- verify-done CHECKSUMS 게이트를 **집합 동등성**으로 강화(신규 파일 맹점 제거) +
  shasum/sha256sum 폴백 (재감사 A/M2·L7). hooks.json session-start timeout 10s.
- CLAUDE.md 릴리스 체크리스트에 CHECKSUMS 재생성 명문화("드리프트 감지기" 성격 포함).
- (기록 보완) ba531b2 native-absorption 갱신: 8행 watch 격상 + DoD·self-improve 2행
  추가 — 원장 규칙의 CHANGELOG 기록 의무 사후 이행 (재감사 B/L5).
- E2E 실증: 첫 실행에서 기존 잔존 15건/4세션 감지. 테스트 8케이스, 총 240 green.

---

## [2.10.2] — 2026-07-07

### Fixed — 태스크 잔존 버그 (마지막 태스크 미완료 마킹)

증상: 작업이 끝나도 마지막 태스크가 in_progress/pending으로 영구 잔존 (사용자 보고,
~/.claude/tasks/ 실측으로 재현 확인 — 잔존 파일이 남은 세션은 전부 이 패턴).

근본 원인: "마지막 태스크"는 내용이 보고/마무리라 마킹 시점이 턴 종료와 겹치는데,
- auto-dev T-merge가 `TaskUpdate(completed)`를 **사용자 보고 뒤**(4단계)에 배치 —
  보고 후 턴이 사용자 입력 대기로 끝나 마킹이 증발 (순서 결함)
- brainstorming은 완료 마킹 지시 자체가 없음, plan-task는 마지막 [Planning] 태스크
  마감 지시 부재
- 이를 잡는 상시 규율/게이트 부재

수정:
- auto-dev: T-merge 마킹을 사용자 보고 **앞**으로 재배치 + 잔존 태스크 정리 지시
- brainstorming: 항목별 즉시 마킹 + 마지막 항목은 "invoke 직전 마킹" 규약 신설
- plan-task Step 4: 핸드오프 전 [Planning]/[Brainstorm] 잔존분 일괄 마감 (Step 4-0)
- definition-of-done(상시 주입 룰): "Task 마감 규율" 신설 — 보고·핸드오프·대기로
  턴을 끝내기 직전 TaskList 정리, 마킹이 보고보다 먼저. ad-hoc 태스크에도 적용.
  단 미완 항목의 completed 위장 금지(false-green 방지) 명시

---

## [2.10.1] — 2026-07-07

### Fixed — 5-차원 적대적 재감사 (v2.10.0 배치 전체 fresh-context 재검증)

릴리스 직후 5개 병렬 리뷰어(evals 심층·훅/게이트 무결성·스킬/문서 정합·보안·live 사이트)로
재감사 — 발견 H3·M15·L16 전건 반영 (+오탐 2건 증거 기각).

**게이트 false-green 차단:**
- evals `--baseline` × `--agent/--scenario` 필터 조합 시 저장 거부 — 부분 기준선이
  커버리지를 침묵 은닉하던 경로 차단. 손상 baseline(pass_rate 누락)은 크래시 대신 회귀 플래그.
- verify-done §6 표-셀 검사의 매직 `33` 커플링 제거(에이전트 수가 바뀌면 검사가 조용히
  skip-green되던 self-disable) + 에이전트 수 검증 신설. §3 ruff를 evals/까지 확장.
- CI: pytest exit 5(수집 0)를 green→fail로 (테스트 소실은 실패), ruff 스텝 신설,
  `permissions: contents: read` 명시.
- discover가 `.ruff_cache` 등 로컬 캐시를 유령 시나리오로 취급해 게이트를 무너뜨리던 것 스킵.

**MUST MATCH 단일소스화:**
- auto-dev T-merge 마커 스니펫이 지문 로직을 복제하던 것(예외절·타임아웃 3곳 드리프트
  실재) → stop-validator 모듈을 로드해 `_worktree_state_hash()` 직접 호출 — 물리적 단일 소스.
- stop-validator eval 제외를 `/fixture/` 세그먼트로 축소 + run.py --validate가
  "시나리오 루트 .py 금지"·"fixture 모듈 스코프 위험 호출(os.system 등) 금지"를 구조로 강제.

**보안/공급망:**
- self-improve에 입력 신뢰 경계 명시(ledger 텍스트는 데이터, 내장 지시 실행 금지 —
  프롬프트 인젝션 방어) + 승인-전 eval 실행 예외의 정직 고지.
- GitHub Actions 전부 커밋 SHA 핀, Hugo 바이너리 sha256 검증, gitleaks 오탐 근원 제거
  (fixture 식별자가 private-패턴 룰의 `_quant` 부분열과 충돌 → `total_count`로 리네임).

**채점 견고성:** `_norm` NFC 정규화(한글 false-red), `CKKIT_EVAL_TIMEOUT` 비정수 폴백,
validate를 실행 경로에선 필터 범위로(무관 WIP가 dry-run까지 막던 것).

**문서/발견성:** 세션 주입 Skill Trigger Map·README Key Skills에 native-watch/self-improve
등재, gitignore된 Work ID 인용 → spec 경로로 정규화, spec의 self-improve 원설계에
"구현 시 조정" 주석, 사이트 en 죽은 링크 6건(live 404 실측)·en 페이지 한국어 UI 문자열·
x-default hreflang·meta 절단 수정, evals/README 주의사항(리포트 민감정보·.bak 1세대) 추가.

**Notes:** 테스트 232 green(+7), 오탐 기각 2건(baseline 미추적 주장 — ef858ee로 반증,
CLAUDE.md 2.3.0 스테일 주장 — 9806d1c에서 기수정).

---

## [2.10.0] — 2026-07-07

W-014 toolkit 개선 배치 (spec: `docs/specs/2026-07-07-toolkit-improvement-batch.md`).
각 Work마다 적대적 리뷰(A~E) 수행 — 발견 전건(HIGH 9 · MEDIUM 19 · LOW 18) 반영 후 머지.

### Added

- **Agent Evals 하네스** (`evals/` + `scripts/run-evals.sh` + verify-done §10) — 핵심
  에이전트(review-code·fix-bugs·implement-code) 행동 회귀를 기계 검증. deterministic
  채점 우선, LLM-judge 보조, API 부재 시 명시적 SKIPPED(exit 2).
- **`/native-watch` 스킬** + `docs/native-absorption.md` SSOT 대조표 — 네이티브 흡수
  감시 루틴화 (스케줄링은 네이티브 `/schedule` 위임).
- **`/self-improve` 스킬** — feedback ledger 반복 결함을 에이전트/스킬 정의 개선
  diff로 제안. evals 후퇴 없음 + 사용자 승인 없이는 적용 불가(HARD-GATE).
- **사이트 다국어(ko+en)** — about 아키텍처 페이지 승격, getting-started 신규, SEO
  front matter. 프로젝트 홍보 전용(개인 콘텐츠 배제, `docs/personal/` gitignore).

- **implement-code 계약 강화** — DELEGATION_SIGNAL을 모든 응답의 마지막 블록으로
  무조건 출력하도록 명시 (evals가 잡은 첫 실회귀: 헤드리스 실행 간헐 누락 flake).
- **stop-validator 검증 스코프** — `evals/scenarios/`(의도적 red fixture 데이터)를
  lint/pytest 스코프에서 제외 (+ auto-dev T-merge 마커 스니펫 MUST MATCH 동기화).

### Changed

- README/CLAUDE.md/marketplace-submission.md — `claude-plugins-community` 카탈로그
  **등재 완료** 반영(2026-07-07 확인), 두 설치 경로(공식 카탈로그 ~1일 전파 / 개인
  마켓플레이스 즉시) 문서화. 스킬 카운트 14 → 16.

---

## [2.9.3] — 2026-07-03

### Fixed — 3-차원 적대적 재감사 (P0 false-green + 정직성 + 훅 fail-open)

2.9.2 상태를 3개 fresh-context 리뷰어(checklist·게이트·훅보안)로 재감사해 나온 결함 수정.

**게이트 false-green:**
- **P0 — verify-done §5 시크릿 스캔 false-green**: `... | head -1 | grep -q`가 매치 다수(≈16KB+)일 때
  상류 grep을 SIGPIPE(141)로 죽여 `pipefail`이 파이프라인을 비정상 종료로 만들고, 시크릿이 있어도
  green으로 빠졌다. 결과를 변수로 수집(`$(... || true)`)해 `[ -n ]` 판정으로 교체. 2000줄 매치 DETECTED 실증.

**훅 보안(fail-open/우회):**
- **protect-sensitive content-scan fail-open (P1)**: 구조화(list/dict) message payload에 `re.search`가
  TypeError→blanket except→exit0(스캔 우회). `str()` 강제 직렬화로 차단.
- **protect-sensitive 검사 순서 (P2)**: syscall 없는 원본 경로 검사를 realpath(널바이트 등에 ValueError)
  **앞으로** 이동 — syscall 실패로 게이트가 건너뛰어지지 않게.
- **secret 경로 heuristic (P2)**: `mysecret.txt`/`api_secret.json`이 안 걸리던 lookbehind 제거,
  `secrets?(?=[._/\d-]|$)`로 교체(`secretary` 제외 유지).
- **stop-validator false-green (P1)**: bash `.py` write 대상 추출이 따옴표(`> "x.py"`)·변수·`python -c`·xargs를
  놓쳤다. 따옴표 strip + **세션이 .py를 bash로만 쓰고 신뢰가능한 Edit .py가 없으면 전체 dirty 검증으로
  폴백**(미검증 green보다 오검증 red) + NotebookEdit `notebook_path` 반영.
- **훅 hang 방지 (P2)**: Pre/PostToolUse에 `timeout` 추가, protect-sensitive·auto-format에 stdin `isatty` 가드.

**checklist 동시성/정직성:**
- **cmd_pass TOCTOU (P2)**: verify를 락 밖에서 도는 동안 항목 verify가 바뀌면 stale 명령으로 flip하던 것 →
  락 안에서 verify 문자열 재확인 후 다르면 flip 거부.
- **cmd_verify lost-update (P2)**: 전체 스냅샷을 덮어써 동시 pass/신규 항목을 잃던 것 → 락 안에서 재읽기 후 id별 병합.
- **F1 정직성 (P1)**: docstring이 gate-time staleness를 "해소"로 과장 → 자동 게이트(§8)는 여전히 status(원장)를
  읽고 `verify`는 opt-in임을 명시(해소 아님, 재증명 도구 제공).
- **killpg docstring/테스트**: "grandchild 안 남김" → setsid/데몬화는 못 잡는 best-effort로 정정, F6 테스트를
  실제 grandchild 정리 검증으로 강화.

**게이트 견고성:**
- verify-done §9 test-ratchet: fresh/단일커밋 저장소에서 base를 HEAD로 폴백(워킹트리 삭제 포착),
  test 디렉토리 레이아웃(`tests/`·`spec/`) 인식. §7 stale-ref가 중첩 경로(`scripts/sub/x.sh`)도 검사.

### Notes
- 테스트 6건 추가(총 179 pytest green), verify-done exit 0(13/0), P0/P1 E2E 스모크 검증.
- 수용된 경계(문서화): Bash를 통한 시크릿 **읽기/유출**은 path-based 훅이 막지 않음(gitleaks는 커밋만).
  feedback_ledger digest의 persistent-injection 여지는 후속 하드닝 후보(P2).

---

## [2.9.2] — 2026-07-03

### Fixed — 2.9.1 감사가 남긴 잔여 2건 마저 정리 (F6 버그 + F1 트레이드오프)

2.9.1에서 "정직한 한계"로 남겼던 checklist 잔여 2건을 애매함 없이 닫음.

- **F6 (verify subprocess grandchild leak, 버그)**: `cmd_pass`가 verify를 `shell=True`로
  실행하면서 (1) 타임아웃 시 shell만 죽고 손자 프로세스가 누수되고, (2) 락을 verify 실행
  600s 내내 점유했다. → `_run_verify` 헬퍼로 분리: `start_new_session=True`로 새 프로세스
  그룹에 띄우고 타임아웃 시 `killpg`로 그룹 전체 종료(손자 정리, exit 124). verify는 **락 밖**에서
  실행하고 flip(재읽기→수정→쓰기)만 락 안에서 수행.
- **F1 (gate-time staleness, 트레이드오프)**: `passes`는 flip 시점 기록이라 `status`는 재검증을
  안 한다. 자동 재검증은 재귀·side-effect(재배포 등) 부채라 기본화하지 않되, **opt-in
  `checklist verify <work_dir>` 명령**을 추가 — 전 항목 verify를 재실행해 회귀한 stale-true를
  false로 되돌린다(gate-time 재증명). `status`=빠른 원장, `verify`=재증명.

### Notes
- 테스트 4건 추가(verify 통과/stale-demote/부재 + F6 타임아웃 killpg), 173 pytest green,
  verify-done exit 0. blog 포스트 "초록불은 거짓말을 한다" 말미를 정리 완료 상태로 갱신.

---

## [2.9.1] — 2026-07-03

### Fixed — 6-차원 적대적 감사 반영 (보안·게이트 false-green·거버넌스)

프로젝트 전체를 6개 fresh-context 적대적 리뷰어로 감사해 나온 결함을 수정. 특히
**게이트가 실패를 green으로 보고하던 false-green** 계열과 시크릿 차단 우회를 우선 처리.

**보안:**
- **protect-sensitive 매처 우회 (P1)**: `hooks.json` PreToolUse 매처가 `Edit|Write|...`라
  `MultiEdit`/`NotebookEdit`를 안 잡아 `MultiEdit(".env")`로 시크릿 파일 차단이 우회됐다.
  매처에 `MultiEdit|NotebookEdit` 추가 + `notebook_path` 경로도 검사(auto-format 매처도 동일 보정).
- **문서 정정**: protect-sensitive는 "커밋/내용의 시크릿 차단"이 아니라 **경로 기반**
  (`.env`/키) 차단이며 Bash·commit은 안 잡는다(그건 gitleaks+pre-commit)고 CLAUDE.md/README 정정.

**게이트 false-green:**
- **checklist `status` 손상/빈 파일 (P1)**: `echo '[]' > checklist.json` 또는 손상 파일이
  exit 3(skip)이 되어 완료 게이트를 조용히 통과했다. 존재하는 파일이 빈/비-리스트/파싱실패면
  FAIL(1), 진짜 부재만 3(skip)으로 구분.
- **verify-done §8 helper 부재 (P1)**: `checklist.py`가 없으면 미완 checklist가 있어도 green이던
  fail-open을 fail-closed로.
- **test-ratchet §9 (P1)**: `merge-base main HEAD`가 `main`에서 HEAD와 같아져(=빈 diff) 커밋된
  테스트 삭제를 못 보던 blind-spot + main/merge-base 부재 시 조용한 green을 수정 —
  origin/main→HEAD~1 폴백 + 실패 시 [warn]. `--`/`++` 내용줄을 파일헤더로 오인하던 파서도 `@@` 상태추적으로 수정.
- **stop-validator `_bash_may_write_py` (P1)**: 동시에 너무 좁고(`python gen.py`·cp/shutil 놓침)
  너무 넓던(`cmd > log`·`grep open( x.py` 오탐으로 세션 스코핑 무력화) blanket 휴리스틱을 폐기 →
  ① 명시적 .py write 대상만 정밀 추출 + ② git-untracked .py union(opaque codegen 포착)으로 교체.

**거버넌스·always-injected 룰 죽은 참조:**
- `agent-system.md`: 없는 에이전트 참조(schedule-task/trigger-pipeline/notify-team/track-sla)
  `background:true` 섹션 제거, "check plugin.json agent list"→auto-discovery, 위임 시그널을
  canonical 4-type(agent-delegation-chain.md SSOT)로 정렬, diagnose/monitor 예시 제거.
- `mcp-usage.md`: 존재하지 않는 `scripts/db-tunnel.sh` 참조 제거.
- 에이전트: `design-services` `disallowedTools`에 `Task` 추가, `notify-team` 유령 위임
  (analyze-tech-debt/manage-api-versions) → `TASK_COMPLETE`, 누락된 `maxTurns` 21개 에이전트에 추가.

**setup/CI:**
- `setup.sh`: `_check_version`의 `return 1`이 `set -e`로 설치를 중단(fresh-env brick)하던 것 +
  버전 파싱 파이프라인 abort → `|| true`로 자문(advisory)화.
- `validate.yml`: pytest 스텝이 `|| echo`로 **테스트 실패도 green**이던 no-op 수정
  (exit 5=no-tests만 skip, 그 외 실패는 CI 실패). 금지필드에 `hooks` 추가(문서 주장과 일치).

**재발 방지 (신규 게이트):**
- `verify-done.sh §7`: hooks.json뿐 아니라 **rules/agents의 `scripts/*.sh` 참조 실재도 검증** —
  always-injected 룰의 죽은 스크립트 참조가 매 세션 주입되던 문제를 기계로 차단.

### Notes
- 신규 rule 0 → count 변동 없음. 테스트 4건 추가(checklist 손상 2 + bash-target 2), 169 pytest green,
  verify-done exit 0. 모든 P1 E2E 스모크 검증(MultiEdit 차단·corrupt checklist FAIL).
- 정직한 잔여 한계: checklist `passes`는 flip 시점 기록이라 gate-time 재검증은 안 함(F1) —
  '연속 모니터'가 아닌 '완료 원장'으로 문서화. verify subprocess의 grandchild leak(F6)은 P2로 잔류.

---

## [2.9.0] — 2026-07-03

### Added — Durable Executor Checklist & 기계 완료 게이트 (W-013)

장기·다세션 루프 실행에서 "무엇이 검증되어 완료인가"를 모델 주장이 아닌 **기계로**
판정한다. 네이티브 Task는 `~/.claude/tasks/<session-UUID>/` 세션 스코프라 세션 경계를
못 넘는다 — kit은 루프 엔진을 재발명하지 않고(네이티브 위임), 네이티브가 없는 것 —
durable 상태 파일 + 결정론 완료 게이트 + 검증 계약 — 만 얇게 추가한다.

- **`checklist.py` + `scripts/checklist.sh` 신설**: 완료 상태의 단일 authority
  (`docs/works/<W>/checklist.json`, 스키마 `{id, description, acceptance, verify, passes}`).
  `pass <id>`는 모델 주장으로 flip하지 않고 항목의 `verify` 명령을 **실제 실행해 exit 0**일
  때만 `passes:true`로 전환한다(self-mark 차단). W-011 flock/os.replace 원자 쓰기 재사용.
- **`verify-done.sh`에 게이트 2건 추가**: (8) active Work checklist에 `passes:false`
  잔존 시 FAIL·부재 시 스킵, (9) test-ratchet — diff에서 test/assert가 `TEST-RATCHET-ALLOW`
  마커 없이 순감소하면 FAIL(산문 규율이 아닌 기계 체크).
- **인라인 규율(신규 rule 파일 없음 — ssot 준수)**: `loop-engineering.md`에 재앵커
  (요약 아닌 planning-results 원본 재독) + idle 감지(커밋 0 = 종료); `auto-dev/SKILL.md`에
  durable executor 규율(미완 1항목/iter, verify 통과 전 passes 금지, 상태 쓰기 메인 세션 소유);
  `review-code.md`에 검증 독립성(작성자≠검증자 fresh context 충족, cross-family judge 미충족 갭 정직 표기).

### Fixed — Bash 편집 .py의 Stop 검증 커버리지 갭 (W-012 #3)

- **`stop-validator._session_edited_files`**: 기존엔 Edit/Write 계열 tool_use만 스코프에
  잡아, 루프 에이전트가 Bash(heredoc/sed/tee/redirect)로 쓴 `.py`는 검증을 우회했다.
  transcript에서 Bash `.py` 쓰기가 감지되면 스코프를 '불완전'으로 보고 **전체 dirty .py
  폴백**(오검증은 안전, 미검증은 위험) → 미검증 코드 유입 차단. 읽기 전용 Bash(.py 대상
  pytest/ruff/grep)는 폴백 트리거 안 함.

### Notes

- 신규 rule 0개 → rules count/CHECKSUMS 변동 없음. checklist.py는 CLI 헬퍼(feedback_ledger
  선례)라 hooks.json 미등록. 테스트 25건 추가(checklist 13 + stop-validator Bash 커버리지 12 계열).
- 설계·적대적 리뷰 과정: `docs/specs/2026-07-03-durable-executor-discipline.md`(v2, 3중 리뷰),
  리서치: `docs/research/2026-07-long-running-loop-agents.md`.

---

## [2.8.0] — 2026-07-02

### Added — 병렬 worktree 병합 프로토콜 (W-011)

kit은 "worktree 격리 진입" 정책은 있었지만 "병합 복귀" 규범이 없었다 — 격리 없이는
충돌이 즉시 나고, 격리만 있으면 충돌이 병합 시점으로 이연될 뿐이다. 이번 릴리스가
복귀 프로토콜을 명문화한다.

- **`rules/parallel-worktree.md` 신설** (rules 1.3.0): 검증 그린 후에만 ExitWorktree,
  순차 병합 원칙, dispatch 전 파일 소유권 확인, 충돌 시 `git-workflow`로
  NEED_USER_INPUT 에스컬레이션, worktree 안 `docs/works/**` 갱신 금지.
- **에이전트 8개 정비**: `optimize-logic`에 `isolation: worktree` + `maxTurns` +
  `disallowedTools: [Task]` 추가(커버리지 누락). `implement-api`·`generate-boilerplate`·
  `sync-docs`에 `ExitWorktree` 툴 추가(격리 진입만 있고 복귀 수단이 없었음). 파일 수정
  에이전트 8개 전부에 "Worktree 복귀 프로토콜" 섹션 추가.
- **auto-dev Step 2에 worktree 병합 절차 명시**: 하나 병합 → 검증 → 다음(동시 병합
  금지), 동일 지점 충돌 2회 = 청크 재설계 신호.
- **유령 참조 정리**: 존재하지 않는 `write-ui-tests`를 CLAUDE.md/README/
  `rules/agent-system.md`의 isolation 목록에서 제거하고 실제 8개 에이전트로 교체.
- **리서치 노트 게시**: `docs/research/2026-07-harness-loop-engineering.md` —
  하네스/루프 엔지니어링 2026 중반 지형도(개념 계보·3대 루프 구현체·검증 원칙·
  병렬 도구 생태계·kit 대조).

### Fixed — 병렬 세션/프로세스 레이스 컨디션 3건 (W-011)

- **stop-validator 크로스세션 오염**: retry 카운터가 repo 해시로만 키가 만들어져
  같은 프로젝트의 병렬 세션들이 서로의 카운터를 덮어쓰거나 리셋할 수 있었다 —
  stdin `session_id`로 세션 스코프 격리(부재 시 기존 동작). 스코프 적용은 모든
  reset 경로(`stop_hook_active` 가드 포함)보다 선행한다. auto-dev 검증 마커는
  이름 대신 **내용(작업트리 상태 해시 = HEAD + diff + porcelain)** 으로 유효성을
  판정 — 병렬 세션의 마커, 검증 후 변경된 상태, untracked 추가에서는 스킵하지
  않으며 빈 내용 마커(구버전 touch)는 무효다. 회귀 테스트 9개 추가.

### Security — /tmp 예측 경로 하드닝 (W-011)

- 마커/카운터/락/ledger 쓰기 전부 **심링크 비추적**으로 전환(CWE-59/377): `O_NOFOLLOW`
  tmp 파일에 쓴 뒤 `os.replace`(rename은 목적지 심링크 자체를 교체) — 공유 호스트에서
  예측 가능한 `/tmp` 경로를 심링크로 선점해 임의 파일을 덮어쓰는 공격 차단.
  심링크 마커는 내용을 읽지 않고 즉시 무효 처리.
- 시간(TTL) 기반 마커 스킵 제거 — 파일 생성만으로 Stop 검증을 30분 우회할 수 있던
  경로 폐쇄. ledger `severity`는 화이트리스트(critical/high/medium/low) 강제 —
  `|`/개행 주입으로 테이블 행을 깨고 세션 컨텍스트에 위조 행을 주입하는 벡터 차단.
- ledger 락은 `LOCK_NB` + 5초 데드라인(초과 시 무락 진행) — 락 보유 프로세스 정지로
  파이프라인이 무한 대기하지 않는다. `work.sh`는 claim 후 실패 시 trap으로
  `.claimed` 고아 항목을 롤백해 Work 번호 영구 소각을 방지.

### Fixed — 2차 적대적 리뷰(멀티에이전트) 지적 반영 (W-011)

첫 리뷰 라운드가 놓친 결함을 멀티에이전트 워크플로우 리뷰(27 검증 finding)가
잡아냈다. 특히 검증 마커 지문의 untracked 우회는 1차에서 "닫았다"고 본 것이 실제론
남아 있던 케이스다.

- **검증 마커 지문 재설계(F1/F2/F3)**: 지문을 `HEAD + git status --porcelain`에서
  **검증 스코프(get_modified_py_files) 각 .py의 내용 sha256**으로 교체. porcelain은
  untracked 파일의 '경로'만 반영해, 이미 untracked인 .py의 내용을 마커 생성 후
  수정하면 지문이 그대로여서 미검증 코드가 스킵될 수 있었다(실제 검증 우회). 내용
  해시로 그 우회를 닫고, 동시에 .py 아닌 파일(review-results.md) 변경엔 지문이
  불변이라 마커가 불필요하게 무효화되지도 않는다. `git rev-parse HEAD` 실패 시 ''
  반환(보수적 무효)로 훅/스니펫 정합.
- **상태 파일을 사용자 전용 디렉토리로(F4/F10)**: 마커·retry 카운터·ledger 락을
  world-writable `/tmp` 예측 경로에서 `$TMPDIR/claude-{uid}`(0700)로 이전 — 타
  사용자가 심링크 없이 평범한 파일 선점만으로 카운터를 오염(cap 상시 발동)하거나
  유효 마커를 심는 공격을 차단. ledger 락이 저장소 트리를 벗어나 커밋 오염·
  porcelain 교란도 해소. stop-validator 엔트리포인트에 fail-safe try/except 추가
  (타 소유 파일 접근 예외로 훅이 죽지 않고 통과).
- **마커 소비 원자화(F8)**: `exists→read→unlink`를 `os.rename` claim으로 교체 —
  같은 체크아웃의 두 병렬 Stop 훅 중 한쪽만 마커를 가져가고 나머지는 정상 검증.
- **병합 정책 모순 해소(F5)**: "메인이 순차 병합"(강제 불가) 규범을 제거하고 "순차
  **dispatch**"(메인이 실제 통제 가능)로 재정의. 병렬 안전은 dispatch 시점의 파일
  disjoint 분리로 확보 — 각 에이전트는 green이면 스스로 ExitWorktree.
- **feedback ledger 심링크 보존(F7)**: `os.replace`가 심링크를 파괴하던 것을
  realpath 대상 교체로 바꿔 사용자의 공유 원장 심링크를 보존. 락 타임아웃 시
  stderr 경고(F9)로 lost-update 재발을 관측 가능하게.
- **work.sh 중복 가드 비브릭(F6)**: 동일 Work ID 다중 매치 시 exit 1로 모든
  하위명령을 막던 것을 경고 + 결정론적 첫 항목 선택으로 완화(중복 정리용 명령까지
  막던 문제 해소). cross-clone은 로컬로 직렬화 불가함을 스크립트에 명시.
- **feedback ledger lost-update**: auto-dev가 T-review/T-security를 병렬 실행하며
  둘 다 `feedback.sh upsert`를 호출하는데 read-modify-write에 락이 없어 한쪽 기록
  소실·`F-id` 중복 채번이 가능했다 — `fcntl.flock` 배타 락 + tmp 파일 `os.replace`
  원자 교체로 수정. 동시 8프로세스 upsert 무손실 회귀 테스트 추가.
- **work.sh Work ID TOCTOU**: 동시 `work.sh new` 실행 시 동일 `W-XXX`가 중복 발급될
  수 있었다(번호 채번과 디렉토리 생성이 비원자적) — `.claimed/` 레지스트리에 원자적
  `mkdir`로 ID를 선점(재시도 + 지터). `find_work_dir`는 중복 매치 시 `head -1`로
  은폐하지 않고 명시적 에러. 동시 10회 생성 검증(중복 0).

---

## [2.7.2] — 2026-06-22

### Fixed — stop-validator 테스트 타임아웃 오탐 (대형 레포) + 전체 스위트 실행 제거

전체 테스트 스위트가 60초를 넘는 레포에서 `.py`를 편집할 때마다, 코드가 전부
통과하는데도 `test_failure: 테스트 실행 시간 초과 (60초)`로 Stop이 거짓 차단되던
문제를 수정. 근본 원인은 매 턴 종료마다 도는 Stop 훅이 **전체 pytest 스위트**를
실행한 것 — 지연이 스위트 크기에 비례해 대형 레포에서 항상 타임아웃났다.

- **전체 스위트 실행 제거(근본 차단)**: `check_tests()`는 이제 이번 세션이 편집한
  `test_*.py`/`*_test.py`만 실행한다(lint의 스코프 철학과 동일). 소스만 편집했으면
  테스트 검증을 스킵한다. 전체 회귀 검증은 CI(`validate.yml`)·`/test`·
  `verify-done.sh`의 몫. 이로써 대형 레포 타임아웃 오탐이 **구조적으로 불가능**해진다.
- **타임아웃 ≠ 실패**: 남는 단일 느린 테스트를 위해 `TimeoutExpired`는 차단이 아니라
  비차단 `[WARN]`으로 강등(통과 반환). 실제 실패 테스트는 여전히 차단된다.
- **타임아웃 설정 가능**: `CLAUDE_STOP_TEST_TIMEOUT` 환경변수로 한도 조절(기본 60초).
- **죽은 코드 제거**: 전체 스위트 탐색용 `find_test_files()`·`EXCLUDE_DIRS` 삭제.
- **부수**: `scripts/verify-done.sh`가 pytest 인터프리터 탐색 시 프로젝트
  `.venv`/`venv`를 우선하도록 정렬(훅의 `_pytest_python()`과 일관).

---

## [2.7.1] — 2026-06-15

### Fixed — stop-validator 무한 루프 + pytest 오탐

턴 종료 시 도는 `stop-validator.py`가 외부 dirty `.py`(병렬 세션 미커밋 등)를 만나면
무한 차단 루프에 빠지던 문제를 수정. 하니스의 연속 차단 cap이 강제 종료할 때까지 반복됐다.

- **무한 루프 근본 차단**: `max_retries_exceeded` 분기가 `block()` + 카운터 reset 하던 것을
  `allow()`로 전환. cap은 "검증 중단·턴 종료"가 정상인데 정반대로 동작해
  `test_failure ↔ max_retries` 사이클을 영원히 돌렸다.
- **pytest 오탐(#332)**: `check_tests()`가 시스템 `python3`로 pytest를 실행해
  모듈 부재 시 `No module named pytest` → `test_failure`로 차단했다. 이제 프로젝트
  `.venv`/`venv` 인터프리터를 우선 사용하고, 모듈 부재는 차단이 아니라 스킵으로 처리.
- **`stop_hook_active` 존중**: stdin을 읽어 stop-hook 재진입(`stop_hook_active=true`) 시
  즉시 통과 — 네이티브 무한 루프 가드.
- **세션별 파일 스코핑(1차 트리거 제거)**: 기존엔 `git diff HEAD`로 레포 전체 dirty
  `.py`를 검증 대상으로 삼아, *이 세션이 안 건드린* 병렬 세션 미커밋 `.py`에도 매 턴
  pytest를 돌렸다(사건 1차 트리거). 이제 Stop 훅 `transcript_path`를 파싱해 이 세션이
  Edit/Write로 실제 편집한 파일만 검증한다. transcript 부재 시 전체 검증으로 폴백.
- **TTY hang 가드**: `_read_input()`이 수동 실행 시 `stdin.read()` EOF 대기로 멈추지
  않도록 `isatty()` 체크 추가.

## [2.7.0] — 2026-06-14

### Removed — Core-only consolidation

테스트 0개, v2.0.0 이후 실질 변경이 없던 **5개 도메인 플러그인을 제거**하고 단일 core로 집중. 잘 테스트된 core를 들고 가는 게 미검증 플러그인 5개를 배포·버전관리하는 것보다 zero-debt다.

- 제거: `claude-code-kit-frontend`, `-infra`, `-ops`, `-data`, `-integration` (총 33 agents, 10 skills, **0 tests**)
- `marketplace.json`을 core 1개만 노출하도록 정리
- `setup.sh` 도메인 선택/설치 로직 제거 (`--all`/`--list` 플래그 삭제)
- README·CLAUDE.md를 단일 플러그인 구조(2-tier)로 갱신
- **복구 지점**: 제거 직전 상태를 `v2.6.0-with-domains` 태그로 보존 (git 히스토리로 언제든 복원 가능)

### Changed

- core `claude-code-kit` 버전 2.6.0 → 2.7.0
- **배포 모드: 상대경로 → `git-subdir`** — `marketplace.json`의 플러그인 source를 `./plugins/common`(로컬 경로)에서 `git-subdir`(모노레포 서브디렉토리 sparse-clone)로 전환. 이제 진짜 리모트/버전 관리 플러그인으로 동작하며 `/plugin`의 "Update now"가 작동한다. (단일 플러그인이 되어 가능해짐)

---

## [2.6.0] — 2026-06-13

네이티브 프리미티브 최대 활용 + 자체 재구현 제거 (Spec 1~5, W-005~009).
설계 스펙: `docs/specs/2026-06-13-*.md`. 전부 하위호환 (fail-open / graceful degradation).

### Added

- **Feedback memory loop** (Spec 3) — `hooks/feedback_ledger.py`로 validation·review 결함을 누적(상한·중복제거·감쇠 SSOT)하고, session-start가 상위 빈도 교훈을 `=== LESSONS ===`로 주입. 캡처 진입점은 `scripts/feedback.sh`(work.sh와 동일한 ./scripts 관례, `CLAUDE_PLUGIN_ROOT` 의존 없음). `rules/feedback-loop.md`.
- **Loop engineering** (Spec 5) — `rules/loop-engineering.md`로 게이트(설계·사람 멈춤) vs 루프(실행·자율 완주)를 분리. auto-dev 배치 드라이버 + 종료 가드.
- **Plugin dependencies** (Spec 1) — 도메인 5종 매니페스트에 `dependencies: ["claude-code-kit"]` 선언 (네이티브가 common 강제 활성화).
- **Architecture & Concepts** README 섹션 (Spec 4) — 네 갈래 융합(네이티브·superpowers·Hermes·Work) + Harness×Loop engineering narrative.
- **Definition of Done 완료 게이트** (Spec 6) — `scripts/verify-done.sh`(JSON·CI필드·ruff·pytest·시크릿·카운트 sync·stale 참조 통합 게이트, FAIL 시 비정상 종료) + `rules/definition-of-done.md`(Iron Law of Completion + 금지 어휘). "완료"를 판단이 아니라 명령의 출력으로 강제. loop-engineering 종료 조건과 연계.

### Changed

- **Hooks exec form** (Spec 1) — `hooks.json`를 `command`+`args[]` exec form으로 전환, `${CLAUDE_PLUGIN_ROOT}` 경로 인용 문제 제거.
- **Stop hook** (Spec 1) — `stop-validator.py`가 실패 시 네이티브 `{"decision":"block","reason":...}`를 emit해 Claude가 수정 턴을 이어가도록 개선.
- **Orchestration model** (Spec 2) — "main만 조율"에서 "스케일별 네이티브 프리미티브"로 재서술. Small/Medium은 스킬 주도 플랫, Large는 네이티브 `ultracode`. `agent-teams` 스킬을 네이티브 workflow 가이드로 재정의.
- delegation-signal 표준 포맷을 `rules/agent-delegation-chain.md`에 SSOT로 명문화.
- **superpowers interop** — `using-claude-code-kit`을 additive-only로 슬림화. 범용 스킬 규율(1% 룰·red flags)은 `superpowers:using-superpowers`와 공유하고 kit 전용 델타(에이전트맵·Work·체인·native/loop/DoD)만 유지. 둘 다 활성 시 중복 0, kit standalone도 자급. interop 가이드 섹션 추가.

### Removed

- **`agent-lifecycle.py`** (Spec 1) — 순수 로깅 훅 삭제. 서브에이전트 관측은 네이티브 OpenTelemetry(`agent_id`/`parent_agent_id` 스팬)로 위임. `SubagentStart`/`SubagentStop`/`PreCompact` 등록 제거.

### Notes

- 네이티브 dynamic workflow(`ultracode`)·`/goal`은 대화형 전용이라 스킬에서 프로그래밍 트리거 불가(2026.6 검증) → 자동 위임은 검증된 Task 시스템 + 스킬 루프로 구현(자체 데몬 없음).
- 버전: common 2.3.0→2.6.0, 도메인 플러그인 5종 2.0.0→2.1.0.

---

## [2.2.0] — 2026-05-03

### ⚠️ Behavior Change — Stop Hook

The `Stop` hook has been replaced with an automated validator (`stop-validator.py`).

**What changed:** Previously, the Stop hook asked Claude to self-evaluate completion. Now it runs `ruff` and `pytest` automatically and **blocks the session from stopping if either fails.**

**Who is affected:** All users with Python files modified in the current session.

**How to disable** (per-session or globally):

```json
// plugins/common/hooks/hooks.json → restore the prompt-based hook:
"Stop": [
  {
    "hooks": [
      {
        "type": "prompt",
        "prompt": "개발 작업이 완료된 경우 ...",
        "timeout": 30
      }
    ]
  }
]
```

Or remove the `Stop` section entirely to disable all stop validation.

**How it works:**
- No Python files modified → instant pass (no ruff/pytest run)
- `ruff` not installed → warning to stderr, pass
- `pytest` not installed → warning to stderr, pass
- auto-dev pipeline already validated → marker file detected, skip (no double-validation)
- Max 2 auto-fix retries before giving up

### Added

- **`stop-validator.py`** — automated Stop hook: detects Python changes, runs ruff (with auto-fix) and pytest, blocks on failure with structured JSON output
- **7 unit tests** for `stop-validator.py` (`hooks/tests/test_stop_validator.py`):
  - `test_no_py_changes_exits_zero`
  - `test_lint_auto_fixed_prints_json_and_exits_zero`
  - `test_lint_auto_fixed_json_structure`
  - `test_test_failure_exits_two_with_correct_json`
  - `test_marker_skip_exits_zero_and_consumes_marker`
  - `test_lint_error_when_auto_fix_fails_exits_two`
  - `test_max_retries_exceeded_exits_two`
- **auto-dev SKILL.md** — T-merge step now creates a validation marker to prevent double-validation when auto-dev pipeline already ran lint/test

### Fixed

- Stop hook `PROJECT_ROOT` now derived from `git rev-parse --show-toplevel` (stable regardless of harness cwd)
- git-relative paths resolved against `PROJECT_ROOT` before passing to ruff (fixes silent lint skip when hook cwd ≠ project root)
- TOCTOU race condition in marker file check replaced with atomic `try/except unlink()`

---

## [2.0.0] — 2026-04-22

### Breaking Changes

- **Removed from all agent frontmatter** (non-standard fields, unsupported by the official plugin spec):
  - `permissionMode` — removed from 6 agents
  - `context_cache` — removed from all agents
  - `output_schema` — removed from all agents
  - `next_agents` — removed from all agents
  - Inline `hooks:` blocks — removed from all agents (covered by plugin-level `hooks/hooks.json`)
- **Removed from all skill frontmatter**:
  - `domain`, `argument-hint`, `allowed-tools` — non-standard, not supported by official spec

If you extended agents by adding these fields in project-local overrides, remove them to stay compliant.

### Added

- **Manifest compliance** — all 6 `plugin.json` files now include `homepage`, `repository`, `license`, `author.email` for official registry submission
- **`maxTurns` field** — added to 11 agents to prevent infinite loops:
  - Implementation agents (`implement-code`, `fix-bugs`, `write-tests`, `plan-implementation`, `write-api-tests`): `maxTurns: 20`
  - Exploration/review agents (`review-code`, `verify-code`, `verify-integration`, `explore-codebase`, `analyze-dependencies`, `security-scan`): `maxTurns: 10`
- **New lifecycle hooks** in `hooks/hooks.json`:
  - `SubagentStart` — logs agent invocation start
  - `SubagentStop` — logs agent invocation completion
  - `PreCompact` — saves state summary before context compaction
- **`agent-lifecycle.py`** — new hook script handling the three lifecycle events above
- **91 unit tests** for all hook scripts:
  - `tests/test_session_start.py` — 19 tests (frontmatter parsing, task map parsing, rules loading, main output format)
  - `tests/test_protect_sensitive.py` — 33 tests (file path blocking, content scanning, integration)
  - `tests/test_auto_format.py` — 19 tests (path validation, ESLint config detection, pipeline execution)
  - `tests/test_utils.py` — 21 tests (safe_path, debug_log, is_debug_mode, get_project_root)
- **CI strengthened** (`.github/workflows/validate.yml`):
  - `Check plugin.json required fields` step
  - `Check agent frontmatter — no forbidden fields` step
  - `Run hook unit tests` step (`pytest plugins/common/hooks/tests/ -v`)
- **English skill descriptions** — all 14 skill `description` fields converted from Korean to English for correct Claude auto-invocation behavior

### Fixed

- `agent-creator` skill template: removed `permissionMode` from the generated agent template (it was showing a now-unsupported field)
- All `hooks/hooks.json` paths already used `${CLAUDE_PLUGIN_ROOT}` — verified correct

---

## [1.1.5] — 2026-04-21

### Fixed

- W-007 validation issues: T-merge guard, confidence wording, Bash scope

---

## [1.1.4] — 2026-04-14

### Fixed

- GitHub Actions gitleaks failure
- Documentation updates

---

## [1.1.3] and earlier

Initial releases establishing the 33-agent + 12-skill core structure across 6 plugin domains.
