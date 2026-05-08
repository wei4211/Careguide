"""SQLite 評估紀錄與報告儲存模組。"""

import json
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Dict, List, Optional

DB_PATH = Path(__file__).resolve().parent.parent / "database" / "careguide.db"


@contextmanager
def get_conn():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db() -> None:
    with get_conn() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                display_name TEXT,
                password_hash TEXT NOT NULL,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                last_login_at TEXT
            );

            CREATE TABLE IF NOT EXISTS assessments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                age INTEGER,
                gender TEXT,
                living_status TEXT,
                caregiver TEXT,
                adl_score INTEGER,
                iadl_score INTEGER,
                health_score INTEGER,
                family_score INTEGER,
                caregiver_score INTEGER,
                total_score INTEGER,
                risk_level TEXT,
                risk_level_code TEXT,
                risk_factors TEXT,
                user_description TEXT,
                ai_advice TEXT,
                raw_input TEXT,
                FOREIGN KEY(user_id) REFERENCES users(id)
            );

            CREATE TABLE IF NOT EXISTS reports (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                assessment_id INTEGER NOT NULL,
                report_text TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(assessment_id) REFERENCES assessments(id)
            );
            """
        )


def save_assessment(payload: Dict) -> int:
    with get_conn() as conn:
        cur = conn.execute(
            """
            INSERT INTO assessments (
                user_id, age, gender, living_status, caregiver,
                adl_score, iadl_score, health_score, family_score, caregiver_score,
                total_score, risk_level, risk_level_code,
                risk_factors, user_description, ai_advice, raw_input
            ) VALUES (
                :user_id, :age, :gender, :living_status, :caregiver,
                :adl_score, :iadl_score, :health_score, :family_score, :caregiver_score,
                :total_score, :risk_level, :risk_level_code,
                :risk_factors, :user_description, :ai_advice, :raw_input
            )
            """,
            {
                "user_id": payload.get("user_id"),
                "age": payload.get("age"),
                "gender": payload.get("gender"),
                "living_status": payload.get("living_status"),
                "caregiver": payload.get("caregiver"),
                "adl_score": payload.get("adl_score"),
                "iadl_score": payload.get("iadl_score"),
                "health_score": payload.get("health_score"),
                "family_score": payload.get("family_score"),
                "caregiver_score": payload.get("caregiver_score"),
                "total_score": payload.get("total_score"),
                "risk_level": payload.get("risk_level"),
                "risk_level_code": payload.get("risk_level_code"),
                "risk_factors": json.dumps(payload.get("risk_factors", []), ensure_ascii=False),
                "user_description": payload.get("user_description"),
                "ai_advice": payload.get("ai_advice"),
                "raw_input": json.dumps(payload.get("raw_input", {}), ensure_ascii=False),
            },
        )
        return cur.lastrowid


def get_assessment(assessment_id: int, user_id: Optional[int] = None) -> Optional[Dict]:
    with get_conn() as conn:
        if user_id is not None:
            row = conn.execute(
                "SELECT * FROM assessments WHERE id = ? AND user_id = ?",
                (assessment_id, user_id),
            ).fetchone()
        else:
            row = conn.execute(
                "SELECT * FROM assessments WHERE id = ?", (assessment_id,)
            ).fetchone()
        return _row_to_dict(row) if row else None


def get_all_records(limit: int = 50, user_id: Optional[int] = None) -> List[Dict]:
    with get_conn() as conn:
        if user_id is not None:
            rows = conn.execute(
                "SELECT * FROM assessments WHERE user_id = ? ORDER BY id DESC LIMIT ?",
                (user_id, limit),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM assessments ORDER BY id DESC LIMIT ?", (limit,)
            ).fetchall()
        return [_row_to_dict(r) for r in rows]


def delete_record(assessment_id: int) -> None:
    with get_conn() as conn:
        conn.execute("DELETE FROM reports WHERE assessment_id = ?", (assessment_id,))
        conn.execute("DELETE FROM assessments WHERE id = ?", (assessment_id,))


def update_ai_advice(assessment_id: int, advice: str) -> None:
    with get_conn() as conn:
        conn.execute(
            "UPDATE assessments SET ai_advice = ? WHERE id = ?",
            (advice, assessment_id),
        )


# ---- 使用者相關 ----

def create_user(username: str, password_hash: str, display_name: Optional[str] = None) -> int:
    with get_conn() as conn:
        cur = conn.execute(
            "INSERT INTO users (username, password_hash, display_name) VALUES (?, ?, ?)",
            (username, password_hash, display_name or username),
        )
        return cur.lastrowid


def get_user_by_username(username: str) -> Optional[Dict]:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM users WHERE username = ?", (username,)
        ).fetchone()
        return dict(row) if row else None


def get_user_by_id(user_id: int) -> Optional[Dict]:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM users WHERE id = ?", (user_id,)
        ).fetchone()
        return dict(row) if row else None


def update_last_login(user_id: int) -> None:
    with get_conn() as conn:
        conn.execute(
            "UPDATE users SET last_login_at = CURRENT_TIMESTAMP WHERE id = ?",
            (user_id,),
        )


def save_report(assessment_id: int, report_text: str) -> int:
    with get_conn() as conn:
        cur = conn.execute(
            "INSERT INTO reports (assessment_id, report_text) VALUES (?, ?)",
            (assessment_id, report_text),
        )
        return cur.lastrowid


def get_report(assessment_id: int) -> Optional[Dict]:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM reports WHERE assessment_id = ? ORDER BY id DESC LIMIT 1",
            (assessment_id,),
        ).fetchone()
        return dict(row) if row else None


def _row_to_dict(row: sqlite3.Row) -> Dict:
    data = dict(row)
    for field in ("risk_factors", "raw_input"):
        if data.get(field):
            try:
                data[field] = json.loads(data[field])
            except (TypeError, ValueError):
                pass
    return data
