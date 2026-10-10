from pydantic import BaseModel, Field
from google.adk.agents import LlmAgent


class ImageExtraction(BaseModel):
    machine_model: str | None = Field(
        description="Machine model visibly supported by the image, such as VF-2; otherwise null."
    )
    control_generation: str | None = Field(
        description="Control generation only if supported by visible evidence; otherwise null."
    )
    alarm_code: str | None = Field(
        description="Alarm number visible on an alarm screen; otherwise null."
    )
    alarm_text: str | None = Field(
        description="Alarm text transcribed from the image; otherwise null."
    )
    machine_state: str | None = Field(
        description="Machine state explicitly visible or unambiguously indicated by the image; otherwise null."
    )
    confidence: float = Field(
        ge=0.0,
        le=1.0,
        description="Confidence in the overall extraction, from 0.0 to 1.0."
    )
    missing_fields: list[str] = Field(
        description="Names of requested fields that are absent, unreadable, or not reliably identifiable."
    )


root_agent = LlmAgent(
    name="image_extractor",
    model="gemini-2.5-flash",
    description="Extracts machine and alarm information from uploaded maintenance images.",
    instruction="""
You extract structured information from a user-provided machine image.

Rules:
1. Use only information visible in the image.
2. Never invent a model, control generation, alarm code, alarm text, or machine state.ojects ;
3. Return null for fields that are absent, unreadable, or not reliably identifiable.
4. A nameplate is not an alarm screen. Do not infer an active alarm from a nameplate.
5. Include every absent, unreadable, or uncertain field in missing_fields.
6. Reduce confidence when text is blurry, cropped, ambiguous, or unsupported.
7. Confidence must reflect the reliability of the overall extraction, not just one field.
8. Transcribe alarm text faithfully; do not silently correct wording.
9. Do not diagnose faults or recommend repairs. This agent only extracts image fields.
10. If no image is actually provided, do not pretend one was inspected. Set unavailable fields to null and identify them in missing_fields.
""",
    output_schema=ImageExtraction,
    output_key="image_extraction",
)
