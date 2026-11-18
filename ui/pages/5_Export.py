"""Export page: download the filled Excel or CSV questionnaire."""

from __future__ import annotations

import httpx
import streamlit as st

from ui.client import api_get, api_get_bytes

st.set_page_config(page_title="Export", layout="wide")
st.title("Export Questionnaire")

try:
    qns = api_get("/questionnaires").get("questionnaires", [])
except httpx.HTTPError as exc:
    st.error(f"Could not load questionnaires: {exc}")
    st.stop()

if not qns:
    st.info("No questionnaires available.")
    st.stop()

qn_options = {f"{q['name']} (ID {q['id']}, {q['question_count']} questions)": q["id"] for q in qns}
choice = st.selectbox("Select questionnaire", list(qn_options))
qn_id = qn_options[choice]

if st.button("Prepare export", type="primary"):
    try:
        content, filename = api_get_bytes(f"/questionnaires/{qn_id}/export")
        st.download_button(
            label=f"Download {filename}",
            data=content,
            file_name=filename,
        )
    except httpx.HTTPError as exc:
        st.error(f"Export failed: {exc}")
