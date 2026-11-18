"""End-to-end FastAPI endpoint tests using StubLLM and FakeEmbedder."""

from __future__ import annotations

import io
from pathlib import Path

from fastapi.testclient import TestClient
from openpyxl import Workbook, load_workbook

from qc.api import app, get_db, get_embedder_dep, get_llm_dep
from qc.embed import FakeEmbedder
from qc.llm import StubLLM


def _make_sample_xlsx_bytes() -> bytes:
    wb = Workbook()
    ws = wb.active
    ws.title = "Security"
    ws.append(["ID", "Question", "Response", "Comments"])
    ws.append(["T-001", "Do you encrypt customer data at rest with AES-256?", None, None])
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def test_api_upload_draft_review_export(db_conn, tmp_path: Path, monkeypatch):
    monkeypatch.setenv("UPLOADS_DIR", str(tmp_path / "uploads"))
    monkeypatch.setenv("MIN_EVIDENCE", "0.1")
    from qc.config import get_settings

    get_settings.cache_clear()

    emb = FakeEmbedder()

    # StubLLM that cites the first chunk id present in the prompt so check_draft passes.
    class _DynamicStub(StubLLM):
        def structured(self, system, messages, schema, *, max_tokens=1500):
            import re

            prompt = messages[-1]["content"]
            m = re.search(r"\[chunk_id=(\d+)\]", prompt)
            cid = int(m.group(1)) if m else 1
            from qc.checks import Draft
            from qc.llm import LLMUsage

            return (
                Draft(
                    can_answer=True,
                    short_answer="yes",
                    answer_text=None,
                    explanation="AES-256 encryption at rest is enabled.",
                    citation_chunk_ids=[cid],
                    confidence="high",
                ),
                LLMUsage(100, 30, 0.0, 1, "stub"),
            )

    llm = _DynamicStub()

    # Use a connection wrapper that ignores commit() so db_conn rolls back cleanly.
    class _NoCommitConn:
        def __init__(self, inner):
            self._inner = inner

        def commit(self):
            pass

        def __getattr__(self, name):
            return getattr(self._inner, name)

    wrapped = _NoCommitConn(db_conn)
    app.dependency_overrides[get_db] = lambda: wrapped
    app.dependency_overrides[get_llm_dep] = lambda: llm
    app.dependency_overrides[get_embedder_dep] = lambda: emb

    try:
        client = TestClient(app)

        assert client.get("/health").json() == {"status": "ok"}

        policy_md = (
            b"---\npolicy_id: test-api-enc\ntitle: API Encryption\n"
            b"version: 1\neffective_date: 2026-01-01\n---\n\n"
            b"# API Encryption\n\n## Data at rest\n\n"
            b"Customer data is encrypted at rest using AES-256.\n"
        )
        r_pol = client.post(
            "/policies/upload",
            files={"file": ("enc.md", policy_md, "text/markdown")},
            data={
                "policy_id": "test-api-enc",
                "title": "API Encryption",
                "version": "1",
                "effective_date": "2026-01-01",
            },
        )
        assert r_pol.status_code == 200
        assert r_pol.json()["chunks_total"] == 1

        r_qn = client.post(
            "/questionnaires/upload",
            files={
                "file": (
                    "sample.xlsx",
                    _make_sample_xlsx_bytes(),
                    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                )
            },
        )
        assert r_qn.status_code == 200
        qn_id = r_qn.json()["id"]
        assert r_qn.json()["question_count"] == 1

        r_draft = client.post(f"/questionnaires/{qn_id}/draft")
        assert r_draft.status_code == 200
        assert r_draft.json()["drafted"] == 1

        r_list = client.get(f"/questionnaires/{qn_id}/drafts")
        assert r_list.status_code == 200
        item = r_list.json()["items"][0]
        assert item["status"] == "drafted"
        assert item["citations"][0]["text"]

        r_rev = client.post(
            f"/drafts/{item['draft_id']}/review",
            json={"reviewer": "Amira Haddad", "action": "approve"},
        )
        assert r_rev.status_code == 200
        assert r_rev.json()["status"] == "approved"
        assert r_rev.json()["library_id"] is not None

        r_lib = client.get("/library")
        assert r_lib.status_code == 200
        assert any(e["id"] == r_rev.json()["library_id"] for e in r_lib.json()["items"])

        r_exp = client.get(f"/questionnaires/{qn_id}/export")
        assert r_exp.status_code == 200
        wb = load_workbook(io.BytesIO(r_exp.content))
        ws = wb["Security"]
        assert [c.value for c in ws[1]] == [
            "ID",
            "Question",
            "Response",
            "Comments",
            "Source",
            "Status",
        ]
        assert ws.cell(2, 3).value == "Yes"
        assert ws.cell(2, 6).value == "approved"
        wb.close()
    finally:
        app.dependency_overrides.clear()
        get_settings.cache_clear()
        db_conn.rollback()
