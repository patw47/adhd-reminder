# ADHD Reminder

A Telegram-based task capture and reminder system designed for ADHD brains — fast capture, automatic categorisation, priority selection via inline buttons, recurring reminders with snooze, and a daily morning recap.

## Features

- **Task capture** — text or voice transcription, auto-categorised
- **Priority keyboard** — Telegram inline buttons: Urgent / High / Normal / Low
- **Smart reminders** — recurring, cron-driven, frequency tied to priority
- **Snooze** — delay a reminder with one button tap
- **Morning recap** — daily 08:00 Paris time summary of all pending tasks
- **Quiet hours** — no reminders between 21:00 and 08:00 Paris time
- **Natural completion** — mark tasks done via free text ("I did it", "done")

## Tech stack

- Python 3
- SQLite (local database)
- Telegram Bot API
- Cron (task scheduling)
- [OpenClaw](https://openclaw.dev) skill runtime

## Project structure

```
adhd-reminder/
├── scripts/
│   ├── todo.py       # Core logic: add, list, remind, handle callbacks
│   └── remind.sh     # Cron entry point (reminders + morning recap)
├── schema.sql        # Database schema (no data)
└── SKILL.md          # OpenClaw skill definition
```

## Database

Schema defined in `schema.sql`. The `.db` file is excluded from version control — create it locally:

```bash
sqlite3 adhd-reminder.db < schema.sql
```

## Reminder frequencies

| Priority | Interval     |
|----------|--------------|
| Urgent   | every 2h     |
| High     | every 24h    |
| Normal   | every 3.5 days |
| Low      | every 7 days |

## Categories

`lifestyle` · `budget` · `coding` · `health` · `work` · `montana` · `biscarosse` · `other`

## Setup

1. Clone the repo
2. Set environment variables: `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`
3. Init the database: `sqlite3 adhd-reminder.db < schema.sql`
4. Add cron jobs pointing to `scripts/remind.sh`

## License

MIT
