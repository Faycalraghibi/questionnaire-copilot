"""Questionnaires page: upload Excel/CSV, inspect detected layout, and draft all."""

from __future__ import annotations

import httpx
import streamlit as st

from ui.client import api_get, api_post_file, api_post_json

st.set_page_config(page_title="Questionnaires", layout="wide")
st.title("Questionnaires")

with st.expander("Upload a questionnaire (Excel or CSV)", expanded=False):
    with st.form("upload_qn_form"):
        uploaded = st.file_uploader("Questionnaire file", type=["xlsx", "csv"])
        qid_prefix = st.text_input("Optional QID prefix (e.g. B)", value="")
        submitted = st.form_submit_button("Upload and detect columns")

    if submitted:
        if not uploaded:
            st.error("Choose an .xlsx or .csv file first.")
        else:
            try:
                res = api_post_file(
                    "/questionnaires/upload",
                    uploaded.name,
                    uploaded.getvalue(),
                    {"qid_prefix": qid_prefix.strip()},
                )
                st.success(f"Imported {res['name']} ({res['question_count']} questions).")
                st.json(res["sheet_map"])
            except httpx.HTTPError as exc:
                st.error(f"Upload failed: {exc}")

try:
    qns = api_get("/questionnaires").get("questionnaires", [])
except httpx.HTTPError as exc:
    st.error(f"Could not load questionnaires: {exc}")
    st.stop()

if not qns:
    st.info("No questionnaires imported yet.")
    st.stop()

for qn in qns:
    with st.container(border=True):
        c1, c2 = st.columns([3, 1])
        c1.subheader(f"{qn['name']} (ID {qn['id']})")
        c1.caption(f"{qn['question_count']} questions | File: {qn['file_path']}")
        if c2.button("Draft all", key=f"draft_{qn['id']}", type="primary"):
            progress = st.progress(10, text="Drafting answers from current policies...")
            try:
                summary = api_post_json(f"/questionnaires/{qn['id']}/draft", {})
                progress.progress(100, text="Drafting complete")
                st.success(
                    f"Run {summary['run_id']}: {summary['drafted']} drafted "
                    f"({summary['library_reused']} from library), "
                    f"{summary['needs_input']} needs input."
                )
            except httpx.HTTPError as exc:
                progress.empty()
                st.error(f"Drafting failed: {exc}")
        with st.expander("Detected sheets and columns"):
            st.json(qn["sheet_map"])
