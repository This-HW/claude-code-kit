# 레퍼런스 조사 — superpowers의 다중 플랫폼 배포 (obra/superpowers)

- 조사일 2026-08-27 · 조사자: 기획 세션 · 방법: 로컬 설치본 해부 + `gh api` 로 원본 저장소 직접 조회
- 목적: CCK의 다중 타겟 패키징(W-019)과 AGENTS.md 단일 소스(W-020)의 선행 사례 확보

## 1. 배포 타겟 — 플러그인 9종 + npm + 컨텍스트 파일 3종

`[confirmed: gh api repos/obra/superpowers/contents, 2026-08-27]`

| 타겟 디렉토리/파일 | 대상 |
| --- | --- |
| `.claude-plugin/` (plugin.json + marketplace.json) | Claude Code |
| `.codex-plugin/plugin.json` | Codex |
| `.agents/plugins/` | Codex 표준 마켓플레이스 경로 |
| `.cursor-plugin/plugin.json` | Cursor |
| `.devin-plugin/plugin.json` | Devin |
| `.kimi-plugin/plugin.json` | Kimi |
| `.hermes-plugin/` (**plugin.yaml + `__init__.py`**) | Hermes — 유일하게 YAML + Python 규격 |
| `.opencode/` (INSTALL.md + plugins/) | OpenCode — JS/TS 실행 코드 |
| `.pi/extensions/` | Pi |
| `gemini-extension.json` | Gemini/Antigravity 확장 |
| `package.json` | npm |

→ **CCK는 현재 2종(Codex·Antigravity). superpowers는 9종 + npm.**

## 2. 컨텍스트 파일 — 심링크 방향이 통념과 반대다

`[confirmed: git tree API 의 file mode]`

```
AGENTS.md    mode=120000  SYMLINK  size=9   → "CLAUDE.md"
CLAUDE.md    mode=100644  실체 파일 8,873 B   ← **단일 소스**
GEMINI.md    mode=100644  실체 파일 92 B      ← 심링크 아님. 별도 얇은 파일
```

**`CLAUDE.md` 가 원본이고 `AGENTS.md` 가 그것을 가리키는 심링크다.** Anthropic 공식 문서가 예시로 드는
`ln -s AGENTS.md CLAUDE.md`(AGENTS.md가 원본)와 **방향이 반대**다. 둘 다 POSIX에서 동작하므로
어느 쪽을 실체로 둘지는 선택의 문제이고, superpowers는 `CLAUDE.md` 를 택했다.

**`GEMINI.md` 는 심링크가 아니라 92바이트짜리 별도 파일이고 내용이 다르다:**

```
@./skills/using-superpowers/SKILL.md
@./skills/using-superpowers/references/gemini-tools.md
```

즉 Gemini에는 **전문을 복제하지 않고 부트스트랩 import 두 줄만** 준다. 그리고
`gemini-extension.json` 이 `"contextFileName": "GEMINI.md"` 로 어느 파일을 읽을지 지정한다.

> **시사점**: "모든 하네스에 같은 파일을 링크"가 아니라 **하네스별로 필요한 만큼만 준다.**
> 링크가 맞는 곳(AGENTS.md)과 얇은 별도 파일이 맞는 곳(GEMINI.md)이 갈린다.

## 3. 버전 팬아웃 — `.version-bump.json`

`[confirmed: 파일 원문]`

```json
{
  "files": [
    { "path": "package.json",                 "field": "version" },
    { "path": ".claude-plugin/plugin.json",   "field": "version" },
    { "path": ".cursor-plugin/plugin.json",   "field": "version" },
    { "path": ".codex-plugin/plugin.json",    "field": "version" },
    { "path": ".claude-plugin/marketplace.json", "field": "plugins.0.version" },
    { "path": "gemini-extension.json",        "field": "version" }
  ],
  "audit": { "exclude": ["CHANGELOG.md", "RELEASE-NOTES.md", "node_modules", ".git", ...] }
}
```

**버전을 올리면 모든 타겟 매니페스트로 전파하는 선언적 매니페스트** + `scripts/bump-version.sh`.
`audit.exclude` 가 있다는 건 **레포 전체에서 낡은 버전 문자열을 훑는 감사 기능**이 있다는 뜻이다.

