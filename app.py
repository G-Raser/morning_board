from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS
from pathlib import Path
import sqlite3
from datetime import date, datetime, timedelta

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "morning_board.db"
app = Flask(__name__, static_folder="static", static_url_path="")
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
            "day_start_hour": str(DEFAULT_DAY_START_HOUR)
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
        conn.commit()

def dicts(rows):
    return [dict(r) for r in rows]


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
        settings = {r["key"]: r["value"] for r in conn.execute("SELECT key,value FROM settings").fetchall()}
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

@app.route("/api/settings", methods=["POST"])
def update_settings():
    init_db()
    data = request.get_json(silent=True) or {}
    allowed = {"focus", "reminder_enabled", "reminder_time", "theme", "day_start_hour"}
    with get_conn() as conn:
        for key, value in data.items():
            if key not in allowed:
                continue
            if key == "day_start_hour":
                try:
                    value = str(max(0, min(23, int(value))))
                except (TypeError, ValueError):
                    value = str(DEFAULT_DAY_START_HOUR)
            conn.execute(
                "INSERT INTO settings(key,value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                (key, str(value))
            )
        conn.commit()
    return jsonify({"ok": True})

if __name__ == "__main__":
    init_db()
    # app.run(host="127.0.0.1", port=5001, debug=True)
    app.run(host="100.97.142.99", port=5001, debug=True)
    # app.run(host="100.97.142.99", port=5000, debug=False)
