"""
COMMODEX — SQLite Backup Utility
Daily backup of commodex.db to data/backups/
Keeps last 30 days of backups automatically.
"""

import shutil
import logging
from datetime import datetime, timedelta
from pathlib import Path
from config import DB_PATH, BACKUP_DIR

logger = logging.getLogger(__name__)


def run_backup() -> dict:
    """
    Copy commodex.db to data/backups/commodex_YYYYMMDD.db
    Returns result dict with status and backup path.
    """
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)

    if not DB_PATH.exists():
        return {"status": "skipped", "reason": "Database file not found"}

    backup_name = f"commodex_{datetime.today().strftime('%Y%m%d')}.db"
    backup_path = BACKUP_DIR / backup_name

    try:
        shutil.copy2(DB_PATH, backup_path)
        logger.info(f"Backup created: {backup_path}")
        _cleanup_old_backups(keep_days=30)
        return {
            "status":      "ok",
            "backup_path": str(backup_path),
            "size_kb":     round(backup_path.stat().st_size / 1024, 1),
            "timestamp":   datetime.now().isoformat(),
        }
    except Exception as e:
        logger.error(f"Backup failed: {e}")
        return {"status": "error", "error": str(e)}


def _cleanup_old_backups(keep_days: int = 30):
    """Delete backup files older than keep_days."""
    cutoff = datetime.today() - timedelta(days=keep_days)
    for f in BACKUP_DIR.glob("commodex_*.db"):
        try:
            date_str = f.stem.replace("commodex_", "")
            file_date = datetime.strptime(date_str, "%Y%m%d")
            if file_date < cutoff:
                f.unlink()
                logger.info(f"Deleted old backup: {f.name}")
        except (ValueError, OSError):
            pass


def list_backups() -> list[dict]:
    """Return list of available backups with metadata."""
    if not BACKUP_DIR.exists():
        return []
    backups = []
    for f in sorted(BACKUP_DIR.glob("commodex_*.db"), reverse=True):
        backups.append({
            "filename":   f.name,
            "size_kb":    round(f.stat().st_size / 1024, 1),
            "created_at": datetime.fromtimestamp(
                f.stat().st_mtime
            ).strftime("%Y-%m-%d %H:%M"),
        })
    return backups