#!/usr/bin/env python3

import json
from pathlib import Path
from collections import Counter

ROOT = Path(__file__).resolve().parent.parent

INPUT = (
    ROOT
    / "upload"
    / "maintenance_investigator_troubleshooting_chunks.json"
)

OUTPUT = (
    ROOT
    / "upload"
    / "maintenance_investigator_troubleshooting_chunks_review.json"
)


def load_chunks():
    with INPUT.open(
        "r",
        encoding="utf-8",
    ) as f:
        data = json.load(f)

    return data["chunks"]


def print_chunk(chunk, index):
    print()
    print("=" * 80)
    print(f"CHUNK {index}")
    print("=" * 80)

    print(
        f"ID:       {chunk['chunk_id']}"
    )

    print(
        f"Revision: {chunk['revision']}"
    )

    print(
        f"Topic:    {chunk['topic']}"
    )

    print(
        f"Subsystem:{chunk['subsystem']}"
    )

    print(
        f"Manual:   "
        f"{chunk['manual_page_start']}-"
        f"{chunk['manual_page_end']}"
    )

    print(
        f"PDF:      "
        f"{chunk['pdf_page_start']}-"
        f"{chunk['pdf_page_end']}"
    )

    print(
        f"Length:   {chunk['text_length']}"
    )

    print()
    print(chunk["text"])


def review(chunks):
    print()
    print("=" * 80)
    print("TROUBLESHOOTING CHUNK QUALITY REVIEW")
    print("=" * 80)

    print(
        f"Total chunks: {len(chunks)}"
    )

    print()

    by_revision = Counter(
        c["revision"]
        for c in chunks
    )

    by_topic = Counter(
        c["topic"]
        for c in chunks
    )

    print("By revision:")

    for key, value in sorted(
        by_revision.items()
    ):
        print(
            f"  {key}: {value}"
        )

    print()

    print("By topic:")

    for key, value in sorted(
        by_topic.items()
    ):
        print(
            f"  {key}: {value}"
        )

    print()

    # -------------------------------------------------------------
    # Flag suspiciously short chunks.
    # -------------------------------------------------------------

    short = [
        c
        for c in chunks
        if c["text_length"] < 500
    ]

    print(
        f"Chunks under 500 characters: "
        f"{len(short)}"
    )

    for i, chunk in enumerate(
        short,
        start=1,
    ):
        print_chunk(
            chunk,
            i,
        )

    # -------------------------------------------------------------
    # Flag chunks with very small page ranges.
    # -------------------------------------------------------------

    single_page = [
        c
        for c in chunks
        if (
            c["manual_page_start"]
            == c["manual_page_end"]
        )
    ]

    print()
    print(
        f"Single-manual-page chunks: "
        f"{len(single_page)}"
    )

    # -------------------------------------------------------------
    # Flag chunks with very many keywords.
    # -------------------------------------------------------------

    broad = [
        c
        for c in chunks
        if len(
            c["matched_keywords"]
        ) >= 8
    ]

    print(
        f"Broad keyword chunks: "
        f"{len(broad)}"
    )

    for i, chunk in enumerate(
        broad,
        start=1,
    ):
        print_chunk(
            chunk,
            i,
        )

    # -------------------------------------------------------------
    # Save reviewed copy.
    # -------------------------------------------------------------

    payload = {
        "dataset":
            "maintenance_investigator_troubleshooting_review",

        "source":
            str(INPUT),

        "chunk_count":
            len(chunks),

        "chunks":
            chunks,
    }

    with OUTPUT.open(
        "w",
        encoding="utf-8",
    ) as f:
        json.dump(
            payload,
            f,
            indent=2,
            ensure_ascii=False,
        )

    print()
    print(
        f"Review file written to:\n"
        f"{OUTPUT}"
    )


def main():
    chunks = load_chunks()
    review(chunks)


if __name__ == "__main__":
    main()