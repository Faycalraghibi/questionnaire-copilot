"""`make seed`: generate the synthetic files, migrate, reset and load the database.

Phase 1 scope (decision D1): registers policies and versions from front matter (Markdown) and the
manifest (PDF, DOCX), and loads questions using the generator's known layouts. Phase 2 adds
ingestion into chunks; Phase 3 replaces the known layouts with header detection.

Usage: uv run python -m data.seed
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass
from pathlib import Path

import psycopg
import yaml
from openpyxl import load_workbook
from psycopg.types.json import Jsonb

from data.make_questionnaires import LAYOUTS, make_all
from data.render import render_all
from qc.db import connect, migrate, reset
from qc.markdown import split_front_matter

DATA = Path(__file__).parent
REPO = DATA.parent
POLICY_DIR = DATA / "policies"
MIN_QUESTION_CHARS = 15  # spec 7.2


@dataclass(frozen=True)
class PolicyFile:
    policy_id: str
    title: str
    version: int
    effective_date: dt.date
    path: Path


def discover_policies(policy_dir: Path = POLICY_DIR) -> list[PolicyFile]:
    """Markdown files carry front matter; PDF and DOCX files are described by manifest.yaml."""
    found = []
    for path in sorted(policy_dir.glob("*.md")):
        meta, _ = split_front_matter(path.read_text(encoding="utf-8"))
        found.append(
            PolicyFile(
                meta["policy_id"],
                meta["title"],
                int(meta["version"]),
                _date(meta["effective_date"]),
                path,
            )
        )
    manifest = policy_dir / "manifest.yaml"
    if manifest.exists():
        for e in yaml.safe_load(manifest.read_text(encoding="utf-8")) or []:
            found.append(
                PolicyFile(
                    e["policy_id"],
                    e["title"],
                    int(e["version"]),
                    _date(e["effective_date"]),
                    policy_dir / e["file"],
                )
            )
    return found


def _date(value) -> dt.date:
    return value if isinstance(value, dt.date) else dt.date.fromisoformat(str(value))


def load_policies(conn: psycopg.Connection, files: list[PolicyFile]) -> None:
    latest: dict[str, int] = {}
    for f in files:
        latest[f.policy_id] = max(latest.get(f.policy_id, 0), f.version)
    for f in files:
        conn.execute(
            "INSERT INTO policies (policy_id, title) VALUES (%s, %s) "
            "ON CONFLICT (policy_id) DO UPDATE SET title = EXCLUDED.title",
            (f.policy_id, f.title),
        )
    for f in files:
        conn.execute(
            "INSERT INTO policy_versions "
            "(policy_id, version, effective_date, source_file, is_current) "
            "VALUES (%s, %s, %s, %s, %s)",
            (
                f.policy_id,
                f.version,
                f.effective_date,
                f.path.relative_to(REPO).as_posix(),
                f.version == latest[f.policy_id],
            ),
        )


def read_known_layout(path: Path, layout: dict, qid_prefix: str | None) -> list[dict]:
    """Read question rows with a known layout. `qid_prefix` numbers rows across sheets
    (Questionnaire B, decision D13); otherwise the qid comes from the ID column."""
    wb = load_workbook(path, read_only=True)
    out = []
    for sheet, cfg in layout.items():
        ws = wb[sheet]
        for row_idx, row in enumerate(
            ws.iter_rows(min_row=cfg["header_row"] + 1, values_only=True),
            start=cfg["header_row"] + 1,
        ):
            text = row[cfg["col_question"] - 1]
            if not isinstance(text, str) or len(text.strip()) < MIN_QUESTION_CHARS:
                continue
            qid = f"{qid_prefix}-{len(out) + 1:03d}" if qid_prefix else str(row[cfg["col_qid"] - 1])
            out.append(
                {
                    "qid": qid,
                    "sheet": sheet,
                    "row": row_idx,
                    "col_question": cfg["col_question"],
                    "col_answer": cfg["col_answer"],
                    "text": text.strip(),
                }
            )
    wb.close()
    return out


def load_questionnaire(
    conn: psycopg.Connection, name: str, path: Path, layout: dict, qid_prefix: str | None
) -> int:
    questions = read_known_layout(path, layout, qid_prefix)
    qn_id = conn.execute(
        "INSERT INTO questionnaires (name, file_path, sheet_map) VALUES (%s, %s, %s) RETURNING id",
        (name, path.relative_to(REPO).as_posix(), Jsonb(layout)),
    ).fetchone()[0]
    with conn.cursor() as cur:
        cur.executemany(
            "INSERT INTO questions "
            "(questionnaire_id, qid, sheet, row, col_question, col_answer, text) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s)",
            [
                (
                    qn_id,
                    q["qid"],
                    q["sheet"],
                    q["row"],
                    q["col_question"],
                    q["col_answer"],
                    q["text"],
                )
                for q in questions
            ],
        )
    return len(questions)


def seed(conn: psycopg.Connection) -> dict:
    render_all()
    paths = make_all()
    migrate(conn)
    reset(conn)
    load_policies(conn, discover_policies())
    counts = {}
    for name, prefix in [("acme_vendor_security_2026", None), ("globex_supplier_review", "B")]:
        counts[name] = load_questionnaire(conn, name, paths[name], LAYOUTS[name], prefix)
    conn.commit()
    counts["policies"] = conn.execute("SELECT count(*) FROM policies").fetchone()[0]
    counts["versions"] = conn.execute("SELECT count(*) FROM policy_versions").fetchone()[0]
    counts["current"] = conn.execute(
        "SELECT count(*) FROM policy_versions WHERE is_current"
    ).fetchone()[0]
    return counts


def main() -> None:
    with connect() as conn:
        c = seed(conn)
    print(
        f"{c['policies']} policies, {c['versions']} versions, "
        f"{c['acme_vendor_security_2026']} + {c['globex_supplier_review']} questions"
    )


if __name__ == "__main__":
    main()
