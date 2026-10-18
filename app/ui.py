from pathlib import Path
import sys
from types import SimpleNamespace

import streamlit as st
import asyncio
import uuid
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types
from agents.image_extractor.agent import root_agent


def extract_uploaded_image(uploaded_file):
    """Extract visible machine/alarm details; do not diagnose from the image."""
    session_service = InMemorySessionService()
    app_name = "maintenance_image_extractor"
    user_id = "maintenance_technician"
    session_id = str(uuid.uuid4())

    async def create_and_run():
        await session_service.create_session(
            app_name=app_name, user_id=user_id, session_id=session_id
        )
        runner = Runner(
            app_name=app_name,
            agent=root_agent,
            session_service=session_service,
        )
        message = types.Content(
            role="user",
            parts=[
                types.Part.from_bytes(
                    data=uploaded_file.getvalue(),
                    mime_type=uploaded_file.type or "application/octet-stream",
                ),
                types.Part.from_text(
                    text="Extract only the visible machine and alarm fields from this image."
                ),
            ],
        )

        final_text = None
        async for event in runner.run_async(
            user_id=user_id, session_id=session_id, new_message=message
        ):
            if event.is_final_response() and event.content:
                for part in event.content.parts or []:
                    if part.text:
                        final_text = part.text

        if not final_text:
            raise RuntimeError("Image extractor returned no structured result.")
        return root_agent.output_schema.model_validate_json(final_text).model_dump()

    return asyncio.run(create_and_run())

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from agents.day5_workflow.agent import (
    new_case,
    ask_check,
    check_result,
    explain,
    close_out,
    more_evidence,
)

st.set_page_config(page_title="Maintenance Investigator", page_icon="🔧", layout="wide")
st.title("Maintenance Investigator")
st.caption("Day 5 · Evidence-led troubleshooting")

st.warning(
    "Safety first: this tool supports troubleshooting; it does not authorize work. "
    "Do not perform a suggested check until applicable machine-specific safety "
    "procedures and isolation requirements have been established. Escalate "
    "unresolved safety concerns to qualified personnel."
)

if "case_state" not in st.session_state:
    st.session_state.case_state = {}
if "last_output" not in st.session_state:
    st.session_state.last_output = None
if "active_check" not in st.session_state:
    st.session_state.active_check = None

def context():
    return SimpleNamespace(state=st.session_state.case_state)

def output_of(result):
    return getattr(result, "output", result)

def route_of(result):
    actions = getattr(result, "actions", None)
    return getattr(actions, "route", None) if actions else None

def show_result(result):
    data = output_of(result)
    st.session_state.last_output = data
    if isinstance(data, dict):
        st.json(data)
    else:
        st.write(data)
    return data

def display_next_step(result):
    route = route_of(result)

    if route == "ask_check":
        data = ask_check(context(), {})
        active_check = output_of(data)

        st.session_state.active_check = active_check

        if isinstance(active_check, dict):
            case = st.session_state.case_state.get("diagnostic_case", {})
            diagnosis = (
                case.get("session_state", {})
                if isinstance(case, dict)
                else {}
            )

            if isinstance(diagnosis, dict):
                st.session_state.latest_diagnosis = diagnosis

            st.subheader("Next recommended check")

            check = active_check.get("check")
            if check:
                st.markdown(f"**{check}**")

            reason = active_check.get("reason")
            if reason:
                st.caption(reason)

            evidence = active_check.get("evidence", [])
            if evidence:
                with st.expander("Why this check was selected"):
                    for ref in evidence:
                        if isinstance(ref, dict):
                            citation = ref.get(
                                "citation", "Source not specified"
                            )
                            text = ref.get("text", "")
                            st.caption(citation)
                            if text:
                                st.write(text)
                        else:
                            st.write(str(ref))

            safety = active_check.get("safety", {})
            if isinstance(safety, dict):
                if safety.get("blocked"):
                    st.error(
                        safety.get("message")
                        or "This check is blocked pending verified safety controls."
                    )
                elif safety.get("message"):
                    st.info(safety["message"])

    elif route == "close_out":
        st.subheader("Case close-out")
        st.info(
            "The diagnostic cause has been confirmed. "
            "Complete the close-out details below to record the confirmed work order."
        )

    elif route == "more_evidence":
        st.subheader("Additional evidence needed")
        data = output_of(more_evidence(context(), {}))
        if isinstance(data, dict):
            message = data.get("message") or data.get("status")
            if message:
                st.write(message)
        elif data:
            st.write(data)

    elif route == "case_error":
        st.error("The case could not be initialized. Review the case status.")


