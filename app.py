from flask import Flask, jsonify, request, send_from_directory
from werkzeug.utils import secure_filename
from flask_cors import CORS
from pathlib import Path
import sqlite3
from datetime import date, datetime, timedelta
import json
import threading
import time
import urllib.request
import urllib.error
import uuid
import re

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "morning_board.db"
EXAM_DB_PATH = BASE_DIR / "exam_board.db"
TELEGRAM_TEMPLATE_PATH = BASE_DIR / "telegram_message_templates.txt"
EXAM_IMAGE_DIR = BASE_DIR / "static" / "uploads" / "exam_evidence"
ALLOWED_EXAM_IMAGE_EXTENSIONS = {"png", "jpg", "jpeg", "webp", "gif"}
app = Flask(__name__, static_folder="static", static_url_path="")
app.config["MAX_CONTENT_LENGTH"] = 20 * 1024 * 1024
CORS(app)

DEFAULT_DAY_START_HOUR = 5

def local_now_str():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

def get_day_start_hour():
    try:
        with get_conn() as conn:
            if not table_exists(conn, "settings"):
                return DEFAULT_DAY_START_HOUR
            row = conn.execute("SELECT value FROM settings WHERE key='day_start_hour'").fetchone()
            if not row:
                return DEFAULT_DAY_START_HOUR
            hour = int(row["value"])
            return max(0, min(23, hour))
    except Exception:
        return DEFAULT_DAY_START_HOUR

def local_today_str():
    now = datetime.now()
    cutoff_hour = get_day_start_hour()
    if now.hour < cutoff_hour:
        now = now - timedelta(days=1)
    return now.strftime("%Y-%m-%d")

def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def table_exists(conn, name):
    row = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?", (name,)).fetchone()
    return row is not None

def columns(conn, table):
    return {row["name"] for row in conn.execute(f"PRAGMA table_info({table})").fetchall()}

def add_col(conn, table, col_sql, col_name):
    if col_name not in columns(conn, table):
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {col_sql}")

