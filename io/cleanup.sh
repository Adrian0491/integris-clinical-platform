#!/usr/bin/env bash
set -euo pipefail

#############################################
# ClinicalDataComplianceTool-Prototype
# cleanup.sh — repo-root cleanup utility
#
# Features:
# - dry-run / execute
# - select targets: json/logs/cache/tmp/python/node/all
# - time filter: --older-than 7d|12h|30m
# - size filter: --min-size 5M|200K
# - safe trash: move to .trash/ instead of delete
# - git-aware: only untracked or only ignored
# - protect paths, include paths, exclude patterns
# - report bytes freed, counts, log file
#############################################

SCRIPT_NAME="$(basename "$0")"
REPO_ROOT="$(pwd)"

# Default settings
MODE="dry-run"                 # dry-run | execute
ACTION="delete"                # delete | trash
TARGETS=()                     # list of targets
OLDER_THAN=""                  # e.g. 7d 12h
MIN_SIZE=""                    # e.g. 5M 200K
MAX_SIZE=""                    # optional
INTERACTIVE=0
VERBOSE=0
JOBS=1
GIT_MODE="off"                 # off | untracked | ignored
FOLLOW_SYMLINKS=0

# Paths
TRASH_DIR=".trash"
STATE_DIR=".cleanup"
LOG_FILE=""

# Allow/deny controls
INCLUDE_PATHS=()               # if set: only clean inside these
PROTECT_PATHS=(                # never touch
  "./.git"
  "./venv"
  "./.venv"
  "./node_modules"
  "./.trash"
  "./.cleanup"
)
EXCLUDE_GLOBS=(                # skip these file globs anywhere
  "*/package-lock.json"
  "*/pnpm-lock.yaml"
  "*/yarn.lock"
  "*/tsconfig.json"
  "*/composer.json"
  "*/composer.lock"
)

# Config file support
CONFIG_FILE="cleanup.conf"

#############################################
# Helpers
#############################################

die() { echo "Something went wrong... $*" >&2; exit 1; }

info() { echo "Warning...  $*"; }

vlog() { [[ "$VERBOSE" -eq 1 ]] && echo "🧾 $*"; }

human_bytes() {
  # input bytes -> human readable
  local bytes="${1:-0}"
  awk -v b="$bytes" 'function human(x){
    s="B KB MB GB TB PB"; split(s,arr," ");
    for(i=1; x>=1024 && i<6; i++) x/=1024;
    return sprintf("%.2f %s", x, arr[i]);
  } BEGIN{print human(b)}'
}

parse_age_to_find_mmin() {
  # Converts 7d/12h/30m to find -mmin equivalent (integer)
  local spec="$1"
  [[ -z "$spec" ]] && echo "" && return 0
  if [[ "$spec" =~ ^([0-9]+)([dhm])$ ]]; then
    local n="${BASH_REMATCH[1]}"
    local u="${BASH_REMATCH[2]}"
    case "$u" in
      d) echo $(( n * 24 * 60 )) ;;
      h) echo $(( n * 60 )) ;;
      m) echo $(( n )) ;;
      *) die "Invalid age unit: $u" ;;
    esac
  else
    die "Invalid --older-than format: '$spec' (use 7d, 12h, 30m)"
  fi
}

parse_size_to_find() {
  # supports K M G suffix for find -size
  # find uses: c (bytes), k (1024), M, G
  local spec="$1"
  [[ -z "$spec" ]] && echo "" && return 0
  if [[ "$spec" =~ ^([0-9]+)([KMG])$ ]]; then
    echo "${BASH_REMATCH[1]}${BASH_REMATCH[2]}"
  elif [[ "$spec" =~ ^([0-9]+)B$ ]]; then
    echo "${BASH_REMATCH[1]}c"
  else
    die "Invalid size format: '$spec' (use 200K, 5M, 1G, 500B)"
  fi
}

ensure_repo_rootish() {
  [[ -d ".git" ]] || die "Run this from repo root (no .git directory found)."
}

load_config_if_present() {
  [[ -f "$CONFIG_FILE" ]] || return 0
  # shellcheck disable=SC1090
  source "$CONFIG_FILE"
}

