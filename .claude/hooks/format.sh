#!/bin/bash
# format.sh
# PostToolUse hook for Edit|Write.
# Formats the file Claude just edited. Never blocks: always exits 0.

INPUT=$(cat)

PYTHON_BIN=$(command -v python3 || command -v python)
if [ -z "$PYTHON_BIN" ]; then
  exit 0
fi

FILE_PATH=$(printf '%s' "$INPUT" | "$PYTHON_BIN" -c 'import json, sys; data = json.load(sys.stdin); print(data.get("tool_input", {}).get("file_path", ""))')

if [ -z "$FILE_PATH" ] || [ ! -f "$FILE_PATH" ]; then
  exit 0
fi

PROJECT_DIR="${CLAUDE_PROJECT_DIR:-.}"
PRETTIER_BIN="$PROJECT_DIR/node_modules/.bin/prettier"

case "$FILE_PATH" in
  *.py)
    if command -v ruff > /dev/null 2>&1; then
      ruff format --quiet "$FILE_PATH" > /dev/null 2>&1
    fi
    ;;
  *.ts|*.tsx|*.js|*.jsx|*.css)
    if [ -x "$PRETTIER_BIN" ]; then
      "$PRETTIER_BIN" --write --log-level silent "$FILE_PATH" > /dev/null 2>&1
    fi
    ;;
esac

exit 0
