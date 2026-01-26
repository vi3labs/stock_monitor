#!/bin/bash
# Stock Monitor Report Runner
# Wrapper script for cron jobs with logging

SCRIPT_DIR="/Users/tom/Documents/VScode/stock_monitor"
PYTHON="/Library/Frameworks/Python.framework/Versions/3.13/bin/python3"
LOG_FILE="$SCRIPT_DIR/cron.log"

cd "$SCRIPT_DIR"

# Load environment variables
if [ -f "$SCRIPT_DIR/.env" ]; then
    export $(grep -v '^#' "$SCRIPT_DIR/.env" | xargs)
fi

echo "========================================" >> "$LOG_FILE"
echo "$(date): Running $1 report" >> "$LOG_FILE"
echo "========================================" >> "$LOG_FILE"

case "$1" in
    premarket)
        $PYTHON premarket_report.py >> "$LOG_FILE" 2>&1
        ;;
    postmarket)
        $PYTHON postmarket_report.py >> "$LOG_FILE" 2>&1
        ;;
    weekly)
        $PYTHON weekly_report.py >> "$LOG_FILE" 2>&1
        ;;
    *)
        echo "Usage: $0 {premarket|postmarket|weekly}" >> "$LOG_FILE"
        exit 1
        ;;
esac

echo "$(date): $1 report completed" >> "$LOG_FILE"
echo "" >> "$LOG_FILE"
