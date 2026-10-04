import json
import os
import tempfile
from datetime import datetime
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
RECORDS_FILE = BASE_DIR / "database" / "records.json"


def _read_all():
    try:
        with open(RECORDS_FILE, "r", encoding="utf-8") as file:
            data = json.load(file)
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return []
    return data if isinstance(data, list) else []


def _write_all(records):
    RECORDS_FILE.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_path = tempfile.mkstemp(dir=RECORDS_FILE.parent, suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as file:
            json.dump(records, file, indent=2, ensure_ascii=False)
        os.replace(temp_path, RECORDS_FILE)
    except Exception:
        if os.path.exists(temp_path):
            os.remove(temp_path)
        raise


def save_record(tracker_id, name, month, budget, expenses):
    total_spent = round(sum(amount for _, _, amount in expenses), 2)
    record = {
        "tracker_id": tracker_id,
        "name": name,
        "month": month,
        "budget": budget,
        "total_spent": total_spent,
        "remaining": round(budget - total_spent, 2),
        "over_budget": total_spent > budget,
        "saved_at": datetime.now().isoformat(timespec="seconds"),
        "expenses": [
            {"category": c, "description": d, "amount": a}
            for c, d, a in expenses
        ],
    }

    records = [r for r in _read_all() if r.get("tracker_id") != tracker_id]
    records.append(record)
    _write_all(records)
    return record


def load_records():
    return _read_all()


def get_record(tracker_id):
    for record in _read_all():
        if record.get("tracker_id") == tracker_id:
            return record
    return None


def delete_record(tracker_id):
    records = [r for r in _read_all() if r.get("tracker_id") != tracker_id]
    _write_all(records)