make_logfile() {
  mkdir -p "$STATE_DIR"
  local ts
  ts="$(date +%Y%m%d-%H%M%S)"
  LOG_FILE="$STATE_DIR/cleanup-$ts.log"
  touch "$LOG_FILE"
}

log_line() {
  echo "$*" >> "$LOG_FILE"
}

usage() {
  cat <<EOF
Usage: ./$SCRIPT_NAME [options]

Modes:
  --dry-run                 Preview what would happen (default)
  --execute                 Actually perform cleanup

Actions:
  --delete                  Permanently delete matched files (default)
  --trash                   Move files to $TRASH_DIR/ (safer)

Targets (choose any, default: json logs):
  --json                    Clean *.json (typically generated outputs)
  --logs                    Clean *.log
  --cache                   Clean common cache dirs/files
  --tmp                     Clean temp dirs/files
  --python                  Clean __pycache__, *.pyc, .pytest_cache, etc.
  --node                    Clean node artifacts (dist/, .next/, coverage/, etc.)
  --all                     All targets above

Filters:
  --older-than 7d|12h|30m   Only files older than this
  --min-size 5M|200K|500B   Only files at least this size
  --max-size 1G             Only files at most this size

Scope / safety:
  --include path            Only clean inside this path (repeatable)
  --protect path            Never touch this path (repeatable)
  --exclude-glob pattern    Exclude files matching glob anywhere (repeatable)
  --follow-symlinks         Follow symlinks (default: no)

Git-aware:
  --git-untracked           Only remove untracked matching files
  --git-ignored             Only remove ignored matching files (safe for generated outputs)
  --git-off                 Disable git filtering (default)

Behavior:
  --interactive             Ask before performing operations
  --jobs N                  Parallelism for move/delete (default: 1)
  --verbose                 More logs
  --help                    Show help

Examples:
  ./$SCRIPT_NAME --dry-run --json --logs
  ./$SCRIPT_NAME --execute --trash --all --older-than 7d
  ./$SCRIPT_NAME --execute --delete --logs --git-ignored
  ./$SCRIPT_NAME --execute --trash --json --min-size 1M --interactive
EOF
}

#############################################
# Parse args
#############################################

TARGETS_DEFAULTED=1

while [[ $# -gt 0 ]]; do
  case "$1" in
    --dry-run) MODE="dry-run"; shift ;;
    --execute) MODE="execute"; shift ;;

    --delete) ACTION="delete"; shift ;;
    --trash) ACTION="trash"; shift ;;

    --json) TARGETS+=("json"); TARGETS_DEFAULTED=0; shift ;;
    --logs) TARGETS+=("logs"); TARGETS_DEFAULTED=0; shift ;;
    --cache) TARGETS+=("cache"); TARGETS_DEFAULTED=0; shift ;;
    --tmp) TARGETS+=("tmp"); TARGETS_DEFAULTED=0; shift ;;
    --python) TARGETS+=("python"); TARGETS_DEFAULTED=0; shift ;;
    --node) TARGETS+=("node"); TARGETS_DEFAULTED=0; shift ;;
    --all) TARGETS=("json" "logs" "cache" "tmp" "python" "node"); TARGETS_DEFAULTED=0; shift ;;

    --older-than) OLDER_THAN="${2:-}"; shift 2 ;;
    --min-size) MIN_SIZE="${2:-}"; shift 2 ;;
    --max-size) MAX_SIZE="${2:-}"; shift 2 ;;

    --include) INCLUDE_PATHS+=("$2"); shift 2 ;;
    --protect) PROTECT_PATHS+=("$2"); shift 2 ;;
    --exclude-glob) EXCLUDE_GLOBS+=("$2"); shift 2 ;;
    --follow-symlinks) FOLLOW_SYMLINKS=1; shift ;;

    --git-untracked) GIT_MODE="untracked"; shift ;;
    --git-ignored) GIT_MODE="ignored"; shift ;;
    --git-off) GIT_MODE="off"; shift ;;

    --interactive) INTERACTIVE=1; shift ;;
    --jobs) JOBS="${2:-1}"; shift 2 ;;
    --verbose) VERBOSE=1; shift ;;
    --help|-h) usage; exit 0 ;;

    *) die "Unknown option: $1 (use --help)" ;;
  esac
