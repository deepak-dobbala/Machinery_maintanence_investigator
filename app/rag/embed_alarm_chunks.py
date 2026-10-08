#!/usr/bin/env python3

import os
import time

from google import genai
from google.genai import types
from google.cloud import firestore


PROJECT_ID = os.environ["GOOGLE_CLOUD_PROJECT"]
LOCATION = os.getenv("GOOGLE_CLOUD_LOCATION", "us-central1")

MODEL_ID = os.getenv(
    "EMBEDDING_MODEL",
    "gemini-embedding-001",
)

OUTPUT_DIMENSIONALITY = int(
    os.getenv("EMBEDDING_DIMENSION", "768")
)

SOURCE_COLLECTION = "alarms"
TARGET_COLLECTION = "manual_chunks"

BATCH_SIZE = 5
MAX_RETRIES = 6


def create_embeddings(client, texts):
    """
    Generate embeddings for a batch of document texts.
    """

    for attempt in range(MAX_RETRIES):
        try:
            response = client.models.embed_content(
                model=MODEL_ID,
                contents=texts,
                config=types.EmbedContentConfig(
                    task_type="RETRIEVAL_DOCUMENT",
                    output_dimensionality=OUTPUT_DIMENSIONALITY,
                    auto_truncate=True,
                ),
            )

            embeddings = [
                item.values
                for item in response.embeddings
            ]

            if len(embeddings) != len(texts):
                raise RuntimeError(
                    f"Expected {len(texts)} embeddings, "
                    f"received {len(embeddings)}."
                )

            for index, embedding in enumerate(embeddings):
                if len(embedding) != OUTPUT_DIMENSIONALITY:
                    raise RuntimeError(
                        f"Embedding {index}: expected "
                        f"{OUTPUT_DIMENSIONALITY} dimensions, "
                        f"received {len(embedding)}."
                    )

            return embeddings

        except Exception as exc:
            error_text = str(exc)

            is_quota_error = (
                "429" in error_text
                or "RESOURCE_EXHAUSTED" in error_text
            )

            if not is_quota_error:
                raise

            if attempt == MAX_RETRIES - 1:
                raise

            wait_seconds = min(
                60,
                10 * (2 ** attempt),
            )

            print(
                f"    Vertex quota limit reached. "
                f"Waiting {wait_seconds}s "
                f"before retry "
                f"({attempt + 1}/{MAX_RETRIES})..."
            )

            time.sleep(wait_seconds)

    raise RuntimeError(
        "Embedding request failed after retries."
    )


def main():
    print(
        "Maintenance Investigator - "
        "Alarm Embedding Pipeline"
    )
    print()

    print(f"Project:       {PROJECT_ID}")
    print(f"Location:      {LOCATION}")
    print(f"Model:         {MODEL_ID}")
    print(f"Dimension:     {OUTPUT_DIMENSIONALITY}")
    print(f"Batch size:    {BATCH_SIZE}")
    print()

    db = firestore.Client(
        project=PROJECT_ID
    )

    client = genai.Client(
        vertexai=True,
        project=PROJECT_ID,
        location=LOCATION,
    )

    source_docs = list(
        db.collection(SOURCE_COLLECTION)
        .stream()
    )

    print(
        f"Found {len(source_docs)} source documents "
        f"in '{SOURCE_COLLECTION}'."
    )

    if not source_docs:
        raise RuntimeError(
            "No alarm documents found."
        )

    pending = []
    skipped = 0

    # ---------------------------------------------------------
    # Identify chunks that still need embeddings.
    # ---------------------------------------------------------
    for source_doc in source_docs:
        chunk_id = source_doc.id
        source = source_doc.to_dict()

        target_ref = (
            db.collection(TARGET_COLLECTION)
            .document(chunk_id)
        )

        existing = target_ref.get()

        if existing.exists:
            existing_data = existing.to_dict()

            existing_embedding = (
                existing_data.get("embedding")
            )

            if (
                isinstance(existing_embedding, list)
                and len(existing_embedding)
                == OUTPUT_DIMENSIONALITY
            ):
                skipped += 1
                continue

        text = source.get("text")

        if not text:
            print(
                f"WARNING: {chunk_id} has no text. "
                f"Skipping."
            )
            skipped += 1
            continue

        pending.append(
            {
                "chunk_id": chunk_id,
                "source": source,
            }
        )

    print()
    print(f"Already embedded: {skipped}")
    print(f"Remaining:        {len(pending)}")
    print()

    embedded = 0

    # ---------------------------------------------------------
    # Process remaining chunks in small batches.
    # ---------------------------------------------------------
    for start in range(
        0,
        len(pending),
        BATCH_SIZE,
    ):
        batch = pending[
            start:start + BATCH_SIZE
        ]

        print(
            f"Processing batch "
            f"{start + 1}-"
            f"{start + len(batch)} "
            f"of {len(pending)}"
        )

        texts = [
            item["source"]["text"]
            for item in batch
        ]

        embeddings = create_embeddings(
            client,
            texts,
        )

        # -----------------------------------------------------
        # Store each embedding.
        # -----------------------------------------------------
        for item, embedding in zip(
            batch,
            embeddings,
        ):
            chunk_id = item["chunk_id"]
            source = item["source"]

            target_data = dict(source)

            target_data["chunk_id"] = chunk_id
            target_data["embedding"] = embedding
            target_data["embedding_model"] = MODEL_ID
            target_data["embedding_dimension"] = (
                OUTPUT_DIMENSIONALITY
            )
            target_data["embedding_task"] = (
                "RETRIEVAL_DOCUMENT"
            )

            (
                db.collection(TARGET_COLLECTION)
                .document(chunk_id)
                .set(
                    target_data,
                    merge=True,
                )
            )

            embedded += 1

            print(
                f"    stored "
                f"manual_chunks/{chunk_id}"
            )

        # Small pause between batches.
        if (
            start + BATCH_SIZE
            < len(pending)
        ):
            time.sleep(2)

    print()
    print("Embedding complete.")
    print(f"Embedded: {embedded}")
    print(f"Skipped:  {skipped}")
    print(
        f"Total:    "
        f"{embedded + skipped}"
    )


if __name__ == "__main__":
    main()