#!/usr/bin/env python3

import os
from typing import Optional

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

VECTOR_LIMIT = 30


client = genai.Client(
    vertexai=True,
    project=PROJECT_ID,
    location=LOCATION,
)

db = firestore.Client(
    project=PROJECT_ID
)


def embed_query(query: str) -> Vector:

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
            "Embedding dimension mismatch: "
            f"expected {EMBEDDING_DIMENSION}, "
            f"got {len(values)}"
        )

    return Vector(values)


def exact_alarm_lookup(
    alarm_number: str,
):
    """
    Retrieve authoritative alarm definitions.

    Both string and integer representations are checked.
    """

    alarm_text = str(
        alarm_number
    ).strip()

    values = [
        alarm_text
    ]

    try:
        values.append(
            int(alarm_text)
        )
    except ValueError:
        pass

    results = []
    seen = set()

    for value in values:

        query = (
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
        )

        for doc in query.stream():

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
                normalize_result(
                    data,
                    chunk_id,
                    "exact_alarm",
                    None,
                )
            )

    return results


def semantic_lookup(
    query_text: str,
):
    """
    Retrieve troubleshooting and related
    diagnostic evidence.
    """

    query_vector = embed_query(
        query_text
    )

    vector_query = (
        db.collection(
            COLLECTION
        )
        .find_nearest(
            vector_field="embedding",
            query_vector=query_vector,
            distance_measure=DistanceMeasure.COSINE,
            limit=VECTOR_LIMIT,
            distance_result_field="vector_distance",
        )
    )

    results = []

    for doc in vector_query.stream():

        data = doc.to_dict()

        results.append(
            normalize_result(
                data,
                data.get(
                    "chunk_id",
                    doc.id,
                ),
                "semantic",
                data.get(
                    "vector_distance"
                ),
            )
        )

    return results


