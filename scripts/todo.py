#!/usr/bin/env python3
"""adhd-reminder: SQLite CRUD + Telegram reminder logic for Your Agent."""

import argparse
import json
import os
import sqlite3
import sys
import uuid
from datetime import datetime, timedelta
from urllib.request import urlopen, Request
from urllib.error import URLError
from zoneinfo import ZoneInfo

# ── Config (read from openclaw.json — no hardcoded secrets) ───────────────────

def _load_config():
    cfg_path = "/home/youragent/.openclaw/openclaw.json"
    with open(cfg_path) as f:
        cfg = json.load(f)
    bot_token = cfg["channels"]["telegram"]["accounts"]["default"]["botToken"]
    chat_id = int(cfg["commands"]["ownerAllowFrom"][0].split(":")[1])
    return bot_token, chat_id

BOT_TOKEN, CHAT_ID = _load_config()
DB_PATH = "/home/youragent/.openclaw/workspace/adhd-reminder/adhd-reminder.db"
TZ = ZoneInfo("Europe/Paris")
UTC = ZoneInfo("UTC")
TGAPI = f"https://api.telegram.org/bot{BOT_TOKEN}"

PRIORITY_INTERVALS = {
    "urgent": timedelta(hours=2),
    "high":   timedelta(hours=24),
    "normal": timedelta(hours=84),   # 3.5 days
    "low":    timedelta(hours=168),  # 7 days
}
PRIORITY_EMOJI = {"urgent": "🔴", "high": "🟠", "normal": "🟡", "low": "🔵"}
PRIORITY_LABEL = {"urgent": "Urgent", "high": "High", "normal": "Normal", "low": "Low"}
CATEGORY_EMOJI = {
    "lifestyle":  "🌿",
    "budget":     "💰",
    "coding":     "💻",
    "health":     "❤️",
    "work":       "💼",
    "other":      "📌",
}
CATEGORIES = list(CATEGORY_EMOJI.keys())
PRIORITIES  = list(PRIORITY_INTERVALS.keys())


# ── Timezone helpers ──────────────────────────────────────────────────────────

def now_utc() -> datetime:
    return datetime.now(UTC)

def now_paris() -> datetime:
    return datetime.now(TZ)

def is_night_shift(dt_paris: datetime) -> bool:
    h = dt_paris.hour
    return h >= 21 or h < 8

def adjust_for_night_shift(dt_utc: datetime) -> datetime:
    """Push dt_utc to 08:00 Paris if it lands in the 21h-8h silence window."""
    dt_p = dt_utc.astimezone(TZ)
    if not is_night_shift(dt_p):
        return dt_utc
    if dt_p.hour >= 21:
        target = (dt_p + timedelta(days=1)).replace(hour=8, minute=0, second=0, microsecond=0)
    else:
        target = dt_p.replace(hour=8, minute=0, second=0, microsecond=0)
    return target.astimezone(UTC)

def compute_next_reminder(priority: str) -> str:
    base = now_utc() + PRIORITY_INTERVALS[priority]
    return adjust_for_night_shift(base).isoformat()


# ── Telegram API ──────────────────────────────────────────────────────────────

def _tg(method: str, payload: dict) -> dict | None:
    url = f"{TGAPI}/{method}"
    body = json.dumps(payload).encode()
    req = Request(url, data=body, headers={"Content-Type": "application/json"})
    try:
        with urlopen(req, timeout=15) as r:
            return json.loads(r.read())
    except URLError as e:
        print(f"[TG ERROR] {method}: {e}", file=sys.stderr)
        return None

def send_message(text: str, reply_markup: dict | None = None) -> dict | None:
    payload: dict = {"chat_id": CHAT_ID, "text": text, "parse_mode": "HTML"}
    if reply_markup:
        payload["reply_markup"] = reply_markup
    return _tg("sendMessage", payload)

def answer_callback(query_id: str, text: str = "✅") -> None:
    _tg("answerCallbackQuery", {"callback_query_id": query_id, "text": text})


