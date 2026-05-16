#!/bin/bash
# Cron runner for adhd-reminder. Called every 30min (and at 08:00 for recap).
SCRIPT_DIR="$(dirname "$(readlink -f "$0")")"
PYTHON3="$(which python3)"

if [ "$1" = "--recap" ]; then
    "$PYTHON3" "$SCRIPT_DIR/todo.py" --daily-recap
else
    "$PYTHON3" "$SCRIPT_DIR/todo.py" --check-reminders
fi
