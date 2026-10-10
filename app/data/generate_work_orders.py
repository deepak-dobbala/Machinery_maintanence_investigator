import csv
import json
import random
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

random.seed(42)

BASE = Path(__file__).resolve().parents[1]
ALARM_FILE = BASE / "upload/maintenance_investigator_alarm_chunks.json"
OUTPUT = BASE / "data/work_orders.csv"

data = json.loads(ALARM_FILE.read_text(encoding="utf-8"))
by_code = defaultdict(list)

for chunk in data["chunks"]:
    by_code[str(chunk["alarm_number"])].append(chunk)

# Prefer Rev E; fall back to another source entry if needed.
alarms = {}
for code, entries in by_code.items():
    entries.sort(key=lambda x: (x.get("revision") != "Rev E"))
    alarms[code] = entries[0]["alarm_text"]

models = ["VF-2", "VF-4", "VF-6"]
statuses = ["unresolved", "escalated", "resolved"]

unresolved_cases = [
    ("Alarm recorded; machine remains stopped pending diagnosis",
     "Cause not confirmed; qualified inspection required"),
    ("Intermittent alarm reported by operator",
     "Insufficient evidence to determine root cause"),
    ("Alarm returned after restart",
     "Further troubleshooting required; no cause assumed"),
]
escalated_cases = [
    ("Alarm and symptoms documented for maintenance",
     "Root cause undetermined; referred for qualified diagnosis"),
    ("Initial observation recorded; further testing pending",
     "Possible control or mechanical issue; not confirmed"),
]
resolved_cases = [
    ("Simulated inspection identified and corrected a documented issue",
     "Simulated corrective action completed; operation rechecked"),
    ("Simulated maintenance action completed and result verified",
     "Simulated cause documented; post-maintenance check passed"),
]

fields = [
    "work_order_id", "machine_model", "alarm_code", "alarm_text",
    "symptom", "diagnosis", "action_taken", "resolution_status",
    "created_at", "source",
]

now = datetime.now(timezone.utc)

with OUTPUT.open("w", newline="", encoding="utf-8") as f:
    writer = csv.DictWriter(f, fieldnames=fields)
    writer.writeheader()

    for i in range(1, 101):
        code = random.choice(sorted(alarms, key=int))
        status = random.choices(
            statuses, weights=[45, 30, 25], k=1
        )[0]

        if status == "unresolved":
            symptom, diagnosis = random.choice(unresolved_cases)
            action = "Documented symptoms; left open for further investigation"
        elif status == "escalated":
            symptom, diagnosis = random.choice(escalated_cases)
            action = "Referred to qualified maintenance personnel"
        else:
            symptom, diagnosis = random.choice(resolved_cases)
            action = (
                "Synthetic example only: corrective action and verification "
                "recorded for test-data purposes"
            )

        writer.writerow({
            "work_order_id": f"WO-{i:04d}",
            "machine_model": random.choice(models),
            "alarm_code": code,
            "alarm_text": alarms[code],
            "symptom": symptom,
            "diagnosis": diagnosis,
            "action_taken": action,
            "resolution_status": status,
            "created_at": (
                now - timedelta(days=random.randint(0, 365))
            ).isoformat(),
            "source": "synthetic",
        })

print(f"Created 100 synthetic records: {OUTPUT}")
print(f"Alarm descriptions sourced from {ALARM_FILE.name}")
