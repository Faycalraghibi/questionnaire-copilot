"""`make seed` loads the counts required by Phase 1 acceptance (needs the Docker database)."""

from data.seed import seed


def test_seed_counts(db_conn):
    counts = seed(db_conn)
    assert counts["policies"] == 11
    assert counts["versions"] == 14
    assert counts["current"] == 11
    assert counts["acme_vendor_security_2026"] == 60
    assert counts["globex_supplier_review"] == 40


def test_seed_current_versions(db_conn):
    seed(db_conn)
    rows = db_conn.execute(
        "SELECT policy_id, version FROM policy_versions WHERE NOT is_current ORDER BY policy_id"
    ).fetchall()
    assert rows == [("data-retention", 2), ("encryption-standard", 1), ("infosec-policy", 1)]


def test_seed_question_cells(db_conn):
    seed(db_conn)
    rows = dict(
        (r[0], r[1:])
        for r in db_conn.execute("SELECT qid, sheet, row, col_question, col_answer FROM questions")
    )
    assert rows["A-001"] == ("Vendor Security Assessment", 5, 3, 4)
    assert rows["A-060"] == ("Vendor Security Assessment", 64, 3, 4)
    assert rows["B-001"] == ("Security", 2, 2, 3)
    assert rows["B-026"] == ("Privacy", 2, 2, 3)
    assert rows["B-040"] == ("Privacy", 16, 2, 3)
