# SSOT (Single Source of Truth) Rules

## Core Principles

- ALWAYS define error types, API endpoints, and env vars in exactly one file
- NEVER copy values — always reference via import: `import { API_URL } from "@/config/env"`
- ALWAYS structure code so one change propagates everywhere — if one change requires editing 10 files, that is an SSOT violation

## Error Logging

- ALWAYS route all errors through a single central handler
- ALWAYS include these fields in every error log: `code` (e.g. AUTH_001), `message`, `timestamp` (ISO 8601), `severity` (debug → critical)
- NEVER scatter error handling logic across multiple modules

```
src/infrastructure/errors/
├── types.ts     # error codes + AppError interface
├── messages.ts  # error message constants
├── handler.ts   # central handler (normalizeError + notifyOnCall)
└── logger.ts    # structured logger
```

## SSOT Checklist

- Is this value already defined somewhere else? → reference it, don't redefine
- Is this a hardcoded string/number that should be a named constant? → extract it
- Does this error go through the central handler? → if not, fix it
- Does changing this require editing multiple files? → SSOT violation signal
- Does the same bug appear in multiple places? → duplicate code signal