> **시사점**: CCK는 v2.15.0 릴리스에서 **정확히 이 문제를 밟았다.** `.claude-plugin/plugin.json` 만
> 올리고 생성물을 재생성하지 않아 §14가 드리프트로 잡았다. 우리는 게이트로 사후 탐지했고,
> superpowers는 팬아웃으로 사전 예방한다. **탐지보다 예방이 낫다.**
> (다만 우리 쪽은 매니페스트가 *생성물*이라 팬아웃 대신 재생성이 정답 — 자동 재생성을 bump에 묶는 것)

## 4. 배포 경로 — Codex는 별도 마켓플레이스 저장소로 PR

`scripts/` = `bump-version.sh`, `lint-shell.sh`, `sync-to-codex-plugin.sh`, `package-codex-plugin.sh`

`sync-to-codex-plugin.sh` 원문 요지 `[confirmed]`:
- 대상: **`prime-radiant-inc/openai-codex-plugins` 포크**로 rsync → 커밋 → 브랜치 push → **PR 생성**
- "OpenAI-owned marketplace metadata already in the destination" 는 **보존**
- **결정적(deterministic)**: 같은 upstream SHA로 두 번 돌리면 동일한 diff의 PR이 나온다 — 도구 자체를 검증 가능
- `--bootstrap` 모드로 대상에 플러그인 디렉토리가 없을 때 생성

> **시사점**: Codex 공개 배포는 매니페스트만 만든다고 끝이 아니라 **마켓플레이스 저장소에 PR**을 넣는
> 절차가 실재한다. 우리 `docs/codex-submission-checklist.md` 의 `[unresolved]` 중 일부가 이걸로 좁혀진다.

## 5. 그 밖에 눈여겨볼 것

- `.github/ISSUE_TEMPLATE/platform_support.md` — **플랫폼 지원을 1급 이슈 카테고리로** 둔다
- 기여 가이드가 새 하네스 지원 PR에 **수용 테스트**를 요구한다: 깨끗한 세션에서
  `Let's make a react todo list` 를 보내 `brainstorming` 스킬이 **자동 발동**하는 트랜스크립트 첨부.
  "스킬 파일 수동 복사", "런타임 shim", "세션마다 opt-in" 은 진짜 통합이 아니라고 명시
- 스킬 행동 evals는 별도 저장소(`superpowers-evals`)에서 **실제 tmux 세션**(Claude Code/Codex/Gemini CLI)을
  구동하고 LLM 검증자로 준수를 판정한다 — 우리 evals가 에이전트 단위인 것과 대비되는 설계

## 6. CCK가 가져올 것 / 안 가져올 것

| 가져온다 | 이유 |
| --- | --- |
| 버전 팬아웃(우리는 **재생성 자동화**) | v2.15.0에서 실제로 밟은 함정. 탐지보다 예방 |
| 하네스별 컨텍스트 파일 전략(링크 vs 얇은 파일) | W-020의 설계 근거. 통념(AGENTS.md 원본)이 유일한 답이 아니다 |
| 타겟 확장 후보 목록 | Cursor·OpenCode·Devin·Kimi·Hermes·Pi·Gemini extension |
| 플랫폼 지원 이슈 템플릿 | 저비용, 기여 경로 명확화 |
| **새 하네스 지원의 수용 테스트 개념** | "매니페스트가 있다"와 "실제로 동작한다"는 다르다 — 우리도 실물 CLI 검증을 했지만 성문화는 안 됐다 |

| 안 가져온다 | 이유 |
| --- | --- |
| npm 배포 | CCK는 npm 패키지가 아니다. 배포 채널을 늘리는 것 자체가 목적이 될 수 없다 |
| 별도 evals 저장소 + tmux 하네스 | 우리 evals는 에이전트 단위로 이미 동작한다. 스킬 행동 evals는 별도 문제 |
| 마켓플레이스 포크 PR 자동화 | **자격 미확보**(공개 게시는 사람의 행위). 다만 절차를 문서에 반영한다 |