def init_db():
    with get_conn() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS daily_done (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                done_date TEXT NOT NULL,
                text TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS daily_thoughts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                thought_date TEXT NOT NULL,
                text TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
        """)

        conn.execute("""
            CREATE TABLE IF NOT EXISTS thought_groups (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                thought_date TEXT NOT NULL,
                emoji TEXT NOT NULL DEFAULT '💭',
                title TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS thought_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                group_id INTEGER NOT NULL,
                text TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                source_thought_id INTEGER UNIQUE,
                FOREIGN KEY(group_id) REFERENCES thought_groups(id)
            )
        """)

        conn.execute("""
            CREATE TABLE IF NOT EXISTS tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                due_date TEXT,
                due_time TEXT,
                note TEXT,
                status TEXT NOT NULL DEFAULT 'active',
                completed_at TEXT,
                completed_date TEXT,
                archived_at TEXT,
                archived_date TEXT,
                archive_reason TEXT,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
        """)
        add_col(conn, "tasks", "due_time TEXT", "due_time")
        add_col(conn, "tasks", "status TEXT NOT NULL DEFAULT 'active'", "status")
        add_col(conn, "tasks", "completed_at TEXT", "completed_at")
        add_col(conn, "tasks", "completed_date TEXT", "completed_date")
        add_col(conn, "tasks", "archived_at TEXT", "archived_at")
        add_col(conn, "tasks", "archived_date TEXT", "archived_date")
        add_col(conn, "tasks", "archive_reason TEXT", "archive_reason")
        conn.execute("""
            UPDATE tasks
            SET archived_at=COALESCE(archived_at, completed_at),
                archived_date=COALESCE(archived_date, completed_date),
                archive_reason=COALESCE(archive_reason, 'completed')
            WHERE status='completed' AND completed_date IS NOT NULL
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS day_notes (
                note_date TEXT PRIMARY KEY,
                tomorrow_note TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            )
        """)
        defaults = {
            "focus": "",
            "reminder_enabled": "0",
            "reminder_time": "22:30",
            "theme": "light",
            "day_start_hour": str(DEFAULT_DAY_START_HOUR),
            "telegram_enabled": "0",
            "telegram_bot_token": "",
            "telegram_chat_id": "",
            "telegram_last_sent_key": ""
        }
        for key, value in defaults.items():
            conn.execute("INSERT OR IGNORE INTO settings(key,value) VALUES(?,?)", (key, value))
        if table_exists(conn, "done_items"):
            count = conn.execute("SELECT COUNT(*) AS n FROM daily_done").fetchone()["n"]
            if count == 0:
                old_cols = columns(conn, "done_items")
                if {"text", "created_at"}.issubset(old_cols):
                    conn.execute("""
                        INSERT INTO daily_done(done_date, text, created_at)
                        SELECT date(created_at), text, created_at FROM done_items
                    """)
        migrate_legacy_thoughts(conn)
        conn.commit()

def dicts(rows):
    return [dict(r) for r in rows]


def get_settings(conn):
    return {r["key"]: r["value"] for r in conn.execute("SELECT key,value FROM settings").fetchall()}

def send_telegram_message(bot_token, chat_id, text):
    if not bot_token or not chat_id:
        raise ValueError("Telegram bot token or chat id is empty")
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    payload = json.dumps({
        "chat_id": str(chat_id),
        "text": text
    }).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST"
    )
    with urllib.request.urlopen(req, timeout=10) as resp:
        body = resp.read().decode("utf-8", errors="replace")
    try:
        data = json.loads(body)
    except json.JSONDecodeError:
        data = {"ok": False, "raw": body}
    if not data.get("ok"):
        raise RuntimeError(f"Telegram API error: {data}")
    return data

def minutes_from_hhmm(value):
    try:
        hh, mm = str(value).split(":")[:2]
        return int(hh) * 60 + int(mm)
    except Exception:
        return None

def format_date_label(value):
    weekday_names = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]
    try:
        day = datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError:
        day = date.today()
    return f"{day.isoformat()}（{weekday_names[day.weekday()]}）"

def tomorrow_date_str(today):
    try:
        return (datetime.strptime(today, "%Y-%m-%d").date() + timedelta(days=1)).isoformat()
    except ValueError:
        return (date.today() + timedelta(days=1)).isoformat()

DEFAULT_TELEGRAM_TEMPLATE_FILE = """# Telegram 晚间提醒模板
# 你可以直接改这里的文案。
# 建议保留这些占位符：{{date}}、{{today_done}}、{{tomorrow_ddl_section}}
# {{date}} 会自动替换成日期。
# {{today_done}} 会自动替换成今天完成事项列表。
# {{tomorrow_ddl_section}} 会自动替换成完整 DDL 段落；如果明天没有 DDL，会自动消失。
# 如果想改 DDL 段落本身，请改下面的 [ddl_section]。

[with_done]
📅 {{date}}
🌙 晚间收尾时间到喵

今天做到了这些：

{{today_done}}

主人好棒！每一步无论大小都值得肯定喵៸៸᳐⦁⩊⦁៸៸᳐ ੭ﾞ❤

{{tomorrow_ddl_section}}

记得给明天的自己写点小提醒喵：

1. 今天完成了什么
2. 明天最先看什么
[/with_done]

[without_done]
📅 {{date}}
🌙 晚间收尾时间到喵

今天还没记录完成事项哦。
休息休息也很好喵，也可以随手写点简单的小事，比如“整理了一点资料”之类的喵៸៸᳐⦁⩊⦁៸៸᳐ ੭ﾞ❤

{{tomorrow_ddl_section}}

记得给明天的自己写点小提醒喵：

1. 今天完成了什么
2. 明天最先看什么
[/without_done]

[ddl_section]
这是明天要留意的 DDL喵：

{{tomorrow_ddl}}
[/ddl_section]
"""

def ensure_telegram_template_file():
    if not TELEGRAM_TEMPLATE_PATH.exists():
        TELEGRAM_TEMPLATE_PATH.write_text(DEFAULT_TELEGRAM_TEMPLATE_FILE, encoding="utf-8")


def parse_telegram_templates(raw_text):
    templates = {}
    for name in ("with_done", "without_done", "ddl_section"):
        start_tag = f"[{name}]"
        end_tag = f"[/{name}]"
        start = raw_text.find(start_tag)
        end = raw_text.find(end_tag)
        if start != -1 and end != -1 and end > start:
            templates[name] = raw_text[start + len(start_tag):end].strip()
    return templates


def get_telegram_templates():
    ensure_telegram_template_file()
    try:
        raw_text = TELEGRAM_TEMPLATE_PATH.read_text(encoding="utf-8")
        templates = parse_telegram_templates(raw_text)
    except Exception:
        templates = {}
    default_templates = parse_telegram_templates(DEFAULT_TELEGRAM_TEMPLATE_FILE)
    if "with_done" not in templates or "without_done" not in templates:
        templates = default_templates
    if "ddl_section" not in templates:
        templates["ddl_section"] = default_templates["ddl_section"]
    return templates


def cleanup_telegram_message(text):
    lines = [line.rstrip() for line in text.splitlines()]
    text = "\n".join(lines).strip()
    return re.sub(r"\n{3,}", "\n\n", text)

def render_text_template(template, values):
    text = template
    for key, value in values.items():
        text = text.replace("{{" + key + "}}", str(value))
    return cleanup_telegram_message(text)


def get_today_done_items(conn, today):
    done_rows = conn.execute("""
        SELECT text,created_at
        FROM daily_done
        WHERE done_date=?
        ORDER BY id DESC
    """, (today,)).fetchall()
    task_rows = conn.execute("""
        SELECT title,due_date,due_time,archived_at
        FROM tasks
        WHERE status='completed' AND archived_date=?
        ORDER BY archived_at DESC, id DESC
    """, (today,)).fetchall()
    return done_rows, task_rows


def build_today_done_lines(conn, today):
    done_rows, task_rows = get_today_done_items(conn, today)
    if not done_rows and not task_rows:
        return "", False
    lines = []
    shown_count = 0
    for row in done_rows[:6]:
        lines.append(f"- {row['text']}")
        shown_count += 1
    for row in task_rows[:6]:
        lines.append(f"- 任务：{row['title']}")
        shown_count += 1
    remaining = len(done_rows) + len(task_rows) - shown_count
    if remaining > 0:
        lines.append(f"……还有 {remaining} 条，打开 Morning Board 看完整记录。")
    return "\n".join(lines), True


def build_tomorrow_ddl_lines(conn, today):
    tomorrow = tomorrow_date_str(today)
    rows = conn.execute("""
        SELECT title,due_date,due_time,note
        FROM tasks
        WHERE status='active' AND due_date=?
        ORDER BY COALESCE(due_time,'23:59'), id
    """, (tomorrow,)).fetchall()
    if not rows:
        return "", False
    lines = []
    shown = rows[:8]
    for row in shown:
        time_label = row["due_time"] or "未设时间"
        lines.append(f"- {time_label} · {row['title']}")
    remaining = len(rows) - len(shown)
    if remaining > 0:
        lines.append(f"……还有 {remaining} 个 DDL，打开 Morning Board 看完整列表。")
    return "\n".join(lines), True


def build_telegram_reminder_message(conn, today):
    today_done, has_done = build_today_done_lines(conn, today)
    tomorrow_ddl, has_ddl = build_tomorrow_ddl_lines(conn, today)
    templates = get_telegram_templates()
    template = templates["with_done"] if has_done else templates["without_done"]
    tomorrow_ddl_section = ""
    if has_ddl:
        tomorrow_ddl_section = render_text_template(templates["ddl_section"], {"tomorrow_ddl": tomorrow_ddl})
    values = {
        "date": format_date_label(today),
        "today_done": today_done,
        "tomorrow_ddl": tomorrow_ddl,
        "tomorrow_ddl_section": tomorrow_ddl_section
    }
    return render_text_template(template, values)

def telegram_reminder_loop():
    while True:
        try:
            init_db()
            now = datetime.now()
            current_minutes = now.hour * 60 + now.minute
            today = local_today_str()
            with get_conn() as conn:
                settings = get_settings(conn)
                if settings.get("reminder_enabled") == "1" and settings.get("telegram_enabled") == "1":
                    reminder_time = settings.get("reminder_time", "22:30")
                    target_minutes = minutes_from_hhmm(reminder_time)
                    if target_minutes is not None and 0 <= current_minutes - target_minutes <= 2:
                        send_key = f"{today}-{reminder_time}"
                        if settings.get("telegram_last_sent_key", "") != send_key:
                            msg = build_telegram_reminder_message(conn, today)
                            send_telegram_message(
                                settings.get("telegram_bot_token", ""),
                                settings.get("telegram_chat_id", ""),
                                msg
                            )
                            conn.execute(
                                "INSERT INTO settings(key,value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                                ("telegram_last_sent_key", send_key)
                            )
                            conn.commit()
        except Exception as e:
            print("[telegram reminder error]", e)
        time.sleep(20)

_scheduler_started = False

def start_background_scheduler():
    global _scheduler_started
    if _scheduler_started:
        return
    _scheduler_started = True
    thread = threading.Thread(target=telegram_reminder_loop, daemon=True)
    thread.start()



def ensure_default_thought_group(conn, thought_date):
    row = conn.execute(
        "SELECT id FROM thought_groups WHERE thought_date=? AND emoji=? AND title=? ORDER BY id LIMIT 1",
        (thought_date, "💭", "未分类小感想")
    ).fetchone()
    if row:
        return row["id"]
    cur = conn.execute(
        "INSERT INTO thought_groups(thought_date,emoji,title,created_at) VALUES(?,?,?,?)",
        (thought_date, "💭", "未分类小感想", local_now_str())
    )
    return cur.lastrowid

def migrate_legacy_thoughts(conn):
    if not table_exists(conn, "daily_thoughts"):
        return
    rows = conn.execute(
        "SELECT id,thought_date,text,created_at FROM daily_thoughts ORDER BY thought_date, id"
    ).fetchall()
    for row in rows:
        group_id = ensure_default_thought_group(conn, row["thought_date"])
        conn.execute(
            "INSERT OR IGNORE INTO thought_items(group_id,text,created_at,source_thought_id) VALUES(?,?,?,?)",
            (group_id, row["text"], row["created_at"], row["id"])
        )

def get_thought_groups(conn, thought_date):
    groups = dicts(conn.execute(
        "SELECT id,thought_date,emoji,title,created_at FROM thought_groups WHERE thought_date=? ORDER BY id DESC",
        (thought_date,)
    ).fetchall())
    for group in groups:
        group["items"] = dicts(conn.execute(
            "SELECT id,group_id,text,created_at FROM thought_items WHERE group_id=? ORDER BY id DESC",
            (group["id"],)
        ).fetchall())
    return groups


def get_note(conn, note_date):
    row = conn.execute("SELECT note_date,tomorrow_note,updated_at FROM day_notes WHERE note_date=?", (note_date,)).fetchone()
    if row:
        return dict(row)
    return {"note_date": note_date, "tomorrow_note": "", "updated_at": ""}


def task_due_datetime(row):
    due_date = row["due_date"]
    if not due_date:
        return None
    due_time = row["due_time"] or "23:59"
    try:
        return datetime.strptime(f"{due_date} {due_time}", "%Y-%m-%d %H:%M")
    except ValueError:
        try:
            return datetime.strptime(f"{due_date} 23:59", "%Y-%m-%d %H:%M")
        except ValueError:
            return None

def archive_expired_tasks(conn):
    now_dt = datetime.now()
    now = local_now_str()
    today = local_today_str()
    rows = conn.execute("""
        SELECT id,due_date,due_time FROM tasks
        WHERE status='active' AND due_date IS NOT NULL
    """).fetchall()
    expired_ids = []
    for row in rows:
        due_dt = task_due_datetime(row)
        if due_dt and due_dt < now_dt:
            expired_ids.append(row["id"])
    if expired_ids:
        conn.executemany("""
            UPDATE tasks
            SET status='expired',
                archived_at=?,
                archived_date=?,
                archive_reason='expired'
            WHERE id=?
        """, [(now, today, task_id) for task_id in expired_ids])
        conn.commit()
    return len(expired_ids)

@app.route("/")
def index():
    theme = ""
    try:
        with get_conn() as conn:
            row = conn.execute("SELECT value FROM settings WHERE key='theme'").fetchone()
            if row and row["value"] == "dark":
                theme = "dark"
    except Exception:
        theme = ""
    html_path = Path(app.static_folder) / "index.html"
    html = html_path.read_text(encoding="utf-8")
    html = html.replace('<html lang="zh-CN">', f'<html lang="zh-CN" class="{theme}">')
    return html


@app.route("/exams")
def exams_page():
    return send_from_directory("static", "exams.html")

@app.route("/api/state")
def state():
    init_db()
    today = request.args.get("date") or local_today_str()
    try:
        yesterday = (datetime.strptime(today, "%Y-%m-%d").date() - timedelta(days=1)).isoformat()
    except ValueError:
        today = local_today_str()
        yesterday = (datetime.strptime(today, "%Y-%m-%d").date() - timedelta(days=1)).isoformat()
    with get_conn() as conn:
        migrate_legacy_thoughts(conn)
        archive_expired_tasks(conn)
        today_done = dicts(conn.execute(
            "SELECT id, done_date, text, created_at FROM daily_done WHERE done_date=? ORDER BY id DESC",
            (today,)
        ).fetchall())
        yesterday_done = dicts(conn.execute(
            "SELECT id, done_date, text, created_at FROM daily_done WHERE done_date=? ORDER BY id DESC",
            (yesterday,)
        ).fetchall())
        today_thoughts = dicts(conn.execute(
            "SELECT id, thought_date, text, created_at FROM daily_thoughts WHERE thought_date=? ORDER BY id DESC",
            (today,)
        ).fetchall())
        yesterday_thoughts = dicts(conn.execute(
            "SELECT id, thought_date, text, created_at FROM daily_thoughts WHERE thought_date=? ORDER BY id DESC",
            (yesterday,)
        ).fetchall())
        today_thought_groups = get_thought_groups(conn, today)
        yesterday_thought_groups = get_thought_groups(conn, yesterday)
        active_tasks = dicts(conn.execute(
            "SELECT id,title,due_date,due_time,note,status,created_at FROM tasks WHERE status='active' ORDER BY COALESCE(due_date,'9999-99-99'), COALESCE(due_time,'23:59'), id"
        ).fetchall())
        today_completed_tasks = dicts(conn.execute(
            "SELECT id,title,due_date,due_time,note,status,completed_at,completed_date,archived_at,archived_date,archive_reason,created_at FROM tasks WHERE status IN ('completed','expired') AND archived_date=? ORDER BY archived_at DESC, id DESC",
            (today,)
        ).fetchall())
        yesterday_completed_tasks = dicts(conn.execute(
            "SELECT id,title,due_date,due_time,note,status,completed_at,completed_date,archived_at,archived_date,archive_reason,created_at FROM tasks WHERE status IN ('completed','expired') AND archived_date=? ORDER BY archived_at DESC, id DESC",
            (yesterday,)
        ).fetchall())
        settings = get_settings(conn)
        today_note = get_note(conn, today)
        yesterday_note = get_note(conn, yesterday)
    return jsonify({
        "today": today,
        "yesterday": yesterday,
        "today_done": today_done,
        "yesterday_done": yesterday_done,
        "today_thoughts": today_thoughts,
        "yesterday_thoughts": yesterday_thoughts,
        "today_thought_groups": today_thought_groups,
        "yesterday_thought_groups": yesterday_thought_groups,
        "active_tasks": active_tasks,
        "today_completed_tasks": today_completed_tasks,
        "yesterday_completed_tasks": yesterday_completed_tasks,
        "today_note": today_note,
        "yesterday_note": yesterday_note,
        "focus": settings.get("focus", ""),
        "reminder_enabled": settings.get("reminder_enabled", "0"),
        "reminder_time": settings.get("reminder_time", "22:30"),
        "day_start_hour": settings.get("day_start_hour", str(DEFAULT_DAY_START_HOUR)),
        "telegram_enabled": settings.get("telegram_enabled", "0"),
        "telegram_chat_id": settings.get("telegram_chat_id", ""),
        "telegram_has_token": "1" if settings.get("telegram_bot_token", "") else "0",
        "theme": settings.get("theme", "light")
    })

@app.route("/api/done", methods=["POST"])
def add_done():
    data = request.get_json(silent=True) or {}
    text = data.get("text", "").strip()
    done_date = data.get("done_date") or local_today_str()
    now = local_now_str()
    if not text:
        return jsonify({"error": "text is required"}), 400
    with get_conn() as conn:
        cur = conn.execute("INSERT INTO daily_done(done_date,text,created_at) VALUES(?,?,?)", (done_date, text, now))
        conn.commit()
    return jsonify({"id": cur.lastrowid, "done_date": done_date, "text": text, "created_at": now}), 201

@app.route("/api/done/<int:item_id>", methods=["DELETE"])
def delete_done(item_id):
    with get_conn() as conn:
        conn.execute("DELETE FROM daily_done WHERE id=?", (item_id,))
        conn.commit()
    return jsonify({"ok": True})

@app.route("/api/tasks", methods=["POST"])
def add_task():
    data = request.get_json(silent=True) or {}
    title = data.get("title", "").strip()
    due_date = data.get("due_date") or None
    due_time = data.get("due_time") or None
    note = data.get("note", "").strip()
    now = local_now_str()
    if not title:
        return jsonify({"error": "title is required"}), 400
    with get_conn() as conn:
        cur = conn.execute(
            "INSERT INTO tasks(title,due_date,due_time,note,status,created_at) VALUES(?,?,?,?, 'active', ?)",
            (title, due_date, due_time, note, now)
        )
        conn.commit()
    return jsonify({"id": cur.lastrowid, "title": title, "due_date": due_date, "due_time": due_time, "note": note, "status": "active", "created_at": now}), 201

@app.route("/api/tasks/<int:task_id>/complete", methods=["POST"])
def complete_task(task_id):
    data = request.get_json(silent=True) or {}
    completed_date = data.get("completed_date") or local_today_str()
    now = local_now_str()
    with get_conn() as conn:
        conn.execute(
            "UPDATE tasks SET status='completed', completed_at=?, completed_date=?, archived_at=?, archived_date=?, archive_reason='completed' WHERE id=?",
            (now, completed_date, now, completed_date, task_id)
        )
        conn.commit()
    return jsonify({"ok": True, "completed_date": completed_date, "completed_at": now})

@app.route("/api/tasks/<int:task_id>/reactivate", methods=["POST"])
def reactivate_task(task_id):
    data = request.get_json(silent=True) or {}
    new_due_date = data.get("due_date") or None
    new_due_time = data.get("due_time") or None
    with get_conn() as conn:
        row = conn.execute("SELECT id,status,due_date,due_time FROM tasks WHERE id=?", (task_id,)).fetchone()
        if not row:
            return jsonify({"error": "task not found"}), 404
        if new_due_date:
            conn.execute(
                "UPDATE tasks SET status='active', due_date=?, due_time=?, completed_at=NULL, completed_date=NULL, archived_at=NULL, archived_date=NULL, archive_reason=NULL WHERE id=?",
                (new_due_date, new_due_time, task_id)
            )
        else:
            due_dt = task_due_datetime(row)
            clear_due = bool(due_dt and due_dt < datetime.now())
            if clear_due:
                conn.execute(
                    "UPDATE tasks SET status='active', due_date=NULL, due_time=NULL, completed_at=NULL, completed_date=NULL, archived_at=NULL, archived_date=NULL, archive_reason=NULL WHERE id=?",
                    (task_id,)
                )
            else:
                conn.execute(
                    "UPDATE tasks SET status='active', completed_at=NULL, completed_date=NULL, archived_at=NULL, archived_date=NULL, archive_reason=NULL WHERE id=?",
                    (task_id,)
                )
        conn.commit()
    return jsonify({"ok": True})


@app.route("/api/tasks/<int:task_id>/due", methods=["POST", "PATCH"])
def update_task_due(task_id):
    data = request.get_json(silent=True) or {}
    due_date = data.get("due_date") or None
    due_time = data.get("due_time") or None
    if due_time == "":
        due_time = None
    with get_conn() as conn:
        row = conn.execute("SELECT id,status FROM tasks WHERE id=?", (task_id,)).fetchone()
        if not row:
            return jsonify({"error": "task not found"}), 404
        if row["status"] != "active":
            return jsonify({"error": "only active tasks can edit due date"}), 400
        conn.execute(
            "UPDATE tasks SET due_date=?, due_time=? WHERE id=?",
            (due_date, due_time, task_id)
        )
        conn.commit()
    return jsonify({"ok": True, "due_date": due_date, "due_time": due_time})

@app.route("/api/tasks/<int:task_id>", methods=["DELETE"])
def delete_task(task_id):
    with get_conn() as conn:
        conn.execute("DELETE FROM tasks WHERE id=?", (task_id,))
        conn.commit()
    return jsonify({"ok": True})



@app.route("/api/thought_groups", methods=["POST"])
def add_thought_group():
    init_db()
    data = request.get_json(silent=True) or {}
    emoji = (data.get("emoji") or "💭").strip() or "💭"
    title = (data.get("title") or "").strip()
    thought_date = data.get("thought_date") or local_today_str()
    now = local_now_str()
    with get_conn() as conn:
        cur = conn.execute(
            "INSERT INTO thought_groups(thought_date,emoji,title,created_at) VALUES(?,?,?,?)",
            (thought_date, emoji[:8], title[:80], now)
        )
        conn.commit()
    return jsonify({"id": cur.lastrowid, "thought_date": thought_date, "emoji": emoji[:8], "title": title[:80], "created_at": now, "items": []}), 201

@app.route("/api/thought_groups/<int:group_id>", methods=["DELETE"])
def delete_thought_group(group_id):
    init_db()
    with get_conn() as conn:
        conn.execute("DELETE FROM thought_items WHERE group_id=?", (group_id,))
        conn.execute("DELETE FROM thought_groups WHERE id=?", (group_id,))
        conn.commit()
    return jsonify({"ok": True})

@app.route("/api/thought_groups/<int:group_id>/items", methods=["POST"])
def add_thought_item(group_id):
    init_db()
    data = request.get_json(silent=True) or {}
    text = data.get("text", "").strip()
    now = local_now_str()
    if not text:
        return jsonify({"error": "text is required"}), 400
    with get_conn() as conn:
        row = conn.execute("SELECT id FROM thought_groups WHERE id=?", (group_id,)).fetchone()
        if not row:
            return jsonify({"error": "thought group not found"}), 404
        cur = conn.execute(
            "INSERT INTO thought_items(group_id,text,created_at) VALUES(?,?,?)",
            (group_id, text, now)
        )
        conn.commit()
    return jsonify({"id": cur.lastrowid, "group_id": group_id, "text": text, "created_at": now}), 201


@app.route("/api/thought_items/<int:item_id>/move", methods=["POST"])
def move_thought_item(item_id):
    init_db()
    data = request.get_json(silent=True) or {}
    emoji = (data.get("emoji") or "").strip()
    if not emoji:
        return jsonify({"error": "emoji is required"}), 400
    emoji = emoji[:8]
    with get_conn() as conn:
        item = conn.execute("""
            SELECT thought_items.id, thought_items.group_id, thought_items.text, thought_groups.thought_date
            FROM thought_items
            JOIN thought_groups ON thought_items.group_id = thought_groups.id
            WHERE thought_items.id=?
        """, (item_id,)).fetchone()
        if not item:
            return jsonify({"error": "thought item not found"}), 404
        thought_date = item["thought_date"]
        target_title = "未分类小感想" if emoji == "💭" else ""
        target = conn.execute(
            "SELECT id FROM thought_groups WHERE thought_date=? AND emoji=? AND title=? ORDER BY id LIMIT 1",
            (thought_date, emoji, target_title)
        ).fetchone()
        if target:
            target_id = target["id"]
        else:
            cur = conn.execute(
                "INSERT INTO thought_groups(thought_date,emoji,title,created_at) VALUES(?,?,?,?)",
                (thought_date, emoji, target_title, local_now_str())
            )
            target_id = cur.lastrowid
        conn.execute(
            "UPDATE thought_items SET group_id=? WHERE id=?",
            (target_id, item_id)
        )
        conn.commit()
    return jsonify({"ok": True, "group_id": target_id, "emoji": emoji})

@app.route("/api/thought_items/<int:item_id>", methods=["DELETE"])
def delete_thought_item(item_id):
    init_db()
    with get_conn() as conn:
        conn.execute("DELETE FROM thought_items WHERE id=?", (item_id,))
        conn.commit()
    return jsonify({"ok": True})

@app.route("/api/thoughts", methods=["POST"])
def add_thought():
    init_db()
    data = request.get_json(silent=True) or {}
    text = data.get("text", "").strip()
    thought_date = data.get("thought_date") or local_today_str()
    now = local_now_str()
    if not text:
        return jsonify({"error": "text is required"}), 400
    with get_conn() as conn:
        cur = conn.execute(
            "INSERT INTO daily_thoughts(thought_date,text,created_at) VALUES(?,?,?)",
            (thought_date, text, now)
        )
        group_id = ensure_default_thought_group(conn, thought_date)
        conn.execute(
            "INSERT OR IGNORE INTO thought_items(group_id,text,created_at,source_thought_id) VALUES(?,?,?,?)",
            (group_id, text, now, cur.lastrowid)
        )
        conn.commit()
    return jsonify({"id": cur.lastrowid, "thought_date": thought_date, "text": text, "created_at": now}), 201

@app.route("/api/thoughts/<int:thought_id>", methods=["DELETE"])
def delete_thought(thought_id):
    with get_conn() as conn:
        conn.execute("DELETE FROM daily_thoughts WHERE id=?", (thought_id,))
        conn.commit()
    return jsonify({"ok": True})

@app.route("/api/notes", methods=["POST"])
def save_note():
    data = request.get_json(silent=True) or {}
    note_date = data.get("note_date") or local_today_str()
    tomorrow_note = data.get("tomorrow_note", "").strip()
    now = local_now_str()
    with get_conn() as conn:
        conn.execute("""
            INSERT INTO day_notes(note_date,tomorrow_note,updated_at)
            VALUES(?,?,?)
            ON CONFLICT(note_date) DO UPDATE SET tomorrow_note=excluded.tomorrow_note, updated_at=excluded.updated_at
        """, (note_date, tomorrow_note, now))
        conn.commit()
    return jsonify({"ok": True})



def get_exam_conn():
    conn = sqlite3.connect(EXAM_DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def allowed_exam_image(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXAM_IMAGE_EXTENSIONS

def exam_image_url(filename):
    return f"/uploads/exam_evidence/{filename}"

def delete_exam_image_file(filename):
    if not filename:
        return
    try:
        (EXAM_IMAGE_DIR / filename).unlink(missing_ok=True)
    except Exception as e:
        print("[exam image delete error]", e)

def init_exam_db():
    with get_exam_conn() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS exam_courses (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                code TEXT NOT NULL DEFAULT '',
                name TEXT NOT NULL DEFAULT '',
                exam_datetime TEXT NOT NULL DEFAULT '',
                exam_location TEXT NOT NULL DEFAULT '',
                exam_duration TEXT NOT NULL DEFAULT '',
                cheatsheet_allowed TEXT NOT NULL DEFAULT '',
                cheatsheet_note TEXT NOT NULL DEFAULT '',
                focus_note TEXT NOT NULL DEFAULT '',
                progress_note TEXT NOT NULL DEFAULT '',
                next_action TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS exam_checklist (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                course_id INTEGER NOT NULL,
                text TEXT NOT NULL,
                done INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(course_id) REFERENCES exam_courses(id)
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS exam_images (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                course_id INTEGER NOT NULL,
                filename TEXT NOT NULL,
                original_name TEXT NOT NULL DEFAULT '',
                mime_type TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(course_id) REFERENCES exam_courses(id)
            )
        """)
        conn.commit()

