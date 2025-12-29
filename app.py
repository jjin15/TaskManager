from flask import Flask, render_template, request, redirect, url_for, send_from_directory, abort
import sqlite3
from datetime import datetime, date, timedelta
import os
from werkzeug.utils import secure_filename

app = Flask(__name__)

UPLOAD_ROOT = "uploads"

app.config["MAX_CONTENT_LENGTH"] = 10 * 1024 * 1024  # 10 MB per request

ALLOWED_EXTENSIONS = {
    "jpg", "jpeg", "png", "gif",
    "pdf", "txt",
    "doc", "docx",
    "xls", "xlsx"
}
DB = "tasks.db"

def get_db():
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    return conn

def now_local():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

def allowed_file(filename):
    return "." in filename and \
           filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS

def task_upload_dir(task_id):
    path = os.path.join(UPLOAD_ROOT, f"task_{task_id}")
    os.makedirs(path, exist_ok=True)
    return path

# ---------------- RECURRING GENERATOR ----------------

def generate_recurring_tasks():
    db = get_db()
    today = date.today()

    rows = db.execute("SELECT * FROM recurring_tasks").fetchall()

    for r in rows:
        last = r["last_generated"] or r["start_date"]
        last_date = date.fromisoformat(last)

        if r["frequency"] == "weekly":
            next_due = last_date + timedelta(weeks=r["interval"])
        elif r["frequency"] == "monthly":
            next_due = last_date + timedelta(days=30 * r["interval"])
        else:
            continue

        if today >= next_due:
            db.execute("""
                INSERT INTO tasks
                (title, description, prerequisites, assignee,
                 created_at, due_date)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                r["title"],
                r["description"],
                r["prerequisites"],
                r["assignee"],
                now_local(),
                next_due.isoformat()
            ))

            db.execute("""
                UPDATE recurring_tasks
                SET last_generated = ?
                WHERE id = ?
            """, (today.isoformat(), r["id"]))

    db.commit()
    db.close()

# ---------------- ROUTES ----------------

@app.route("/delete-file/<int:file_id>")
def delete_file(file_id):
    db = get_db()

    file = db.execute("""
        SELECT task_id, filename
        FROM task_files
        WHERE id = ?
    """, (file_id,)).fetchone()

    if not file:
        abort(404)

    path = os.path.join(
        UPLOAD_ROOT,
        f"task_{file['task_id']}",
        file["filename"]
    )

    if os.path.exists(path):
        os.remove(path)

    db.execute("DELETE FROM task_files WHERE id = ?", (file_id,))
    db.commit()
    db.close()

    return redirect(request.referrer or url_for("index"))

@app.route("/")
def index():
    generate_recurring_tasks()

    status = request.args.get("status", "created")

    db = get_db()
    tasks = db.execute("""
        SELECT * FROM tasks
        WHERE status = ?
        ORDER BY due_date IS NULL, due_date
    """, (status,)).fetchall()

    files = db.execute("""
        SELECT * FROM task_files
    """).fetchall()

    counts = {
        "created": db.execute(
            "SELECT COUNT(*) FROM tasks WHERE status = 'created'"
        ).fetchone()[0],
        "ongoing": db.execute(
            "SELECT COUNT(*) FROM tasks WHERE status = 'ongoing'"
        ).fetchone()[0],
        "completed": db.execute(
            "SELECT COUNT(*) FROM tasks WHERE status = 'completed'"
        ).fetchone()[0],
    }
    db.close()
    return render_template(
        "index.html",
        tasks=tasks,
        files=files,
        current_status=status,
        today=date.today().isoformat(),
        counts=counts
    )

@app.route("/assignees")
def list_assignees():
    db = get_db()
    rows = db.execute(
        "SELECT name FROM assignees ORDER BY name"
    ).fetchall()
    return [r["name"] for r in rows]

@app.route("/assignees/manage")
def manage_assignees():
    db = get_db()
    assignees = db.execute(
        "SELECT name FROM assignees ORDER BY name"
    ).fetchall()
    return render_template(
        "assignees.html",
        assignees=assignees
    )

@app.route("/assignees/add", methods=["POST"])
def add_assignee():
    name = request.form["name"].strip()
    db = get_db()
    if name:
        db.execute(
            "INSERT OR IGNORE INTO assignees (name) VALUES (?)",
            (name,)
        )
        db.commit()
    return redirect("/assignees/manage")

@app.route("/assignees/delete/<name>")
def delete_assignee(name):
    db = get_db()
    if name == "Unassigned":
        return redirect("/assignees/manage")

    db.execute(
        "UPDATE tasks SET assignee='Unassigned' WHERE assignee=?",
        (name,)
    )
    db.execute(
        "DELETE FROM assignees WHERE name=?",
        (name,)
    )
    db.commit()

    return redirect("/assignees/manage")

@app.route("/by-assignee")
def by_assignee():
    status = request.args.get("status", "created")
    assignee = request.args.get("assignee", "All")

    db = get_db()

    # list of assignees
    assignees = [
        r["name"] for r in db.execute(
            "SELECT name FROM assignees ORDER BY name"
        ).fetchall()
    ]

    # badge counts per assignee (status-aware)
    counts = {
        r["assignee"]: r["count"]
        for r in db.execute("""
            SELECT assignee, COUNT(*) AS count
            FROM tasks
            WHERE status = ?
            GROUP BY assignee
        """, (status,)).fetchall()
    }

    # total count for "All"
    total_count = sum(counts.values())

    # task list
    if assignee == "All":
        tasks = db.execute("""
            SELECT * FROM tasks
            WHERE status = ?
            ORDER BY due_date IS NULL, due_date
        """, (status,)).fetchall()
    else:
        tasks = db.execute("""
            SELECT * FROM tasks
            WHERE status = ? AND assignee = ?
            ORDER BY due_date IS NULL, due_date
        """, (status, assignee)).fetchall()

    return render_template(
        "by_assignee.html",
        tasks=tasks,
        assignees=assignees,
        counts=counts,
        total_count=total_count,
        current_status=status,
        current_assignee=assignee
    )

@app.route("/new", methods=["GET", "POST"])
def new_task():
    if request.method == "POST":
        db = get_db()

        cur = db.execute("""
            INSERT INTO tasks
            (title, description, prerequisites, assignee,
             created_at, due_date)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
            request.form["title"],
            request.form["description"],
            request.form["prerequisites"],
            request.form["assignee"],
            now_local(),
            request.form["due_date"] or None
        ))

        task_id = cur.lastrowid
        upload_dir = task_upload_dir(task_id)

        files = request.files.getlist("files")
        for f in files:
            if not f or f.filename == "":
                continue
            if not allowed_file(f.filename):
                continue

            filename = secure_filename(f.filename)
            f.save(os.path.join(upload_dir, filename))

            db.execute("""
                INSERT INTO task_files (task_id, filename, uploaded_at)
                VALUES (?, ?, ?)
            """, (task_id, filename, now_local()))

        db.commit()
        db.close()
        return redirect(url_for("index"))

    # 👇 THIS IS THE IMPORTANT PART
    db = get_db()
    assignees = [
        r["name"] for r in db.execute(
            "SELECT name FROM assignees ORDER BY name"
        ).fetchall()
    ]
    db.close()

    return render_template(
        "new_task.html",
        assignees=assignees
    )

