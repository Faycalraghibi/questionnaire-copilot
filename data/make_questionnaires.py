"""Build the two synthetic questionnaires as real-looking Excel files from data/truth/*.yaml.

A: one sheet, 2-row merged title block, blank row, header at row 4 (spec 6.2).
B: two sheets ("Security", "Privacy"), header at row 1, Yes/No/N.A. column (spec 6.2).

Usage: uv run python -m data.make_questionnaires
"""

from __future__ import annotations

import datetime as dt
from pathlib import Path

import yaml
from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.worksheet.datavalidation import DataValidation

DATA = Path(__file__).parent
TRUTH_DIR = DATA / "truth"
OUT_DIR = DATA / "questionnaires"

A_NAME = "acme_vendor_security_2026"
B_NAME = "globex_supplier_review"
A_SHEET = "Vendor Security Assessment"

# Known layouts. Phase 1 seed reads questions with these; Phase 3 replaces them with detection.
LAYOUTS = {
    A_NAME: {A_SHEET: {"header_row": 4, "col_qid": 1, "col_question": 3, "col_answer": 4}},
    B_NAME: {
        "Security": {"header_row": 1, "col_qid": 1, "col_question": 2, "col_answer": 3},
        "Privacy": {"header_row": 1, "col_qid": 1, "col_question": 2, "col_answer": 3},
    },
}

FIXED_TIME = dt.datetime(2026, 10, 1, 9, 0, 0)
THIN = Side(style="thin", color="A6A6A6")
BORDER = Border(left=THIN, right=THIN, top=THIN, bottom=THIN)
WRAP = Alignment(wrap_text=True, vertical="top")


def load_truth(name: str) -> list[dict]:
    return yaml.safe_load((TRUTH_DIR / f"{name}.yaml").read_text(encoding="utf-8"))


def _header(ws, row: int, values: list[str], fill: str) -> None:
    for col, value in enumerate(values, start=1):
        cell = ws.cell(row=row, column=col, value=value)
        cell.font = Font(bold=True, color="FFFFFF")
        cell.fill = PatternFill("solid", fgColor=fill)
        cell.alignment = Alignment(vertical="center", wrap_text=True)
        cell.border = BORDER


def _body_row(ws, row: int, values: list) -> None:
    for col, value in enumerate(values, start=1):
        cell = ws.cell(row=row, column=col, value=value)
        cell.alignment = WRAP
        cell.border = BORDER


def make_a(rows: list[dict], path: Path) -> None:
    wb = Workbook()
    ws = wb.active
    ws.title = A_SHEET
    ws["A1"] = "Acme Corporation: Vendor Security Assessment 2026"
    ws["A1"].font = Font(bold=True, size=14)
    ws.merge_cells("A1:E1")
    ws["A2"] = (
        "Vendor: Northbeam Cloud. Please answer every question in the Response column and add "
        "detail in Comments. Return the completed file to your Acme vendor risk contact."
    )
    ws["A2"].alignment = WRAP
    ws.merge_cells("A2:E2")
    ws.row_dimensions[2].height = 32
    _header(ws, 4, ["ID", "Domain", "Question", "Response", "Comments"], "1F4E79")
    for i, q in enumerate(rows):
        _body_row(ws, 5 + i, [q["qid"], q["domain"], q["question"], None, None])
    for col, width in zip("ABCDE", [9, 20, 60, 22, 45], strict=True):
        ws.column_dimensions[col].width = width
    ws.freeze_panes = "A5"
    wb.properties.creator = "Acme Corporation"
    wb.properties.created = FIXED_TIME
    wb.properties.modified = FIXED_TIME
    wb.save(path)


def make_b(rows: list[dict], path: Path) -> None:
    wb = Workbook()
    wb.remove(wb.active)
    for sheet in ["Security", "Privacy"]:
        ws = wb.create_sheet(sheet)
        _header(ws, 1, ["#", "Control question", "Yes/No/N.A.", "Explanation"], "385723")
        sheet_rows = [q for q in rows if q["sheet"] == sheet]
        for i, q in enumerate(sheet_rows, start=1):
            _body_row(ws, 1 + i, [i, q["question"], None, None])
        dv = DataValidation(type="list", formula1='"Yes,No,N.A."', allow_blank=True)
        ws.add_data_validation(dv)
        dv.add(f"C2:C{1 + len(sheet_rows)}")
        for col, width in zip("ABCD", [5, 70, 14, 50], strict=True):
            ws.column_dimensions[col].width = width
        ws.freeze_panes = "A2"
    wb.properties.creator = "Globex Procurement"
    wb.properties.created = FIXED_TIME
    wb.properties.modified = FIXED_TIME
    wb.save(path)


def make_all(out_dir: Path = OUT_DIR) -> dict[str, Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    a_path = out_dir / f"{A_NAME}.xlsx"
    b_path = out_dir / f"{B_NAME}.xlsx"
    make_a(load_truth(A_NAME), a_path)
    make_b(load_truth(B_NAME), b_path)
    return {A_NAME: a_path, B_NAME: b_path}


if __name__ == "__main__":
    for path in make_all().values():
        print(f"wrote {path.relative_to(DATA.parent)}")
