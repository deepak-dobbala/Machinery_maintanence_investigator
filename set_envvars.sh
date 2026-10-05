#!/usr/bin/env bash

# Gathers the Project ID from env; falls back to gcloud if unset
export GOOGLE_CLOUD_PROJECT="${GOOGLE_CLOUD_PROJECT:-$(gcloud config get-value project -q 2>/dev/null)}"

# Reads CLOUD_REGION from env; falls back to gcloud run/region,
# then defaults to us-central1
export CLOUD_REGION="${CLOUD_REGION:-$(gcloud config get-value run/region -q 2>/dev/null)}"

#set the Service account name 
export SA="model-invocation-sa@maintenance-investigator.iam.gserviceaccount.com"

# If CLOUD_REGION is still empty, use us-central1
export CLOUD_REGION="${CLOUD_REGION:-us-central1}"

source .venv/bin/activate
pip install -r requirements.txt
pip freeze | grep -iE "^(fastapi|uvicorn|pydantic|google-genai|google-cloud-firestore|google-cloud-storage)=="
# Display the values
echo "GOOGLE_CLOUD_PROJECT : ${GOOGLE_CLOUD_PROJECT}"
echo "CLOUD_REGION         : ${CLOUD_REGION}"