done

# Default targets if none specified
if [[ "$TARGETS_DEFAULTED" -eq 1 ]]; then
  TARGETS=("json" "logs")
fi

#############################################
# Build match rules
#############################################

ensure_repo_rootish
load_config_if_present
make_logfile

info "Repo: $REPO_ROOT"
info "Mode: $MODE | Action: $ACTION | Git mode: $GIT_MODE"
info "Targets: ${TARGETS[*]}"
log_line "Started: $(date)"
log_line "Mode=$MODE Action=$ACTION GitMode=$GIT_MODE Targets=${TARGETS[*]}"

[[ "$JOBS" =~ ^[0-9]+$ ]] || die "--jobs must be an integer"
[[ "$JOBS" -ge 1 ]] || die "--jobs must be >= 1"

# find options
FIND_OPTS=()
if [[ "$FOLLOW_SYMLINKS" -eq 1 ]]; then
  FIND_OPTS+=("-L")
fi

# time filter
MMIN=""
if [[ -n "$OLDER_THAN" ]]; then
  MMIN="$(parse_age_to_find_mmin "$OLDER_THAN")"
fi

# size filter
MINSIZE=""
MAXSIZE=""
if [[ -n "$MIN_SIZE" ]]; then
  MINSIZE="$(parse_size_to_find "$MIN_SIZE")"
fi
if [[ -n "$MAX_SIZE" ]]; then
  MAXSIZE="$(parse_size_to_find "$MAX_SIZE")"
fi

# scope roots
SEARCH_ROOTS=(".")
if [[ "${#INCLUDE_PATHS[@]}" -gt 0 ]]; then
  SEARCH_ROOTS=()
  for p in "${INCLUDE_PATHS[@]}"; do
    [[ -e "$p" ]] || die "Include path not found: $p"
    SEARCH_ROOTS+=("$p")
  done
fi

#############################################
# Target definitions
#############################################

# file patterns
FILE_PATTERNS=()
# dir patterns (to remove entire dirs)
DIR_PATTERNS=()

for t in "${TARGETS[@]}"; do
  case "$t" in
    json) FILE_PATTERNS+=("-name" "*.json") ;;
    logs) FILE_PATTERNS+=("-name" "*.log") ;;

    cache)
      DIR_PATTERNS+=(
        ".cache"
        ".mypy_cache"
        ".ruff_cache"
        ".pytest_cache"
      )
      FILE_PATTERNS+=("-name" "*.cache")
      ;;

    tmp)
      DIR_PATTERNS+=("tmp" "temp" ".tmp")
      FILE_PATTERNS+=("-name" "*.tmp")
      ;;

    python)
      DIR_PATTERNS+=("__pycache__" ".pytest_cache" ".tox" ".nox")
      FILE_PATTERNS+=("-name" "*.pyc" "-o" "-name" "*.pyo")
      ;;

    node)
      DIR_PATTERNS+=("dist" "build" ".next" "coverage" ".turbo")
      FILE_PATTERNS+=("-name" "*.tsbuildinfo")
      ;;

    *) die "Unknown target internal: $t" ;;
  esac
done

#############################################
# Build "protect prune" expression for find
#############################################

# protect paths -> prune
# We'll normalize to ./... style when possible.
PRUNE_EXPR=()
if [[ "${#PROTECT_PATHS[@]}" -gt 0 ]]; then
  PRUNE_EXPR+=("(")
  local_first=1
  for p in "${PROTECT_PATHS[@]}"; do
    # Accept both "dir" and "./dir"
    if [[ "$local_first" -eq 0 ]]; then PRUNE_EXPR+=("-o"); fi
    PRUNE_EXPR+=("-path" "$p" "-o" "-path" "${p#./}")
    local_first=0
  done
  PRUNE_EXPR+=(")" "-prune" "-false" "-o")
fi

#############################################
# Exclude globs helper (post-filter)
#############################################

is_excluded_glob() {
  local f="$1"
  for g in "${EXCLUDE_GLOBS[@]}"; do
    if [[ "$f" == $g ]]; then
      return 0
    fi
  done
  return 1
}

#############################################
# Gather candidates
#############################################

CANDIDATES_FILE="$STATE_DIR/candidates.txt"
: > "$CANDIDATES_FILE"

