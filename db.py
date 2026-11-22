import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime
from zoneinfo import ZoneInfo

import jdatetime

DB_PATH = os.environ.get("DB_PATH", "fuel_bot.db")
TIMEZONE = ZoneInfo(os.environ.get("TIMEZONE", "Asia/Tehran"))
DAILY_REQUIRED = int(os.environ.get("DAILY_REQUIRED", "300"))


@contextmanager
def conn():
    """Yield a row-aware SQLite connection and always commit/close it safely."""
    connection = sqlite3.connect(DB_PATH, timeout=15)
    connection.row_factory = sqlite3.Row
    try:
        yield connection
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def init():
    # Fuel-bot tables are deliberately named separately from the original
    # delivery-tracking tables, so an existing deliveries.db remains intact.
    with conn() as c:
        c.executescript("""
        CREATE TABLE IF NOT EXISTS fuel_users (
            user_id INTEGER PRIMARY KEY,
            username TEXT NOT NULL DEFAULT '',
            first_name TEXT NOT NULL DEFAULT '',
            joined_at TEXT NOT NULL,
            is_admin INTEGER NOT NULL DEFAULT 0,
            is_super_admin INTEGER NOT NULL DEFAULT 0,
            is_clan_member INTEGER NOT NULL DEFAULT 1,
            is_banned INTEGER NOT NULL DEFAULT 0,
            leave_until TEXT,
            penalty INTEGER NOT NULL DEFAULT 0,
            total_fuel INTEGER NOT NULL DEFAULT 0,
            total_sulfur INTEGER NOT NULL DEFAULT 0,
            total_rocket INTEGER NOT NULL DEFAULT 0,
            total_c4 INTEGER NOT NULL DEFAULT 0
        );
        CREATE TABLE IF NOT EXISTS fuel_deliveries (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            raw_fuel INTEGER NOT NULL DEFAULT 0,
            raw_sulfur INTEGER NOT NULL DEFAULT 0,
            raw_rocket INTEGER NOT NULL DEFAULT 0,
            raw_c4 INTEGER NOT NULL DEFAULT 0,
            total_fuel_calc INTEGER NOT NULL DEFAULT 0,
            date_jalali TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'pending',
            created_at TEXT NOT NULL,
            FOREIGN KEY(user_id) REFERENCES fuel_users(user_id)
        );
        CREATE TABLE IF NOT EXISTS fuel_daily_stats (
            user_id INTEGER NOT NULL,
            date_jalali TEXT NOT NULL,
            fuel INTEGER NOT NULL DEFAULT 0,
            sulfur INTEGER NOT NULL DEFAULT 0,
            rocket INTEGER NOT NULL DEFAULT 0,
            c4 INTEGER NOT NULL DEFAULT 0,
            PRIMARY KEY (user_id, date_jalali),
            FOREIGN KEY(user_id) REFERENCES fuel_users(user_id)
        );
        CREATE INDEX IF NOT EXISTS idx_fuel_deliveries_status_id
            ON fuel_deliveries(status, id DESC);
        CREATE INDEX IF NOT EXISTS idx_fuel_deliveries_user_date
            ON fuel_deliveries(user_id, date_jalali);
        """)


def today_jalali():
    return jdatetime.date.today().strftime("%Y/%m/%d")


def now_str():
    return jdatetime.datetime.now(TIMEZONE).strftime("%Y/%m/%d %H:%M:%S")


