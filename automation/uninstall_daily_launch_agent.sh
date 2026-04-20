#!/bin/zsh
set -euo pipefail

AGENT_LABEL="com.onlyjobs.daily-scrape"
PLIST_PATH="$HOME/Library/LaunchAgents/$AGENT_LABEL.plist"
AUTOMATION_HOME="$HOME/.onlyjobs-automation"

launchctl bootout "gui/$(id -u)" "$PLIST_PATH" >/dev/null 2>&1 || true
rm -f "$PLIST_PATH"

echo "Removed $AGENT_LABEL"
echo "Plist deleted from $PLIST_PATH"
echo "Automation runtime kept at $AUTOMATION_HOME"
