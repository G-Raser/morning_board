from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS
from pathlib import Path
import sqlite3
from datetime import date, datetime, timedelta

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "morning_board.db"
app = Flask(__name__, static_folder="static", static_url_path="")
CORS(app)

def local_now_str():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

def local_today_str():
    return datetime.now().strftime("%Y-%m-%d")

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
            CREATE TABLE IF NOT EXISTS tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                due_date TEXT,
                due_time TEXT,
                note TEXT,
                status TEXT NOT NULL DEFAULT 'active',
                completed_at TEXT,
                completed_date TEXT,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
        """)
        add_col(conn, "tasks", "due_time TEXT", "due_time")
        add_col(conn, "tasks", "status TEXT NOT NULL DEFAULT 'active'", "status")
        add_col(conn, "tasks", "completed_at TEXT", "completed_at")
        add_col(conn, "tasks", "completed_date TEXT", "completed_date")
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
            "theme": "light"
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

def get_note(conn, note_date):
    row = conn.execute("SELECT note_date,tomorrow_note,updated_at FROM day_notes WHERE note_date=?", (note_date,)).fetchone()
    if row:
        return dict(row)
    return {"note_date": note_date, "tomorrow_note": "", "updated_at": ""}

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
    today = request.args.get("date") or local_today_str()
    try:
        yesterday = (datetime.strptime(today, "%Y-%m-%d").date() - timedelta(days=1)).isoformat()
    except ValueError:
        today = local_today_str()
        yesterday = (date.today() - timedelta(days=1)).isoformat()
    with get_conn() as conn:
        today_done = dicts(conn.execute(
            "SELECT id, done_date, text, created_at FROM daily_done WHERE done_date=? ORDER BY id DESC",
            (today,)
        ).fetchall())
        yesterday_done = dicts(conn.execute(
            "SELECT id, done_date, text, created_at FROM daily_done WHERE done_date=? ORDER BY id DESC",
            (yesterday,)
        ).fetchall())
        active_tasks = dicts(conn.execute(
            "SELECT id,title,due_date,due_time,note,status,created_at FROM tasks WHERE status='active' ORDER BY COALESCE(due_date,'9999-99-99'), COALESCE(due_time,'23:59'), id"
        ).fetchall())
        today_completed_tasks = dicts(conn.execute(
            "SELECT id,title,due_date,due_time,note,status,completed_at,completed_date,created_at FROM tasks WHERE status='completed' AND completed_date=? ORDER BY completed_at DESC, id DESC",
            (today,)
        ).fetchall())
        yesterday_completed_tasks = dicts(conn.execute(
            "SELECT id,title,due_date,due_time,note,status,completed_at,completed_date,created_at FROM tasks WHERE status='completed' AND completed_date=? ORDER BY completed_at DESC, id DESC",
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
        "active_tasks": active_tasks,
        "today_completed_tasks": today_completed_tasks,
        "yesterday_completed_tasks": yesterday_completed_tasks,
        "today_note": today_note,
        "yesterday_note": yesterday_note,
        "focus": settings.get("focus", ""),
        "reminder_enabled": settings.get("reminder_enabled", "0"),
        "reminder_time": settings.get("reminder_time", "22:30"),
        "theme": settings.get("theme", "light")
    })

@app.route("/api/done", methods=["POST"])
def add_done():
    data = request.json or {}
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
    data = request.json or {}
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
    data = request.json or {}
    completed_date = data.get("completed_date") or local_today_str()
    now = local_now_str()
    with get_conn() as conn:
        conn.execute(
            "UPDATE tasks SET status='completed', completed_at=?, completed_date=? WHERE id=?",
            (now, completed_date, task_id)
        )
        conn.commit()
    return jsonify({"ok": True, "completed_date": completed_date, "completed_at": now})

@app.route("/api/tasks/<int:task_id>/reactivate", methods=["POST"])
def reactivate_task(task_id):
    with get_conn() as conn:
        conn.execute("UPDATE tasks SET status='active', completed_at=NULL, completed_date=NULL WHERE id=?", (task_id,))
        conn.commit()
    return jsonify({"ok": True})

@app.route("/api/tasks/<int:task_id>", methods=["DELETE"])
def delete_task(task_id):
    with get_conn() as conn:
        conn.execute("DELETE FROM tasks WHERE id=?", (task_id,))
        conn.commit()
    return jsonify({"ok": True})

@app.route("/api/notes", methods=["POST"])
def save_note():
    data = request.json or {}
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
    data = request.json or {}
    allowed = {"focus", "reminder_enabled", "reminder_time", "theme"}
    with get_conn() as conn:
        for key, value in data.items():
            if key in allowed:
                conn.execute(
                    "INSERT INTO settings(key,value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                    (key, str(value))
                )
        conn.commit()
    return jsonify({"ok": True})

if __name__ == "__main__":
    init_db()
    app.run(host="100.97.142.99", port=5000, debug=False)
