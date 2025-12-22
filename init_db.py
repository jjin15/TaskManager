import sqlite3

conn = sqlite3.connect("tasks.db")
c = conn.cursor()

c.execute("""
CREATE TABLE IF NOT EXISTS tasks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    description TEXT,
    prerequisites TEXT,
    status TEXT NOT NULL DEFAULT 'created',
    assignee TEXT,
    created_at TEXT,
    due_date TEXT,
    completed_at TEXT
)
""")

c.execute("""
CREATE TABLE IF NOT EXISTS recurring_tasks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    description TEXT,
    prerequisites TEXT,
    assignee TEXT,
    frequency TEXT NOT NULL,
    interval INTEGER DEFAULT 1,
    start_date TEXT NOT NULL,
    last_generated TEXT
)
""")

c.execute("""
CREATE TABLE IF NOT EXISTS task_files (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id INTEGER NOT NULL,
    filename TEXT NOT NULL,
    uploaded_at TEXT,
    FOREIGN KEY(task_id) REFERENCES tasks(id)
)
""")

conn.commit()
conn.close()

print("Database initialized.")