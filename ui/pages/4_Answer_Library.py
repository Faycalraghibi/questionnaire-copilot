"""Answer Library page: view approved answers and re-approve stale entries."""

from __future__ import annotations

import httpx
import streamlit as st

from ui.client import api_get, api_post_json

st.set_page_config(page_title="Answer Library", layout="wide")
st.title("Answer Library")

try:
    data = api_get("/library")
    reviewers = api_get("/config/reviewers").get("reviewers", ["Reviewer"])
except httpx.HTTPError as exc:
    st.error(f"Could not load answer library: {exc}")
    st.stop()

stale_count = data.get("stale_count", 0)
if stale_count:
    st.warning(f"{stale_count} approved answers rely on a policy that changed")

items = data.get("items", [])
if not items:
    st.info("No approved answers yet. Approve drafts on the Review page to populate the library.")
    st.stop()

reviewer = st.selectbox("Reviewer", reviewers)

rows = [
    {
        "ID": it["id"],
        "Question": it["question_text"][:80] + ("..." if len(it["question_text"]) > 80 else ""),
        "Answer": it["short_answer"] or "-",
        "Policy Versions": ", ".join(
            f"{pv['policy_id']} v{pv['version']}" for pv in it["policy_versions"]
        ),
        "Approved By": it["approved_by"],
        "Stale": "Policy changed" if it["stale"] else "Current",
    }
    for it in items
]
st.dataframe(rows, use_container_width=True, hide_index=True)

stale_items = [it for it in items if it["stale"]]
if stale_items:
    st.subheader("Re-approve stale answers")
    for it in stale_items:
        with st.container(border=True):
            st.markdown(f"**#{it['id']}: {it['question_text']}**")
            left, right = st.columns(2)
            with left:
                st.caption("Previous approved answer")
                new_ans = st.text_input(
                    "Answer",
                    value=it["short_answer"] or "",
                    key=f"lib_ans_{it['id']}",
                )
                new_exp = st.text_area(
                    "Explanation",
                    value=it["explanation"] or "",
                    key=f"lib_exp_{it['id']}",
                )
            with right:
                st.caption("Current policy section(s)")
                for p in it.get("current_passages", []):
                    st.markdown(f"**{p['policy_id']} v{p['version']} | {p['section']}**")
                    st.write(p["text"])
            if st.button(
                "Re-approve against current policy", key=f"reapp_{it['id']}", type="primary"
            ):
                api_post_json(
                    f"/library/{it['id']}/reapprove",
                    {
                        "reviewer": reviewer,
                        "short_answer": new_ans,
                        "explanation": new_exp,
                    },
                )
                st.rerun()
