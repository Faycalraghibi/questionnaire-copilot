"""Excel and CSV questionnaire import (header/column detection) and export."""

from __future__ import annotations

import csv
import shutil
from collections.abc import Callable
from copy import copy
from dataclasses import dataclass
from pathlib import Path

from openpyxl import load_workbook

MIN_QUESTION_CHARS = 15  # spec 7.2
MAX_HEADER_SCAN_ROWS = 15

# Decision D3: three name groups for header scoring.
QUESTION_TERMS = ("question", "control", "requirement", "description")
ANSWER_TERMS = ("response", "answer", "yes/no")
EXPLANATION_TERMS = ("explanation", "comments", "comment")
QID_TERMS = ("id", "qid", "#", "ref")


@dataclass(frozen=True)
class ColumnMapping:
    col_question: int
    col_answer: int | None
    col_explanation: int | None


@dataclass(frozen=True)
class SheetLayout:
    header_row: int
    col_qid: int | None
    col_question: int
    col_answer: int | None
    col_explanation: int | None
    is_yes_no_col: bool

    def to_dict(self) -> dict:
        return {
            "header_row": self.header_row,
            "col_qid": self.col_qid,
            "col_question": self.col_question,
            "col_answer": self.col_answer,
            "col_explanation": self.col_explanation,
            "is_yes_no_col": self.is_yes_no_col,
        }


@dataclass(frozen=True)
class DetectedQuestion:
    qid: str
    sheet: str
    row: int
    col_question: int
    col_answer: int | None
    text: str


@dataclass(frozen=True)
class DetectedQuestionnaire:
    sheet_map: dict[str, dict]
    questions: list[DetectedQuestion]


@dataclass(frozen=True)
class ExportRow:
    sheet: str
    row: int
    short_answer: str | None
    answer_text: str | None
    explanation: str | None
    source: str
    status: str


def _score_cell(text: str, terms: tuple[str, ...]) -> int:
    low = text.strip().lower()
    if not low:
        return 0
    if low in terms:
        return 3
    return sum(1 for t in terms if t in low)


def _pick_best(scores: dict[int, int]) -> tuple[int | None, bool]:
    """Return (best_col, is_ambiguous)."""
    positive = [(col, s) for col, s in scores.items() if s > 0]
    if not positive:
        return None, True
    max_score = max(s for _, s in positive)
    top = [col for col, s in positive if s == max_score]
    if len(top) > 1:
        return None, True
    return top[0], False


def _detect_header_in_rows(
    rows: list[tuple[int, list]],
    *,
    fallback_resolver: Callable[[list[str]], ColumnMapping] | None = None,
) -> tuple[int, list[str]]:
    for row_idx, values in rows[:MAX_HEADER_SCAN_ROWS]:
        text_cells = [v.strip() for v in values if isinstance(v, str) and v.strip()]
        if len(text_cells) >= 3:
            headers = [str(v).strip() if v is not None else "" for v in values]
            return row_idx, headers
    raise ValueError("No header row with at least 3 non-empty text cells found in first 15 rows")


def _build_sheet_layout(
    header_row: int,
    headers: list[str],
    *,
    fallback_resolver: Callable[[list[str]], ColumnMapping] | None = None,
) -> SheetLayout:
    q_scores = {i + 1: _score_cell(h, QUESTION_TERMS) for i, h in enumerate(headers)}
    a_scores = {i + 1: _score_cell(h, ANSWER_TERMS) for i, h in enumerate(headers)}
    e_scores = {i + 1: _score_cell(h, EXPLANATION_TERMS) for i, h in enumerate(headers)}
    id_scores = {i + 1: _score_cell(h, QID_TERMS) for i, h in enumerate(headers)}

    col_q, q_ambig = _pick_best(q_scores)
    col_a, a_ambig = _pick_best(a_scores)
    col_e, _ = _pick_best(e_scores)
    col_qid, _ = _pick_best(id_scores)

    if (q_ambig or a_ambig) and fallback_resolver is not None:
        resolved = fallback_resolver(headers)
        col_q = resolved.col_question
        col_a = resolved.col_answer
        col_e = resolved.col_explanation
        q_ambig = False

    if q_ambig or col_q is None:
        raise ValueError(f"Could not uniquely identify question column from headers: {headers}")

    ans_header = headers[col_a - 1].lower() if col_a is not None else ""
    is_yes_no = "yes/no" in ans_header or "y/n" in ans_header

    return SheetLayout(
        header_row=header_row,
        col_qid=col_qid,
        col_question=col_q,
        col_answer=col_a,
        col_explanation=col_e,
        is_yes_no_col=is_yes_no,
    )


