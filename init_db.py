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

    frequency TEXT NOT NULL,      -- weekly | monthly | annual
    weekday INTEGER,              -- 0 = Monday ... 6 = Sunday
    day_of_month INTEGER,         -- 1–31
    month INTEGER,                -- 1–12 (annual)
    day INTEGER,                  -- 1–31 (annual)

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

c.execute("""
CREATE TABLE IF NOT EXISTS assignees (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE
);
""")

conn.commit()
conn.close()

print("Database initialized.")