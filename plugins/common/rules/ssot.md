# SSOT (Single Source of Truth) 원칙

> 모든 정보는 단일 출처에서 관리됩니다. 중복은 불일치를 만듭니다.

## 핵심 원칙

1. **단일 출처**: 에러 타입, API 엔드포인트, 환경 변수는 각각 한 파일에서만 정의
2. **참조 우선**: 값을 복사하지 말고 `import { API_URL } from "@/config/env"` 형태로 참조
3. **단일 변경 지점**: 하나를 바꾸면 모든 곳에 반영 — 10개 파일 수정 필요 시 → SSOT 위반

```
✅ errors/messages.ts 하나만 수정 → 모든 곳에 반영
❌ 같은 상수를 여러 파일에 중복 정의 / API URL을 컴포넌트마다 하드코딩
```

## 에러 로깅 규칙

**모든 에러는 중앙 단일 시스템으로 수집합니다.**

```
src/infrastructure/errors/
├── types.ts     # 에러 코드(AUTH_001 등) + AppError 인터페이스
├── messages.ts  # 에러 메시지 상수
├── handler.ts   # 중앙 에러 핸들러 (normalizeError + notifyOnCall)
└── logger.ts    # 로그: code, message, timestamp, severity, context
```

에러 로그 필수 필드: `code`(AUTH_001), `message`, `timestamp`(ISO 8601), `severity`(debug~critical)

선택 필드: `userId`, `requestId`, `file`, `line`, `stack`

에러 로그는 `logs/errors/YYYY-MM-DD.log`에 일별 저장, critical은 별도 보관.

## 실전 예시: DB SSH Tunnel

**SSOT 위반** — 7개 파일에 SSH 주소 하드코딩 → 서버 변경 시 7개 파일 수정 필요

**SSOT 적용** — 환경 변수를 단일 출처로:

```bash
export CLAUDE_DB_SSH_HOST="user@your-server.com"
# scripts/db-tunnel.sh 가 환경변수 참조 (REMOTE_HOST="$CLAUDE_DB_SSH_HOST")
# Agent/Skill/Rules는 스크립트 참조만: ./scripts/db-tunnel.sh start
```

결과: 서버 변경 시 `~/.zshrc` 1곳만 수정. **상세:** `docs/guides/ssot-db-tunnel.md`

## SSOT 체크리스트

- 이 값이 다른 곳에 이미 정의되어 있는가?
- 하드코딩 대신 상수/설정을 참조하고 있는가?
- 에러는 중앙 핸들러를 통해 처리되는가?
- 하나의 변경이 여러 파일 수정을 요구하는가? → SSOT 위반 신호
- 같은 버그가 여러 곳에서 발생하는가? → 중복 코드 신호
