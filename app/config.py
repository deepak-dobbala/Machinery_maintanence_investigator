import os

PROJECT_ID = os.environ["GOOGLE_CLOUD_PROJECT"]
REGION = os.getenv("GOOGLE_CLOUD_REGION", "us-central1")

EMBEDDING_MODEL = os.getenv(
    "EMBEDDING_MODEL",
    "text-embedding-005",
)

EMBEDDING_DIMENSION = int(
    os.getenv("EMBEDDING_DIMENSION", "768")
)