#!/usr/bin/env python3

import os

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

ALARM_DOCUMENT_ID = "vf_2001_revc_alarm_103"

def main():
    print(f"Project:       {PROJECT_ID}")
    print(f"Location:      {LOCATION}")
    print(f"Embedding:     {MODEL_ID}")
    print(f"Dimension:     {OUTPUT_DIMENSIONALITY}")
    print()

    # ---------------------------------------------------------
    # 1. Read one real alarm chunk from Firestore.
    # ---------------------------------------------------------
    db = firestore.Client(project=PROJECT_ID)

    ref = (
        db.collection("alarms")
        .document(ALARM_DOCUMENT_ID)
    )

    snapshot = ref.get()

    if not snapshot.exists:
        raise RuntimeError(
            f"Firestore document not found: "
            f"alarms/{ALARM_DOCUMENT_ID}"
        )

    chunk = snapshot.to_dict()

    text = chunk.get("text")

    if not text:
        raise RuntimeError(
            f"Document alarms/{ALARM_DOCUMENT_ID} "
            f"does not contain a 'text' field."
        )

    print("Loaded Firestore chunk:")
    print(f"  document: alarms/{ALARM_DOCUMENT_ID}")
    print(f"  alarm:    {chunk.get('alarm_number')}")
    print(f"  revision: {chunk.get('revision')}")
    print(f"  page:     {chunk.get('manual_page_start')}")
    print()

    print("Text preview:")
    print(text[:500])
    print()

    # ---------------------------------------------------------
    # 2. Create Vertex AI client.
    # ---------------------------------------------------------
    client = genai.Client(
        vertexai=True,
        project=PROJECT_ID,
        location=LOCATION,
    )

    # ---------------------------------------------------------
    # 3. Generate a retrieval-document embedding.
    # ---------------------------------------------------------
    response = client.models.embed_content(
        model=MODEL_ID,
        contents=text,
        config=types.EmbedContentConfig(
            task_type="RETRIEVAL_DOCUMENT",
            output_dimensionality=OUTPUT_DIMENSIONALITY,
            auto_truncate=True,
        ),
    )

    embedding = response.embeddings[0].values

    # ---------------------------------------------------------
    # 4. Verify the result.
    # ---------------------------------------------------------
    print("Embedding generated successfully.")
    print(f"Actual vector dimension: {len(embedding)}")
    print()

    print("First 10 values:")
    print(embedding[:10])
    print()

    if len(embedding) != OUTPUT_DIMENSIONALITY:
        raise RuntimeError(
            f"Expected {OUTPUT_DIMENSIONALITY} dimensions, "
            f"but received {len(embedding)}."
        )

    print("DIMENSION CHECK: PASS")
    print("2.3 embedding test complete.")


if __name__ == "__main__":
    main()