def normalize_result(
    data,
    chunk_id,
    match_type,
    score,
):
    return {
        "match_type": match_type,
        "score": score,
        "chunk_id": chunk_id,
        "document_id": data.get(
            "document_id"
        ),
        "revision": data.get(
            "revision"
        ),
        "manual_number": data.get(
            "manual_number"
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
        "matched_keywords":
            data.get(
                "matched_keywords",
                [],
            ),
        "text": data.get(
            "text",
            "",
        ),
    }


def rank_results(
    exact_results,
    semantic_results,
    alarm_number=None,
):
    """
    Rank maintenance evidence.

    Priority:
      1. Exact alarm, Rev E
      2. Exact alarm, Rev C
      3. Relevant troubleshooting, Rev E
      4. Relevant troubleshooting, Rev C
      5. Other supporting material

    When an alarm has a known subsystem, troubleshooting
    evidence matching that subsystem receives a strong boost.
    """

    combined = []

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

        combined.append(
            result
        )

    revision_rank = {
        "Rev E": 0,
        "Rev C": 1,
        "Rev Y": 2,
    }

    type_rank = {
        "alarm": 0,
        "troubleshooting": 1,
        "technical_reference": 2,
        "operator_context": 3,
    }

    # Known subsystem mapping from the selected alarm set.
    alarm_subsystems = {
        "101": "control_electronics",
        "102": "axis_servo",
        "103": "axis_servo",
        "107": "pneumatic_lubrication",
        "108": "axis_servo",
        "113": "tool_changer",
        "114": "tool_changer",
        "115": "tool_changer",
        "116": "spindle",
        "117": "spindle_gearbox",
        "118": "spindle_gearbox",
        "120": "pneumatic_lubrication",
        "121": "pneumatic_lubrication",
        "122": "spindle_drive",
        "123": "spindle_drive",
    }

    target_subsystem = None

    if alarm_number is not None:
        target_subsystem = alarm_subsystems.get(
            str(alarm_number)
        )

    def key(result):

        # ---------------------------------------------------------
        # Exact alarm evidence always comes first.
        # ---------------------------------------------------------

        exact_rank = (
            0
            if result["match_type"]
            == "exact_alarm"
            else 1
        )

        # ---------------------------------------------------------
        # Revision priority.
        # ---------------------------------------------------------

        revision = result.get(
            "revision"
        )

        revision_value = revision_rank.get(
            revision,
            99,
        )

        # ---------------------------------------------------------
        # Chunk type.
        # ---------------------------------------------------------

        chunk_type = result.get(
            "chunk_type"
        )

        type_value = type_rank.get(
            chunk_type,
            99,
        )

        # ---------------------------------------------------------
        # Subsystem relevance.
        # ---------------------------------------------------------

        subsystem = result.get(
            "subsystem"
        )

        # ---------------------------------------------------------
        # Normalize subsystem aliases for ranking only.
        #
        # Stored source metadata is preserved exactly as-is.
        # ---------------------------------------------------------

        subsystem_aliases = {
            "electrical/spindle": {
                "spindle",
                "spindle_drive",
            },
            "spindle": {
                "spindle",
                "spindle_drive",
            },
            "spindle_drive": {
                "spindle_drive",
                "spindle",
            },
        }

        if target_subsystem is None:
            subsystem_value = 1

        elif subsystem == target_subsystem:
            subsystem_value = 0

        elif (
            subsystem in subsystem_aliases
            and target_subsystem
            in subsystem_aliases[subsystem]
        ):
            subsystem_value = 0

        else:
            subsystem_value = 1

        # ---------------------------------------------------------
        # Semantic distance.
        #
        # Smaller is better.
        # ---------------------------------------------------------

        score = result.get(
            "score"
        )

        if score is None:
            score = -1

        return (
            exact_rank,
            revision_value,
            type_value,
            subsystem_value,
            score,
        )

    combined.sort(
        key=key
    )

    return combined

def search_manual(
    query: str,
    alarm_number: Optional[str] = None,
):
    """
    Main retrieval function for the maintenance investigator.
    """

    exact_results = []

    if alarm_number is not None:
        exact_results = exact_alarm_lookup(
            alarm_number
        )

    semantic_results = semantic_lookup(
        query
    )

    ranked = rank_results(
        exact_results,
        semantic_results,
        alarm_number=alarm_number,
    )

    return {
        "query": query,

        "alarm_number":
            alarm_number,

        "result_count":
            len(ranked),

        "exact_alarm_count":
            len(exact_results),

        "semantic_result_count":
            len(semantic_results),

        "results":
            ranked,
    }


def format_citation(
    result,
):
    revision = result.get(
        "revision",
        "unknown revision",
    )

    page_start = result.get(
        "manual_page_start"
    )

    page_end = result.get(
        "manual_page_end"
    )

    if (
        page_start is not None
        and page_end is not None
    ):
        if page_start == page_end:
            page_text = (
                f"manual p. {page_start}"
            )
        else:
            page_text = (
                f"manual pp. "
                f"{page_start}-{page_end}"
            )
    else:
        page_text = (
            "manual page unavailable"
        )

    return (
        f"VF Series Service Manual "
        f"{revision}, {page_text}"
    )


def format_evidence(
    search_result,
    max_results=8,
):
    """
    Produce compact evidence for an ADK agent.
    """

    results = search_result[
        "results"
    ][:max_results]

    evidence = []

    for index, result in enumerate(
        results,
        start=1,
    ):

        evidence.append(
            {
                "evidence_id":
                    f"E{index}",

                "match_type":
                    result[
                        "match_type"
                    ],

                "revision":
                    result[
                        "revision"
                    ],

                "chunk_type":
                    result[
                        "chunk_type"
                    ],

                "topic":
                    result[
                        "topic"
                    ],

                "subsystem":
                    result[
                        "subsystem"
                    ],

                "alarm_number":
                    result[
                        "alarm_number"
                    ],

                "citation":
                    format_citation(
                        result
                    ),

                "chunk_id":
                    result[
                        "chunk_id"
                    ],

                "text":
                    result[
                        "text"
                    ],
            }
        )

    return evidence