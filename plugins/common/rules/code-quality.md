# Code Quality Rules

## Functions

- ALWAYS keep functions under 20 lines, parameters under 3, nesting under 2 levels
- NEVER write functions with 50+ lines, 5+ parameters, or 4+ levels of nesting
- ALWAYS name functions to clearly express their role (`calculateTotalPrice`, `validateUserInput`)
- NEVER use vague names: `calc`, `process`, `doStuff`, `handle`
- ALWAYS apply single responsibility — one function does one thing

```typescript
// DO: separate responsibilities
function saveUser(user: User) { ... }
function sendWelcomeEmail(email: string) { ... }
function logUserCreation(userId: string) { ... }
```

## Error Handling

- NEVER ignore errors or handle them with `console.log` only
- ALWAYS handle each error type explicitly; rethrow unknown errors upward
- ALWAYS preserve context when rethrowing: `throw new AppError({ code, message: \`...\${userId}\`, cause: error })`

```typescript
} catch (error) {
  if (error instanceof NetworkError) return handleNetworkError(error);
  if (error instanceof ValidationError) return handleValidationError(error);
  throw error;
}
```

## Conditionals

- ALWAYS use early return instead of nested conditions
- ALWAYS extract complex boolean expressions into named variables

```typescript
if (!user) return null;
if (!user.isActive) return null;
if (!user.hasPermission) return null;
return doProcess(user);
```

## Type Safety

- NEVER use `any` — always use explicit types
- NEVER overuse type assertions (`as`) — use type guards (`data is User`) instead
- ALWAYS handle null: `user?.name ?? "Unknown"` — never skip null checks

## Testability

- ALWAYS inject dependencies via constructor: `constructor(private db: IDatabase)`
- NEVER hardcode `new Database()` inside a function
- ALWAYS write pure functions: same input → same output, no side effects on global state
