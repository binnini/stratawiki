#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

SESSION_NAME="${1:-stratawiki-week1}"
PROMPT_FILE="${PROMPT_FILE:-$REPO_ROOT/dev-wiki/logs/2026-04-18-week-1-mvp-batch-prompt.txt}"
LOG_DIR="${LOG_DIR:-$REPO_ROOT/.codex-batch}"
LOG_FILE="$LOG_DIR/${SESSION_NAME}.log"
LAST_MESSAGE_FILE="$LOG_DIR/${SESSION_NAME}.last.txt"
CODEX_SANDBOX_MODE="${CODEX_SANDBOX_MODE:-danger-full-access}"
CODEX_USE_BYPASS="${CODEX_USE_BYPASS:-0}"

mkdir -p "$LOG_DIR"

if ! command -v tmux >/dev/null 2>&1; then
  echo "tmux is required but was not found in PATH." >&2
  exit 1
fi

if ! command -v codex >/dev/null 2>&1; then
  echo "codex is required but was not found in PATH." >&2
  exit 1
fi

if [[ ! -f "$PROMPT_FILE" ]]; then
  echo "Prompt file not found: $PROMPT_FILE" >&2
  exit 1
fi

if tmux has-session -t "$SESSION_NAME" 2>/dev/null; then
  echo "tmux session already exists: $SESSION_NAME" >&2
  exit 1
fi

RUN_CMD=$(
  cat <<EOF
cd "$REPO_ROOT" && $(if [[ "$CODEX_USE_BYPASS" == "1" ]]; then printf 'codex exec --dangerously-bypass-approvals-and-sandbox'; else printf 'codex exec --sandbox %q' "$CODEX_SANDBOX_MODE"; fi) -C "$REPO_ROOT" -o "$LAST_MESSAGE_FILE" - < "$PROMPT_FILE" 2>&1 | tee "$LOG_FILE"
EOF
)

tmux new-session -d -s "$SESSION_NAME" "$RUN_CMD"

echo "Started tmux session: $SESSION_NAME"
echo "Repo: $REPO_ROOT"
echo "Prompt: $PROMPT_FILE"
if [[ "$CODEX_USE_BYPASS" != "1" ]]; then
  echo "Sandbox mode: $CODEX_SANDBOX_MODE"
else
  echo "Sandbox mode: bypass approvals and sandbox"
fi
echo "Log: $LOG_FILE"
echo "Last message: $LAST_MESSAGE_FILE"
echo "Attach with: tmux attach -t $SESSION_NAME"