def calculate_total_fuel(fuel, sulfur, rocket, c4):
    return fuel + (sulfur // 2) + (rocket * 50) + (c4 * 75)


def add_user(uid, username="", first_name=""):
    is_super = int(bool(uid and uid == int(os.environ.get("SUPER_ADMIN_ID", "0"))))
    with conn() as c:
        c.execute("""INSERT INTO fuel_users
            (user_id, username, first_name, joined_at, is_super_admin)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(user_id) DO UPDATE SET
                username=excluded.username, first_name=excluded.first_name,
                is_super_admin=MAX(fuel_users.is_super_admin, excluded.is_super_admin)""",
            (uid, username or "", first_name or "", today_jalali(), is_super))


def get_user(uid):
    with conn() as c:
        return c.execute("SELECT * FROM fuel_users WHERE user_id=?", (uid,)).fetchone()


def get_all_users():
    with conn() as c:
        return c.execute("SELECT * FROM fuel_users ORDER BY joined_at DESC, user_id").fetchall()


def update_user(uid, **fields):
    allowed = {"is_admin", "is_clan_member", "is_banned", "leave_until", "penalty"}
    if not fields or not set(fields).issubset(allowed):
        raise ValueError("Invalid user fields")
    assignments = ", ".join(f"{field}=?" for field in fields)
    with conn() as c:
        cur = c.execute(f"UPDATE fuel_users SET {assignments} WHERE user_id=?",
                        (*fields.values(), uid))
        return cur.rowcount > 0


def submit_delivery(uid, fuel, sulfur, rocket, c4):
    total = calculate_total_fuel(fuel, sulfur, rocket, c4)
    with conn() as c:
        c.execute("""INSERT INTO fuel_deliveries
            (user_id, raw_fuel, raw_sulfur, raw_rocket, raw_c4,
             total_fuel_calc, date_jalali, status, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, 'pending', ?)""",
            (uid, fuel, sulfur, rocket, c4, total, today_jalali(), now_str()))
    return total


def approve_delivery(delivery_id):
    """Approve once and update daily and lifetime aggregates atomically."""
    with conn() as c:
        row = c.execute("SELECT * FROM fuel_deliveries WHERE id=?", (delivery_id,)).fetchone()
        if not row or row["status"] != "pending":
            return False
        c.execute("UPDATE fuel_deliveries SET status='approved' WHERE id=? AND status='pending'", (delivery_id,))
        if c.execute("SELECT changes()").fetchone()[0] != 1:
            return False
        c.execute("""INSERT INTO fuel_daily_stats (user_id, date_jalali, fuel, sulfur, rocket, c4)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(user_id, date_jalali) DO UPDATE SET
                fuel=fuel+excluded.fuel, sulfur=sulfur+excluded.sulfur,
                rocket=rocket+excluded.rocket, c4=c4+excluded.c4""",
            (row["user_id"], row["date_jalali"], row["raw_fuel"], row["raw_sulfur"], row["raw_rocket"], row["raw_c4"]))
        c.execute("""UPDATE fuel_users SET
            total_fuel=total_fuel+?, total_sulfur=total_sulfur+?,
            total_rocket=total_rocket+?, total_c4=total_c4+? WHERE user_id=?""",
            (row["total_fuel_calc"], row["raw_sulfur"], row["raw_rocket"], row["raw_c4"], row["user_id"]))
        return True


def get_pending():
    with conn() as c:
        return c.execute("""SELECT d.*, u.first_name, u.username FROM fuel_deliveries d
            JOIN fuel_users u ON d.user_id=u.user_id
            WHERE d.status='pending' ORDER BY d.id DESC""").fetchall()


def get_approved(limit=50):
    with conn() as c:
        return c.execute("""SELECT d.*, u.first_name, u.username FROM fuel_deliveries d
            JOIN fuel_users u ON d.user_id=u.user_id
            WHERE d.status='approved' ORDER BY d.id DESC LIMIT ?""", (limit,)).fetchall()


def get_leaderboard(limit=10):
    with conn() as c:
        return c.execute("""SELECT u.user_id, u.first_name, u.username,
            COALESCE(SUM(d.fuel + (d.sulfur / 2) + (d.rocket * 50) + (d.c4 * 75)), 0) AS total
            FROM fuel_users u LEFT JOIN fuel_daily_stats d ON u.user_id=d.user_id
            GROUP BY u.user_id ORDER BY total DESC, u.first_name COLLATE NOCASE LIMIT ?""", (limit,)).fetchall()


def get_user_balance(uid):
    user = get_user(uid)
    if not user:
        return 0
    joined = jdatetime.datetime.strptime(user["joined_at"], "%Y/%m/%d").date()
    days = max(1, (jdatetime.date.today() - joined).days + 1)
    return (user["total_fuel"] or 0) - days * DAILY_REQUIRED


def add_manual_delivery(uid, fuel, sulfur, rocket, c4):
    total = calculate_total_fuel(fuel, sulfur, rocket, c4)
    with conn() as c:
        if not c.execute("SELECT 1 FROM fuel_users WHERE user_id=?", (uid,)).fetchone():
            raise ValueError("کاربر پیدا نشد")
        c.execute("""INSERT INTO fuel_deliveries
            (user_id, raw_fuel, raw_sulfur, raw_rocket, raw_c4, total_fuel_calc,
             date_jalali, status, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, 'approved', ?)""",
            (uid, fuel, sulfur, rocket, c4, total, today_jalali(), now_str()))
        c.execute("""INSERT INTO fuel_daily_stats (user_id, date_jalali, fuel, sulfur, rocket, c4)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(user_id, date_jalali) DO UPDATE SET
                fuel=fuel+excluded.fuel, sulfur=sulfur+excluded.sulfur,
                rocket=rocket+excluded.rocket, c4=c4+excluded.c4""",
            (uid, today_jalali(), fuel, sulfur, rocket, c4))
        c.execute("""UPDATE fuel_users SET total_fuel=total_fuel+?, total_sulfur=total_sulfur+?,
            total_rocket=total_rocket+?, total_c4=total_c4+? WHERE user_id=?""",
            (total, sulfur, rocket, c4, uid))
    return total


def get_user_history(uid, limit=30):
    with conn() as c:
        return c.execute("""SELECT * FROM fuel_daily_stats WHERE user_id=?
            ORDER BY date_jalali DESC LIMIT ?""", (uid, limit)).fetchall()