# ── Database ──────────────────────────────────────────────────────────────────

def get_db() -> sqlite3.Connection:
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("""
        CREATE TABLE IF NOT EXISTS tasks (
            id               TEXT PRIMARY KEY,
            text             TEXT NOT NULL,
            category         TEXT NOT NULL,
            priority         TEXT,
            status           TEXT NOT NULL DEFAULT 'pending',
            created_at       TEXT NOT NULL,
            next_reminder_at TEXT,
            snoozed_until    TEXT
        )
    """)
    conn.commit()
    return conn


# ── CRUD ──────────────────────────────────────────────────────────────────────

def validate(value: str, allowed: list, name: str) -> None:
    if value not in allowed:
        print(f"Invalid {name}: {value!r}. Allowed: {allowed}", file=sys.stderr)
        sys.exit(1)

def cmd_add(text: str, category: str, priority: str) -> str:
    validate(category, CATEGORIES, "category")
    validate(priority, PRIORITIES, "priority")
    conn = get_db()
    task_id = str(uuid.uuid4())
    conn.execute(
        "INSERT INTO tasks (id,text,category,priority,status,created_at,next_reminder_at) "
        "VALUES (?,?,?,?,'pending',?,?)",
        (task_id, text, category, priority, now_utc().isoformat(), compute_next_reminder(priority)),
    )
    conn.commit()
    conn.close()
    return task_id

def cmd_add_draft(text: str, category: str) -> str:
    validate(category, CATEGORIES, "category")
    conn = get_db()
    task_id = str(uuid.uuid4())
    conn.execute(
        "INSERT INTO tasks (id,text,category,priority,status,created_at) VALUES (?,?,?,NULL,'draft',?)",
        (task_id, text, category, now_utc().isoformat()),
    )
    conn.commit()
    conn.close()
    return task_id

def cmd_confirm_priority(task_id: str, priority: str) -> None:
    validate(priority, PRIORITIES, "priority")
    conn = get_db()
    conn.execute(
        "UPDATE tasks SET priority=?, status='pending', next_reminder_at=? WHERE id=?",
        (priority, compute_next_reminder(priority), task_id),
    )
    conn.commit()
    conn.close()

def cmd_mark_done(task_id: str) -> None:
    conn = get_db()
    conn.execute("UPDATE tasks SET status='done' WHERE id=?", (task_id,))
    conn.commit()
    conn.close()

def cmd_snooze(task_id: str) -> None:
    conn = get_db()
    row = conn.execute("SELECT priority FROM tasks WHERE id=?", (task_id,)).fetchone()
    if row and row["priority"]:
        nxt = compute_next_reminder(row["priority"])
        conn.execute(
            "UPDATE tasks SET status='snoozed', snoozed_until=?, next_reminder_at=? WHERE id=?",
            (nxt, nxt, task_id),
        )
        conn.commit()
    conn.close()

def cmd_list(pending_only: bool = False, category: str | None = None) -> list:
    conn = get_db()
    q = "SELECT * FROM tasks WHERE 1=1"
    params: list = []
    if pending_only:
        q += " AND status IN ('pending','snoozed')"
    if category:
        q += " AND category=?"
        params.append(category)
    q += " ORDER BY created_at DESC"
    rows = conn.execute(q, params).fetchall()
    conn.close()
    return [dict(r) for r in rows]

