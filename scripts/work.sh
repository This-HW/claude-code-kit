#!/usr/bin/env bash
# scripts/work.sh — Work 상태 관리 CLI
set -euo pipefail

WORKS_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)/docs/works"

# ---------------------------------------------------------------------------
# Usage
# ---------------------------------------------------------------------------
usage() {
  cat <<EOF
Usage: $(basename "$0") <command> [args]

Commands:
  new <title>       새 Work 아이템 생성
  list              전체 Work 목록 출력
  show <id>         Work 상세 조회 (예: W-001)
  start <id>        idea → active 전환
  next-phase <id>   현재 phase를 다음 단계로 전환
  complete <id>     active → completed 전환
  resume <id>       CLAUDE_CODE_TASK_LIST_ID 설정 후 claude 실행 (Task 영속성)

Examples:
  $(basename "$0") new "새 기능 구현"
  $(basename "$0") list
  $(basename "$0") show W-001
  $(basename "$0") start W-001
  $(basename "$0") next-phase W-001
  $(basename "$0") complete W-001
  $(basename "$0") resume W-001
EOF
  exit 1
}

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

iso8601() {
  date -u +"%Y-%m-%dT%H:%M:%SZ"
}

# Convert title to kebab-case slug
# Python heredoc 사용 — POSIX sed의 한글 문자 범위(가-힣) collation 오류 회피,
# 제목에 따옴표·특수문자가 있어도 shell escape 문제 없음
to_slug() {
  local title="$1"
  python3 - "$title" <<'PYEOF'
import re, sys
t = sys.argv[1].lower()
t = re.sub(r'[^\w]', '-', t)   # \w = Unicode word chars (한글 포함)
t = re.sub(r'-+', '-', t).strip('-')
print(t)
PYEOF
}

