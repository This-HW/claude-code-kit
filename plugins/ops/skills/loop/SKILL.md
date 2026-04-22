---
name: loop
description: |
  반복 실행 스케줄 설정. CronCreate로 주기적 작업을 등록합니다.
  MUST USE when: "/loop", "반복", "주기적으로", "매 N분마다", "스케줄"
  OUTPUT: 등록된 크론 작업 ID와 다음 실행 시각
model: haiku
effort: low
---

# Loop 스킬

주기적으로 반복할 작업을 스케줄에 등록합니다.

---

## 사용법

```
/loop 5m /monitor                     # 5분마다 모니터링
/loop 1h /security-scan               # 1시간마다 보안 스캔
/loop list                            # 등록된 반복 작업 목록
/loop stop <id>                       # 반복 작업 중지
```

---

## 사전 준비

CronCreate/CronList/CronDelete는 deferred tool입니다. 실행 전 반드시 로드:

```
ToolSearch("select:CronCreate,CronList,CronDelete")
```

---

## 워크플로우

### 등록 (`/loop <interval> <command>`)

1. `ToolSearch("select:CronCreate,CronList,CronDelete")` 실행
2. interval 파싱: `s`(초), `m`(분), `h`(시간) 단위 지원
3. CronCreate로 작업 등록:
   - `schedule`: cron 표현식으로 변환 (예: `5m` → `*/5 * * * *`)
   - `command`: 실행할 슬래시 커맨드 또는 설명
3. 등록 확인 및 작업 ID 반환

### 조회 (`/loop list`)

CronList로 현재 등록된 반복 작업 목록 출력:

- 작업 ID, interval, 커맨드, 다음 실행 시각

### 중지 (`/loop stop <id>`)

CronDelete로 해당 ID의 반복 작업 제거.

---

## interval 형식

| 입력 | cron 표현식   | 설명                |
| ---- | ------------- | ------------------- |
| `1m` | `*/1 * * * *` | 1분마다 (최소 단위) |
| `5m` | `*/5 * * * *` | 5분마다             |
| `1h` | `0 * * * *`   | 매시 정각           |
| `1d` | `0 0 * * *`   | 매일 자정           |

---

## 관련 에이전트

- **schedule-task**: 일회성 작업 예약 (loop는 반복, schedule-task는 단발)
- **monitor**: `/loop 5m /monitor` 패턴으로 자주 사용
