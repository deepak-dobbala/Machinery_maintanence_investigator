from google.cloud import firestore


PROJECT_ID = "maintenance-investigator"
COLLECTION = "manual_chunks"


def main():

    db = firestore.Client(
        project=PROJECT_ID
    )

    docs = list(
        db.collection(
            COLLECTION
        ).stream()
    )

    print(
        f"manual_chunks: {len(docs)}"
    )

    missing_vectors = []
    invalid_vectors = []

    for doc in docs:

        data = doc.to_dict()

        chunk_id = data.get(
            "chunk_id",
            doc.id,
        )

        vector = data.get(
            "embedding"
        )

        if vector is None:
            missing_vectors.append(
                chunk_id
            )
            continue

        try:
            values = list(vector)

            if len(values) != 768:
                invalid_vectors.append(
                    (
                        chunk_id,
                        len(values),
                    )
                )

        except Exception:
            invalid_vectors.append(
                (
                    chunk_id,
                    "not iterable",
                )
            )

    print(
        f"Missing vectors: "
        f"{len(missing_vectors)}"
    )

    print(
        f"Invalid vectors: "
        f"{len(invalid_vectors)}"
    )

    if missing_vectors:
        print()
        print("Missing:")

        for item in missing_vectors:
            print(
                f"  {item}"
            )

    if invalid_vectors:
        print()
        print("Invalid:")

        for item in invalid_vectors:
            print(
                f"  {item}"
            )

    print()

    if (
        len(docs) == 149
        and not missing_vectors
        and not invalid_vectors
    ):
        print(
            "PASS: 149 chunks with "
            "valid 768-dimensional vectors."
        )

    else:
        print(
            "CHECK REQUIRED."
        )


if __name__ == "__main__":
    main()