# 1) directory candidates
if [[ "${#DIR_PATTERNS[@]}" -gt 0 ]]; then
  for root in "${SEARCH_ROOTS[@]}"; do
    for dname in "${DIR_PATTERNS[@]}"; do
      # find dirs named dname, excluding protected
      find "${FIND_OPTS[@]}" "$root" \
        "${PRUNE_EXPR[@]}" \
        -type d -name "$dname" -print >> "$CANDIDATES_FILE" || true
    done
  done
fi

# 2) file candidates
if [[ "${#FILE_PATTERNS[@]}" -gt 0 ]]; then
  for root in "${SEARCH_ROOTS[@]}"; do
    # Build OR expression for patterns safely
    # Example: \( -name "*.json" -o -name "*.log" \)
    PAT_EXPR=()
    PAT_EXPR+=("(")
    # FILE_PATTERNS already has -o inserted in some cases; keep as-is.
    PAT_EXPR+=("${FILE_PATTERNS[@]}")
    PAT_EXPR+=(")")

    FIND_FILE_EXPR=( "${FIND_OPTS[@]}" "$root" )
    FIND_FILE_EXPR+=( "${PRUNE_EXPR[@]}" )
    FIND_FILE_EXPR+=( -type f "${PAT_EXPR[@]}" )

    # time filter
    if [[ -n "$MMIN" ]]; then
      FIND_FILE_EXPR+=( -mmin "+$MMIN" )
    fi
    # size filters
    if [[ -n "$MINSIZE" ]]; then
      FIND_FILE_EXPR+=( -size "+$MINSIZE" )
    fi
    if [[ -n "$MAXSIZE" ]]; then
      FIND_FILE_EXPR+=( -size "-$MAXSIZE" )
    fi

    # output
    find "${FIND_FILE_EXPR[@]}" -print >> "$CANDIDATES_FILE" || true
  done
fi

# De-duplicate
sort -u "$CANDIDATES_FILE" -o "$CANDIDATES_FILE"

#############################################
# Apply git filtering if requested
#############################################

GIT_FILTERED_FILE="$STATE_DIR/candidates.gitfiltered.txt"
: > "$GIT_FILTERED_FILE"

apply_git_filter() {
  local in_file="$1"
  local out_file="$2"

  if [[ "$GIT_MODE" == "off" ]]; then
    cp "$in_file" "$out_file"
    return
  fi

  if ! command -v git >/dev/null 2>&1; then
    die "git not found, but git filter requested"
  fi

  # We need paths relative to repo root without leading "./"
  local rel_list="$STATE_DIR/relpaths.txt"
  : > "$rel_list"
  while IFS= read -r p; do
    p="${p#./}"
    [[ -z "$p" ]] && continue
    echo "$p" >> "$rel_list"
  done < "$in_file"

  if [[ "$GIT_MODE" == "untracked" ]]; then
    # list untracked (not ignored)
    # we'll filter by membership
    git ls-files --others --exclude-standard > "$STATE_DIR/git_untracked.txt"
    grep -Fx -f "$STATE_DIR/git_untracked.txt" "$rel_list" \
      | sed 's|^|./|' > "$out_file" || true
  elif [[ "$GIT_MODE" == "ignored" ]]; then
    # list ignored
    git ls-files --others -i --exclude-standard > "$STATE_DIR/git_ignored.txt"
    grep -Fx -f "$STATE_DIR/git_ignored.txt" "$rel_list" \
      | sed 's|^|./|' > "$out_file" || true
  else
    die "Unknown git mode: $GIT_MODE"
  fi
}

apply_git_filter "$CANDIDATES_FILE" "$GIT_FILTERED_FILE"

#############################################
# Apply exclude globs
#############################################

FINAL_FILE="$STATE_DIR/candidates.final.txt"
: > "$FINAL_FILE"
while IFS= read -r f; do
  [[ -z "$f" ]] && continue
  if is_excluded_glob "$f"; then
    vlog "Excluded by glob: $f"
    continue
  fi
  echo "$f" >> "$FINAL_FILE"
done < "$GIT_FILTERED_FILE"

#############################################
# Compute report (count + bytes)
#############################################

