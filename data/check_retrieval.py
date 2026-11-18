"""Phase 2 acceptance script: print top 3 retrieved chunks for 5 sample questions.

Usage: uv run python -m data.check_retrieval
"""

from __future__ import annotations

from qc.db import connect
from qc.embed import E5Embedder
from qc.retrieve import retrieve

SAMPLE_QIDS = ["A-003", "A-009", "A-012", "A-019", "A-044"]


def main() -> None:
    emb = E5Embedder()
    with connect() as conn:
        rows = dict(
            conn.execute(
                "SELECT q.qid, q.text FROM questions q "
                "JOIN questionnaires qn ON q.questionnaire_id = qn.id "
                "WHERE qn.name = 'acme_vendor_security_2026' AND q.qid = ANY(%s)",
                (SAMPLE_QIDS,),
            ).fetchall()
        )
        for qid in SAMPLE_QIDS:
            question = rows[qid]
            res = retrieve(conn, question, embedder=emb, top_k=3)
            print(f"\n{qid}: {question}")
            if qid == "A-019":
                best = res.chunks[0].score if res.chunks else 0.0
                print(f"  [unanswerable] best_score={best:.4f}")
            for rank, hit in enumerate(res.chunks, start=1):
                print(
                    f"  {rank}. {hit.policy_id} v{hit.version} | {hit.section} "
                    f"(score={hit.score:.4f}, vec={hit.vec_score:.4f}, ft={hit.ft_score:.4f})"
                )


if __name__ == "__main__":
    main()
