from fastapi import FastAPI
from google import genai


app = FastAPI()

client = genai.Client(
    vertexai=True,
    project="maintenance-investigator",
    location="global",
)

@app.get("/health")
def return_health():
    return {"status":"ok"}


@app.get("/gemini-test")
def gemini_test():
    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents="Reply with exactly: GEMINI_OK",
    )

    return {
        "status": "ok",
        "response": response.text,
    }

