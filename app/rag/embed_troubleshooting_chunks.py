#!/usr/bin/env python3

import json
import os
import time
from pathlib import Path

from google import genai
from google.cloud import firestore
from google.cloud.firestore_v1.vector import Vector


ROOT = Path(__file__).resolve().parent.parent

INPUT_JSON = (
    ROOT
    / "upload"
    / "maintenance_investigator_troubleshooting_chunks.json"
)

PROJECT_ID = os.environ.get(
    "GOOGLE_CLOUD_PROJECT",
    "maintenance-investigator",
)

LOCATION = os.environ.get(
    "GOOGLE_CLOUD_LOCATION",
    "us-central1",
)

EMBEDDING_MODEL = os.environ.get(
    "EMBEDDING_MODEL",
    "gemini-embedding-001",
)

EMBEDDING_DIMENSION = int(
    os.environ.get(
        "EMBEDDING_DIMENSION",
        "768",
    )
)

COLLECTION = "manual_chunks"

BATCH_SIZE = 5

MAX_RETRIES = 8


def load_chunks():
    with INPUT_JSON.open(
        "r",
        encoding="utf-8",
    ) as f:
        data = json.load(f)

    return data["chunks"]


def get_existing_chunk_ids(db):
    existing = set()

    docs = db.collection(
        COLLECTION
    ).stream()

    for doc in docs:
        data = doc.to_dict()

        chunk_id = data.get(
            "chunk_id"
        )

        if chunk_id:
            existing.add(
                chunk_id
            )

    return existing


def embed_batch(
    client,
    texts,
):
    for attempt in range(
        MAX_RETRIES
    ):
        try:
            response = client.models.embed_content(
                model=EMBEDDING_MODEL,
                contents=texts,
                config={
                    "task_type": "RETRIEVAL_DOCUMENT",
                    "output_dimensionality":
                        EMBEDDING_DIMENSION,
                },
            )

            vectors = []

            for embedding in response.embeddings:
                values = embedding.values

                if len(values) != EMBEDDING_DIMENSION:
                    raise RuntimeError(
                        "Embedding dimension mismatch: "
                        f"expected "
                        f"{EMBEDDING_DIMENSION}, "
                        f"got {len(values)}"
                    )

                vectors.append(values)

            return vectors

        except Exception as exc:

            message = str(exc)

            if (
                "429" not in message
                and "RESOURCE_EXHAUSTED"
                not in message
            ):
                raise

            wait_seconds = min(
                60,
                10 * (2 ** attempt),
            )

            print(
                f"429 quota response. "
                f"Retrying in "
                f"{wait_seconds}s..."
            )

            time.sleep(
                wait_seconds
            )

    raise RuntimeError(
        "Embedding failed after "
        f"{MAX_RETRIES} retries."
    )


def main():

    print(
        "Maintenance Investigator "
        "Troubleshooting Embedding"
    )

    print(
        f"Project: {PROJECT_ID}"
    )

    print(
        f"Location: {LOCATION}"
    )

    print(
        f"Model: {EMBEDDING_MODEL}"
    )

    print(
        f"Dimension: "
        f"{EMBEDDING_DIMENSION}"
    )

    print()

    # -------------------------------------------------------------
    # Load chunks.
    # -------------------------------------------------------------

    chunks = load_chunks()

    print(
        f"Troubleshooting chunks loaded: "
        f"{len(chunks)}"
    )

    # -------------------------------------------------------------
    # Google clients.
    # -------------------------------------------------------------

    client = genai.Client(
        vertexai=True,
        project=PROJECT_ID,
        location=LOCATION,
    )

    db = firestore.Client(
        project=PROJECT_ID
    )

    # -------------------------------------------------------------
    # Existing chunks.
    # -------------------------------------------------------------

    existing = get_existing_chunk_ids(
        db
    )

    print(
        f"Existing manual_chunks: "
        f"{len(existing)}"
    )

    remaining = [
        chunk
        for chunk in chunks
        if chunk["chunk_id"]
        not in existing
    ]

    print(
        f"Troubleshooting chunks "
        f"already present: "
        f"{len(chunks) - len(remaining)}"
    )

    print(
        f"Troubleshooting chunks "
        f"to embed: "
        f"{len(remaining)}"
    )

    if not remaining:
        print(
            "Nothing to embed."
        )
        return

    # -------------------------------------------------------------
    # Process batches.
    # -------------------------------------------------------------

    total = len(remaining)

    for batch_start in range(
        0,
        total,
        BATCH_SIZE,
    ):

        batch = remaining[
            batch_start:
            batch_start + BATCH_SIZE
        ]

        batch_number = (
            batch_start // BATCH_SIZE
        ) + 1

        total_batches = (
            (total + BATCH_SIZE - 1)
            // BATCH_SIZE
        )

        print()
        print(
            f"Batch {batch_number}/"
            f"{total_batches}"
        )

        print(
            f"  chunks "
            f"{batch_start + 1}-"
            f"{batch_start + len(batch)} "
            f"of {total}"
        )

        texts = [
            chunk["text"]
            for chunk in batch
        ]

        vectors = embed_batch(
            client,
            texts,
        )

        if len(vectors) != len(batch):
            raise RuntimeError(
                "Embedding count mismatch: "
                f"expected {len(batch)}, "
                f"got {len(vectors)}"
            )

        # ---------------------------------------------------------
        # Write each chunk.
        # ---------------------------------------------------------

        for chunk, values in zip(
            batch,
            vectors,
        ):

            document = dict(
                chunk
            )

            document[
                "embedding"
            ] = Vector(values)

            # Keep vector metadata simple.
            document[
                "embedding_model"
            ] = EMBEDDING_MODEL

            document[
                "embedding_dimension"
            ] = EMBEDDING_DIMENSION

            document[
                "embedding_task"
            ] = "RETRIEVAL_DOCUMENT"

            doc_id = chunk[
                "chunk_id"
            ]

            db.collection(
                COLLECTION
            ).document(
                doc_id
            ).set(
                document,
                merge=True,
            )

            print(
                f"  stored {doc_id}"
            )

        # Small pause between batches.
        if (
            batch_start + BATCH_SIZE
            < total
        ):
            time.sleep(2)

    print()
    print(
        "Embedding complete."
    )


if __name__ == "__main__":
    main()