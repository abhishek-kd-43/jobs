#!/bin/zsh
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
AGENT_LABEL="com.onlyjobs.daily-scrape"
LAUNCH_AGENTS_DIR="$HOME/Library/LaunchAgents"
PLIST_PATH="$LAUNCH_AGENTS_DIR/$AGENT_LABEL.plist"
AUTOMATION_HOME="$HOME/.onlyjobs-automation"
RUNTIME_DIR="$AUTOMATION_HOME/runtime"
RUN_SCRIPT="$RUNTIME_DIR/run_daily_scrape.sh"
LOG_DIR="$AUTOMATION_HOME/logs"
OUT_LOG="$LOG_DIR/launchd.out.log"
ERR_LOG="$LOG_DIR/launchd.err.log"
HOUR="${1:-8}"
MINUTE="${2:-0}"

if ! [[ "$HOUR" =~ ^[0-9]+$ ]] || [ "$HOUR" -lt 0 ] || [ "$HOUR" -gt 23 ]; then
  echo "Hour must be between 0 and 23."
  exit 1
fi

if ! [[ "$MINUTE" =~ ^[0-9]+$ ]] || [ "$MINUTE" -lt 0 ] || [ "$MINUTE" -gt 59 ]; then
  echo "Minute must be between 0 and 59."
  exit 1
fi

mkdir -p "$LAUNCH_AGENTS_DIR" "$LOG_DIR" "$RUNTIME_DIR"

cp "$REPO_DIR/scraper.py" "$RUNTIME_DIR/scraper.py"
cp "$REPO_DIR/scrape_now.py" "$RUNTIME_DIR/scrape_now.py"
cp "$REPO_DIR/state_portals.json" "$RUNTIME_DIR/state_portals.json"

if [ -f "$REPO_DIR/data.json" ] && [ ! -L "$REPO_DIR/data.json" ]; then
  cp "$REPO_DIR/data.json" "$RUNTIME_DIR/data.json"
elif [ ! -f "$RUNTIME_DIR/data.json" ]; then
  printf '{\n  "status": "success",\n  "results": [],\n  "admit_cards": [],\n  "latest_jobs": [],\n  "answer_keys": [],\n  "private_jobs": [],\n  "remote_jobs": []\n}\n' > "$RUNTIME_DIR/data.json"
fi

if [ -f "$REPO_DIR/scrape_status.json" ] && [ ! -L "$REPO_DIR/scrape_status.json" ]; then
  cp "$REPO_DIR/scrape_status.json" "$RUNTIME_DIR/scrape_status.json"
fi

cat > "$RUN_SCRIPT" <<EOF
#!/bin/zsh
set -u

RUNTIME_DIR="$RUNTIME_DIR"
LOG_DIR="$LOG_DIR"
LOG_FILE="\$LOG_DIR/daily_scrape.log"

mkdir -p "\$LOG_DIR"

timestamp() {
  date '+%Y-%m-%d %H:%M:%S'
}

{
  echo "[\$(timestamp)] Starting OnlyJobs daily scrape"
  echo "[\$(timestamp)] Runtime: \$RUNTIME_DIR"
} >> "\$LOG_FILE"

if ! command -v python3 >/dev/null 2>&1; then
  echo "[\$(timestamp)] ERROR: python3 not found in PATH" >> "\$LOG_FILE"
  exit 127
fi

export PYTHONDONTWRITEBYTECODE=1

cd "\$RUNTIME_DIR" || exit 1

python3 -u scrape_now.py >> "\$LOG_FILE" 2>&1
exit_code=\$?

if [ "\$exit_code" -eq 0 ]; then
  echo "[\$(timestamp)] Scrape completed successfully" >> "\$LOG_FILE"
else
  echo "[\$(timestamp)] Scrape failed with exit code \$exit_code" >> "\$LOG_FILE"
fi

exit "\$exit_code"
EOF

chmod +x "$RUN_SCRIPT"

cat > "$PLIST_PATH" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key>
  <string>$AGENT_LABEL</string>
  <key>ProgramArguments</key>
  <array>
    <string>/bin/zsh</string>
    <string>$RUN_SCRIPT</string>
  </array>
  <key>WorkingDirectory</key>
  <string>$REPO_DIR</string>
  <key>StartCalendarInterval</key>
  <dict>
    <key>Hour</key>
    <integer>$HOUR</integer>
    <key>Minute</key>
    <integer>$MINUTE</integer>
  </dict>
  <key>RunAtLoad</key>
  <false/>
  <key>StandardOutPath</key>
  <string>$OUT_LOG</string>
  <key>StandardErrorPath</key>
  <string>$ERR_LOG</string>
  <key>EnvironmentVariables</key>
  <dict>
    <key>PATH</key>
    <string>/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin</string>
    <key>PYTHONDONTWRITEBYTECODE</key>
    <string>1</string>
  </dict>
</dict>
</plist>
EOF

launchctl bootout "gui/$(id -u)" "$PLIST_PATH" >/dev/null 2>&1 || true
launchctl bootstrap "gui/$(id -u)" "$PLIST_PATH"
launchctl enable "gui/$(id -u)/$AGENT_LABEL" >/dev/null 2>&1 || true

echo "Installed $AGENT_LABEL"
echo "Schedule: every day at $(printf '%02d:%02d' "$HOUR" "$MINUTE") local time"
echo "Plist: $PLIST_PATH"
echo "Run once now: launchctl kickstart -k gui/$(id -u)/$AGENT_LABEL"
echo "Runtime: $RUNTIME_DIR"
echo "Logs: $LOG_DIR"
echo "Repo files remain normal files for GitHub compatibility."
