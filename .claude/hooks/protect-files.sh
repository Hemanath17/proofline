#!/bin/bash
# protect-files.sh
# PreToolUse hook for Edit|Write.
# Blocks edits to files that must never change. Exit code 2 blocks the tool call,
# and the message on stderr is shown to Claude as the reason.

INPUT=$(cat)

# Use Python to read the JSON input, so the hook does not depend on jq.
PYTHON_BIN=$(command -v python3 || command -v python)
if [ -z "$PYTHON_BIN" ]; then
  echo "protect-files.sh: Python not found, cannot check protected files" >&2
  exit 0
fi

FILE_PATH=$(printf '%s' "$INPUT" | "$PYTHON_BIN" -c 'import json, sys; data = json.load(sys.stdin); print(data.get("tool_input", {}).get("file_path", ""))')

# Normalize Windows backslashes so the patterns below match.
FILE_PATH="${FILE_PATH//\\//}"

if [ -z "$FILE_PATH" ]; then
  exit 0
fi

PROTECTED_PATTERNS=(
  "api/data/packet.json"
  "/.env"
)

for PATTERN in "${PROTECTED_PATTERNS[@]}"; do
  if [[ "$FILE_PATH" == *"$PATTERN"* ]]; then
    echo "Blocked: $FILE_PATH is protected ($PATTERN). The packet is read-only and secrets are never edited by Claude. If this change is truly needed, stop and ask the user." >&2
    exit 2
  fi
done

exit 0
