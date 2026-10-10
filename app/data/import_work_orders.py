import argparse
import csv
from pathlib import Path

from google.cloud import firestore

PROJECT_ID = "maintenance-investigator"
COLLECTION = "work_orders"
CSV_PATH = Path(__file__).with_name("work_orders.csv")

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Write records to Firestore; default is dry run",
    )
    args = parser.parse_args()

    with CSV_PATH.open(newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    if len(rows) != 100:
        raise SystemExit(f"Expected 100 rows; found {len(rows)}")

    ids = [r["work_order_id"] for r in rows]
    if len(set(ids)) != len(ids):
        raise SystemExit("Duplicate work_order_id values found")

    db = firestore.Client(project=PROJECT_ID)
    refs = [db.collection(COLLECTION).document(i) for i in ids]

    # Read existing documents first; do not overwrite them.
    existing = []
    for ref in refs:
        if ref.get().exists:
            existing.append(ref.id)

    if existing:
        raise SystemExit(
            f"Refusing to overwrite {len(existing)} existing documents. "
            f"Examples: {existing[:10]}"
        )

    print(f"Validated {len(rows)} records for {PROJECT_ID}/{COLLECTION}.")
    print("Existing document IDs: none.")

    if not args.apply:
        print("DRY RUN ONLY. No documents written.")
        print("To import, rerun with: python data/import_work_orders.py --apply")
        return

    # Batch writes in groups below Firestore's batch operation limit.
    for start in range(0, len(rows), 400):
        batch = db.batch()
        for row in rows[start:start + 400]:
            doc_id = row["work_order_id"]
            batch.create(db.collection(COLLECTION).document(doc_id), row)
        batch.commit()

    print(f"Imported {len(rows)} synthetic work orders.")

if __name__ == "__main__":
    main()
