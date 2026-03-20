"""
COMMODEX — Database Layer
SQLite setup and table initialisation.
All tables use IF NOT EXISTS — safe to call init() on every startup.
"""

import sqlite3
import logging
from config import DB_PATH

logger = logging.getLogger(__name__)


def get_connection() -> sqlite3.Connection:
    """Return a SQLite connection with row_factory for dict-style access."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")   # better concurrent read performance
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init():
    """
    Create all tables if they don't exist.
    Safe to call on every application startup.
    """
    conn = get_connection()
    cursor = conn.cursor()

    # ── Signals Log ────────────────────────────────────────────────────────
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS signals_log (
            id                  INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp           DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
            commodity           TEXT NOT NULL,
            contract            TEXT NOT NULL,
            timeframe           TEXT NOT NULL,
            trading_style       TEXT NOT NULL,
            mode                TEXT NOT NULL,
            llm_provider        TEXT NOT NULL,
            llm_model           TEXT NOT NULL,
            prompt_version      TEXT,
            action              TEXT NOT NULL,
            confidence          INTEGER,
            signal_quality      TEXT,
            entry_price         REAL,
            stop_loss           REAL,
            target_1            REAL,
            target_2            REAL,
            rr_ratio            REAL,
            position_lots       INTEGER,
            capital_risk_pct    REAL,
            capital_risk_inr    REAL,
            market_regime       TEXT,
            sentiment           TEXT,
            primary_reason      TEXT,
            analyst_output      TEXT,
            signal_output       TEXT,
            risk_output         TEXT,
            guardrail_flags     TEXT,
            news_available      INTEGER DEFAULT 1,
            followed            INTEGER DEFAULT NULL,
            created_at          DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # ── Trades Log ─────────────────────────────────────────────────────────
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS trades_log (
            id                  INTEGER PRIMARY KEY AUTOINCREMENT,
            signal_id           INTEGER REFERENCES signals_log(id),
            commodity           TEXT NOT NULL,
            contract            TEXT NOT NULL,
            mode                TEXT NOT NULL,
            action              TEXT NOT NULL,
            lots                INTEGER NOT NULL,
            entry_price         REAL NOT NULL,
            entry_time          DATETIME,
            exit_price          REAL,
            exit_time           DATETIME,
            stop_loss           REAL,
            target_1            REAL,
            target_2            REAL,
            target_hit          INTEGER,
            pnl_inr             REAL,
            pnl_pct             REAL,
            exit_reason         TEXT,
            notes               TEXT,
            created_at          DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # ── Market Cache ───────────────────────────────────────────────────────
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS market_cache (
            id                  INTEGER PRIMARY KEY AUTOINCREMENT,
            commodity           TEXT NOT NULL,
            contract            TEXT NOT NULL,
            timeframe           TEXT NOT NULL,
            candle_time         DATETIME NOT NULL,
            open                REAL,
            high                REAL,
            low                 REAL,
            close               REAL,
            volume              INTEGER,
            cached_at           DATETIME DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(contract, timeframe, candle_time)
        )
    """)

    # ── News Cache ─────────────────────────────────────────────────────────
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS news_cache (
            id                  INTEGER PRIMARY KEY AUTOINCREMENT,
            commodity           TEXT NOT NULL,
            headline            TEXT NOT NULL,
            snippet             TEXT,
            source              TEXT,
            url                 TEXT,
            published_at        DATETIME,
            fetched_at          DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # ── Daily Summary ──────────────────────────────────────────────────────
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS daily_summary (
            id                      INTEGER PRIMARY KEY AUTOINCREMENT,
            date                    DATE NOT NULL,
            commodity               TEXT NOT NULL,
            signals_generated       INTEGER DEFAULT 0,
            signals_followed        INTEGER DEFAULT 0,
            paper_pnl_inr           REAL DEFAULT 0,
            real_pnl_inr            REAL DEFAULT 0,
            win_count               INTEGER DEFAULT 0,
            loss_count              INTEGER DEFAULT 0,
            daily_loss_limit_hit    INTEGER DEFAULT 0,
            UNIQUE(date, commodity)
        )
    """)

    # ── Prompt Versions ────────────────────────────────────────────────────
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS prompt_versions (
            id                  INTEGER PRIMARY KEY AUTOINCREMENT,
            agent_name          TEXT NOT NULL,
            version             TEXT NOT NULL,
            prompt_text         TEXT NOT NULL,
            notes               TEXT,
            active              INTEGER DEFAULT 1,
            created_at          DATETIME DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(agent_name, version)
        )
    """)

    conn.commit()
    conn.close()
    logger.info(f"Database initialised at {DB_PATH}")


def health_check() -> dict:
    """Quick check that DB is accessible and all tables exist."""
    expected_tables = {
        "signals_log", "trades_log", "market_cache",
        "news_cache", "daily_summary", "prompt_versions"
    }
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        existing = {row["name"] for row in cursor.fetchall()}
        conn.close()
        missing = expected_tables - existing
        return {
            "status":  "ok" if not missing else "degraded",
            "tables":  list(existing),
            "missing": list(missing),
            "db_path": str(DB_PATH),
        }
    except Exception as e:
        return {"status": "error", "error": str(e)}