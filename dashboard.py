"""Dashboard logic - task summaries, completion %, and deadline-based prioritization. No AI/API calls."""

from datetime import date, datetime
from dateutil import parser as date_parser


def parse_deadline(deadline_text: str):
    """Try to parse a free-text deadline into a date object. Returns None if not parseable."""
    if not deadline_text:
        return None

    cleaned = deadline_text.strip().lower()
    if cleaned in ("none found", "none", "n/a", "not found", ""):
        return None

    try:
        parsed = date_parser.parse(deadline_text, fuzzy=True, default=datetime(2026, 1, 1))
        return parsed.date()
    except (ValueError, OverflowError):
        return None


def days_until(deadline_date):
    if deadline_date is None:
        return None
    today = date.today()
    return (deadline_date - today).days


def compute_completion(document_matches: list[dict]) -> dict:
    """Given a list of match dicts, compute completion stats."""
    if not document_matches:
        return {"matched": 0, "total": 0, "percent": 0, "missing": []}

    total = len(document_matches)
    matched = sum(1 for m in document_matches if m["status"] == "matched")
    missing = [m["document"] for m in document_matches if m["status"] != "matched"]
    percent = round((matched / total) * 100) if total > 0 else 0

    return {"matched": matched, "total": total, "percent": percent, "missing": missing}


def build_dashboard_rows(tasks: list[dict]) -> list[dict]:
    """
    tasks: list of dicts with keys: filename, task_type, deadline, document_matches
    Returns rows sorted by deadline urgency (soonest first, no-deadline last),
    each enriched with days_left and completion stats.
    """
    rows = []
    for task in tasks:
        deadline_date = parse_deadline(task.get("deadline", ""))
        remaining_days = days_until(deadline_date)
        completion = compute_completion(task.get("document_matches", []))

        if completion["total"] > 0:
            completion_text = f"{completion['matched']}/{completion['total']} ready"
        else:
            completion_text = "Not checked yet"

        if remaining_days is None:
            urgency_label = "No deadline"
        elif remaining_days < 0:
            urgency_label = "Overdue"
        elif remaining_days == 0:
            urgency_label = "Due today"
        else:
            urgency_label = f"{remaining_days} days left"

        rows.append({
            "filename": task.get("filename", ""),
            "task_type": task.get("task_type", ""),
            "deadline": task.get("deadline") or "None found",
            "urgency_label": urgency_label,
            "completion_percent": completion["percent"],
            "completion_text": completion_text,
            "missing": completion["missing"],
            "_sort_key": remaining_days if remaining_days is not None else 999999,
        })

    rows.sort(key=lambda r: r["_sort_key"])
    for r in rows:
        del r["_sort_key"]

    return rows