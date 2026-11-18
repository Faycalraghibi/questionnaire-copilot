"""Policy Library page: upload policies and inspect versions."""

from __future__ import annotations

import datetime as dt

import httpx
import streamlit as st

from ui.client import api_get, api_post_file

st.set_page_config(page_title="Policy Library", layout="wide")
st.title("Policy Library")

try:
    data = api_get("/policies")
except httpx.HTTPError as exc:
    st.error(f"Could not load policies: {exc}")
    st.stop()

stale_count = data.get("stale_count", 0)
if stale_count:
    st.warning(f"{stale_count} approved answers rely on a policy that changed")

with st.expander("Upload a new policy version", expanded=False):
    with st.form("upload_policy_form"):
        uploaded = st.file_uploader("Policy file", type=["pdf", "docx", "md"])
        c1, c2 = st.columns(2)
        policy_id = c1.text_input("Policy ID", placeholder="data-retention")
        title = c2.text_input("Title", placeholder="Data Retention Policy")
        c3, c4 = st.columns(2)
        version = c3.number_input("Version", min_value=1, step=1, value=1)
        effective_date = c4.date_input("Effective date", value=dt.date.today())
        submitted = st.form_submit_button("Upload and ingest")

    if submitted:
        if not uploaded or not policy_id.strip() or not title.strip():
            st.error("Provide a file, policy ID, and title.")
        else:
            try:
                res = api_post_file(
                    "/policies/upload",
                    uploaded.name,
                    uploaded.getvalue(),
                    {
                        "policy_id": policy_id.strip(),
                        "title": title.strip(),
                        "version": str(int(version)),
                        "effective_date": effective_date.isoformat(),
                    },
                )
                st.success(
                    f"Ingested {res['policy_id']} v{res['version']} "
                    f"({res['chunks_total']} chunks, {res['embedded']} embedded)."
                )
                st.rerun()
            except httpx.HTTPError as exc:
                st.error(f"Upload failed: {exc}")

policies = data.get("policies", [])
if not policies:
    st.info("No policies ingested yet. Run `make seed` or upload a policy above.")
else:
    rows = [
        {
            "Policy ID": p["policy_id"],
            "Title": p["title"],
            "Version": f"v{p['version']}",
            "Effective Date": p["effective_date"],
            "Current": "Yes" if p["is_current"] else "No",
            "Source": p["source_file"],
        }
        for p in policies
    ]
    st.dataframe(rows, use_container_width=True, hide_index=True)
