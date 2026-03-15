# 코드 품질 규칙

> 읽기 쉽고, 유지보수하기 쉽고, 테스트 가능한 코드를 작성합니다.

## 핵심 원칙

| 원칙 | ✅ 좋은 코드 | ❌ 나쁜 코드 |
| ---- | ---------- | ---------- |
| **단순함** | 한 눈에 이해, 한 가지 일만 수행 | 스크롤 필요, 여러 책임 혼재 |
| **명확함** | 이름만 봐도 역할 파악, 의도가 드러남 | 약어 남발, 매직 넘버, 복잡한 조건 |
| **일관성** | 컨벤션 준수, 예측 가능한 구조 | 파일마다 다른 스타일 |

## 함수/메서드 규칙

**크기:** 함수 20줄 이하, 파라미터 3개 이하, 들여쓰기 2단계 이하 (경고: 50줄+, 5개+, 4단계+)

**네이밍:** 역할을 명확히 표현 (`calculateTotalPrice`, `validateUserInput`) — `calc`, `process`, `doStuff` ❌

**단일 책임:**

```typescript
// ✅ 분리된 책임
function saveUser(user: User) { ... }
function sendWelcomeEmail(email: string) { ... }
function logUserCreation(userId: string) { ... }
```

## 에러 처리

에러를 무시하거나 `console.log`로만 처리하지 않습니다. 타입별로 명시적 처리하고, 알 수 없는 에러는 상위로 전파합니다.

```typescript
// ✅ 명시적 처리
} catch (error) {
  if (error instanceof NetworkError) return handleNetworkError(error);
  if (error instanceof ValidationError) return handleValidationError(error);
  throw error; // 알 수 없는 에러는 상위로
}
```

에러 전파 시 컨텍스트 보존: `throw new AppError({ code, message: \`...\${userId}\`, cause: error })`

## 조건문 규칙

**Early Return:** 중첩 조건 대신 조기 반환

```typescript
// ✅
if (!user) return null;
if (!user.isActive) return null;
if (!user.hasPermission) return null;
return doProcess(user);
```

**복잡한 조건:** 의미 있는 변수명으로 추출 (`const isEligibleUser = user.age >= 18 && ...`)

## 타입 안전성

- `any` 사용 금지 → 명시적 타입 사용
- 타입 단언(`as`) 남용 대신 타입 가드(`data is User`) 사용
- Null 처리: `user?.name ?? "Unknown"` (Null 체크 누락 ❌)

## 테스트 가능성

- **의존성 주입:** `constructor(private db: IDatabase)` — 하드코딩된 `new Database()` ❌
- **순수 함수:** 부수 효과 없이 동일 입력 → 동일 출력 (`globalState` 변경 ❌)

## 코드 품질 체크리스트

**작성 시:** 함수가 한 가지 일 / 이름이 역할 표현 / 에러 처리 명시적 / 타입 명확

**리뷰 시:** 한 눈에 이해 / 불필요한 복잡성 없음 / 컨벤션 준수 / 테스트 가능 구조

**리팩토링 시:** 중복 코드 있는가 / 너무 큰 함수 있는가 / 의존성이 명확한가