def display_candidate_bands(diagnosis):
    """Render technician-facing candidate causes grouped by confidence band."""
    if not isinstance(diagnosis, dict):
        return

    candidates = diagnosis.get("candidate_causes", [])
    if not candidates:
        return

    labels = {
        "likely": "Likely",
        "probable": "Probable",
        "unlikely": "Unlikely",
    }

    st.markdown("### Candidate causes")
    st.caption(
        "Evidence-based prioritization, not probability estimates. "
        "Technician judgment and applicable safety procedures remain authoritative."
    )

    for band in ("likely", "probable", "unlikely"):
        items = [
            candidate
            for candidate in candidates
            if str(candidate.get("confidence_band", "unlikely")).lower() == band
        ]

        if not items:
            continue

        st.markdown(f"**{labels[band]}**")

        for candidate in items:
            cause = candidate.get("cause", "Unspecified cause")

            with st.container(border=True):
                st.markdown(f"**{cause}**")

                evidence = candidate.get("evidence", [])
                if evidence:
                    with st.expander("Why this is listed"):
                        for ref in evidence:
                            if isinstance(ref, dict):
                                citation = ref.get(
                                    "citation", "Source not specified"
                                )
                                text = ref.get("text", "")
                                st.caption(citation)
                                if text:
                                    st.write(text)
                            else:
                                st.write(str(ref))

                check = candidate.get("next_check")
                if check:
                    st.caption(f"Next useful check: {check}")


st.subheader("1. Start a case")
uploaded_image = st.file_uploader(
    "Optional alarm-screen or machine-nameplate image",
    type=["png", "jpg", "jpeg", "webp"],
    help="The image is used only to extract visible details, not to diagnose a fault.",
)

with st.form("new_case_form"):
    alarm_number = st.text_input(
        "Alarm number or code",
        placeholder="e.g. 123",
        key="new_case_alarm_number",
    )
    query = st.text_input(
        "Machine / symptom details",
        placeholder="Machine model, symptom, and relevant context",
        key="new_case_query",
    )
    start_case = st.form_submit_button("Investigate", type="primary")

if start_case:
    if not alarm_number.strip() and not query.strip() and uploaded_image is None:
        st.error("Enter an alarm code or symptom description, or upload an image.")
    else:
        st.session_state.case_state = {}
        st.session_state.active_check = None
        try:
            extracted = {}
            if uploaded_image is not None:
                with st.spinner("Extracting visible details from the image..."):
                    extracted = extract_uploaded_image(uploaded_image)
                st.subheader("Image extraction — confirm before investigation")

                extraction_rows = [
                    ("Machine model", extracted.get("machine_model") or "Not detected"),
                    ("Control generation", extracted.get("control_generation") or "Not detected"),
                    ("Alarm code", extracted.get("alarm_code") or "Not detected"),
                    ("Alarm text", extracted.get("alarm_text") or "Not detected"),
                    ("Machine state", extracted.get("machine_state") or "Not detected"),
                    (
                        "Confidence",
                        f"{float(extracted.get('confidence', 0)) * 100:.0f}%"
                        if extracted.get("confidence") is not None
                        else "Not reported",
                    ),
                    (
                        "Missing fields",
                        ", ".join(extracted.get("missing_fields") or [])
                        or "None",
                    ),
                ]

                table_rows = [
                    "| Extracted field | Value |",
                    "|---|---|",
                ]
                table_rows.extend(
                    f"| **{label}** | {value} |"
                    for label, value in extraction_rows
                )
                st.markdown("\n".join(table_rows))
                st.caption(
                    "Check these extracted fields against the image. "
                    "Image extraction does not diagnose the fault."
                )

            final_alarm = alarm_number.strip() or str(extracted.get("alarm_code") or "")
            final_query = query.strip()
            extracted_context = " ".join(
                str(extracted.get(key) or "")
                for key in ("machine_model", "control_generation", "alarm_text", "machine_state")
            ).strip()
            if extracted_context:
                final_query = (final_query + " " + extracted_context).strip()

            if not final_alarm and not final_query:
                st.error("No usable details were provided or extracted. Enter details manually.")
                st.stop()

            with st.spinner("Retrieving relevant diagnostic evidence..."):
                result = new_case(
                    context(),
                    {
                        "alarm_number": final_alarm,
                        "query": final_query,
                        "machine_model": str(extracted.get("machine_model") or ""),
                    },
                )
            st.subheader("Investigation")

            data = result.get("diagnosis", {}) if isinstance(result, dict) else {}

            if isinstance(data, dict):
                st.session_state.latest_diagnosis = data

            display_next_step(result)
        except Exception as exc:
            st.error(f"Case initialization failed: {exc}")

