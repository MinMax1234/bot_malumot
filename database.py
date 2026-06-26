import sqlite3
from config import DB_PATH


def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with get_conn() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS teachers (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                telegram_id     INTEGER UNIQUE,
                full_name       TEXT,
                position        TEXT    NOT NULL,
                degree          TEXT    NOT NULL,
                experience_years INTEGER NOT NULL,
                university      TEXT,
                specialization  TEXT,
                subjects        TEXT,
                has_ielts       INTEGER DEFAULT 0,
                ielts_score     TEXT,
                has_cefr        INTEGER DEFAULT 0,
                cefr_level      TEXT,
                has_national_cert INTEGER DEFAULT 0,
                bio             TEXT,
                photo_path      TEXT,
                awards          TEXT,
                created_at      DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at      DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.commit()


def upsert_teacher(telegram_id: int, data: dict):
    fields = list(data.keys())
    values = list(data.values())

    with get_conn() as conn:
        existing = conn.execute(
            "SELECT id FROM teachers WHERE telegram_id = ?", (telegram_id,)
        ).fetchone()

        if existing:
            set_clause = ", ".join(f"{f} = ?" for f in fields)
            set_clause += ", updated_at = CURRENT_TIMESTAMP"
            conn.execute(
                f"UPDATE teachers SET {set_clause} WHERE telegram_id = ?",
                values + [telegram_id],
            )
        else:
            fields_str = "telegram_id, " + ", ".join(fields)
            placeholders = ", ".join("?" * (len(fields) + 1))
            conn.execute(
                f"INSERT INTO teachers ({fields_str}) VALUES ({placeholders})",
                [telegram_id] + values,
            )
        conn.commit()


def get_teacher(telegram_id: int):
    with get_conn() as conn:
        return conn.execute(
            "SELECT * FROM teachers WHERE telegram_id = ?", (telegram_id,)
        ).fetchone()


def get_all_teachers():
    with get_conn() as conn:
        return conn.execute(
            "SELECT * FROM teachers ORDER BY created_at DESC"
        ).fetchall()


def delete_teacher(telegram_id: int):
    with get_conn() as conn:
        conn.execute("DELETE FROM teachers WHERE telegram_id = ?", (telegram_id,))
        conn.commit()
