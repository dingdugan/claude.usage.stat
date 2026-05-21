"""SQLite 历史归档 —— 把 (session × 日期) 聚合永久存到本地。

源 jsonl 被 Claude Code 清理后,归档里的数据仍在。
只存数字聚合,不存对话内容 —— 一年的数据 < 1 MB。
"""
import os
import sqlite3

from .scanner import scan

DB_DIR = os.path.expanduser("~/.local/share/claude-usage-stat")
DB_PATH = os.path.join(DB_DIR, "history.db")

_SCHEMA = """
CREATE TABLE IF NOT EXISTS sessions (
    sid       TEXT PRIMARY KEY,
    proj      TEXT,
    proj_path TEXT,
    title     TEXT,
    branch    TEXT
);
CREATE TABLE IF NOT EXISTS daily (
    sid  TEXT,
    d    TEXT,
    i    INTEGER,
    o    INTEGER,
    cr   INTEGER,
    cw   INTEGER,
    cost REAL,
    PRIMARY KEY (sid, d)
);
CREATE INDEX IF NOT EXISTS idx_daily_d   ON daily(d);
CREATE INDEX IF NOT EXISTS idx_daily_sid ON daily(sid);
"""


def _connect() -> sqlite3.Connection:
    os.makedirs(DB_DIR, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.executescript(_SCHEMA)
    return conn


def archive_now(projects_dir: str, pricing: dict):
    """扫描当前 projects_dir,把数据 upsert 到归档。

    返回 (本次扫到的 session 数, 本次扫到的日聚合行数)。
    多次运行幂等 —— 重复跑只会用最新值覆盖,不会重复计数。
    """
    sessions, daily = scan(projects_dir, pricing)
    with _connect() as conn:
        if sessions:
            conn.executemany(
                """INSERT INTO sessions (sid, proj, proj_path, title, branch)
                   VALUES (?, ?, ?, ?, ?)
                   ON CONFLICT(sid) DO UPDATE SET
                     proj=excluded.proj, proj_path=excluded.proj_path,
                     title=excluded.title, branch=excluded.branch""",
                [(sid, s.get("proj", ""), s.get("projPath", ""),
                  s.get("title", ""), s.get("branch", ""))
                 for sid, s in sessions.items()],
            )
        if daily:
            conn.executemany(
                """INSERT INTO daily (sid, d, i, o, cr, cw, cost)
                   VALUES (?, ?, ?, ?, ?, ?, ?)
                   ON CONFLICT(sid, d) DO UPDATE SET
                     i=excluded.i, o=excluded.o, cr=excluded.cr,
                     cw=excluded.cw, cost=excluded.cost""",
                [(r["sid"], r["d"], r["i"], r["o"], r["cr"], r["cw"], r["cost"])
                 for r in daily],
            )
    return len(sessions), len(daily)


def read_archive():
    """从归档读出全部数据,返回 (sessions, daily) —— 格式与 scan() 完全一致。"""
    sessions = {}
    daily = []
    with _connect() as conn:
        for sid, proj, proj_path, title, branch in conn.execute(
            "SELECT sid, proj, proj_path, title, branch FROM sessions"
        ):
            sessions[sid] = {
                "proj": proj or "",
                "projPath": proj_path or "",
                "title": title or "",
                "branch": branch or "",
            }
        for sid, d, i, o, cr, cw, cost in conn.execute(
            "SELECT sid, d, i, o, cr, cw, cost FROM daily"
        ):
            daily.append({
                "sid": sid, "d": d,
                "i": i, "o": o, "cr": cr, "cw": cw,
                "cost": cost,
            })
    return sessions, daily


def db_stats():
    """返回 (session 数, 日行数, 文件大小字节, 路径)。"""
    if not os.path.exists(DB_PATH):
        return 0, 0, 0, DB_PATH
    with _connect() as conn:
        ns = conn.execute("SELECT COUNT(*) FROM sessions").fetchone()[0]
        nd = conn.execute("SELECT COUNT(*) FROM daily").fetchone()[0]
    return ns, nd, os.path.getsize(DB_PATH), DB_PATH