case = st.session_state.case_state.get("diagnostic_case")
if case:
    main_col, side_col = st.columns([2.2, 1], gap="large")

    with main_col:
        st.subheader("Investigation")

        active_check = st.session_state.active_check or {}
        check_text = (
            active_check.get("check")
            if isinstance(active_check, dict)
            else None
        )

        if check_text:
            st.markdown(f"### Current check")
            st.markdown(f"**{check_text}**")

            safety = active_check.get("safety", {})
            if isinstance(safety, dict):
                st.info(
                    safety.get("message")
                    or "Verify applicable safety requirements before performing any check."
                )

                demo = safety.get("demo_checklist")
                if (
                    isinstance(demo, dict)
                    and demo.get("fixture_type") == "synthetic_demo"
                ):
                    st.warning(
                        "PROTOTYPE DEMO ONLY — this illustrative checklist is fabricated, "
                        "not verified against an approved machine-specific procedure, "
                        "and must not be used to authorize work."
                    )
                    st.caption(
                        f"Demo fixture: {demo.get('title', 'Illustrative checklist')}"
                    )
                    st.write(
                        demo.get(
                            "notice",
                            "Synthetic data; not an approved procedure.",
                        )
                    )
                    for item in demo.get("items", []):
                        st.markdown(
                            f"- **{item.get('label', 'Unspecified item')}**"
                        )
                        st.caption(
                            f"Status: {item.get('status', 'requires review')}"
                        )

                    st.error(
                        "Safety clearance unavailable. The real checklist remains "
                        "missing; the action is still blocked pending the applicable "
                        "approved procedure."
                    )
        else:
            st.caption("No active check is currently available.")

        with st.form("check_result_form"):
            observation = st.text_area(
                "Observed result",
                placeholder=(
                    "Record what was actually observed. "
                    "Do not guess or infer a result."
                ),
            )
            submit_observation = st.form_submit_button("Record result")

        if submit_observation:
            if not observation.strip():
                st.error("Enter the observed result before submitting.")
            else:
                try:
                    result = check_result(
                        context(),
                        {"observation": observation.strip()},
                    )
                    result_data = output_of(result)
                    diagnosis = (
                        result_data.get("diagnosis", {})
                        if isinstance(result_data, dict)
                        else {}
                    )
                    if diagnosis:
                        st.session_state.latest_diagnosis = diagnosis
                        st.session_state.active_check = diagnosis.get("next_check") or {}

                    # Refresh the page so the newly selected check replaces
                    # the previous check instead of being rendered below it.
                    st.rerun()
                except Exception as exc:
                    st.error(f"Could not record the result: {exc}")

        st.divider()

        with st.expander("Evidence and reasoning", expanded=False):
            try:
                explanation_result = explain(context(), {})

                if isinstance(explanation_result, dict):
                    confirmed = explanation_result.get("confirmed_cause")
                    candidates = explanation_result.get("candidates", [])
                    observations = explanation_result.get("observations", [])
                    next_check = explanation_result.get("next_check")

                    if confirmed:
                        st.markdown(f"**Confirmed cause:** {confirmed}")

                    for candidate in candidates:
                        cause = candidate.get(
                            "cause", "Unspecified candidate"
                        )
                        status = candidate.get("status", "possible")
                        band = candidate.get("confidence_band", "unknown")

                        st.markdown(
                            f"**{cause}** — `{band}` / `{status}`"
                        )

                        evidence_for = candidate.get("evidence_for", [])
                        if evidence_for:
                            st.markdown("**Source evidence**")
                            for item in evidence_for:
                                text = item.get("text", "").strip()
                                citation = item.get("citation", "").strip()

                                if text and citation:
                                    st.markdown(
                                        f"- {text}  \n"
                                        f"  *Source: {citation}*"
                                    )
                                elif text:
                                    st.markdown(f"- {text}")

                    if observations:
                        st.markdown("**Recorded observations**")
                        for observation in observations:
                            st.markdown(f"- {observation}")

                    if next_check:
                        st.markdown(f"**Next check:** {next_check}")
                    elif confirmed:
                        st.caption(
                            "No further diagnostic check is required; "
                            "the cause is confirmed."
                        )
                else:
                    st.write(explanation_result)

            except Exception as exc:
                st.warning(
                    f"Evidence and reasoning could not be displayed: {exc}"
                )

        st.divider()
        st.subheader("Stop or close the case")
        st.caption(
            "Use close-out when work must stop, the case needs escalation, "
            "or the investigation should end without further checks."
        )

        case = st.session_state.case_state.get("diagnostic_case", {})
        diagnosis = (
            case.get("session_state", {})
            if isinstance(case, dict)
            else {}
        )
        if not isinstance(diagnosis, dict):
            diagnosis = st.session_state.get("latest_diagnosis", {})

        confirmed_cause = (
            diagnosis.get("confirmed_cause")
            if isinstance(diagnosis, dict)
            else None
        )

        # Day 7.4 diagnostic visibility: show the authoritative close-out state.
        if confirmed_cause:
            st.success(f"Confirmed cause: {confirmed_cause}")

        if confirmed_cause:
            case = st.session_state.case_state.get("diagnostic_case", {})
            default_machine = str(case.get("machine_model", "") or "VF-2")
            default_symptom = str(
                case.get("query", "")
                or f"Alarm {case.get('alarm_number', '')}"
            )

            close_machine = st.text_input(
                "Machine model",
                value=default_machine,
                key="closeout_machine_model",
            )

            close_symptom = st.text_input(
                "Symptom / alarm",
                value=default_symptom,
                key="closeout_symptom",
            )

            close_action = st.text_area(
                "Action taken / confirmation",
                value=(
                    f"Demo / simulated diagnostic confirmation: "
                    f"{confirmed_cause}."
                ),
                key="closeout_action_taken",
            )

            if st.button("Record confirmed work order"):
                try:
                    result = close_out(
                        context(),
                        {
                            "machine_model": close_machine,
                            "symptom": close_symptom,
                            "action_taken": close_action,
                        },
                    )

                    if isinstance(result, dict):
                        if result.get("status") == "confirmed":
                            st.success(
                                "Confirmed cause recorded successfully."
                            )
                            if result.get("confirmed_cause"):
                                st.write(
                                    f"**Confirmed cause:** "
                                    f"{result['confirmed_cause']}"
                                )
                            if result.get("work_order_id"):
                                st.write(
                                    f"**Work-order ID:** "
                                    f"{result['work_order_id']}"
                                )
                        else:
                            st.warning(
                                result.get("stop_reason")
                                or result.get("status")
                                or "Close-out was not recorded."
                            )
                    else:
                        st.write(result)

                except Exception as exc:
                    st.error(f"Could not record the confirmed work order: {exc}")

        else:
            if st.button("Stop investigation and close out"):
                try:
                    result = close_out(context(), {})
                    st.success("Investigation closed.")
                    if isinstance(result, dict):
                        message = (
                            result.get("message")
                            or result.get("status")
                        )
                        if message:
                            st.write(message)
                except Exception as exc:
                    st.error(f"Could not close the case: {exc}")

    with side_col:
        with st.container(border=True, height=650):
            diagnosis = st.session_state.get("latest_diagnosis", {})

            if not diagnosis:
                diagnosis = (
                    result.get("diagnosis", {})
                    if isinstance(result, dict)
                    else {}
                )

            display_candidate_bands(diagnosis)

st.divider()
st.caption(
    "Diagnostic output depends on retrieved evidence and recorded observations. "
    "Missing evidence is not proof that a component is healthy or faulty."
)