@app.route("/upload/<int:task_id>", methods=["POST"])
def upload_files(task_id):
    db = get_db()

    task = db.execute("SELECT id FROM tasks WHERE id=?", (task_id,)).fetchone()
    if not task:
        abort(404)

    upload_dir = task_upload_dir(task_id)

    files = request.files.getlist("files")
    for f in files:
        if not f or f.filename == "":
            continue
        if not allowed_file(f.filename):
            continue

        filename = secure_filename(f.filename)
        f.save(os.path.join(upload_dir, filename))

        db.execute("""
            INSERT INTO task_files (task_id, filename, uploaded_at)
            VALUES (?, ?, ?)
        """, (task_id, filename, now_local()))

    db.commit()
    db.close()
    return redirect(url_for("index"))

@app.route("/files/<int:task_id>/<filename>")
def get_file(task_id, filename):
    directory = task_upload_dir(task_id)
    return send_from_directory(directory, filename)

@app.route("/complete/<int:task_id>")
def complete_task(task_id):
    db = get_db()
    db.execute("""
        UPDATE tasks
        SET status='completed', completed_at=?
        WHERE id=?
    """, (now_local(), task_id))
    db.commit()
    db.close()
    return redirect(url_for("index"))

@app.route("/start/<int:task_id>")
def start_task(task_id):
    db = get_db()
    db.execute("""
        UPDATE tasks
        SET status='ongoing'
        WHERE id=?
    """, (task_id,))
    db.commit()
    db.close()
    return redirect(url_for("index"))

@app.route("/delete/<int:task_id>")
def delete_task(task_id):
    db = get_db()
    db.execute("DELETE FROM tasks WHERE id=?", (task_id,))
    db.commit()
    db.close()
    return redirect(url_for("index"))

@app.route("/recurring", methods=["GET", "POST"])
def recurring():
    db = get_db()

    if request.method == "POST":
        frequency = request.form["frequency"]

        # Default all optional fields
        weekday = None
        day_of_month = None
        month = None
        day = None

        if frequency == "weekly":
            weekday = int(request.form["weekday"])

        elif frequency == "monthly":
            day_of_month = int(request.form["day_of_month"])

        elif frequency == "annual":
            month = int(request.form["month"])
            day = int(request.form["day"])

        db.execute("""
            INSERT INTO recurring_tasks
            (title, description, assignee,
             frequency, weekday, day_of_month, month, day)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            request.form["title"],
            request.form["description"],
            request.form["assignee"],
            frequency,
            weekday,
            day_of_month,
            month,
            day
        ))

        db.commit()

    recurring_tasks = db.execute(
        "SELECT * FROM recurring_tasks ORDER BY id DESC"
    ).fetchall()

    assignees = db.execute(
        "SELECT name FROM assignees ORDER BY name"
    ).fetchall()

    db.close()

    return render_template(
        "recurring.html",
        recurring=recurring_tasks,
        assignees=assignees
    )

@app.route("/edit/<int:task_id>", methods=["GET", "POST"])
def edit_task(task_id):
    db = get_db()

    task = db.execute(
        "SELECT * FROM tasks WHERE id = ?",
        (task_id,)
    ).fetchone()

    if not task:
        abort(404)

    if request.method == "POST":
        db.execute("""
            UPDATE tasks
            SET title = ?,
                description = ?,
                prerequisites = ?,
                assignee = ?,
                due_date = ?
            WHERE id = ?
        """, (
            request.form["title"],
            request.form["description"],
            request.form["prerequisites"],
            request.form["assignee"],
            request.form["due_date"] or None,
            task_id
        ))

        db.commit()
        db.close()
        return redirect(request.referrer or url_for("index"))

    db.close()
    return render_template("edit_task.html", task=task)

# -------- JINJA DATE FILTER --------

@app.template_filter("pretty_date")
def pretty_date(value):
    if not value:
        return ""
    try:
        dt = datetime.fromisoformat(value)
        return dt.strftime("%b %d, %Y %I:%M %p")
    except ValueError:
        return value

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)