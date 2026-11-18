"""Tests for Excel and CSV questionnaire export."""

from __future__ import annotations

import csv
from pathlib import Path

from openpyxl import load_workbook

from data.make_questionnaires import A_NAME, A_SHEET, B_NAME, make_all
from qc.xlsx_io import ExportRow, export_questionnaire, read_questionnaire


def test_export_questionnaire_a_preserves_layout_and_writes_columns(tmp_path: Path):
    paths = make_all(tmp_path / "in")
    src = paths[A_NAME]
    detected = read_questionnaire(src)
    dest = tmp_path / "out" / f"{A_NAME}_filled.xlsx"

    q_yes = detected.questions[0]
    q_text = detected.questions[3]
    q_needs = detected.questions[14]

    rows = [
        ExportRow(
            sheet=q_yes.sheet,
            row=q_yes.row,
            short_answer="yes",
            answer_text=None,
            explanation="AES-256 is used for all databases and backups.",
            source="encryption-standard v2 (Data at rest)",
            status="approved",
        ),
        ExportRow(
            sheet=q_text.sheet,
            row=q_text.row,
            short_answer="text",
            answer_text="User access is reviewed every quarter.",
            explanation="Quarterly reviews cover all production systems.",
            source="access-control v1 (Access reviews)",
            status="drafted",
        ),
        ExportRow(
            sheet=q_needs.sheet,
            row=q_needs.row,
            short_answer=None,
            answer_text=None,
            explanation=None,
            source="",
            status="needs_input",
        ),
    ]

    export_questionnaire(src, dest, detected.sheet_map, rows)

    orig_wb = load_workbook(src)
    out_wb = load_workbook(dest)
    try:
        orig_ws = orig_wb[A_SHEET]
        out_ws = out_wb[A_SHEET]

        # Header row has Source and Status appended.
        assert [c.value for c in out_ws[4]] == [
            "ID",
            "Domain",
            "Question",
            "Response",
            "Comments",
            "Source",
            "Status",
        ]
        # Title block and merged cells untouched.
        assert out_ws["A1"].value == orig_ws["A1"].value
        assert out_ws["A2"].value == orig_ws["A2"].value
        assert {str(r) for r in out_ws.merged_cells.ranges} == {"A1:E1", "A2:E2"}

        # Answers landed in the right cells.
        assert out_ws.cell(q_yes.row, 4).value == "Yes"
        assert out_ws.cell(q_yes.row, 5).value == "AES-256 is used for all databases and backups."
        assert out_ws.cell(q_yes.row, 6).value == "encryption-standard v2 (Data at rest)"
        assert out_ws.cell(q_yes.row, 7).value == "approved"

        assert out_ws.cell(q_text.row, 4).value == "User access is reviewed every quarter."
        assert out_ws.cell(q_text.row, 7).value == "drafted"

        assert out_ws.cell(q_needs.row, 4).value is None
        assert out_ws.cell(q_needs.row, 7).value == "needs_input"

        # Untouched question columns remain identical.
        for r in range(5, 65):
            assert out_ws.cell(r, 1).value == orig_ws.cell(r, 1).value
            assert out_ws.cell(r, 2).value == orig_ws.cell(r, 2).value
            assert out_ws.cell(r, 3).value == orig_ws.cell(r, 3).value
    finally:
        orig_wb.close()
        out_wb.close()


def test_export_questionnaire_b_yes_no_rules(tmp_path: Path):
    paths = make_all(tmp_path / "in")
    src = paths[B_NAME]
    detected = read_questionnaire(src, qid_prefix="B")
    dest = tmp_path / "out" / f"{B_NAME}_filled.xlsx"

    q_sec_yes = detected.questions[0]  # Security sheet
    q_sec_part = detected.questions[1]  # Security sheet
    q_priv_text = detected.questions[-1]  # Privacy sheet (B-040)

    rows = [
        ExportRow(
            sheet=q_sec_yes.sheet,
            row=q_sec_yes.row,
            short_answer="yes",
            answer_text=None,
            explanation="Encrypted with AES-256.",
            source="encryption-standard v2",
            status="approved",
        ),
        ExportRow(
            sheet=q_sec_part.sheet,
            row=q_sec_part.row,
            short_answer="partially",
            answer_text=None,
            explanation="Planned for Q4.",
            source="access-control v1",
            status="drafted",
        ),
        ExportRow(
            sheet=q_priv_text.sheet,
            row=q_priv_text.row,
            short_answer="text",
            answer_text="Hosted in AWS eu-west-1 (Ireland).",
            explanation=None,
            source="business-continuity v1",
            status="approved",
        ),
    ]

    export_questionnaire(src, dest, detected.sheet_map, rows)

    out_wb = load_workbook(dest)
    try:
        sec_ws = out_wb["Security"]
        priv_ws = out_wb["Privacy"]
        assert [c.value for c in sec_ws[1]] == [
            "#",
            "Control question",
            "Yes/No/N.A.",
            "Explanation",
            "Source",
            "Status",
        ]
        assert sec_ws.cell(q_sec_yes.row, 3).value == "Yes"
        assert sec_ws.cell(q_sec_part.row, 3).value == "Partially"
        # Decision D10: text answer leaves Yes/No/N.A. blank and puts text in Explanation.
        assert priv_ws.cell(q_priv_text.row, 3).value is None
        assert priv_ws.cell(q_priv_text.row, 4).value == "Hosted in AWS eu-west-1 (Ireland)."
        assert priv_ws.cell(q_priv_text.row, 5).value == "business-continuity v1"
        assert priv_ws.cell(q_priv_text.row, 6).value == "approved"
    finally:
        out_wb.close()


def test_export_csv_adds_source_and_status(tmp_path: Path):
    src = tmp_path / "in.csv"
    src.write_text(
        "ID,Question,Response,Comments\nQ-1,Do you use MFA for admins?,,\n", encoding="utf-8"
    )
    detected = read_questionnaire(src)
    dest = tmp_path / "out.csv"

    q = detected.questions[0]
    export_questionnaire(
        src,
        dest,
        detected.sheet_map,
        [
            ExportRow(
                sheet=q.sheet,
                row=q.row,
                short_answer="yes",
                answer_text=None,
                explanation="SSO with MFA is required.",
                source="access-control v1",
                status="approved",
            )
        ],
    )
    with dest.open("r", encoding="utf-8", newline="") as fh:
        rows = list(csv.reader(fh))
    assert rows[0] == ["ID", "Question", "Response", "Comments", "Source", "Status"]
    assert rows[1] == [
        "Q-1",
        "Do you use MFA for admins?",
        "Yes",
        "SSO with MFA is required.",
        "access-control v1",
        "approved",
    ]
