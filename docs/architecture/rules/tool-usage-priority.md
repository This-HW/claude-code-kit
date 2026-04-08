# 전용 도구 우선 규칙

> 이 문서는 파일 작업에 Bash 대신 전용 도구를 우선 사용해야 하는 이유와 올바른 선택 방법을 설명합니다.

---

## 1. 핵심 원칙

```
NEVER use Bash for file operations.
ALWAYS use the dedicated tool.
```

전용 도구는 Bash 명령보다 더 나은 사용자 경험을 제공합니다:

- 도구 호출이 UI에서 명확하게 표시되어 사용자가 검토하기 쉬움
- 권한 요청이 명시적으로 이루어져 실수로 파일을 덮어쓰는 일 방지
- 에러 메시지가 더 구체적으로 제공됨

---

## 2. 전용 도구 vs Bash 매핑 표

| 작업      | Bash 명령 (사용 금지)                                   | 전용 도구 (사용 필수) | 이유                                           |
| --------- | ------------------------------------------------------- | --------------------- | ---------------------------------------------- |
| 파일 읽기 | `cat file.txt`, `head -20 file.txt`, `tail -f file.txt` | **Read**              | 라인 번호 표시, 범위 지정, PDF/이미지 지원     |
| 파일 수정 | `sed -i 's/old/new/g' file.txt`, `awk '...' file.txt`   | **Edit**              | diff만 전송해 토큰 절약, 변경 내용 명확히 표시 |
| 파일 생성 | `echo "..." > file.txt`, `cat << EOF > file.txt`        | **Write**             | 전체 내용 검토 가능, 덮어쓰기 실수 방지        |
| 파일 검색 | `find . -name "*.ts"`, `ls -la src/`                    | **Glob**              | 수정 시간 기준 정렬, 패턴 매칭 최적화          |
| 내용 검색 | `grep -r "pattern" .`, `rg "pattern"`                   | **Grep**              | 파일 타입 필터, 컨텍스트 라인, 정규식 지원     |

---

## 3. Bash 허용 케이스

아래 작업은 전용 도구가 없으므로 Bash를 사용합니다.

### 버전 관리 (git)

```bash
# 허용 — git은 전용 도구 없음
git status
git diff HEAD
git add src/auth.ts
git commit -m "feat: add JWT authentication"
git push origin feature/auth
git log --oneline -10
```

---

### 패키지 매니저

```bash
# 허용 — 패키지 설치/관리는 Bash 필요
npm install express
npm run build
npm test
pip install fastapi
brew install postgresql
```

---

### 서비스 관리

```bash
# 허용 — 서비스 시작/중지는 Bash 필요
docker compose up -d
docker compose logs -f api
systemctl status nginx
systemctl restart postgresql
```

---

### 빌드 도구

```bash
# 허용 — 빌드 실행은 Bash 필요
make build
cargo build --release
go build ./...
npm run lint
npx tsc --noEmit
```

---

### DB CLI (직접 접속)

```bash
# 허용 — PostgreSQL MCP 대신 직접 CLI 사용 시
psql postgresql://localhost:5432/mydb -c "SELECT version();"
mysql -u root -p mydb < schema.sql
redis-cli PING
```

---

### 시스템 작업

```bash
# 허용 — 파일 시스템 구조 변경, 권한 설정
mkdir -p src/infrastructure/errors
chmod 600 .env
chown -R www-data:www-data /var/www
ln -sf /usr/local/bin/node /usr/bin/node
```

---

### 프로세스 관리

```bash
# 허용 — 프로세스 조회/종료
ps aux | grep node
lsof -i :3000
kill -9 $(lsof -t -i:3000)
```

---

## 4. 잘못된 사용 패턴 예시

### 파일 읽기에 cat 사용

```bash
# ❌ 잘못된 예
cat src/auth/auth.service.ts
head -50 src/auth/auth.service.ts
```

```
# ✅ 올바른 예
Read("src/auth/auth.service.ts")
Read("src/auth/auth.service.ts", offset=0, limit=50)
```

---

### 파일 수정에 sed 사용

```bash
# ❌ 잘못된 예
sed -i 's/console.log/logger.info/g' src/app.ts
```

```
# ✅ 올바른 예
Edit(
  file_path="src/app.ts",
  old_string='console.log("Server started")',
  new_string='logger.info("Server started")'
)
```

**sed를 사용하면 안 되는 이유:**

- 변경 내용이 UI에 표시되지 않아 사용자가 검토할 수 없음
- 정규식 실수로 의도하지 않은 부분까지 변경될 위험
- 에러 발생 시 어떤 내용이 바뀌었는지 추적 어려움

---

### 파일 검색에 find/ls 사용

```bash
# ❌ 잘못된 예
find . -name "*.test.ts" -not -path "*/node_modules/*"
ls -la src/components/
```

```
# ✅ 올바른 예
Glob("**/*.test.ts")
Glob("src/components/*")
```

---

### 내용 검색에 grep 사용

```bash
# ❌ 잘못된 예
grep -r "useAuth" src/ --include="*.tsx"
rg "import.*from.*@/lib" --type ts
```

```
# ✅ 올바른 예
Grep("useAuth", path="src/", glob="*.tsx")
Grep("import.*from.*@/lib", type="ts")
```

---

## 5. 판단이 모호한 케이스

| 케이스                                   | 판단                  | 이유                                |
| ---------------------------------------- | --------------------- | ----------------------------------- |
| `wc -l file.txt` (줄 수 세기)            | Bash 허용             | 전용 도구로 대체 불가               |
| `diff file1 file2`                       | Bash 허용             | 전용 도구 없음                      |
| `cp src/template.ts dist/output.ts`      | **Read + Write** 권장 | 복사 후 수정이 동반되는 경우가 많음 |
| `touch .gitkeep`                         | Bash 허용             | 빈 파일 생성은 Write보다 간단       |
| `echo $PATH`                             | Bash 허용             | 환경변수 확인은 시스템 작업         |
| `cat package.json \| jq '.dependencies'` | **Read** 후 처리 권장 | 파일 읽기 부분은 전용 도구 사용     |
