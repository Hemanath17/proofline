#!/bin/bash
# after-compact.sh
# SessionStart hook with matcher "compact".
# Whatever this script prints is added to Claude's context after the conversation is compacted.

PROJECT_DIR="${CLAUDE_PROJECT_DIR:-.}"
TODO_FILE="$PROJECT_DIR/docs/TODO.md"

echo "Context was just compacted. Reminders:"
echo "- The packet (api/data/packet.json) is read-only; never read it whole."
echo "- Checks are general rules: never hard-code packet values or expected answers."
echo "- Show test output before saying a step is done; wait for the user's OK between steps."
echo ""

if [ -f "$TODO_FILE" ]; then
  echo "Current docs/TODO.md (first 40 lines):"
  head -n 40 "$TODO_FILE"
else
  echo "docs/TODO.md not found."
fi

exit 0
