"""Review page: filter drafts, inspect cited passages, and approve/edit/reject."""

from __future__ import annotations

import httpx
import streamlit as st

from ui.client import api_get, api_post_json

st.set_page_config(page_title="Review", layout="wide")
st.title("Review Drafts")

try:
    qns = api_get("/questionnaires").get("questionnaires", [])
    reviewers = api_get("/config/reviewers").get("reviewers", ["Reviewer"])
except httpx.HTTPError as exc:
    st.error(f"API unavailable: {exc}")
    st.stop()

if not qns:
    st.info("No questionnaires found. Upload or seed one first.")
    st.stop()

top_c1, top_c2, top_c3, top_c4 = st.columns([2, 1, 1, 1])
qn_options = {f"{q['name']} (ID {q['id']})": q["id"] for q in qns}
selected_label = top_c1.selectbox("Questionnaire", list(qn_options))
selected_qn_id = qn_options[selected_label]
reviewer = top_c2.selectbox("Reviewer", reviewers)
status_filter = top_c3.multiselect(
    "Status",
    ["drafted", "needs_input", "approved", "edited", "rejected", "undrafted"],
    default=[],
)
conf_filter = top_c4.multiselect("Confidence", ["high", "medium", "low"], default=[])

items = api_get(f"/questionnaires/{selected_qn_id}/drafts").get("items", [])
filtered = [
    it
    for it in items
    if (not status_filter or it["status"] in status_filter)
    and (not conf_filter or it["confidence"] in conf_filter)
]

if not filtered:
    st.info("No questions match the selected filters.")
    st.stop()

left, right = st.columns([1.3, 1.0])

with left:
    table_rows = [
        {
            "QID": it["qid"],
            "Question": it["text"][:80] + ("..." if len(it["text"]) > 80 else ""),
            "Short Answer": it["short_answer"] or "-",
            "Status": it["status"],
            "Confidence": it["confidence"] or "-",
            "Source": it["source"] or "-",
        }
        for it in filtered
    ]
    st.dataframe(table_rows, use_container_width=True, hide_index=True)

with right:
    qid_choices = [f"{it['qid']} - {it['status']}" for it in filtered]
    picked = st.selectbox("Inspect question", qid_choices)
    item = filtered[qid_choices.index(picked)]

    st.subheader(item["qid"])
    st.write(item["text"])
    st.caption(
        f"Status: {item['status']} | Confidence: {item['confidence'] or '-'} "
        f"| Source: {item['source'] or '-'}"
    )

    if item["draft_id"] is None:
        st.info("Not drafted yet. Go to Questionnaires and click Draft all.")
    else:
        st.markdown("**Cited passages**")
        if not item["citations"]:
            st.caption("No citations.")
        for cite in item["citations"]:
            with st.container(border=True):
                st.markdown(f"**{cite['policy_id']} v{cite['version']} | {cite['section']}**")
                if cite.get("text"):
                    st.write(cite["text"])

        edited_ans = st.text_input(
            "Answer",
            value=item["short_answer"] or "",
            key=f"ans_{item['draft_id']}",
        )
        edited_exp = st.text_area(
            "Explanation",
            value=item["explanation"] or "",
            key=f"exp_{item['draft_id']}",
            height=110,
        )

        b1, b2, b3 = st.columns(3)
        if b1.button("Approve", key=f"app_{item['draft_id']}", type="primary"):
            api_post_json(
                f"/drafts/{item['draft_id']}/review",
                {"reviewer": reviewer, "action": "approve"},
            )
            st.rerun()
        if b2.button("Edit & Approve", key=f"edit_{item['draft_id']}"):
            api_post_json(
                f"/drafts/{item['draft_id']}/review",
                {
                    "reviewer": reviewer,
                    "action": "edit",
                    "final_answer": edited_ans,
                    "final_explanation": edited_exp,
                },
            )
            st.rerun()
        if b3.button("Reject", key=f"rej_{item['draft_id']}"):
            api_post_json(
                f"/drafts/{item['draft_id']}/review",
                {"reviewer": reviewer, "action": "reject"},
            )
            st.rerun()
