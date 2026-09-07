---
tier: core
portable: true
---

# SSOT (Single Source of Truth) Rules

## Core Principles

- ALWAYS define error types, API endpoints, and env vars in exactly one place
- NEVER copy values — always reference the single definition, however the language/framework expresses that (import, include, require, …)
- ALWAYS structure code so one change propagates everywhere — if one change requires editing 10 files, that is an SSOT violation

## Error Logging

- ALWAYS route all errors through a single central handler
- ALWAYS include these fields in every error log: `code` (e.g. AUTH_001), `message`, `timestamp` (ISO 8601), `severity` (debug → critical)
- NEVER scatter error handling logic across multiple modules — one module owns error types, one owns the handler, one owns the logger

## SSOT Checklist

- Is this value already defined somewhere else? → reference it, don't redefine
- Is this a hardcoded string/number that should be a named constant? → extract it
- Does this error go through the central handler? → if not, fix it
- Does changing this require editing multiple files? → SSOT violation signal
- Does the same bug appear in multiple places? → duplicate code signal
