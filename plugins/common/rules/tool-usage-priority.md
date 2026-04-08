# Tool Usage Priority Rules

## File Operations

NEVER use Bash for file operations. ALWAYS use the dedicated tool:

- Read files → **Read** (NOT cat/head/tail)
- Edit files → **Edit** (NOT sed/awk)
- Create files → **Write** (NOT echo>/cat<<EOF)
- Search files → **Glob** (NOT find/ls)
- Search content → **Grep** (NOT grep/rg)

## Bash Allowed Cases

DO use Bash for: git, package managers (npm/pip/brew), services (docker/systemctl), builds (make/cargo/go), DB CLIs (psql/mysql/redis-cli), system ops (chmod/chown/ln/mkdir), process management (kill/ps/lsof).
