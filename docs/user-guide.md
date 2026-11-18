# Reviewer User Guide

This guide explains how a security or compliance reviewer uses Questionnaire Copilot to answer customer security questionnaires in under an hour.

## 1. Check the Policy Library

Open **Library** in the left sidebar.

- Every policy shows its **Version** (`v1`, `v2`, `v3`) and whether it is **Current** (`Yes` or `No`).
- Only **Current** policy versions are used when drafting new answers. Older versions stay in the library for audit history.
- To add a new policy or update an existing one, open **Upload a new policy version**, choose the PDF, DOCX, or Markdown file, enter the Policy ID, Title, Version, and Effective date, and click **Upload and ingest**.
- If a yellow banner says **"X approved answers rely on a policy that changed"**, open **Answer Library** to review those answers before reusing them.

## 2. Import and Draft a Questionnaire

Open **Questionnaires** in the left sidebar.

1. Expand **Upload a questionnaire (Excel or CSV)** and upload the customer's `.xlsx` or `.csv` file.
2. Check the detected sheets and column mapping (Question, Answer, and Explanation columns).
3. Click **Draft all** next to the questionnaire. Each question is either:
   - Reused from an approved **Answer Library** entry,
   - Drafted from current policy passages with exact citations, or
   - Marked **Needs input** when no current policy covers the question.

## 3. Review Drafts

Open **Review** in the left sidebar.

1. Select your name in **Reviewer** and pick the questionnaire.
2. Use the **Status** and **Confidence** filters to focus on `needs_input` or `low` confidence items first.
3. Click a question in **Inspect question** to see the drafted answer alongside the exact cited policy passages on the right:
   - **Approve**: saves the answer and its citations to the Answer Library for future questionnaires.
   - **Edit & Approve**: adjust the **Answer** or **Explanation** text, then save to the Answer Library.
   - **Reject**: marks the draft rejected without saving it to the Answer Library.

## 4. Handle Stale Answers When Policies Change

Open **Answer Library** in the left sidebar.

- Entries marked **Policy changed** are never reused automatically until reviewed.
- Under **Re-approve stale answers**, compare the previous approved answer on the left against the updated policy section on the right, edit if needed, and click **Re-approve against current policy**.

## 5. Export the Completed Questionnaire

Open **Export** in the left sidebar, select the questionnaire, click **Prepare export**, and click **Download**. The exported file keeps the customer's original layout, sheets, and formatting, fills in the answer and explanation columns, and appends **Source** and **Status** columns.
