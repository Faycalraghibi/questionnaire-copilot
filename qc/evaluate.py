"""Built-in end-to-end evaluation (`make eval`, spec section 9)."""

from __future__ import annotations

import datetime as dt
import time
import uuid
from dataclasses import dataclass
from pathlib import Path

import psycopg
import yaml

from data.seed import seed
from qc.config import get_settings
from qc.db import connect
from qc.draft import DraftOutcome, draft_question
from qc.embed import Embedder, get_embedder
from qc.ingest import ingest_policy
from qc.library import count_stale, review_draft
from qc.llm import LLM, get_llm

REPO_ROOT = Path(__file__).parent.parent
TRUTH_DIR = REPO_ROOT / "data" / "truth"
V4_PATH = REPO_ROOT / "data" / "policies_updates" / "data-retention-v4.md"
REPORT_PATH = REPO_ROOT / "evals" / "report.md"


@dataclass
class FailureItem:
    questionnaire: str
    qid: str
    expected: str
    got: str
    reason: str


def phrase_in(phrase: str, text: str) -> bool:
    """Case-insensitive match supporting `a | b` alternatives (decisions D11, D24)."""
    low = text.lower()
    return any(alt.strip().lower() in low for alt in phrase.split("|"))


def check_answer_correct(outcome: DraftOutcome, truth: dict) -> tuple[bool, str | None]:
    if outcome.status != "drafted":
        return False, f"status={outcome.status}"
    blob = " ".join(
        p for p in [outcome.short_answer, outcome.answer_text, outcome.explanation] if p
    )
    expected_short = str(truth.get("short_answer", "")).lower()
    if expected_short in ("yes", "no"):
        got_short = (outcome.short_answer or "").strip().lower()
        if got_short != expected_short:
            return False, f"short_answer={got_short!r} != {expected_short!r}"
    for kp in truth.get("key_phrases", []):
        if not phrase_in(kp, blob):
            return False, f"missing key phrase: {kp}"
    for fp in truth.get("forbidden_phrases", []):
        if phrase_in(fp, blob):
            return False, f"contains forbidden phrase: {fp}"
    return True, None


def check_citation_correct(outcome: DraftOutcome, truth: dict) -> tuple[bool, str | None]:
    truth_set = {
        (s["policy_id"], int(s["version"]), s["section"]) for s in truth.get("sources", [])
    }
    cited_set = {(c["policy_id"], int(c["version"]), c["section"]) for c in outcome.citations}
    if not cited_set:
        return False, "no citations"
    if not (cited_set & truth_set):
        return False, f"no truth source cited (got {sorted(cited_set)})"
    extra = cited_set - truth_set
    if extra:
        return False, f"extra citation outside truth: {sorted(extra)}"
    return True, None


def _current_versions(conn: psycopg.Connection) -> dict[str, int]:
    return {
        r[0]: int(r[1])
        for r in conn.execute(
            "SELECT policy_id, version FROM policy_versions WHERE is_current = TRUE"
        ).fetchall()
    }


