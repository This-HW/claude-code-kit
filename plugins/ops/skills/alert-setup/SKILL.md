---
name: alert-setup
description: |
  알림 규칙 설정 스킬. 모니터링 알림, SLA 위반 알림, 비용 알림을 설정합니다.
model: sonnet
effort: medium
---

# /alert-setup - 알림 규칙 설정

시스템 알림 규칙을 설정하고 관리합니다.

---

## 사용법

```bash
/alert-setup                     # 현재 알림 규칙 목록
/alert-setup add [type]          # 알림 규칙 추가
/alert-setup edit [rule-id]      # 알림 규칙 수정
/alert-setup delete [rule-id]    # 알림 규칙 삭제
/alert-setup test [rule-id]      # 알림 테스트
```

---

## 알림 유형

### 1. SLA 알림

```yaml
type: sla
trigger:
  metric: availability
  condition: "< 99.9%"
  window: 1h
notification:
  channel: slack
  urgency: high
```

### 2. 비용 알림

```yaml
type: cost
trigger:
  metric: daily_cost
  condition: "> $10"
  # 또는 증가율
  condition: "increase > 50%"
notification:
  channel: slack
  urgency: medium
```

### 3. 헬스체크 알림

```yaml
type: health
trigger:
  check: api_response
  condition: "fail >= 3"
  window: 5m
notification:
  channel: slack
  urgency: critical
```

### 4. 에이전트 알림

```yaml
type: agent
trigger:
  metric: error_rate
  condition: "> 10%"
  agent: "implement-code"
notification:
  channel: slack
  urgency: medium
```

---

## 설정 파일

`.claude/alerts.yaml`:

```yaml
alerts:
  - id: sla-availability
    name: "가용성 SLA 위반"
    type: sla
    trigger:
      metric: availability
      condition: "< 99.9%"
      window: 1h
    notification:
      channel: "#ops-alerts"
      urgency: high
    enabled: true

  - id: cost-spike
    name: "비용 급증"
    type: cost
    trigger:
      metric: daily_cost
      condition: "increase > 100%"
    notification:
      channel: "#cost-alerts"
      urgency: medium
    enabled: true

  - id: health-api
    name: "API 헬스체크 실패"
    type: health
    trigger:
      check: api_response
      condition: "fail >= 3"
      window: 5m
    notification:
      channel: "#ops-alerts"
      urgency: critical
    enabled: true
```

---

## 실행 흐름

```
/alert-setup add sla
        │
        ▼
┌──────────────┐
│ 알림 유형    │
│ 선택         │
└──────────────┘
        │
        ▼
┌──────────────┐
│ 조건 설정    │
│ (임계치)     │
└──────────────┘
        │
        ▼
┌──────────────┐
│ 알림 채널    │
│ 설정         │
└──────────────┘
        │
        ▼
┌──────────────┐
│ 테스트       │
│ (선택)       │
└──────────────┘
        │
        ▼
┌──────────────┐
│ 규칙 저장    │
└──────────────┘
```

---

## 출력 예시

### 알림 목록

```markdown
# 🔔 알림 규칙 목록

| ID               | 이름            | 유형   | 상태    |
| ---------------- | --------------- | ------ | ------- |
| sla-availability | 가용성 SLA 위반 | sla    | ✅ 활성 |
| cost-spike       | 비용 급증       | cost   | ✅ 활성 |
| health-api       | API 헬스체크    | health | ✅ 활성 |

## 최근 발동 (24시간)

| 시간  | 규칙       | 상태   |
| ----- | ---------- | ------ |
| 14:30 | health-api | 해결됨 |
| 09:15 | cost-spike | 확인중 |
```

### 알림 추가

```markdown
# ✅ 알림 규칙 추가됨

**ID**: latency-p99
**이름**: P99 응답시간 초과
**유형**: sla
**조건**: p99_latency > 10s (5분 window)
**채널**: #ops-alerts
**긴급도**: high

테스트 알림을 보내시겠습니까? [Y/n]
```

---

## 연동 에이전트

| 에이전트    | 역할            |
| ----------- | --------------- |
| track-sla   | SLA 메트릭 수집 |
| monitor     | 모니터링 데이터 |
| notify-team | 실제 알림 발송  |

---

## 관련 에이전트

| 에이전트      | 설명                   |
| ------------- | ---------------------- |
| track-sla     | SLA 추적 및 모니터링   |
| monitor       | 실시간 시스템 모니터링 |
| notify-team   | 팀 알림 발송           |
