"""SQLite：药箱里的每一盒。

同一种药不同批次（有效期不同）分开记——过期是按批次算的，合成一条就查不准了。
所以唯一键是「名字 + 有效期」，不是名字。
"""

from __future__ import annotations

import json
import os
import sqlite3
import threading
from datetime import datetime

_LOCK = threading.Lock()

SCHEMA = """
CREATE TABLE IF NOT EXISTS medicines (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    generic TEXT NOT NULL DEFAULT '',
    qty REAL NOT NULL DEFAULT 0,
    expire TEXT NOT NULL DEFAULT '',
    place TEXT NOT NULL DEFAULT '',
    note TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_med_name_expire ON medicines(name, expire);
CREATE TABLE IF NOT EXISTS advices (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    actions TEXT NOT NULL DEFAULT '[]',
    summary TEXT NOT NULL DEFAULT '',
    outsiders TEXT NOT NULL DEFAULT '[]',
    created_at TEXT NOT NULL
);
"""


def now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def connect(path: str = "data/kangji.db") -> sqlite3.Connection:
    parent = os.path.dirname(os.path.abspath(path))
    if parent:
        os.makedirs(parent, exist_ok=True)
    conn = sqlite3.connect(path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    return conn


def add_med(conn, name: str, generic: str, qty: float, expire: str,
            place: str = "", note: str = "") -> int:
    with _LOCK:
        row = conn.execute(
            "SELECT id FROM medicines WHERE name=? AND expire=?", (name, expire)
        ).fetchone()
        if row:
            # 同一批次再放一次：数量叠加，位置按最新的记
            conn.execute(
                "UPDATE medicines SET qty=qty+?, place=?, note=? WHERE id=?",
                (qty, place, note, row["id"]),
            )
            conn.commit()
            return row["id"]
        cur = conn.execute(
            "INSERT INTO medicines(name, generic, qty, expire, place, note, created_at) VALUES (?,?,?,?,?,?,?)",
            (name, generic, qty, expire, place, note, now()),
        )
        conn.commit()
        return cur.lastrowid


def list_meds(conn) -> list[dict]:
    return [dict(r) for r in conn.execute("SELECT * FROM medicines ORDER BY expire, id").fetchall()]


def get_med(conn, med_id: int) -> dict | None:
    row = conn.execute("SELECT * FROM medicines WHERE id=?", (med_id,)).fetchone()
    return dict(row) if row else None


def use_med(conn, med_id: int, n: float = 1) -> float | None:
    """用掉几个，返回剩余数量；id 不存在返回 None。到 0 不自动删——你自己确认才删。"""
    with _LOCK:
        conn.execute("UPDATE medicines SET qty=MAX(0, qty-?) WHERE id=?", (n, med_id))
        conn.commit()
        row = conn.execute("SELECT qty FROM medicines WHERE id=?", (med_id,)).fetchone()
        return float(row["qty"]) if row else None


def delete_med(conn, med_id: int) -> None:
    with _LOCK:
        conn.execute("DELETE FROM medicines WHERE id=?", (med_id,))
        conn.commit()


def save_advice(conn, actions: list[dict], summary: str, foreign: list[str]) -> int:
    with _LOCK:
        cur = conn.execute(
            # 列名不能叫 foreign：那是 SQLite 的保留字，建表会直接语法错误
            "INSERT INTO advices(actions, summary, outsiders, created_at) VALUES (?,?,?,?)",
            (json.dumps(actions, ensure_ascii=False), summary,
             json.dumps(foreign, ensure_ascii=False), now()),
        )
        conn.commit()
        return cur.lastrowid


def last_advice(conn) -> dict | None:
    row = conn.execute("SELECT * FROM advices ORDER BY id DESC LIMIT 1").fetchone()
    if not row:
        return None
    d = dict(row)
    d["actions"] = json.loads(d["actions"] or "[]")
    d["foreign"] = json.loads(d["outsiders"] or "[]")
    d.pop("outsiders", None)
    return d


def stats(conn) -> dict:
    total = conn.execute("SELECT COUNT(*) n FROM medicines").fetchone()["n"]
    units = conn.execute("SELECT COALESCE(SUM(qty),0) q FROM medicines").fetchone()["q"]
    with_expire = conn.execute("SELECT COUNT(*) n FROM medicines WHERE expire<>''").fetchone()["n"]
    unrecognized = conn.execute("SELECT COUNT(*) n FROM medicines WHERE generic=''").fetchone()["n"]
    return {"total": total, "units": units, "with_expire": with_expire,
            "unrecognized": unrecognized}