def parse_exam_dt(value):
    if not value:
        return None
    for fmt in ("%Y-%m-%dT%H:%M", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M"):
        try:
            return datetime.strptime(value, fmt)
        except ValueError:
            pass
    return None

def normalize_exam_course(row, conn):
    course = dict(row)
    items = dicts(conn.execute(
        "SELECT id,course_id,text,done,created_at FROM exam_checklist WHERE course_id=? ORDER BY id",
        (course["id"],)
    ).fetchall())
    course["checklist"] = items
    images = dicts(conn.execute(
        "SELECT id,course_id,filename,original_name,mime_type,created_at FROM exam_images WHERE course_id=? ORDER BY id DESC",
        (course["id"],)
    ).fetchall())
    for image in images:
        image["url"] = exam_image_url(image["filename"])
    course["images"] = images
    course["image_count"] = len(images)
    done = sum(1 for item in items if int(item.get("done") or 0) == 1)
    total = len(items)
    course["checklist_done"] = done
    course["checklist_total"] = total
    course["progress_percent"] = round(done * 100 / total) if total else 0
    dt = parse_exam_dt(course.get("exam_datetime", ""))
    if dt:
        delta = dt - datetime.now()
        total_seconds = int(delta.total_seconds())
        course["seconds_left"] = total_seconds
        if total_seconds < 0:
            course["countdown"] = "已结束"
            course["urgency"] = "past"
        else:
            days = total_seconds // 86400
            hours = (total_seconds % 86400) // 3600
            minutes = (total_seconds % 3600) // 60
            if days > 0:
                course["countdown"] = f"还有 {days} 天 {hours} 小时 {minutes} 分钟"
            else:
                course["countdown"] = f"还有 {hours} 小时 {minutes} 分钟"
            if days >= 14:
                course["urgency"] = "calm"
            elif days >= 7:
                course["urgency"] = "soon"
            elif days >= 3:
                course["urgency"] = "near"
            else:
                course["urgency"] = "urgent"
    else:
        course["seconds_left"] = None
        course["countdown"] = "未设置考试时间"
        course["urgency"] = "unknown"
    return course

def get_exam_course_or_404(conn, course_id):
    row = conn.execute("SELECT * FROM exam_courses WHERE id=?", (course_id,)).fetchone()
    if not row:
        return None
    return normalize_exam_course(row, conn)

@app.route("/api/exams", methods=["GET"])
def list_exam_courses():
    init_exam_db()
    with get_exam_conn() as conn:
        rows = conn.execute("""
            SELECT * FROM exam_courses
            ORDER BY
              CASE WHEN exam_datetime='' THEN 1 ELSE 0 END,
              exam_datetime ASC,
              id DESC
        """).fetchall()
        courses = [normalize_exam_course(row, conn) for row in rows]
    return jsonify({"courses": courses})

@app.route("/api/exams", methods=["POST"])
def create_exam_course():
    init_exam_db()
    data = request.get_json(silent=True) or {}
    code = (data.get("code") or "").strip()
    name = (data.get("name") or "").strip()
    exam_datetime = (data.get("exam_datetime") or "").strip()
    if not code and not name:
        return jsonify({"error": "code or name is required"}), 400
    now = local_now_str()
    with get_exam_conn() as conn:
        cur = conn.execute("""
            INSERT INTO exam_courses(
                code,name,exam_datetime,exam_location,exam_duration,
                cheatsheet_allowed,cheatsheet_note,focus_note,progress_note,next_action,
                created_at,updated_at
            ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)
        """, (
            code, name, exam_datetime,
            (data.get("exam_location") or "").strip(),
            (data.get("exam_duration") or "").strip(),
            (data.get("cheatsheet_allowed") or "").strip(),
            (data.get("cheatsheet_note") or "").strip(),
            (data.get("focus_note") or "").strip(),
            (data.get("progress_note") or "").strip(),
            (data.get("next_action") or "").strip(),
            now, now
        ))
        conn.commit()
        course = get_exam_course_or_404(conn, cur.lastrowid)
    return jsonify(course), 201

@app.route("/api/exams/<int:course_id>", methods=["PATCH"])
def update_exam_course(course_id):
    init_exam_db()
    data = request.get_json(silent=True) or {}
    allowed = [
        "code","name","exam_datetime","exam_location","exam_duration",
        "cheatsheet_allowed","cheatsheet_note","focus_note","progress_note","next_action"
    ]
    updates = []
    values = []
    for key in allowed:
        if key in data:
            updates.append(f"{key}=?")
            values.append(str(data.get(key) or "").strip())
    if not updates:
        return jsonify({"ok": True})
    updates.append("updated_at=?")
    values.append(local_now_str())
    values.append(course_id)
    with get_exam_conn() as conn:
        conn.execute(f"UPDATE exam_courses SET {', '.join(updates)} WHERE id=?", values)
        conn.commit()
        course = get_exam_course_or_404(conn, course_id)
        if not course:
            return jsonify({"error": "course not found"}), 404
    return jsonify(course)

@app.route("/api/exams/<int:course_id>", methods=["DELETE"])
def delete_exam_course(course_id):
    init_exam_db()
    with get_exam_conn() as conn:
        image_rows = conn.execute("SELECT filename FROM exam_images WHERE course_id=?", (course_id,)).fetchall()
        conn.execute("DELETE FROM exam_checklist WHERE course_id=?", (course_id,))
        conn.execute("DELETE FROM exam_images WHERE course_id=?", (course_id,))
        conn.execute("DELETE FROM exam_courses WHERE id=?", (course_id,))
        conn.commit()
    for row in image_rows:
        delete_exam_image_file(row["filename"])
    return jsonify({"ok": True})

@app.route("/api/exams/<int:course_id>/images", methods=["POST"])
def upload_exam_images(course_id):
    init_exam_db()
    uploaded_files = request.files.getlist("images") or request.files.getlist("image")
    uploaded_files = [f for f in uploaded_files if f and f.filename]
    if not uploaded_files:
        return jsonify({"error": "no image files uploaded"}), 400
    for file in uploaded_files:
        if not allowed_exam_image(file.filename):
            return jsonify({"error": "only png, jpg, jpeg, webp and gif images are supported"}), 400
    EXAM_IMAGE_DIR.mkdir(parents=True, exist_ok=True)
    now = local_now_str()
    saved = []
    with get_exam_conn() as conn:
        row = conn.execute("SELECT id FROM exam_courses WHERE id=?", (course_id,)).fetchone()
        if not row:
            return jsonify({"error": "course not found"}), 404
        for file in uploaded_files:
            original_name = file.filename
            safe_name = secure_filename(original_name) or "screenshot"
            ext = safe_name.rsplit(".", 1)[1].lower()
            stem = Path(safe_name).stem[:60] or "screenshot"
            filename = f"course{course_id}_{datetime.now().strftime('%Y%m%d%H%M%S')}_{uuid.uuid4().hex[:8]}_{stem}.{ext}"
            file.save(EXAM_IMAGE_DIR / filename)
            cur = conn.execute(
                "INSERT INTO exam_images(course_id,filename,original_name,mime_type,created_at) VALUES(?,?,?,?,?)",
                (course_id, filename, original_name, file.mimetype or "", now)
            )
            saved.append({
                "id": cur.lastrowid,
                "course_id": course_id,
                "filename": filename,
                "original_name": original_name,
                "mime_type": file.mimetype or "",
                "created_at": now,
                "url": exam_image_url(filename)
            })
        conn.commit()
    return jsonify({"ok": True, "images": saved}), 201

@app.route("/api/exams/images/<int:image_id>", methods=["DELETE"])
def delete_exam_image(image_id):
    init_exam_db()
    with get_exam_conn() as conn:
        row = conn.execute("SELECT filename FROM exam_images WHERE id=?", (image_id,)).fetchone()
        if not row:
            return jsonify({"error": "image not found"}), 404
        conn.execute("DELETE FROM exam_images WHERE id=?", (image_id,))
        conn.commit()
    delete_exam_image_file(row["filename"])
    return jsonify({"ok": True})

@app.route("/api/exams/<int:course_id>/checklist", methods=["POST"])
def add_exam_checklist_item(course_id):
    init_exam_db()
    data = request.get_json(silent=True) or {}
    text = (data.get("text") or "").strip()
    if not text:
        return jsonify({"error": "text is required"}), 400
    with get_exam_conn() as conn:
        row = conn.execute("SELECT id FROM exam_courses WHERE id=?", (course_id,)).fetchone()
        if not row:
            return jsonify({"error": "course not found"}), 404
        cur = conn.execute(
            "INSERT INTO exam_checklist(course_id,text,done,created_at) VALUES(?,?,0,?)",
            (course_id, text, local_now_str())
        )
        conn.commit()
    return jsonify({"id": cur.lastrowid, "course_id": course_id, "text": text, "done": 0}), 201

@app.route("/api/exams/checklist/<int:item_id>", methods=["PATCH"])
def update_exam_checklist_item(item_id):
    init_exam_db()
    data = request.get_json(silent=True) or {}
    with get_exam_conn() as conn:
        if "done" in data:
            conn.execute("UPDATE exam_checklist SET done=? WHERE id=?", (1 if data.get("done") else 0, item_id))
        if "text" in data:
            text = (data.get("text") or "").strip()
            if text:
                conn.execute("UPDATE exam_checklist SET text=? WHERE id=?", (text, item_id))
        conn.commit()
    return jsonify({"ok": True})

@app.route("/api/exams/checklist/<int:item_id>", methods=["DELETE"])
def delete_exam_checklist_item(item_id):
    init_exam_db()
    with get_exam_conn() as conn:
        conn.execute("DELETE FROM exam_checklist WHERE id=?", (item_id,))
        conn.commit()
    return jsonify({"ok": True})


@app.route("/api/telegram/test", methods=["POST"])
def test_telegram():
    init_db()
    today = local_today_str()
    with get_conn() as conn:
        settings = get_settings(conn)
        msg = build_telegram_reminder_message(conn, today)
    token = settings.get("telegram_bot_token", "")
    chat_id = settings.get("telegram_chat_id", "")
    if not token or not chat_id:
        return jsonify({"error": "telegram bot token or chat id is empty"}), 400
    try:
        send_telegram_message(token, chat_id, msg)
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    return jsonify({"ok": True})

@app.route("/api/settings", methods=["POST"])
def update_settings():
    init_db()
    data = request.get_json(silent=True) or {}
    allowed = {"focus", "reminder_enabled", "reminder_time", "theme", "day_start_hour", "telegram_enabled", "telegram_bot_token", "telegram_chat_id"}
    with get_conn() as conn:
        for key, value in data.items():
            if key not in allowed:
                continue
            if key == "day_start_hour":
                try:
                    value = str(max(0, min(23, int(value))))
                except (TypeError, ValueError):
                    value = str(DEFAULT_DAY_START_HOUR)
            if key == "telegram_bot_token" and not str(value).strip():
                continue
            if key in {"telegram_bot_token", "telegram_chat_id"}:
                value = str(value).strip()
            conn.execute(
                "INSERT INTO settings(key,value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                (key, str(value))
            )
        conn.commit()
    return jsonify({"ok": True})

if __name__ == "__main__":
    init_db()
    init_exam_db()
    start_background_scheduler()
    # app.run(host="127.0.0.1", port=5001, debug=True, use_reloader=False)
    app.run(host="100.97.142.99", port=5001, debug=True, use_reloader=False)
    # app.run(host="100.97.142.99", port=5000, debug=False, use_reloader=False)