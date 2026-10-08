#!/usr/bin/env python3

import os
import sys
from pathlib import Path

from google import genai
from google.cloud import firestore
from google.cloud.firestore_v1.base_vector_query import DistanceMeasure
from google.cloud.firestore_v1.vector import Vector


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

VECTOR_FIELD = "embedding"

VECTOR_LIMIT = 8


# ---------------------------------------------------------------------
# Clients
# ---------------------------------------------------------------------

client = genai.Client(
    vertexai=True,
    project=PROJECT_ID,
    location=LOCATION,
)

db = firestore.Client(
    project=PROJECT_ID
)


# ---------------------------------------------------------------------
# Query embedding
# ---------------------------------------------------------------------

def embed_query(query: str):

    response = client.models.embed_content(
        model=EMBEDDING_MODEL,
        contents=query,
        config={
            "task_type": "RETRIEVAL_QUERY",
            "output_dimensionality":
                EMBEDDING_DIMENSION,
        },
    )

    values = response.embeddings[0].values

    if len(values) != EMBEDDING_DIMENSION:
        raise RuntimeError(
            "Query embedding dimension mismatch: "
            f"expected {EMBEDDING_DIMENSION}, "
            f"got {len(values)}"
        )

    return Vector(values)


# ---------------------------------------------------------------------
# Exact alarm lookup
# ---------------------------------------------------------------------

def search_alarm(alarm_number: str):

    alarm_number_text = str(
        alarm_number
    ).strip()

    # Try both representations because the existing
    # Firestore alarm documents may contain alarm_number
    # as either a string or integer.
    values_to_try = [
        alarm_number_text
    ]

    try:
        values_to_try.append(
            int(alarm_number_text)
        )
    except ValueError:
        pass

    results = []
    seen = set()

    for value in values_to_try:

        docs = (
            db.collection(
                COLLECTION
            )
            .where(
                filter=firestore.FieldFilter(
                    field_path="alarm_number",
                    op_string="==",
                    value=value,
                )
            )
            .limit(10)
            .stream()
        )

        for doc in docs:

            data = doc.to_dict()

            chunk_id = data.get(
                "chunk_id",
                doc.id,
            )

            if chunk_id in seen:
                continue

            seen.add(
                chunk_id
            )

            results.append(
                {
                    "match_type": "exact_alarm",

                    "score": None,

                    "chunk_id": chunk_id,

                    "document_id": data.get(
                        "document_id"
                    ),

                    "revision": data.get(
                        "revision"
                    ),

                    "manual_page_start":
                        data.get(
                            "manual_page_start"
                        ),

                    "manual_page_end":
                        data.get(
                            "manual_page_end"
                        ),

                    "pdf_page_start":
                        data.get(
                            "pdf_page_start"
                        ),

                    "pdf_page_end":
                        data.get(
                            "pdf_page_end"
                        ),

                    "chunk_type": data.get(
                        "chunk_type"
                    ),

                    "topic": data.get(
                        "topic"
                    ),

                    "subsystem": data.get(
                        "subsystem"
                    ),

                    "alarm_number":
                        data.get(
                            "alarm_number"
                        ),

                    "alarm_text":
                        data.get(
                            "alarm_text"
                        ),

                    "text": data.get(
                        "text",
                        ""
                    ),
                }
            )

    return results


# ---------------------------------------------------------------------
# Semantic vector search
# ---------------------------------------------------------------------

def vector_search(
    query: str,
    limit: int = VECTOR_LIMIT,
):

    query_vector = embed_query(
        query
    )

    vector_query = (
        db.collection(
            COLLECTION
        )
        .find_nearest(
            vector_field=VECTOR_FIELD,
            query_vector=query_vector,
            distance_measure=DistanceMeasure.COSINE,
            limit=limit,
            distance_result_field="vector_distance",
        )
    )

    docs = vector_query.stream()

    results = []

    for doc in docs:

        data = doc.to_dict()

        results.append(
            {
                "match_type":
                    "semantic",

                "score":
                    data.get(
                        "vector_distance"
                    ),

                "chunk_id":
                    data.get(
                        "chunk_id",
                        doc.id,
                    ),

                "document_id":
                    data.get(
                        "document_id"
                    ),

                "revision":
                    data.get(
                        "revision"
                    ),

                "manual_page_start":
                    data.get(
                        "manual_page_start"
                    ),

                "manual_page_end":
                    data.get(
                        "manual_page_end"
                    ),

                "pdf_page_start":
                    data.get(
                        "pdf_page_start"
                    ),

                "pdf_page_end":
                    data.get(
                        "pdf_page_end"
                    ),

                "chunk_type":
                    data.get(
                        "chunk_type"
                    ),

                "topic":
                    data.get(
                        "topic"
                    ),

                "subsystem":
                    data.get(
                        "subsystem"
                    ),

                "alarm_number":
                    data.get(
                        "alarm_number"
                    ),

                "alarm_text":
                    data.get(
                        "alarm_text"
                    ),

                "text":
                    data.get(
                        "text",
                        ""
                    ),
            }
        )

    return results


