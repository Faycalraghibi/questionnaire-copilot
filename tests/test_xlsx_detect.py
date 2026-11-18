"""Tests for Excel and CSV header and column detection."""

from __future__ import annotations

from pathlib import Path

from openpyxl import Workbook

from data.make_questionnaires import A_NAME, A_SHEET, B_NAME, make_all
from qc.xlsx_io import ColumnMapping, read_questionnaire


def test_detect_questionnaire_a(tmp_path: Path):
    paths = make_all(tmp_path)
    detected = read_questionnaire(paths[A_NAME])

    assert list(detected.sheet_map) == [A_SHEET]
    cfg = detected.sheet_map[A_SHEET]
    assert cfg["header_row"] == 4
    assert cfg["col_qid"] == 1
    assert cfg["col_question"] == 3
    assert cfg["col_answer"] == 4
    assert cfg["col_explanation"] == 5
    assert cfg["is_yes_no_col"] is False

    assert len(detected.questions) == 60
    assert detected.questions[0].qid == "A-001"
    assert detected.questions[0].row == 5
    assert detected.questions[-1].qid == "A-060"
    assert detected.questions[-1].row == 64


def test_detect_questionnaire_b_two_sheets(tmp_path: Path):
    paths = make_all(tmp_path)
    detected = read_questionnaire(paths[B_NAME], qid_prefix="B")

    assert list(detected.sheet_map) == ["Security", "Privacy"]
    for sheet in ["Security", "Privacy"]:
        cfg = detected.sheet_map[sheet]
        assert cfg["header_row"] == 1
        assert cfg["col_question"] == 2
        assert cfg["col_answer"] == 3
        assert cfg["col_explanation"] == 4
        assert cfg["is_yes_no_col"] is True

    assert len(detected.questions) == 40
    assert detected.questions[0].qid == "B-001"
    assert detected.questions[0].sheet == "Security"
    assert detected.questions[25].qid == "B-026"
    assert detected.questions[25].sheet == "Privacy"
    assert detected.questions[-1].qid == "B-040"


def test_ambiguous_headers_use_fallback_resolver_once(tmp_path: Path):
    wb = Workbook()
    ws = wb.active
    ws.append(["Col A", "Col B", "Col C", "Col D"])
    ws.append(["1", "Do you encrypt customer data at rest?", "", ""])
    path = tmp_path / "ambig.xlsx"
    wb.save(path)

    calls = 0

    def resolver(headers: list[str]) -> ColumnMapping:
        nonlocal calls
        calls += 1
        assert headers == ["Col A", "Col B", "Col C", "Col D"]
        return ColumnMapping(col_question=2, col_answer=3, col_explanation=4)

    detected = read_questionnaire(path, fallback_resolver=resolver)
    assert calls == 1
    assert len(detected.questions) == 1
    assert detected.questions[0].text == "Do you encrypt customer data at rest?"


def test_detect_csv_questionnaire(tmp_path: Path):
    csv_path = tmp_path / "sample.csv"
    csv_path.write_text(
        "ID,Question,Response,Comments\nQ-1,Do you enforce MFA for all admins?,,\nQ-2,Short,,\n",
        encoding="utf-8",
    )
    detected = read_questionnaire(csv_path)
    assert len(detected.questions) == 1
    assert detected.questions[0].qid == "Q-1"
    assert detected.questions[0].row == 2
