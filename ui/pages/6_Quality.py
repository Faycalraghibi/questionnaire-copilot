"""Quality page: render the latest evaluation report (evals/report.md)."""

from __future__ import annotations

import httpx
import streamlit as st

from ui.client import api_get

st.set_page_config(page_title="Quality", layout="wide")
st.title("Evaluation Quality")

try:
    data = api_get("/eval/report")
except httpx.HTTPError as exc:
    st.error(f"Could not load evaluation report: {exc}")
    st.stop()

if not data.get("exists"):
    st.info("No evaluation report yet. Run `make eval` (Phase 7) to generate `evals/report.md`.")
else:
    st.markdown(data["content"])
