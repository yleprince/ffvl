import csv
import os
import random
import sqlite3
from contextlib import asynccontextmanager, contextmanager
from datetime import datetime, timedelta
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

BASE_DIR = Path(__file__).resolve().parent.parent
DB_PATH = Path(os.environ.get("DB_PATH", BASE_DIR / "data" / "qcm.db"))
QUESTIONS_CSV = BASE_DIR / "questions.csv"
OPTIONS_CSV = BASE_DIR / "options.csv"
STATIC_DIR = BASE_DIR / "static"

# Leitner box -> how long until a question in that box is due again.
BOX_INTERVALS = {
    1: timedelta(minutes=1),
    2: timedelta(hours=1),
    3: timedelta(days=1),
    4: timedelta(days=3),
    5: timedelta(days=7),
    6: timedelta(days=16),
}
MAX_BOX = max(BOX_INTERVALS)


def now_iso() -> str:
    return datetime.utcnow().isoformat()


@contextmanager
def get_db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db():
    with get_db() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS questions (
                id INTEGER PRIMARY KEY,
                text TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS options (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                question_id INTEGER NOT NULL REFERENCES questions(id),
                text TEXT NOT NULL,
                score INTEGER NOT NULL
            );
            CREATE TABLE IF NOT EXISTS review_state (
                question_id INTEGER PRIMARY KEY REFERENCES questions(id),
                box INTEGER NOT NULL DEFAULT 1,
                next_due TEXT NOT NULL,
                times_seen INTEGER NOT NULL DEFAULT 0,
                times_correct INTEGER NOT NULL DEFAULT 0,
                last_reviewed TEXT
            );
            """
        )
        already_seeded = conn.execute("SELECT COUNT(*) c FROM questions").fetchone()["c"] > 0
        if already_seeded:
            return

        with open(QUESTIONS_CSV, encoding="utf-8") as f:
            questions = list(csv.DictReader(f))
        with open(OPTIONS_CSV, encoding="utf-8") as f:
            options = list(csv.DictReader(f))

        due_now = now_iso()
        conn.executemany(
            "INSERT INTO questions (id, text) VALUES (?, ?)",
            [(int(q["questionId"]), q["Text"]) for q in questions],
        )
        conn.executemany(
            "INSERT INTO options (question_id, text, score) VALUES (?, ?, ?)",
            [(int(o["questionId"]), o["text"], int(o["score"])) for o in options],
        )
        conn.executemany(
            "INSERT INTO review_state (question_id, box, next_due) VALUES (?, 1, ?)",
            [(int(q["questionId"]), due_now) for q in questions],
        )


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(lifespan=lifespan)


class AnswerIn(BaseModel):
    question_id: int
    selected_option_ids: list[int]


@app.get("/api/next")
def get_next():
    with get_db() as conn:
        now = now_iso()
        due_rows = conn.execute(
            "SELECT question_id FROM review_state WHERE next_due <= ? ORDER BY next_due ASC LIMIT 50",
            (now,),
        ).fetchall()

        stats = _stats(conn)

        if not due_rows:
            upcoming = conn.execute(
                "SELECT next_due FROM review_state ORDER BY next_due ASC LIMIT 1"
            ).fetchone()
            return {
                "question_id": None,
                "next_due_at": upcoming["next_due"] if upcoming else None,
                "stats": stats,
            }

        question_id = random.choice(due_rows)["question_id"]
        question = conn.execute(
            "SELECT id, text FROM questions WHERE id = ?", (question_id,)
        ).fetchone()
        options = conn.execute(
            "SELECT id, text FROM options WHERE question_id = ?", (question_id,)
        ).fetchall()
        shuffled = list(options)
        random.shuffle(shuffled)

        return {
            "question_id": question["id"],
            "text": question["text"],
            "options": [{"id": o["id"], "text": o["text"]} for o in shuffled],
            "stats": stats,
        }


@app.post("/api/answer")
def submit_answer(payload: AnswerIn):
    with get_db() as conn:
        options = conn.execute(
            "SELECT id, text, score FROM options WHERE question_id = ?",
            (payload.question_id,),
        ).fetchall()
        if not options:
            raise HTTPException(status_code=404, detail="Unknown question_id")

        correct_ids = {o["id"] for o in options if o["score"] > 0}
        selected_ids = set(payload.selected_option_ids)
        all_correct = selected_ids == correct_ids

        state = conn.execute(
            "SELECT box FROM review_state WHERE question_id = ?",
            (payload.question_id,),
        ).fetchone()
        box = state["box"] if state else 1
        box = min(box + 1, MAX_BOX) if all_correct else 1
        next_due = datetime.utcnow() + BOX_INTERVALS[box]

        conn.execute(
            """
            UPDATE review_state
            SET box = ?, next_due = ?, times_seen = times_seen + 1,
                times_correct = times_correct + ?, last_reviewed = ?
            WHERE question_id = ?
            """,
            (box, next_due.isoformat(), 1 if all_correct else 0, now_iso(), payload.question_id),
        )

        return {
            "correct": all_correct,
            "options": [{"id": o["id"], "correct": o["score"] > 0} for o in options],
            "box": box,
            "next_due_at": next_due.isoformat(),
        }


def _stats(conn) -> dict:
    total = conn.execute("SELECT COUNT(*) c FROM review_state").fetchone()["c"]
    due = conn.execute(
        "SELECT COUNT(*) c FROM review_state WHERE next_due <= ?", (now_iso(),)
    ).fetchone()["c"]
    mastered = conn.execute(
        "SELECT COUNT(*) c FROM review_state WHERE box = ?", (MAX_BOX,)
    ).fetchone()["c"]
    not_seen = conn.execute(
        "SELECT COUNT(*) c FROM review_state WHERE times_seen = 0"
    ).fetchone()["c"]
    successful = conn.execute(
        "SELECT COUNT(*) c FROM review_state WHERE times_correct > 0"
    ).fetchone()["c"]
    needs_practice = conn.execute(
        "SELECT COUNT(*) c FROM review_state WHERE times_seen > 0 AND times_correct = 0"
    ).fetchone()["c"]
    return {
        "total": total,
        "due": due,
        "mastered": mastered,
        "not_seen": not_seen,
        "successful": successful,
        "needs_practice": needs_practice,
    }


@app.get("/api/stats")
def get_stats():
    with get_db() as conn:
        return _stats(conn)


app.mount("/", StaticFiles(directory=STATIC_DIR, html=True), name="static")