def _evaluate_questionnaire(
    conn: psycopg.Connection,
    qn_name: str,
    truth_rows: list[dict],
    *,
    run_id: str,
    llm: LLM,
    embedder: Embedder,
    simulate_review: bool,
) -> tuple[dict, list[FailureItem]]:
    t0 = time.perf_counter()
    q_rows = conn.execute(
        "SELECT q.id, q.qid, q.text FROM questions q "
        "JOIN questionnaires qn ON q.questionnaire_id = qn.id "
        "WHERE qn.name = %s ORDER BY q.id",
        (qn_name,),
    ).fetchall()
    truth_by_qid = {t["qid"]: t for t in truth_rows}
    cur_vers = _current_versions(conn)

    ans_total = ans_correct = cite_correct = stale_cites = 0
    unans_total = needs_input_total = needs_input_true = 0
    edit_count = reuse_count = 0
    failures: list[FailureItem] = []

    for q_id, qid, q_text in q_rows:
        truth = truth_by_qid[qid]
        out = draft_question(
            conn,
            q_id,
            qid,
            q_text,
            run_id=run_id,
            llm=llm,
            embedder=embedder,
            persist=True,
        )
        if out.source == "library":
            reuse_count += 1
        if out.status == "needs_input":
            needs_input_total += 1

        if any(int(c["version"]) != cur_vers.get(c["policy_id"]) for c in out.citations):
            stale_cites += 1

        if truth["answerable"]:
            ans_total += 1
            ans_ok, ans_reason = check_answer_correct(out, truth)
            cite_ok, cite_reason = check_citation_correct(out, truth)
            if ans_ok:
                ans_correct += 1
            if cite_ok:
                cite_correct += 1
            if not (ans_ok and cite_ok):
                reasons = [r for r in [ans_reason, cite_reason] if r]
                failures.append(
                    FailureItem(
                        questionnaire=qn_name,
                        qid=qid,
                        expected=f"{truth['short_answer']} ({truth.get('key_phrases', [])})",
                        got=f"{out.status}: {out.answer_text or out.short_answer}",
                        reason="; ".join(reasons),
                    )
                )

            if simulate_review:
                draft_id = conn.execute(
                    "SELECT id FROM drafts WHERE question_id = %s AND run_id = %s "
                    "ORDER BY id DESC LIMIT 1",
                    (q_id, run_id),
                ).fetchone()[0]
                if ans_ok and cite_ok:
                    review_draft(
                        conn,
                        draft_id,
                        reviewer="EvalReviewer",
                        action="approve",
                        embedder=embedder,
                    )
                else:
                    edit_count += 1
                    truth_cites = [
                        {
                            "policy_id": s["policy_id"],
                            "version": int(s["version"]),
                            "section": s["section"],
                        }
                        for s in truth.get("sources", [])
                    ]
                    review_draft(
                        conn,
                        draft_id,
                        reviewer="EvalReviewer",
                        action="edit",
                        final_answer=truth["short_answer"],
                        final_explanation=truth["reference_answer"],
                        final_citations=truth_cites,
                        embedder=embedder,
                    )
        else:
            unans_total += 1
            if out.status == "needs_input":
                needs_input_true += 1
            else:
                failures.append(
                    FailureItem(
                        questionnaire=qn_name,
                        qid=qid,
                        expected="needs_input",
                        got=f"{out.status}: {out.short_answer}",
                        reason="unanswerable question was answered",
                    )
                )
                if simulate_review:
                    draft_id = conn.execute(
                        "SELECT id FROM drafts WHERE question_id = %s AND run_id = %s "
                        "ORDER BY id DESC LIMIT 1",
                        (q_id, run_id),
                    ).fetchone()[0]
                    review_draft(
                        conn,
                        draft_id,
                        reviewer="EvalReviewer",
                        action="reject",
                        embedder=embedder,
                    )

    wall_s = time.perf_counter() - t0
    cost_row = conn.execute(
        "SELECT COALESCE(SUM(cost_usd), 0), COALESCE(SUM(latency_ms), 0) "
        "FROM run_steps WHERE run_id = %s",
        (run_id,),
    ).fetchone()
    total_cost = float(cost_row[0]) if cost_row else 0.0

    metrics = {
        "total": len(q_rows),
        "answer_correctness": (ans_correct / ans_total) if ans_total else 0.0,
        "citation_correctness": (cite_correct / ans_total) if ans_total else 0.0,
        "stale_citations": stale_cites,
        "needs_input_recall": (needs_input_true / unans_total) if unans_total else 0.0,
        "needs_input_precision": (
            (needs_input_true / needs_input_total) if needs_input_total else 1.0
        ),
        "edit_rate": (edit_count / ans_total) if ans_total else 0.0,
        "reuse_rate": (reuse_count / len(q_rows)) if q_rows else 0.0,
        "cost_usd": total_cost,
        "time_s": wall_s,
    }
    return metrics, failures


