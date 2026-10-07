#!/usr/bin/env python3
"""
Maintenance Investigator asset uploader.

What this does:
1. Uploads the three Haas PDFs to a Google Cloud Storage "manuals" bucket.
2. Uploads the generated alarm JSON/CSV dataset to an "alarms" bucket.
3. Writes manual metadata to Firestore collection: manuals
4. Writes the 30 alarm chunks to Firestore collection: alarms

It intentionally DOES NOT create embeddings yet. That is the next RAG step.

Prerequisites:
    pip install google-cloud-storage google-cloud-firestore

Authentication:
    gcloud auth application-default login
or use a service account / Cloud Run service account with ADC.

Example:
    export GOOGLE_CLOUD_PROJECT="your-project-id"
    export MANUALS_BUCKET="your-project-manuals"
    export ALARMS_BUCKET="your-project-alarms"

    python upload_maintenance_assets.py --dry-run
    python upload_maintenance_assets.py

Recommended GCS layout:
    gs://<manuals-bucket>/manuals/96-8100/rev-e/...
    gs://<manuals-bucket>/manuals/96-8100/rev-c/...
    gs://<manuals-bucket>/manuals/96-8000/rev-y/...

    gs://<alarms-bucket>/alarms/96-8100/rev-e/...
    gs://<alarms-bucket>/alarms/96-8100/rev-c/...
"""

import argparse
import csv
import json
import os
from pathlib import Path
from typing import Dict, List

from google.cloud import firestore
from google.cloud import storage


ROOT = Path(__file__).resolve().parent

MANUALS = [
    {
        "local_path": ROOT / "english---vf-series-service-manual---2002.pdf",
        "document_id": "96-8100-rev-e-2002",
        "manual_number": "96-8100",
        "title": "VF Series Service Manual",
        "revision": "Rev E",
        "publication_date": "June 2002",
        "source_role": "primary",
        "gcs_prefix": "manuals/96-8100/rev-e/",
    },
    {
        "local_path": ROOT / "english---vf-series-service-manual---2001.pdf",
        "document_id": "96-8100-rev-c-2001",
        "manual_number": "96-8100",
        "title": "VF Series Service Manual",
        "revision": "Rev C",
        "publication_date": "June 2001",
        "source_role": "revision_reference",
        "gcs_prefix": "manuals/96-8100/rev-c/",
    },
    {
        "local_path": ROOT / "english---mill-operator's-manual---2009.pdf",
        "document_id": "96-8000-rev-y-2009",
        "manual_number": "96-8000",
        "title": "Mill Operator's Manual",
        "revision": "Rev Y",
        "publication_date": "December 2009",
        "source_role": "supplementary_operator_context",
        "gcs_prefix": "manuals/96-8000/rev-y/",
    },
]

ALARM_JSON = ROOT / "maintenance_investigator_alarm_chunks.json"
ALARM_CSV = ROOT / "maintenance_investigator_alarm_chunks.csv"

def required_env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise SystemExit(
            f"Missing environment variable {name}. "
            f"Set it before running the uploader."
        )
    return value


def upload_file(bucket, local_path: Path, object_name: str, content_type: str):
    blob = bucket.blob(object_name)
    blob.upload_from_filename(str(local_path), content_type=content_type)
    return f"gs://{bucket.name}/{object_name}"


def load_alarm_chunks() -> List[Dict]:
    data = json.loads(ALARM_JSON.read_text(encoding="utf-8"))
    return data["chunks"]


