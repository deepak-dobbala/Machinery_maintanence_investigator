from pathlib import Path
import sys
from types import SimpleNamespace

import streamlit as st

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
        st.session_state.active_check = output_of(data)
        st.subheader("Next recommended check")
        st.json(st.session_state.active_check)
    elif route == "close_out":
        st.subheader("Case close-out")
        show_result(close_out(context(), {}))
    elif route == "more_evidence":
        st.subheader("Additional evidence needed")
        show_result(more_evidence(context(), {}))
    elif route == "case_error":
        st.error("The case could not be initialized. Review the result above.")

with st.sidebar:
    st.header("Case controls")
    if st.button("Clear current case", use_container_width=True):
        st.session_state.case_state = {}
        st.session_state.last_output = None
        st.session_state.active_check = None
        st.rerun()

st.subheader("1. Start a case")
with st.form("new_case_form"):
    alarm_number = st.text_input("Alarm number or code", placeholder="e.g. 123")
    query = st.text_input(
        "Machine / symptom details",
        placeholder="Machine model, symptom, and relevant context",
    )
    start_case = st.form_submit_button("Investigate", type="primary")

if start_case:
    if not alarm_number.strip() and not query.strip():
        st.error("Enter an alarm code or symptom description.")
    else:
        st.session_state.case_state = {}
        st.session_state.active_check = None
        try:
            with st.spinner("Retrieving relevant diagnostic evidence..."):
                result = new_case(
                    context(),
                    {
                        "alarm_number": alarm_number.strip(),
                        "query": query.strip(),
                    },
                )
            st.subheader("Case initialization")
            show_result(result)
            display_next_step(result)
        except Exception as exc:
            st.error(f"Case initialization failed: {exc}")

case = st.session_state.case_state.get("diagnostic_case")
if case:
    st.divider()
    st.subheader("2. Record a check result")
    active_check = st.session_state.active_check or {}
    check_text = active_check.get("check") if isinstance(active_check, dict) else None
    if check_text:
        st.markdown(f"**Current check:** {check_text}")
        safety = active_check.get("safety", {})
        if isinstance(safety, dict):
            st.info(
                safety.get("message")
                or "Verify applicable safety requirements before performing any check."
            )

            demo = safety.get("demo_checklist")
            if isinstance(demo, dict) and demo.get("fixture_type") == "synthetic_demo":
                st.warning(
                    "PROTOTYPE DEMO ONLY — this illustrative checklist is fabricated, "
                    "not verified against an approved machine-specific procedure, "
                    "and must not be used to authorize work."
                )
                st.caption(f"Demo fixture: {demo.get('title', 'Illustrative checklist')}")
                st.write(demo.get("notice", "Synthetic data; not an approved procedure."))
                for item in demo.get("items", []):
                    st.markdown(f"- **{item.get('label', 'Unspecified item')}**")
                    st.caption(f"Status: {item.get('status', 'requires review')}")

                st.error(
                    "Safety clearance unavailable. The real checklist remains missing; "
                    "the action is still blocked pending the applicable approved procedure."
                )
    else:
        st.caption("No active check is currently available.")

    with st.form("check_result_form"):
        observation = st.text_area(
            "Observed result",
            placeholder="Record what was actually observed. Do not guess or infer a result.",
        )
        submit_observation = st.form_submit_button("Record result")
    if submit_observation:
        if not observation.strip():
            st.error("Enter the observed result before submitting.")
        else:
            try:
                result = check_result(context(), {"observation": observation.strip()})
                st.subheader("Recorded result")
                show_result(result)
                display_next_step(result)
            except Exception as exc:
                st.error(f"Could not record the result: {exc}")

    st.divider()
    st.subheader("3. Explain the current assessment")
    if st.button("Show evidence and reasoning"):
        try:
            show_result(explain(context(), {}))
        except Exception as exc:
            st.error(f"Could not generate the explanation: {exc}")

    st.divider()
    st.subheader("4. Stop or close the case")
    st.caption(
        "Use close-out when work must stop, the case needs escalation, "
        "or the investigation should end without further checks."
    )
    if st.button("Stop investigation and close out"):
        try:
            show_result(close_out(context(), {}))
            st.session_state.active_check = None
        except Exception as exc:
            st.error(f"Could not close out the case: {exc}")
else:
    st.caption("Start an investigation above to see the case workflow.")

st.divider()
st.caption(
    "Diagnostic output depends on retrieved evidence and recorded observations. "
    "Missing evidence is not proof that a component is healthy or faulty."
)