# Find the next W-XXX number by scanning all three stage dirs
next_work_number() {
  local max="0"
  while IFS= read -r -d '' dir; do
    local base
    base="$(basename "$dir")"
    if [[ "$base" =~ ^W-([0-9]+) ]]; then
      local n="${BASH_REMATCH[1]}"
      n=$((10#$n))  # strip leading zeros
      if (( n > max )); then max=$n; fi
    fi
  done < <(find "$WORKS_DIR" -mindepth 2 -maxdepth 2 -type d -print0 2>/dev/null)
  printf "%03d" $(( max + 1 ))
}

# Locate the directory for a given Work ID across all stage dirs
find_work_dir() {
  local id="$1"  # e.g. W-001
  local result
  result="$(find "$WORKS_DIR" -mindepth 2 -maxdepth 2 -type d -name "${id}-*" 2>/dev/null | head -1 || true)"
  if [[ -z "$result" ]]; then
    echo "Error: Work '$id' not found under $WORKS_DIR" >&2
    exit 1
  fi
  echo "$result"
}

# Locate the primary .md file inside a work directory
find_work_md() {
  local dir="$1"
  local id
  id="$(basename "$dir" | grep -oE '^W-[0-9]+')"
  find "$dir" -maxdepth 1 -name "${id}-*.md" | head -1 || true
}

# Read a frontmatter field value from a work .md file
get_field() {
  local file="$1"
  local field="$2"
  python3 - "$file" "$field" <<'PYEOF'
import sys, re
file, field = sys.argv[1], sys.argv[2]
with open(file) as f:
    content = f.read()
m = re.search(r'^---\n(.*?)\n---', content, re.DOTALL)
if not m:
    sys.exit(0)
fm = m.group(1)
pat = re.compile(r'^' + re.escape(field) + r':\s*(.+)$', re.MULTILINE)
hit = pat.search(fm)
if hit:
    val = hit.group(1).strip().strip('"').strip("'")
    print(val)
PYEOF
}

# Update (or insert) a frontmatter scalar field in a work .md file
set_field() {
  local file="$1"
  local field="$2"
  local value="$3"
  python3 - "$file" "$field" "$value" <<'PYEOF'
import sys, re

file, field, value = sys.argv[1], sys.argv[2], sys.argv[3]
with open(file) as f:
    content = f.read()

m = re.match(r'^(---\n)(.*?)(\n---)(.*)', content, re.DOTALL)
if not m:
    print(f"Error: no frontmatter found in {file}", file=sys.stderr)
    sys.exit(1)

open_fence, fm, close_fence, body = m.group(1), m.group(2), m.group(3), m.group(4)

pat = re.compile(r'^(' + re.escape(field) + r'):[ \t]*.*$', re.MULTILINE)
replacement = f'{field}: "{value}"' if ' ' in value or ':' in value else f'{field}: {value}'

if pat.search(fm):
    fm = pat.sub(replacement, fm)
else:
    fm = fm + f'\n{replacement}'

with open(file, 'w') as f:
    f.write(open_fence + fm + close_fence + body)
PYEOF
}

# Append a value to a frontmatter list field (phases_completed: [...])
append_to_list_field() {
  local file="$1"
  local field="$2"
  local item="$3"
  python3 - "$file" "$field" "$item" <<'PYEOF'
import sys, re

file, field, item = sys.argv[1], sys.argv[2], sys.argv[3]
with open(file) as f:
    content = f.read()

m = re.match(r'^(---\n)(.*?)(\n---)(.*)', content, re.DOTALL)
if not m:
    print(f"Error: no frontmatter in {file}", file=sys.stderr)
    sys.exit(1)

open_fence, fm, close_fence, body = m.group(1), m.group(2), m.group(3), m.group(4)

pat = re.compile(r'^(' + re.escape(field) + r'):[ \t]*\[(.*?)\][ \t]*$', re.MULTILINE)
hit = pat.search(fm)
if hit:
    existing = hit.group(2).strip()
    if existing:
        new_list = f'[{existing}, {item}]'
    else:
        new_list = f'[{item}]'
    fm = pat.sub(f'{field}: {new_list}', fm)
else:
    fm = fm + f'\n{field}: [{item}]'

with open(file, 'w') as f:
    f.write(open_fence + fm + close_fence + body)
PYEOF
}

# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------

cmd_new() {
  if [[ $# -lt 1 ]]; then
    echo "Error: 'new' requires a title argument" >&2
    echo "Usage: $(basename "$0") new <title>" >&2
    exit 1
  fi
  local title="$*"
  local num
  num="$(next_work_number)"
  local id="W-${num}"
  local slug
  slug="$(to_slug "$title")"
  local dir="${WORKS_DIR}/idea/${id}-${slug}"
  local now
  now="$(iso8601)"

  if [[ -d "$dir" ]]; then
    echo "Error: Directory already exists: $dir" >&2
    exit 1
  fi

  mkdir -p "$dir"

  # Escape special characters in title to prevent heredoc injection
  local title_esc
  title_esc="${title//\\/\\\\}"
  title_esc="${title_esc//\`/\\\`}"
  title_esc="${title_esc//\$/\\\$}"

  # --- W-XXX-{slug}.md ---
  cat > "${dir}/${id}-${slug}.md" <<MDEOF
---
work_id: "${id}"
title: "${title_esc}"
status: idea
current_phase: idea
phases_completed: []
size: ""
priority: P2
tags: []
created_at: "${now}"
updated_at: "${now}"
---

# ${title_esc}

> Work ID: ${id}
> Status: idea

## 요약

## 요구사항

## 다음 단계
MDEOF

  # --- progress.md ---
  cat > "${dir}/progress.md" <<MDEOF
# Progress: ${title_esc}

> Work ID: ${id}
> Last Updated: ${now}

## Phase 진행 상황

### Planning Phase
- [ ] 규모 판단
- [ ] 요구사항 명확화
- [ ] 구현 계획 수립

### Development Phase
- [ ] 대기 중 (Planning 완료 후)

### Validation Phase
- [ ] 대기 중 (Development 완료 후)

## 체크포인트

| 날짜 | Phase | 체크포인트 | 상태 |
|------|-------|-----------|------|
MDEOF

  # --- decisions.md ---
  cat > "${dir}/decisions.md" <<MDEOF
# Decisions: ${title_esc}

> Work ID: ${id}
> Last Updated: ${now}

## 의사결정 기록
MDEOF

  # --- planning-results.md ---
  cat > "${dir}/planning-results.md" <<MDEOF
# Planning 결과: ${title_esc}

> Work ID: ${id}
> Last Updated: ${now}

## 규모 판단
## 요구사항 명확화
## 구현 계획
MDEOF

  echo "Created: ${id}"
  echo "Title  : ${title}"
  echo "Path   : ${dir}"
}

cmd_list() {
  local found=0
  for stage in idea active completed; do
    local stage_dir="${WORKS_DIR}/${stage}"
    [[ -d "$stage_dir" ]] || continue
    while IFS= read -r -d '' work_dir; do
      local base
      base="$(basename "$work_dir")"
      local id
      id="$(echo "$base" | grep -oE '^W-[0-9]+')"
      [[ -z "$id" ]] && continue
      local md
      md="$(find_work_md "$work_dir" 2>/dev/null)"
      if [[ -z "$md" ]]; then
        printf "  %-8s  %-40s  %-10s  %-4s\n" "$id" "(no md file)" "$stage" "-"
        found=1
        continue
      fi
      local title status priority
      title="$(get_field "$md" title)"
      status="$(get_field "$md" status)"
      priority="$(get_field "$md" priority)"
      printf "  %-8s  %-40s  %-10s  %-4s\n" "$id" "$title" "${status:-$stage}" "${priority:--}"
      found=1
    done < <(find "$stage_dir" -mindepth 1 -maxdepth 1 -type d -print0 2>/dev/null | sort -z)
  done

  if (( found == 0 )); then
    echo "No works found under $WORKS_DIR"
  fi
}

cmd_show() {
  if [[ $# -lt 1 ]]; then
    echo "Error: 'show' requires a Work ID (e.g. W-001)" >&2
    exit 1
  fi
  local id
  id="$(echo "$1" | tr '[:lower:]' '[:upper:]')"  # normalise to uppercase
  local dir
  dir="$(find_work_dir "$id")"
  local md
  md="$(find_work_md "$dir")"
  if [[ -z "$md" ]]; then
    echo "Error: No primary .md file found in $dir" >&2
    exit 1
  fi

  # Print frontmatter + content up to and including the second H2 section
  python3 - "$md" <<'PYEOF'
import sys, re
with open(sys.argv[1]) as f:
    content = f.read()

# Extract frontmatter
fm_m = re.match(r'^---\n(.*?)\n---\n', content, re.DOTALL)
if fm_m:
    print('---')
    print(fm_m.group(1))
    print('---')
    rest = content[fm_m.end():]
else:
    rest = content

# Print up to (and including) the second H2 block
lines = rest.splitlines()
h2_count = 0
out = []
for line in lines:
    if line.startswith('## '):
        h2_count += 1
        if h2_count > 2:
            break
    out.append(line)

print('\n'.join(out))
PYEOF
}

cmd_start() {
  if [[ $# -lt 1 ]]; then
    echo "Error: 'start' requires a Work ID (e.g. W-001)" >&2
    exit 1
  fi
  local id
  id="$(echo "$1" | tr '[:lower:]' '[:upper:]')"
  local dir
  dir="$(find_work_dir "$id")"
  local stage
  stage="$(basename "$(dirname "$dir")")"

  if [[ "$stage" != "idea" ]]; then
    echo "Error: Work '$id' is in '$stage', not 'idea'" >&2
    exit 1
  fi

  local dest="${WORKS_DIR}/active/$(basename "$dir")"
  mv "$dir" "$dest"

  local md
  md="$(find_work_md "$dest")"
  local now
  now="$(iso8601)"

  set_field "$md" status active
  set_field "$md" started_at "$now"
  set_field "$md" updated_at "$now"

  echo "Started: $id"
  echo "Moved  : $dest"
}

cmd_next_phase() {
  if [[ $# -lt 1 ]]; then
    echo "Error: 'next-phase' requires a Work ID (e.g. W-001)" >&2
    exit 1
  fi
  local id
  id="$(echo "$1" | tr '[:lower:]' '[:upper:]')"
  local dir
  dir="$(find_work_dir "$id")"
  local md
  md="$(find_work_md "$dir")"
  local now
  now="$(iso8601)"

  local current_phase
  current_phase="$(get_field "$md" current_phase)"

  local next_phase
  case "$current_phase" in
    idea)      next_phase="planning" ;;
    planning)  next_phase="development" ;;
    development) next_phase="validation" ;;
    validation)
      echo "Error: Work '$id' is already in 'validation' (final phase). Use 'complete' to finish." >&2
      exit 1
      ;;
    *)
      echo "Error: Unknown current_phase '${current_phase}' for '$id'" >&2
      exit 1
      ;;
  esac

  append_to_list_field "$md" phases_completed "$current_phase"
  set_field "$md" current_phase "$next_phase"
  set_field "$md" updated_at "$now"

  # Append checkpoint to progress.md
  local progress_md="${dir}/progress.md"
  if [[ -f "$progress_md" ]]; then
    printf "| %s | %s → %s | Phase 전환 | 완료 |\n" \
      "$(date -u +"%Y-%m-%d")" "$current_phase" "$next_phase" >> "$progress_md"
  fi

  echo "Phase  : ${current_phase} → ${next_phase}"
  echo "Work   : $id"
}

cmd_complete() {
  if [[ $# -lt 1 ]]; then
    echo "Error: 'complete' requires a Work ID (e.g. W-001)" >&2
    exit 1
  fi
  local id
  id="$(echo "$1" | tr '[:lower:]' '[:upper:]')"
  local dir
  dir="$(find_work_dir "$id")"
  local stage
  stage="$(basename "$(dirname "$dir")")"

  if [[ "$stage" != "active" ]]; then
    echo "Error: Work '$id' is in '$stage', not 'active'" >&2
    exit 1
  fi

  local dest="${WORKS_DIR}/completed/$(basename "$dir")"
  mv "$dir" "$dest"

  local md
  md="$(find_work_md "$dest")"
  local now
  now="$(iso8601)"

  set_field "$md" status completed
  set_field "$md" completed_at "$now"
  set_field "$md" updated_at "$now"

  # Only append validation if not already present (e.g. added by next-phase)
  local phases
  phases="$(get_field "$md" phases_completed)"
  if [[ "$phases" != *"validation"* ]]; then
    append_to_list_field "$md" phases_completed validation
  fi

  echo "Completed: $id"
  echo "Moved    : $dest"
}

cmd_resume() {
  if [[ $# -lt 1 ]]; then
    echo "Error: 'resume' requires a Work ID (e.g. W-001)" >&2
    exit 1
  fi
  local id
  id="$(echo "$1" | tr '[:lower:]' '[:upper:]')"
  local dir
  dir="$(find_work_dir "$id")"
  local stage
  stage="$(basename "$(dirname "$dir")")"

  if [[ "$stage" != "active" ]]; then
    echo "Error: Work '$id' is in '$stage', not 'active'" >&2
    echo "Tip   : Use 'start $id' to move it to active first" >&2
    exit 1
  fi

  echo "Resuming $id with persistent task list (CLAUDE_CODE_TASK_LIST_ID=$id)"
  echo "Tasks will be preserved across sessions."
  shift
  exec env CLAUDE_CODE_TASK_LIST_ID="$id" claude "$@"
}

# ---------------------------------------------------------------------------
# Dispatch
# ---------------------------------------------------------------------------

if [[ $# -lt 1 ]]; then
  usage
fi

command="$1"
shift

case "$command" in
  new)         cmd_new "$@" ;;
  list)        cmd_list ;;
  show)        cmd_show "$@" ;;
  start)       cmd_start "$@" ;;
  next-phase)  cmd_next_phase "$@" ;;
  complete)    cmd_complete "$@" ;;
  resume)      cmd_resume "$@" ;;
  *)
    echo "Error: Unknown command '$command'" >&2
    usage
    ;;
esac
