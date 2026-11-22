import os
import sqlite3
from datetime import datetime, timezone

DB_PATH = os.environ.get("DB_PATH", "deliveries.db")
STATUSES = ["pending", "in_transit", "delivered", "cancelled"]


def conn():
    c = sqlite3.connect(DB_PATH, timeout=10)
    c.row_factory = sqlite3.Row
    return c


def init():
    with conn() as c:
        c.execute(
            """CREATE TABLE IF NOT EXISTS deliveries (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            customer TEXT NOT NULL,
            address TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'pending',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL)"""
        )


def now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M")


def add(customer, address):
    with conn() as c:
        cur = c.execute(
            "INSERT INTO deliveries (customer,address,created_at,updated_at) VALUES (?,?,?,?)",
            (customer, address, now(), now()),
        )
        return cur.lastrowid


def set_status(did, status):
    if status not in STATUSES:
        return False
    with conn() as c:
        cur = c.execute(
            "UPDATE deliveries SET status=?, updated_at=? WHERE id=?", (status, now(), did)
        )
        return cur.rowcount > 0


def get(did):
    with conn() as c:
        return c.execute("SELECT * FROM deliveries WHERE id=?", (did,)).fetchone()


def list_all(limit=200):
    with conn() as c:
        return c.execute("SELECT * FROM deliveries ORDER BY id DESC LIMIT ?", (limit,)).fetchall()


def counts():
    with conn() as c:
        rows = c.execute("SELECT status, COUNT(*) n FROM deliveries GROUP BY status").fetchall()
    d = {s: 0 for s in STATUSES}
    d.update({r["status"]: r["n"] for r in rows})
    return d