def _format_report(
    *,
    provider: str,
    model: str,
    metrics_a: dict,
    metrics_b: dict,
    staleness: dict,
    failures: list[FailureItem],
) -> str:
    settings = get_settings()
    lines = [
        "# Evaluation Report",
        "",
        f"- Date: {dt.date.today().isoformat()}",
        f"- Provider / Model: `{provider}` / `{model}`",
        f"- Thresholds (calibrated on A): `MIN_EVIDENCE={settings.min_evidence}`, "
        f"`REUSE_THRESHOLD={settings.reuse_threshold}`",
        "",
        "## Questionnaire A (calibration set, 60 questions)",
        "",
        "| Metric | Value | Target |",
        "| --- | --- | --- |",
        f"| Answer correctness | {metrics_a['answer_correctness']:.1%} | 90%+ |",
        f"| Citation correctness | {metrics_a['citation_correctness']:.1%} | 90%+ |",
        f"| Stale-version citations | {metrics_a['stale_citations']} | 0 |",
        f"| Needs-input recall | {metrics_a['needs_input_recall']:.1%} | 100% |",
        f"| Needs-input precision | {metrics_a['needs_input_precision']:.1%} | 85%+ |",
        f"| Edit rate | {metrics_a['edit_rate']:.1%} | report |",
        f"| Cost / Time | ${metrics_a['cost_usd']:.4f} / {metrics_a['time_s']:.1f}s | report |",
        "",
        "## Questionnaire B (held-out, 40 questions)",
        "",
        "| Metric | Value | Target |",
        "| --- | --- | --- |",
        f"| Answer correctness | {metrics_b['answer_correctness']:.1%} | 90%+ |",
        f"| Citation correctness | {metrics_b['citation_correctness']:.1%} | 90%+ |",
        f"| Stale-version citations | {metrics_b['stale_citations']} | 0 |",
        f"| Needs-input recall | {metrics_b['needs_input_recall']:.1%} | 100% |",
        f"| Needs-input precision | {metrics_b['needs_input_precision']:.1%} | 85%+ |",
        f"| Reuse rate | {metrics_b['reuse_rate']:.1%} | report |",
        f"| Cost / Time | ${metrics_b['cost_usd']:.4f} / {metrics_b['time_s']:.1f}s | report |",
        "",
        "## Staleness Check (data-retention v4)",
        "",
        f"- Expected stale library entries: {staleness['expected']}",
        f"- Flagged stale library entries: {staleness['actual']}",
        f"- Staleness detection: {staleness['rate']:.1%} (target 100%)",
        "",
        "## Failures",
        "",
    ]
    if not failures:
        lines.append("None.")
    else:
        lines.extend(
            [
                "| Questionnaire | QID | Expected | Got | Reason |",
                "| --- | --- | --- | --- | --- |",
            ]
        )
        for f in failures:
            lines.append(f"| {f.questionnaire} | {f.qid} | {f.expected} | {f.got} | {f.reason} |")
    lines.append("")
    return "\n".join(lines)


def run_evaluation(
    conn: psycopg.Connection,
    *,
    llm: LLM | None = None,
    embedder: Embedder | None = None,
    report_path: Path = REPORT_PATH,
) -> dict:
    emb = embedder or get_embedder()
    model_client = llm or get_llm()

    seed(conn, embedder=emb)

    truth_a = yaml.safe_load(
        (TRUTH_DIR / "acme_vendor_security_2026.yaml").read_text(encoding="utf-8")
    )
    truth_b = yaml.safe_load(
        (TRUTH_DIR / "globex_supplier_review.yaml").read_text(encoding="utf-8")
    )

    run_id_a = f"eval-a-{uuid.uuid4().hex[:8]}"
    metrics_a, fail_a = _evaluate_questionnaire(
        conn,
        "acme_vendor_security_2026",
        truth_a,
        run_id=run_id_a,
        llm=model_client,
        embedder=emb,
        simulate_review=True,
    )
    conn.commit()

    run_id_b = f"eval-b-{uuid.uuid4().hex[:8]}"
    metrics_b, fail_b = _evaluate_questionnaire(
        conn,
        "globex_supplier_review",
        truth_b,
        run_id=run_id_b,
        llm=model_client,
        embedder=emb,
        simulate_review=False,
    )
    conn.commit()

    # Step 5: ingest data-retention v4 and verify staleness detection.
    expected_stale = conn.execute(
        """
        SELECT count(*)
        FROM answer_library
        WHERE EXISTS (
            SELECT 1 FROM jsonb_array_elements(policy_versions) AS pv
            WHERE pv->>'policy_id' = 'data-retention' AND (pv->>'version')::int < 4
        )
        """
    ).fetchone()[0]
    ingest_policy(conn, V4_PATH, embedder=emb)
    actual_stale = count_stale(conn)
    conn.commit()

    staleness = {
        "expected": int(expected_stale),
        "actual": int(actual_stale),
        "rate": (actual_stale / expected_stale) if expected_stale else 1.0,
    }

    settings = get_settings()
    prov = "stub" if type(model_client).__name__ == "StubLLM" else settings.llm_provider
    mdl = getattr(model_client, "model", settings.llm_model or "stub")
    report = _format_report(
        provider=prov,
        model=mdl,
        metrics_a=metrics_a,
        metrics_b=metrics_b,
        staleness=staleness,
        failures=fail_a + fail_b,
    )
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(report, encoding="utf-8")
    return {"a": metrics_a, "b": metrics_b, "staleness": staleness, "report_path": str(report_path)}


def main() -> None:
    with connect() as conn:
        res = run_evaluation(conn)
    print(f"Wrote {res['report_path']}")
    print(
        f"A correctness={res['a']['answer_correctness']:.1%}, "
        f"B correctness={res['b']['answer_correctness']:.1%}, "
        f"B reuse={res['b']['reuse_rate']:.1%}, "
        f"staleness={res['staleness']['rate']:.1%}"
    )


if __name__ == "__main__":
    main()