def _read_xlsx(
    path: Path,
    *,
    qid_prefix: str | None = None,
    fallback_resolver: Callable[[list[str]], ColumnMapping] | None = None,
) -> DetectedQuestionnaire:
    wb = load_workbook(path, read_only=True, data_only=True)
    sheet_map: dict[str, dict] = {}
    questions: list[DetectedQuestion] = []

    try:
        for sheet_name in wb.sheetnames:
            ws = wb[sheet_name]
            top_rows = [
                (idx, list(row))
                for idx, row in enumerate(
                    ws.iter_rows(min_row=1, max_row=MAX_HEADER_SCAN_ROWS, values_only=True),
                    start=1,
                )
            ]
            header_row, headers = _detect_header_in_rows(
                top_rows, fallback_resolver=fallback_resolver
            )
            layout = _build_sheet_layout(header_row, headers, fallback_resolver=fallback_resolver)
            sheet_map[sheet_name] = layout.to_dict()

            for row_idx, row in enumerate(
                ws.iter_rows(min_row=header_row + 1, values_only=True),
                start=header_row + 1,
            ):
                if layout.col_question - 1 >= len(row):
                    continue
                raw_q = row[layout.col_question - 1]
                if not isinstance(raw_q, str) or len(raw_q.strip()) < MIN_QUESTION_CHARS:
                    continue

                if qid_prefix:
                    qid = f"{qid_prefix}-{len(questions) + 1:03d}"
                elif (
                    layout.col_qid is not None
                    and layout.col_qid - 1 < len(row)
                    and isinstance(row[layout.col_qid - 1], str)
                    and row[layout.col_qid - 1].strip()
                ):
                    qid = row[layout.col_qid - 1].strip()
                else:
                    qid = f"Q-{len(questions) + 1:03d}"

                questions.append(
                    DetectedQuestion(
                        qid=qid,
                        sheet=sheet_name,
                        row=row_idx,
                        col_question=layout.col_question,
                        col_answer=layout.col_answer,
                        text=raw_q.strip(),
                    )
                )
    finally:
        wb.close()

    return DetectedQuestionnaire(sheet_map=sheet_map, questions=questions)


def _read_csv(
    path: Path,
    *,
    qid_prefix: str | None = None,
    fallback_resolver: Callable[[list[str]], ColumnMapping] | None = None,
) -> DetectedQuestionnaire:
    with path.open("r", encoding="utf-8-sig", newline="") as fh:
        all_rows = list(csv.reader(fh))

    indexed = [(idx + 1, row) for idx, row in enumerate(all_rows[:MAX_HEADER_SCAN_ROWS])]
    header_row, headers = _detect_header_in_rows(indexed, fallback_resolver=fallback_resolver)
    layout = _build_sheet_layout(header_row, headers, fallback_resolver=fallback_resolver)
    sheet_name = "CSV"
    questions: list[DetectedQuestion] = []

    for row_idx, row in enumerate(all_rows[header_row:], start=header_row + 1):
        if layout.col_question - 1 >= len(row):
            continue
        raw_q = row[layout.col_question - 1]
        if not isinstance(raw_q, str) or len(raw_q.strip()) < MIN_QUESTION_CHARS:
            continue

        if qid_prefix:
            qid = f"{qid_prefix}-{len(questions) + 1:03d}"
        elif (
            layout.col_qid is not None
            and layout.col_qid - 1 < len(row)
            and row[layout.col_qid - 1].strip()
        ):
            qid = row[layout.col_qid - 1].strip()
        else:
            qid = f"Q-{len(questions) + 1:03d}"

        questions.append(
            DetectedQuestion(
                qid=qid,
                sheet=sheet_name,
                row=row_idx,
                col_question=layout.col_question,
                col_answer=layout.col_answer,
                text=raw_q.strip(),
            )
        )

    return DetectedQuestionnaire(sheet_map={sheet_name: layout.to_dict()}, questions=questions)


def read_questionnaire(
    path: Path,
    *,
    qid_prefix: str | None = None,
    fallback_resolver: Callable[[list[str]], ColumnMapping] | None = None,
) -> DetectedQuestionnaire:
    """Detect header and columns in an XLSX or CSV questionnaire and extract question rows."""
    suffix = path.suffix.lower()
    if suffix == ".xlsx":
        return _read_xlsx(path, qid_prefix=qid_prefix, fallback_resolver=fallback_resolver)
    if suffix == ".csv":
        return _read_csv(path, qid_prefix=qid_prefix, fallback_resolver=fallback_resolver)
    raise ValueError(f"Unsupported questionnaire file type: {path.suffix}")