# ---------------------------------------------------------------------
# Combined search
# ---------------------------------------------------------------------

def search_manual(
    query: str,
    alarm_number=None,
):

    exact_results = []

    if alarm_number is not None:
        exact_results = search_alarm(
            str(alarm_number)
        )

    semantic_results = vector_search(
        query
    )

    # -------------------------------------------------------------
    # Revision priority
    # -------------------------------------------------------------
    #
    # Rev E = primary
    # Rev C = supporting revision
    #
    # Other documents are supplementary.
    # -------------------------------------------------------------

    revision_priority = {
        "Rev E": 0,
        "Rev C": 1,
        "Rev Y": 2,
    }

    chunk_type_priority = {
        "alarm": 0,
        "troubleshooting": 1,
        "technical_reference": 2,
        "operator_context": 3,
    }

    def rank_key(result):

        match_priority = (
            0
            if result["match_type"]
            == "exact_alarm"
            else 1
        )

        revision = result.get(
            "revision"
        )

        revision_rank = revision_priority.get(
            revision,
            99,
        )

        chunk_type = result.get(
            "chunk_type"
        )

        chunk_rank = chunk_type_priority.get(
            chunk_type,
            99,
        )

        # Semantic distance:
        # smaller = more similar.
        distance = result.get(
            "score"
        )

        if distance is None:
            distance = -1

        return (
            match_priority,
            revision_rank,
            chunk_rank,
            distance,
        )

    # -------------------------------------------------------------
    # Merge and deduplicate.
    # -------------------------------------------------------------

    merged = []

    seen = set()

    for result in (
        exact_results
        + semantic_results
    ):

        chunk_id = result[
            "chunk_id"
        ]

        if chunk_id in seen:
            continue

        seen.add(
            chunk_id
        )

        merged.append(
            result
        )

    # -------------------------------------------------------------
    # Rank.
    # -------------------------------------------------------------

    merged.sort(
        key=rank_key
    )

    return merged


# ---------------------------------------------------------------------
# Formatting
# ---------------------------------------------------------------------

def print_result(
    index,
    result,
):

    print()
    print(
        "=" * 80
    )

    print(
        f"RESULT {index}"
    )

    print(
        f"Match type: "
        f"{result['match_type']}"
    )

    print(
        f"Chunk: "
        f"{result['chunk_id']}"
    )

    print(
        f"Revision: "
        f"{result['revision']}"
    )

    print(
        f"Manual page: "
        f"{result['manual_page_start']}"
        f"-"
        f"{result['manual_page_end']}"
    )

    print(
        f"PDF page: "
        f"{result['pdf_page_start']}"
        f"-"
        f"{result['pdf_page_end']}"
    )

    print(
        f"Chunk type: "
        f"{result['chunk_type']}"
    )

    print(
        f"Topic: "
        f"{result['topic']}"
    )

    print(
        f"Subsystem: "
        f"{result['subsystem']}"
    )

    if result["alarm_number"]:
        print(
            f"Alarm: "
            f"{result['alarm_number']}"
        )

    if result["score"] is not None:
        print(
            f"Vector distance: "
            f"{result['score']}"
        )

    print()
    print(
        result["text"]
    )


# ---------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------

def main():

    if len(sys.argv) < 2:

        print(
            "Usage:"
        )

        print(
            "  python rag/search_manual.py "
            "\"your maintenance question\""
        )

        print()

        print(
            "Optional alarm:"
        )

        print(
            "  python rag/search_manual.py "
            "\"servo error too large\" 103"
        )

        sys.exit(1)

    query = sys.argv[1]

    alarm_number = None

    if len(sys.argv) >= 3:
        alarm_number = sys.argv[2]

    print()
    print(
        "Maintenance Investigator "
        "Manual Search"
    )

    print(
        f"Query: {query}"
    )

    if alarm_number:
        print(
            f"Alarm: {alarm_number}"
        )

    results = search_manual(
        query=query,
        alarm_number=alarm_number,
    )

    print()
    print(
        f"Results: {len(results)}"
    )

    if not results:

        print()
        print(
            "Not found in the supplied manuals."
        )

        return

    for index, result in enumerate(
        results,
        start=1,
    ):

        print_result(
            index,
            result,
        )


if __name__ == "__main__":
    main()