from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, HttpUrl
import secrets
import sqlite3
import string
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pathlib import Path


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: initialize DB
    init_db()
    yield
    
fast = FastAPI(lifespan=lifespan)

DB_PATH = "url_shortener.db"
ALPHABET = string.ascii_letters + string.digits + "-._~"  # URL-safe symbols
MAX_CODE_LEN = 7


class ShortenRequest(BaseModel):
    original_url: HttpUrl


def get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    with get_conn() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS urls (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                original_url TEXT NOT NULL,
                short_code TEXT NOT NULL UNIQUE,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        conn.commit()


def generate_short_code(length: int = MAX_CODE_LEN) -> str:
    return "".join(secrets.choice(ALPHABET) for _ in range(length))




@fast.get("/")
def read_root():
    return FileResponse(Path("static/index.html"))


@fast.post("/shorten")
def shorten_url(payload: ShortenRequest):
    original_url = str(payload.original_url)

    # Try multiple times in case generated code already exists
    for _ in range(10):
        short_code = generate_short_code(7)  # fixed length, max 7
        try:
            with get_conn() as conn:
                conn.execute(
                    "INSERT INTO urls (original_url, short_code) VALUES (?, ?)",
                    (original_url, short_code),
                )
                conn.commit()
            return {
                "original_url": original_url,
                "short_code": short_code,
                "shortened_url": f"http://localhost:8000/{short_code}",
            }
        except sqlite3.IntegrityError:
            # Collision on UNIQUE(short_code), generate a new one
            continue

    raise HTTPException(status_code=500, detail="Could not generate a unique short code")


@fast.get("/{short_code}")
def resolve_short_url(short_code: str):
    with get_conn() as conn:
        row = conn.execute(
            "SELECT original_url FROM urls WHERE short_code = ?",
            (short_code,),
        ).fetchone()

    if not row:
        raise HTTPException(status_code=404, detail="Short URL not found")

    return RedirectResponse(url=row["original_url"], status_code=307)

fast.mount("/static", StaticFiles(directory="static"), name="static")