def _format_cells(item: ExportRow, is_yes_no: bool) -> tuple[str | None, str | None]:
    """Return (answer_cell_value, explanation_cell_value) per spec 7.2 and decision D10."""
    if item.status == "needs_input" or item.short_answer is None:
        return None, item.explanation

    short = item.short_answer.lower()
    if is_yes_no:
        if short == "yes":
            return "Yes", item.explanation
        if short == "no":
            return "No", item.explanation
        if short == "partially":
            return "Partially", item.explanation
        # Decision D10: text answer leaves Yes/No/N.A. blank and puts text in explanation column.
        parts = [p for p in [item.answer_text, item.explanation] if p]
        return None, " ".join(parts) if parts else None

    if short in ("yes", "no", "partially"):
        return short.capitalize(), item.explanation
    # short == "text"
    return item.answer_text or item.explanation, item.explanation


def _ensure_extra_header_cols(ws, header_row: int) -> tuple[int, int]:
    """Find or append Source and Status columns at the end of the header row."""
    max_col = ws.max_column
    existing = {
        str(ws.cell(row=header_row, column=c).value).strip(): c
        for c in range(1, max_col + 1)
        if ws.cell(row=header_row, column=c).value is not None
    }
    col_source = existing.get("Source")
    col_status = existing.get("Status")
    template_cell = ws.cell(row=header_row, column=max_col)

    if col_source is None:
        max_col += 1
        col_source = max_col
        c = ws.cell(row=header_row, column=col_source, value="Source")
        if template_cell.has_style:
            c.font = copy(template_cell.font)
            c.fill = copy(template_cell.fill)
            c.alignment = copy(template_cell.alignment)
            c.border = copy(template_cell.border)

    if col_status is None:
        max_col += 1
        col_status = max_col
        c = ws.cell(row=header_row, column=col_status, value="Status")
        if template_cell.has_style:
            c.font = copy(template_cell.font)
            c.fill = copy(template_cell.fill)
            c.alignment = copy(template_cell.alignment)
            c.border = copy(template_cell.border)

    return col_source, col_status


def export_questionnaire(
    source_path: Path,
    dest_path: Path,
    sheet_map: dict[str, dict],
    answers: list[ExportRow],
) -> Path:
    """Copy source_path to dest_path and write answers, explanations, Source, and Status."""
    dest_path.parent.mkdir(parents=True, exist_ok=True)
    suffix = source_path.suffix.lower()

    if suffix == ".csv":
        return _export_csv(source_path, dest_path, sheet_map, answers)
    if suffix != ".xlsx":
        raise ValueError(f"Unsupported questionnaire file type: {source_path.suffix}")

    shutil.copy2(source_path, dest_path)
    wb = load_workbook(dest_path)
    try:
        extra_cols: dict[str, tuple[int, int]] = {}
        for sheet_name, cfg in sheet_map.items():
            ws = wb[sheet_name]
            extra_cols[sheet_name] = _ensure_extra_header_cols(ws, cfg["header_row"])

        for item in answers:
            cfg = sheet_map[item.sheet]
            ws = wb[item.sheet]
            ans_val, exp_val = _format_cells(item, bool(cfg.get("is_yes_no_col")))

            if cfg.get("col_answer") is not None and ans_val is not None:
                ws.cell(row=item.row, column=cfg["col_answer"], value=ans_val)
            if cfg.get("col_explanation") is not None and exp_val is not None:
                ws.cell(row=item.row, column=cfg["col_explanation"], value=exp_val)

            col_source, col_status = extra_cols[item.sheet]
            ws.cell(row=item.row, column=col_source, value=item.source)
            ws.cell(row=item.row, column=col_status, value=item.status)

        wb.save(dest_path)
    finally:
        wb.close()
    return dest_path


def _export_csv(
    source_path: Path,
    dest_path: Path,
    sheet_map: dict[str, dict],
    answers: list[ExportRow],
) -> Path:
    with source_path.open("r", encoding="utf-8-sig", newline="") as fh:
        rows = list(csv.reader(fh))

    cfg = next(iter(sheet_map.values()))
    header_idx = cfg["header_row"] - 1
    header = rows[header_idx]
    col_source = header.index("Source") + 1 if "Source" in header else len(header) + 1
    if "Source" not in header:
        header.append("Source")
    col_status = header.index("Status") + 1 if "Status" in header else len(header) + 1
    if "Status" not in header:
        header.append("Status")

    for item in answers:
        row = rows[item.row - 1]
        while len(row) < col_status:
            row.append("")
        ans_val, exp_val = _format_cells(item, bool(cfg.get("is_yes_no_col")))
        if cfg.get("col_answer") is not None and ans_val is not None:
            row[cfg["col_answer"] - 1] = ans_val
        if cfg.get("col_explanation") is not None and exp_val is not None:
            row[cfg["col_explanation"] - 1] = exp_val
        row[col_source - 1] = item.source
        row[col_status - 1] = item.status

    with dest_path.open("w", encoding="utf-8", newline="") as fh:
        csv.writer(fh).writerows(rows)
    return dest_path
