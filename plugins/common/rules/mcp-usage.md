# MCP Usage Rules

## MCP Servers

ALWAYS use these MCP servers for their designated purposes:

- **Context7** — library/framework docs; ALWAYS use instead of WebFetch for API references
- **Exa** — semantic code/tech search; ALWAYS use instead of WebSearch for precise technical queries
- **Tavily** — comprehensive research, fact-checking, tech comparison
- **Playwright** — dynamic page scraping, E2E tests; NEVER use WebFetch for JS-rendered pages
- **Sequential Thinking** — complex multi-step design and problem decomposition
- **PostgreSQL** — DB queries, schema exploration, query optimization
- **Magic** (21st.dev) — natural language → UI components

## Tool Selection

ALWAYS choose MCP over built-in tools when:

- Library/framework docs → **Context7** (NOT WebFetch)
- Semantic/code search → **Exa** (NOT WebSearch)
- Dynamic page → **Playwright** (NOT WebFetch)
- DB queries → **PostgreSQL** (NOT Bash psql)

DO use built-in tools when:

- Simple web search → **WebSearch**
- Static page fetch → **WebFetch**

## Required Rules

ALWAYS run `./scripts/db-tunnel.sh start` before using PostgreSQL MCP.

ALWAYS specify the version when using Context7: `"use context7 for Next.js 15 App Router"` — NEVER omit the version.

NEVER rely on training-data memory for library APIs; ALWAYS verify with Context7.

## Agent MCP Configuration

ALWAYS disable unused MCPs via `disallowedTools` to reduce context overhead:

- Code implementation agents: ONLY allow Context7 and Exa; ALWAYS disable Tavily and Magic
- Review agents: ALWAYS disable ALL MCPs (list each individually — wildcard `mcp__*` is NOT supported)
- web-research skill: allow ALL MCPs

## NotebookLM Rules

ALWAYS call `notebook_get` to check current Source count before adding a new Source.

NEVER exceed 50 Sources per notebook — additions will fail above this limit.

DO NOT confuse Source (original evidence) with Note (processed output).