def firestore_write_in_batches(db, collection_name: str, documents: List[Dict]):
    # Firestore supports batches; keep below the API batch operation limit.
    batch_size = 400
    written = 0

    for start in range(0, len(documents), batch_size):
        batch = db.batch()
        subset = documents[start:start + batch_size]

        for document in subset:
            doc_id = document["chunk_id"]
            ref = db.collection(collection_name).document(doc_id)
            batch.set(ref, document, merge=True)

        batch.commit()
        written += len(subset)

    return written


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate files/config and print planned writes without changing GCS/Firestore.",
    )
    args = parser.parse_args()


    project_id = required_env("PROJECT_ID")
    manuals_bucket_name = required_env("MANUALS_BUCKET")
    alarms_bucket_name = required_env("ALARMS_BUCKET")
    print(f"maual_bucket_path : {manuals_bucket_name}")
    print(f"alarms_bucket_name : {alarms_bucket_name}")

    for item in MANUALS:
        if not item["local_path"].exists():
            raise SystemExit(f"Missing manual: {item['local_path']}")

    if not ALARM_JSON.exists():
        raise SystemExit(f"Missing alarm dataset: {ALARM_JSON}")

    chunks = load_alarm_chunks()

    print(f"Project:          {project_id}")
    print(f"Manuals bucket:   gs://{manuals_bucket_name}")
    print(f"Alarms bucket:    gs://{alarms_bucket_name}")
    print(f"Alarm chunks:     {len(chunks)}")
    print()

    for item in MANUALS:
        object_name = item["gcs_prefix"] + item["local_path"].name
        print(f"MANUAL  {item['local_path'].name}")
        print(f"        -> gs://{manuals_bucket_name}/{object_name}")

    print()
    print("ALARM DATASET")
    print(f"        -> gs://{alarms_bucket_name}/alarms/96-8100/alarm_chunks.json")
    print(f"        -> gs://{alarms_bucket_name}/alarms/96-8100/alarm_chunks.csv")
    print()
    print("FIRESTORE")
    print(f"        -> manuals/{len(MANUALS)} documents")
    print(f"        -> alarms/{len(chunks)} documents")
    print()

    if args.dry_run:
        print("DRY RUN: no changes made.")
        return

    storage_client = storage.Client(project=project_id)
    firestore_client = firestore.Client(project=project_id)

    manuals_bucket = storage_client.bucket(manuals_bucket_name)
    alarms_bucket = storage_client.bucket(alarms_bucket_name)

    # 1. Upload source PDFs.
    manual_docs = []
    for item in MANUALS:
        object_name = item["gcs_prefix"] + item["local_path"].name

        uri = upload_file(
            manuals_bucket,
            item["local_path"],
            object_name,
            "application/pdf",
        )

        manual_docs.append({
            **item,
            "gcs_uri": uri,
            "filename": item["local_path"].name,
            "machine_family": "Haas VF Series",
        })

        print(f"Uploaded manual: {uri}")

    # 2. Upload alarm dataset artifacts.
    alarm_json_uri = upload_file(
        alarms_bucket,
        ALARM_JSON,
        "alarms/96-8100/alarm_chunks.json",
        "application/json",
    )

    alarm_csv_uri = upload_file(
        alarms_bucket,
        ALARM_CSV,
        "alarms/96-8100/alarm_chunks.csv",
        "text/csv",
    )

    print(f"Uploaded alarm JSON: {alarm_json_uri}")
    print(f"Uploaded alarm CSV:  {alarm_csv_uri}")

    # 3. Firestore: manual metadata.
    for item in manual_docs:
        doc_id = item["document_id"]

        firestore_item = {
            key: value
            for key, value in item.items()
            if key != "local_path"
        }

        # Store the local filename as a string if useful for traceability.
        firestore_item["local_filename"] = item["local_path"].name

        firestore_client.collection("manuals").document(doc_id).set(
            firestore_item,
            merge=True,
        )

    print(f"Wrote {len(manual_docs)} documents to Firestore collection 'manuals'.")

    # 4. Firestore: alarm chunks.
    # Add the alarm dataset GCS locations as metadata without modifying source text.
    enriched_chunks = []
    for chunk in chunks:
        enriched = dict(chunk)
        enriched["alarm_dataset_gcs_json"] = alarm_json_uri
        enriched["alarm_dataset_gcs_csv"] = alarm_csv_uri
        enriched["embedding_status"] = "not_embedded"
        enriched_chunks.append(enriched)

    count = firestore_write_in_batches(
        firestore_client,
        "alarms",
        enriched_chunks,
    )

    print(f"Wrote {count} documents to Firestore collection 'alarms'.")
    print()
    print("Upload complete.")
    print("No embeddings were generated; that remains the next RAG step.")


if __name__ == "__main__":
    main()