def cmd_find(text: str) -> list:
    conn = get_db()
    rows = conn.execute(
        "SELECT * FROM tasks WHERE status IN ('pending','snoozed','draft') "
        "AND lower(text) LIKE lower(?)",
        (f"%{text}%",),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ── Telegram senders ──────────────────────────────────────────────────────────

def cmd_send_priority_keyboard(task_id: str, description: str) -> None:
    text = f"📝 <b>Task logged:</b>\n{description}\n\nWhat priority?"
    keyboard = {"inline_keyboard": [[
        {"text": "🔴 Urgent", "callback_data": f"adhd:p:{task_id}:urgent"},
        {"text": "🟠 High",   "callback_data": f"adhd:p:{task_id}:high"},
        {"text": "🟡 Normal", "callback_data": f"adhd:p:{task_id}:normal"},
        {"text": "🔵 Low",    "callback_data": f"adhd:p:{task_id}:low"},
    ]]}
    send_message(text, reply_markup=keyboard)

def _send_reminder(task: dict) -> None:
    created = datetime.fromisoformat(task["created_at"]).astimezone(TZ)
    delta = now_paris() - created
    days = delta.days
    if days == 0:
        age = "since today"
    elif days == 1:
        age = "since yesterday"
    else:
        age = f"for {days} days"
    pe = PRIORITY_EMOJI.get(task["priority"] or "normal", "🟡")
    ce = CATEGORY_EMOJI.get(task["category"], "📌")
    text = (
        f"{pe} <b>Reminder</b> — {ce} <i>{task['category'].capitalize()}</i>\n"
        f"{task['text']}\n"
        f"<i>Pending {age}</i>"
    )
    keyboard = {"inline_keyboard": [[
        {"text": "✅ Done!",  "callback_data": f"adhd:d:{task['id']}"},
        {"text": "⏰ Later", "callback_data": f"adhd:s:{task['id']}"},
    ]]}
    send_message(text, reply_markup=keyboard)

def cmd_check_reminders() -> None:
    if is_night_shift(now_paris()):
        return
    now = now_utc().isoformat()
    conn = get_db()
    rows = conn.execute(
        "SELECT * FROM tasks WHERE status IN ('pending','snoozed') "
        "AND next_reminder_at IS NOT NULL AND next_reminder_at <= ?",
        (now,),
    ).fetchall()
    for row in rows:
        task = dict(row)
        _send_reminder(task)
        nxt = compute_next_reminder(task["priority"])
        conn.execute(
            "UPDATE tasks SET status='pending', next_reminder_at=? WHERE id=?",
            (nxt, task["id"]),
        )
    conn.commit()
    conn.close()

def cmd_daily_recap() -> None:
    conn = get_db()
    rows = conn.execute(
        "SELECT * FROM tasks WHERE status IN ('pending','snoozed') ORDER BY category, priority",
    ).fetchall()
    conn.close()
    if not rows:
        send_message("🌅 <b>Good morning!</b>\n\nNo pending tasks. Well done 🎉")
        return
    by_cat: dict = {}
    for r in rows:
        t = dict(r)
        by_cat.setdefault(t["category"], []).append(t)
    lines = ["🌅 <b>Morning recap</b>"]
    for cat, tasks in sorted(by_cat.items()):
        ce = CATEGORY_EMOJI.get(cat, "📌")
        lines.append(f"\n{ce} <b>{cat.capitalize()}</b>")
        for t in tasks:
            pe = PRIORITY_EMOJI.get(t["priority"] or "normal", "🟡")
            lines.append(f"  {pe} {t['text']}")
    lines.append(f"\n<i>{len(rows)} pending task(s). Have a great day! 💪</i>")
    send_message("\n".join(lines))

def cmd_handle_callback(data: str, query_id: str | None = None) -> None:
    parts = data.split(":")
    if len(parts) < 3 or parts[0] != "adhd":
        print(f"Unknown callback: {data!r}", file=sys.stderr)
        return
    action = parts[1]

    if action == "d":
        task_id = parts[2]
        conn = get_db()
        row = conn.execute("SELECT text FROM tasks WHERE id=?", (task_id,)).fetchone()
        conn.close()
        cmd_mark_done(task_id)
        if query_id:
            answer_callback(query_id, "✅ Marked as done!")
        task_text = row["text"] if row else "la tâche"
        send_message(f"✅ <b>Done!</b> <i>{task_text}</i> — taken care of. One less! 🎉")

    elif action == "s":
        task_id = parts[2]
        cmd_snooze(task_id)
        if query_id:
            answer_callback(query_id, "⏰ Snoozed!")
        conn = get_db()
        row = conn.execute("SELECT text, next_reminder_at FROM tasks WHERE id=?", (task_id,)).fetchone()
        conn.close()
        if row and row["next_reminder_at"]:
            nxt_paris = datetime.fromisoformat(row["next_reminder_at"]).astimezone(TZ)
            nxt_str = nxt_paris.strftime("%d/%m à %Hh%M")
            send_message(f"⏰ OK, I'll remind you about <i>{row['text']}</i> on {nxt_str}.")

    elif action == "p" and len(parts) >= 4:
        task_id = parts[2]
        priority = parts[3]
        cmd_confirm_priority(task_id, priority)
        if query_id:
            answer_callback(query_id, f"✅ {PRIORITY_LABEL.get(priority, priority)} !")
        conn = get_db()
        row = conn.execute("SELECT text, next_reminder_at FROM tasks WHERE id=?", (task_id,)).fetchone()
        conn.close()
        if row and row["next_reminder_at"]:
            pe = PRIORITY_EMOJI.get(priority, "🟡")
            nxt_paris = datetime.fromisoformat(row["next_reminder_at"]).astimezone(TZ)
            nxt_str = nxt_paris.strftime("%d/%m à %Hh%M")
            send_message(
                f"✅ <b>Got it!</b>\n"
                f"{pe} <i>{row['text']}</i>\n"
                f"First reminder on {nxt_str}. Nothing gets forgotten here 😄"
            )
    else:
        print(f"Unhandled callback action: {action!r}", file=sys.stderr)


# ── CLI ───────────────────────────────────────────────────────────────────────

def main():
    p = argparse.ArgumentParser(description="ADHD reminder — SQLite + Telegram")
    p.add_argument("--add",                    action="store_true")
    p.add_argument("--add-draft",              action="store_true")
    p.add_argument("--confirm-priority",       action="store_true")
    p.add_argument("--send-priority-keyboard", action="store_true")
    p.add_argument("--mark-done",              action="store_true")
    p.add_argument("--snooze",                 action="store_true")
    p.add_argument("--check-reminders",        action="store_true")
    p.add_argument("--daily-recap",            action="store_true")
    p.add_argument("--list",                   action="store_true")
    p.add_argument("--find",                   action="store_true")
    p.add_argument("--handle-callback",        action="store_true")
    p.add_argument("--text",        type=str)
    p.add_argument("--category",    type=str)
    p.add_argument("--priority",    type=str)
    p.add_argument("--uuid",        type=str)
    p.add_argument("--data",        type=str, help="Callback data string (adhd:action:...)")
    p.add_argument("--query-id",    type=str, help="Telegram callback_query_id")
    p.add_argument("--description", type=str)
    p.add_argument("--pending",     action="store_true")
    args = p.parse_args()

    if args.add:
        print(cmd_add(args.text, args.category, args.priority))
    elif args.add_draft:
        print(cmd_add_draft(args.text, args.category))
    elif args.confirm_priority:
        cmd_confirm_priority(args.uuid, args.priority)
        print("ok")
    elif args.send_priority_keyboard:
        cmd_send_priority_keyboard(args.uuid, args.description or args.text or "")
    elif args.mark_done:
        cmd_mark_done(args.uuid)
        print("done")
    elif args.snooze:
        cmd_snooze(args.uuid)
        print("snoozed")
    elif args.check_reminders:
        cmd_check_reminders()
    elif args.daily_recap:
        cmd_daily_recap()
    elif args.list:
        tasks = cmd_list(pending_only=args.pending, category=args.category)
        print(json.dumps(tasks, ensure_ascii=False, indent=2))
    elif args.find:
        tasks = cmd_find(args.text)
        print(json.dumps(tasks, ensure_ascii=False, indent=2))
    elif args.handle_callback:
        cmd_handle_callback(args.data, args.query_id)
    else:
        p.print_help()

if __name__ == "__main__":
    main()