COUNT=0
BYTES=0
while IFS= read -r f; do
  [[ -z "$f" ]] && continue
  if [[ -e "$f" ]]; then
    COUNT=$((COUNT + 1))
    # dirs count as 0 bytes here (we still remove them)
    if [[ -f "$f" ]]; then
      sz=$(stat -c%s "$f" 2>/dev/null || echo 0)
      BYTES=$((BYTES + sz))
    fi
  fi
done < "$FINAL_FILE"

info "Candidates: $COUNT"
info "Approx bytes: $(human_bytes "$BYTES")"
log_line "Candidates=$COUNT Bytes=$BYTES"

if [[ "$COUNT" -eq 0 ]]; then
  info "Nothing to do."
  info "Log: $LOG_FILE"
  exit 0
fi

#############################################
# Show plan
#############################################

echo
echo "Plan:"
echo " - Mode:   $MODE"
echo " - Action: $ACTION"
echo " - Files/dirs:"
head -n 50 "$FINAL_FILE" | sed 's/^/    /'
if [[ "$COUNT" -gt 50 ]]; then
  echo "    ... and $((COUNT - 50)) more"
fi
echo
echo "Full list: $FINAL_FILE"
echo "Log:       $LOG_FILE"
echo

if [[ "$INTERACTIVE" -eq 1 ]]; then
  read -p "Proceed? (y/N): " ans
  [[ "$ans" == "y" ]] || { info "Aborted."; exit 0; }
fi

#############################################
# Execute
#############################################

do_trash() {
  mkdir -p "$TRASH_DIR"
  # Keep structure under trash with timestamp root
  local ts
  ts="$(date +%Y%m%d-%H%M%S)"
  local base="$TRASH_DIR/$ts"
  mkdir -p "$base"

  # Move each item preserving path
  while IFS= read -r f; do
    [[ -z "$f" ]] && continue
    [[ -e "$f" ]] || continue
    local rel="${f#./}"
    local dest="$base/$rel"
    mkdir -p "$(dirname "$dest")"
    vlog "TRASH: $f -> $dest"
    log_line "TRASH $f -> $dest"
    mv -n "$f" "$dest"
  done < "$FINAL_FILE"
}

do_delete() {
  # Use xargs for parallel if requested
  if [[ "$JOBS" -gt 1 ]]; then
    # Only delete existing items; avoid issues with spaces using -0 pipeline
    # Build NUL list
    local nulfile="$STATE_DIR/candidates.nul"
    : > "$nulfile"
    while IFS= read -r f; do
      [[ -z "$f" ]] && continue
      [[ -e "$f" ]] || continue
      printf '%s\0' "$f" >> "$nulfile"
    done < "$FINAL_FILE"

    if [[ "$MODE" == "dry-run" ]]; then
      info "Dry-run: would delete (parallel jobs=$JOBS)"
      tr '\0' '\n' < "$nulfile" | sed 's/^/  /'
      return
    fi

    info "Deleting with parallelism (jobs=$JOBS)..."
    xargs -0 -P "$JOBS" -I{} bash -c '
      f="$1"
      if [[ -d "$f" ]]; then rm -rf -- "$f"; else rm -f -- "$f"; fi
    ' _ {} < "$nulfile"
  else
    while IFS= read -r f; do
      [[ -z "$f" ]] && continue
      [[ -e "$f" ]] || continue
      if [[ "$MODE" == "dry-run" ]]; then
        echo "DRY: would delete $f"
        log_line "DRY_DELETE $f"
        continue
      fi
      vlog "DELETE: $f"
      log_line "DELETE $f"
      if [[ -d "$f" ]]; then
        rm -rf -- "$f"
      else
        rm -f -- "$f"
      fi
    done < "$FINAL_FILE"
  fi
}

if [[ "$MODE" == "dry-run" ]]; then
  info "Dry-run only: no changes made."
  exit 0
fi

if [[ "$ACTION" == "trash" ]]; then
  info "Moving candidates to trash: $TRASH_DIR/"
  do_trash
elif [[ "$ACTION" == "delete" ]]; then
  info "Deleting candidates..."
  do_delete
else
  die "Unknown action: $ACTION"
fi

info "Cleanup done."
info "Log: $LOG_FILE"
