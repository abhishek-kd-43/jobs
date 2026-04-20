#!/bin/zsh
set -u

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
LOG_DIR="$REPO_DIR/logs"
LOG_FILE="$LOG_DIR/daily_scrape.log"

mkdir -p "$LOG_DIR"

timestamp() {
  date '+%Y-%m-%d %H:%M:%S'
}

{
  echo "[$(timestamp)] Starting OnlyJobs daily scrape"
  echo "[$(timestamp)] Repo: $REPO_DIR"
} >> "$LOG_FILE"

if ! command -v python3 >/dev/null 2>&1; then
  echo "[$(timestamp)] ERROR: python3 not found in PATH" >> "$LOG_FILE"
  exit 127
fi

export PYTHONDONTWRITEBYTECODE=1

cd "$REPO_DIR" || exit 1

python3 -u scrape_now.py >> "$LOG_FILE" 2>&1
exit_code=$?

if [ "$exit_code" -eq 0 ]; then
  echo "[$(timestamp)] Scrape completed successfully" >> "$LOG_FILE"
else
  echo "[$(timestamp)] Scrape failed with exit code $exit_code" >> "$LOG_FILE"
fi

exit "$exit_code"
