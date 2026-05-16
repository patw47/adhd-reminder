# ADHD Reminder

A Telegram-based task capture and reminder system designed for ADHD brains — fast capture, automatic categorisation, priority selection via inline buttons, recurring reminders with snooze, and a daily morning recap.

## Features

- **Task capture** — text or voice transcription, auto-categorised
- **Auto-categorization**: personal, budget, coding, health, work, other
- **Priority keyboard** — Telegram inline buttons: Urgent / High / Normal / Low
- **Smart reminders** — recurring, cron-driven, frequency tied to priority (urgent every 2h → low once/week)
- **Snooze** — delay a reminder with one button tap
- **Morning recap** — daily 08:00 Paris time summary of all pending tasks
- **Quiet hours** — no reminders between 21:00 and 08:00 Paris time
- **Natural completion** — mark tasks done via free text ("I did it", "done")

## Tech stack

- Python 3
- SQLite (local database)
- Telegram Bot API
- Cron (task scheduling)
- [OpenClaw](https://openclaw.dev)

## Requirements

- A running OpenClaw instance with a Telegram channel configured
- Python 3.10+
- `ffmpeg` and `openai-whisper` installed on the VPS

## Project structure

```
adhd-reminder/
├── scripts/
│   ├── todo.py       # Core logic: add, list, remind, handle callbacks
│   └── remind.sh     # Cron entry point (reminders + morning recap)
├── schema.sql        # Database schema (no data)
└── SKILL.md          # OpenClaw skill definition
```

---

## Installation

### 1. Install dependencies

```bash
sudo apt install -y ffmpeg
pip install openai-whisper --break-system-packages
```

### 2. Enable audio transcription in OpenClaw

```bash
openclaw config set tools.media.audio.enabled true
openclaw config set tools.media.audio.echoTranscript true
openclaw config validate
```

### 3. Copy the skill into your OpenClaw workspace

```bash
cp -r adhd-reminder /home/micheline/.openclaw/workspace/skills/
```

### 4. Enable the skill in openclaw.json

Add the following entry under `skills.entries`:

```json
"adhd-reminder": { "enabled": true }
```

Or via CLI:

```bash
openclaw config set skills.entries.adhd-reminder.enabled true
```

### 5. Set up the reminder cron job

The skill includes a `remind.sh` script that must run every 30 minutes
to check pending tasks and send Telegram reminders.

Add it to the agent's crontab:

```bash
sudo -u micheline crontab -e
```

Add this line:

```
*/30 * * * * /home/micheline/.openclaw/workspace/skills/adhd-reminder/scripts/remind.sh
```

### 6. Set up the daily recap

The daily recap runs at 08:00 Paris time. Add a second cron entry:

```
0 8 * * * TZ=Europe/Paris /home/micheline/.openclaw/workspace/skills/adhd-reminder/scripts/remind.sh --daily-recap
```

### 7. Restart OpenClaw

```bash
sudo systemctl restart openclaw-gateway.service
sudo systemctl status openclaw-gateway.service
```

---

## Database

Schema defined in `schema.sql`. The `.db` file is excluded from version control — create it locally:

```bash
sqlite3 adhd-reminder.db < schema.sql
```

Tasks are stored in SQLite at:
/home/youragent/.openclaw/workspace/adhd-reminder/adhd-reminder.db

| Field            | Type | Description                      |
|------------------|------|----------------------------------|
| id               | TEXT | UUID                             |
| text             | TEXT | Task description                 |
| category         | TEXT | personal, budget, coding, etc.   |
| priority         | TEXT | urgent, high, normal, low        |
| status           | TEXT | pending, done, snoozed           |
| created_at       | TEXT | ISO datetime                     |
| next_reminder_at | TEXT | When to send the next reminder   |
| snoozed_until    | TEXT | Snooze expiry datetime           |

---

## Usage

**Add a task** — send a voice note or text message to Micheline on Telegram:

> "I need to pay the electricity bill before Friday"

Micheline will confirm what she understood, detect the category, and ask for priority:

> 💡 Got it: **Pay electricity bill** · Category: 💰 Budget
> What's the priority?
> 🔴 Urgent  🟠 High  🟡 Normal  🔵 Low

**Confirm a task is done** — tap ✅ Done on any reminder, or just tell her:

> "Done", "paid it", "took care of it"

**Snooze a reminder** — tap ⏰ Later — it reschedules by the same interval as the priority.

**Ask for your tasks** — at any time:

> "What are my urgent tasks?"
> "Show me my budget tasks"
> "Give me my full task list"

---

## Reminder Frequencies

| Priority   | Frequency       |
|------------|----------------|
| 🔴 Urgent  | Every 2 hours  |
| 🟠 High    | Every 24 hours |
| 🟡 Normal  | Every 3.5 days |
| 🔵 Low     | Every 7 days   |

Night silence: **21:00 → 08:00 Paris time** — no reminders are sent during this window.
If a reminder falls within the night window, it is automatically pushed to 08:00 the next morning.

---

## Categories

`lifestyle` · `budget` · `coding` · `health` · `work` · `other`

## License

MIT
