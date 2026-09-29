"""Audit trail logic - tracks what was approved/rejected and when. No AI/API calls."""

from datetime import datetime


def create_log_entry(filename: str, action: str, task_type: str = "") -> dict:
    """Create a single audit log entry."""
    return {
        "filename": filename,
        "action": action,
        "task_type": task_type,
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }