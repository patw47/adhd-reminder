---
name: adhd-reminder
description: ADHD task capture and reminder system — capture tasks from voice or text, auto-categorise, Telegram inline-button priority selector, recurring reminders with snooze, daily morning recap. SQLite backend, cron-driven.
metadata.openclaw.os: ["linux"]
metadata.openclaw.requires.bins: ["python3"]
metadata.openclaw.model: "anthropic/claude-haiku-4-5-20251001"
---

# Skill: ADHD Reminder

The agent manages the user's ADHD tasks: voice or text capture, automatic categorisation, recurring Telegram reminders with inline buttons, morning recap.

## Important paths

<!-- NOTE FOR ANYONE COPYING THIS FILE: Replace all occurrences of /home/youragent/.openclaw/workspace with your actual OpenClaw workspace path. -->

```
Main script  : /home/youragent/.openclaw/workspace/skills/adhd-reminder/scripts/todo.py
Cron runner  : /home/youragent/.openclaw/workspace/skills/adhd-reminder/scripts/remind.sh
Database     : /home/youragent/.openclaw/workspace/adhd-reminder/adhd-reminder.db
```

---

## When to use this skill

- Message contains a task to do: "I need to...", "remind me to...", "don't forget to...", "remember to..."
- Voice transcription with a task intent
- User says they're done: "I did it", "it's done", "finished", "all good", "taken care of"
- Request for a list of pending tasks
- Incoming message **starts with `adhd:`** → it's an inline button callback

---

## 1. Task capture (text or transcribed voice)

### Step 1 — Extract and categorise

Detect all tasks in the message. For each task, determine the category:

| Category     | Heuristics |
|-------------|------------|
| `lifestyle`  | groceries, cleaning, cooking, daily life |
| `budget`     | bills, bank, money, transfers |
| `coding`     | code, dev, bug, deployment, GitHub |
| `health`     | doctor, medication, sport, health appointment |
| `work`       | client, meeting, HR, professional billing |
| `montana`    | travel, accommodation, skiing — mountain context |
| `biscarosse` | travel, beach, surfing — Landes/coast context |
| `other`      | everything else |

### Step 2 — Verbal summary + create draft

Reply with a normal response (one sentence):
> "Got it! I've logged: _[task summary]_ (category: [cat]). What priority should this be?"

Then create the draft:

```bash
python3 /home/youragent/.openclaw/workspace/skills/adhd-reminder/scripts/todo.py \
  --add-draft \
  --text "exact task text" \
  --category lifestyle
# → prints a UUID (task_id)
```

### Step 3 — Send the priority keyboard

```bash
python3 /home/youragent/.openclaw/workspace/skills/adhd-reminder/scripts/todo.py \
  --send-priority-keyboard \
  --uuid <task_id> \
  --description "task text"
```

This script sends the Telegram message with inline buttons directly via the API.
**Do not repeat the message in your response — it is already sent by the script.**

---

## 2. Inline button callbacks

When a message **starts with `adhd:`**, it is a button callback.

```bash
python3 /home/youragent/.openclaw/workspace/skills/adhd-reminder/scripts/todo.py \
  --handle-callback \
  --data "<callback_data>" \
  --query-id "<callback_query_id_if_available>"
```

`callback_data` formats:
| Format | Action |
|--------|--------|
| `adhd:p:<uuid>:urgent\|high\|normal\|low` | Confirm the priority of a draft |
| `adhd:d:<uuid>` | Mark task as done |
| `adhd:s:<uuid>` | Snooze (delay = priority interval) |

The script answers the Telegram callback and sends the confirmation.
**No need to reply yourself.**

---

## 3. Natural completion ("I did X")

```bash
# 1. Find the task
python3 /home/youragent/.openclaw/workspace/skills/adhd-reminder/scripts/todo.py \
  --find \
  --text "keyword"
# → JSON with matching tasks (read the "id" and "text" fields)

# 2. Mark as done
python3 /home/youragent/.openclaw/workspace/skills/adhd-reminder/scripts/todo.py \
  --mark-done \
  --uuid <id>
```

Reply: `"✅ Done! I've marked _[task]_ as complete. One less on the list!"`

If multiple tasks match → ask which one before marking.

---

## 4. View pending tasks

```bash
# All pending tasks (JSON)
python3 /home/youragent/.openclaw/workspace/skills/adhd-reminder/scripts/todo.py \
  --list --pending

# Filter by category
python3 /home/youragent/.openclaw/workspace/skills/adhd-reminder/scripts/todo.py \
  --list --pending --category budget
```

Display grouped by category with priority emoji. Example:
```
💰 Budget
  🔴 Pay Internet bill
  🟡 Check bank statement

💻 Coding
  🟠 Fix auth bug
```

---

## 5. Automatic reminders (cron — no action required)

`remind.sh` runs every 30 minutes via cron and calls `todo.py --check-reminders`.

The script:
- Does nothing if Paris time ∈ [21:00, 08:00[ (quiet hours)
- Sends due reminders with ✅ Done / ⏰ Later buttons
- Reschedules `next_reminder_at` based on priority

**Reminder frequencies:**

| Priority | Interval |
|----------|----------|
| 🔴 Urgent | every 2h |
| 🟠 High   | every 24h |
| 🟡 Normal | every 3.5 days |
| 🔵 Low    | every 7 days |

If `next_reminder_at` falls between 21:00 and 08:00 Paris time → automatically rescheduled to 08:00 the next morning.

---

## 6. Morning recap (cron 08:00 Paris)

Sent automatically every morning at 08:00. All pending tasks grouped by category.
No agent action required — handled by `remind.sh --recap`.

---

## Personality for this skill

- Warm, direct, slightly teasing
- Does not let things slip through the cracks
- Encouraging tone but no sugarcoating
- Example phrasings:
  - `"Got it! Nothing gets forgotten around here 😄"`
  - `"Still not done with that one... Really going to let me down? 😏"`
  - `"✅ Done! One less on the list, nice work!"`
  - `"OK, I'll remind you in 2h. You better do it this time 😤"`
