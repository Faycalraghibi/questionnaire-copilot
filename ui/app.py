"""Questionnaire Copilot Streamlit entry point."""

from __future__ import annotations

import httpx
import streamlit as st

from ui.client import api_get

st.set_page_config(
    page_title="Questionnaire Copilot",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.title("Questionnaire Copilot")
st.caption(
    "Answer security questionnaires from your current policies, with a source for every answer."
)

try:
    pol_data = api_get("/policies")
    stale_count = pol_data.get("stale_count", 0)
    if stale_count:
        st.warning(f"{stale_count} approved answers rely on a policy that changed")
    qn_data = api_get("/questionnaires")
    lib_data = api_get("/library")

    c1, c2, c3 = st.columns(3)
    c1.metric("Policy versions", len(pol_data.get("policies", [])))
    c2.metric("Questionnaires", len(qn_data.get("questionnaires", [])))
    c3.metric("Approved answers", len(lib_data.get("items", [])))
except httpx.HTTPError as exc:
    st.error(f"API unavailable: {exc}")

st.markdown(
    """
### Workflow
1. **Library**: Upload policies (PDF, DOCX, Markdown) with version and effective date.
2. **Questionnaires**: Upload an Excel or CSV questionnaire, confirm detected columns, and run
   **Draft all**.
3. **Review**: Inspect drafted answers alongside their cited policy passages; approve, edit, or
   reject.
4. **Answer Library**: Reuse approved answers across questionnaires and re-approve stale answers
   when policies change.
5. **Export**: Download the filled Excel or CSV file in its original layout with Source and Status
   columns.
6. **Quality**: View the built-in evaluation report.
"""
)
