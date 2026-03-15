# 전용 도구 우선 규칙

> 파일 작업은 전용 도구, 시스템 작업은 Bash

## 도구 매핑표

| 작업 | ❌ Bash (금지) | ✅ 전용 도구 |
| ---- | ------------- | ----------- |
| 파일 읽기 | `cat`, `head`, `tail` | **Read** |
| 파일 편집 | `sed`, `awk` | **Edit** |
| 파일 생성 | `echo >`, `cat <<EOF` | **Write** |
| 파일 검색 | `find`, `ls` | **Glob** |
| 내용 검색 | `grep`, `rg` | **Grep** |

## Bash 허용 케이스

```
✅ Git, 패키지(npm/pip/brew), 서비스(docker/systemctl), 빌드(make/cargo/go)
✅ DB(psql/mysql/redis-cli), 시스템(chmod/chown/ln/mkdir), 프로세스(kill/ps/lsof)
```
