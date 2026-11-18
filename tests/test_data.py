"""Integrity of the synthetic data against spec section 6 (offline, no database)."""

import re
from collections import Counter
from pathlib import Path

import pytest
import yaml
from docx import Document
from openpyxl import load_workbook

from data.make_questionnaires import A_NAME, A_SHEET, B_NAME, make_all
from data.render import render_all
from qc.markdown import parse_policy

DATA = Path(__file__).parent.parent / "data"

SPEC_POLICIES = {
    "infosec-policy": [(1, "2024-03-01"), (2, "2026-01-10")],
    "access-control": [(1, "2025-05-01")],
    "encryption-standard": [(1, "2023-09-01"), (2, "2025-10-01")],
    "data-retention": [(2, "2025-02-01"), (3, "2026-03-01")],
    "incident-response": [(1, "2025-06-01")],
    "business-continuity": [(1, "2025-04-01")],
    "vendor-management": [(1, "2025-07-01")],
    "secure-sdlc": [(1, "2026-03-01")],
    "logging-monitoring": [(1, "2025-05-15")],
    "hr-security": [(1, "2025-03-01")],
    "compliance": [(1, "2026-07-15")],
}

SPEC_UNANSWERABLE = [
    "What is the coverage amount of your cyber insurance policy?",
    "Do you support customer-managed encryption keys (BYOK)?",
    "Are your offices protected by 24/7 security guards?",
    "Are you FedRAMP authorized?",
    "How many employees have production database access?",
    "Do you allow customers to perform their own penetration tests?",
    "What is your data center's Uptime Institute tier?",
    "Do you hold PCI DSS certification?",
]

# Spec 6.2 examples, to be written exactly: qid -> (question, short, keys, forbidden, facts)
SPEC_EXAMPLES = {
    "A-001": ("Do you encrypt customer data at rest? If so, with what algorithm?", "yes", ["AES-256"], [], ["F10"]),  # noqa: E501
    "A-004": ("How often is user access reviewed?", "text", ["quarter"], [], ["F06"]),
    "A-009": ("How long are customer data retained after contract termination?", "text", ["30 days"], ["90 days"], ["F13"]),  # noqa: E501
    "A-012": ("How often are encryption keys rotated?", "text", ["12 months"], ["24 months"], ["F12"]),  # noqa: E501
    "A-017": ("How quickly do you notify customers after a confirmed security breach?", "text", ["72 hours"], [], ["F16"]),  # noqa: E501
    "A-021": ("What are your RPO and RTO?", "text", ["4 hours", "8 hours"], [], ["F19"]),
    "A-026": ("Is MFA enforced for administrative access?", "yes", ["multi-factor"], [], ["F05"]),
    "A-033": ("Do you conduct phishing simulations?", "yes", ["quarter"], [], ["F04"]),
    "A-040": ("Are you ISO 27001 certified?", "no", ["2027"], [], ["F32"]),
    "A-044": ("Where is customer data hosted?", "text", ["EU"], [], ["F21", "F33"]),
}  # fmt: skip


def norm(text: str) -> str:
    return " ".join(text.split())


def all_policy_docs():
    docs = {}
    for folder in ["policies", "policies_src"]:
        for path in sorted((DATA / folder).glob("*.md")):
            doc = parse_policy(path.read_text(encoding="utf-8"))
            docs[(doc.meta["policy_id"], int(doc.meta["version"]))] = doc
    return docs


DOCS = all_policy_docs()
CURRENT = {pid: DOCS[(pid, max(v for p, v in DOCS if p == pid))] for pid in {p for p, _ in DOCS}}
FACTS = yaml.safe_load((DATA / "facts.yaml").read_text(encoding="utf-8"))
FACT_BY_ID = {f["id"]: f for f in FACTS}
TRUTH_A = yaml.safe_load((DATA / "truth" / f"{A_NAME}.yaml").read_text(encoding="utf-8"))
TRUTH_B = yaml.safe_load((DATA / "truth" / f"{B_NAME}.yaml").read_text(encoding="utf-8"))


def phrase_in(phrase: str, text: str) -> bool:
    """Key phrase match: case-insensitive, `a | b` accepts either alternative (decision D24)."""
    return any(alt.strip().lower() in text.lower() for alt in phrase.split("|"))


# Policies ------------------------------------------------------------------------------------


def test_policies_and_versions_match_spec():
    found = {}
    for (pid, version), doc in DOCS.items():
        found.setdefault(pid, []).append((version, str(doc.meta["effective_date"])))
    assert {k: sorted(v) for k, v in found.items()} == SPEC_POLICIES
    assert len(DOCS) == 14


@pytest.mark.parametrize("key", sorted(DOCS), ids=lambda k: f"{k[0]}-v{k[1]}")
def test_policy_length_and_front_matter(key):
    doc = DOCS[key]
    assert set(doc.meta) == {"policy_id", "title", "version", "effective_date"}
    words = len(re.findall(r"\S+", doc.full_text()))
    assert 200 <= words <= 600, words


@pytest.mark.parametrize("fact", FACTS, ids=lambda f: f["id"])
def test_fact_appears_exactly_once_in_current_version(fact):
    doc = CURRENT[fact["policy_id"]]
    assert int(doc.meta["version"]) == fact["version"]
    section = norm(doc.section_text(fact["section"]))
    for marker in fact["markers"]:
        assert section.count(marker) == 1, marker
        everywhere = sum(norm(d.full_text()).count(marker) for d in CURRENT.values())
        assert everywhere == 1, f"{marker!r} appears {everywhere} times across current policies"


def test_spec_fact_ids_complete():
    assert [f["id"] for f in FACTS] == [f"F{i:02d}" for i in range(1, 34)]


@pytest.mark.parametrize(
    "key, section, old_phrase, new_phrase",
    [
        (("infosec-policy", 1), "Governance", "reviewed every 2 years", "at least once a year"),
        (("infosec-policy", 1), "Training", "training at hire", "every year after"),
        (("infosec-policy", 1), "Training", "no phishing simulation", "Phishing simulations run"),
        (("encryption-standard", 1), "Key management", "rotated every 24 months", "12 months"),
        (("data-retention", 2), "Customer data", "within 90 days after contract end", "30 days"),
        (("data-retention", 2), "Backups", "Backups are kept for 90 days", "35 days"),
    ],
)
def test_old_versions_hold_the_old_facts(key, section, old_phrase, new_phrase):
    text = norm(DOCS[key].section_text(section))
    assert old_phrase in text
    assert new_phrase not in text


def test_data_retention_v4_only_changes_backups():
    path = DATA / "policies_updates" / "data-retention-v4.md"
    v4 = parse_policy(path.read_text(encoding="utf-8"))
    v3 = CURRENT["data-retention"]
    assert int(v4.meta["version"]) == 4
    assert "Backups are kept for 30 days" in norm(v4.section_text("Backups"))
    for name, _ in v3.sections:
        if name != "Backups":
            assert v4.section_text(name) == v3.section_text(name)


def test_unanswerable_topics_absent_from_current_policies():
    text = " ".join(norm(d.full_text()).lower() for d in CURRENT.values())
    for word in ["insurance", "byok", "customer-managed", "guard", "fedramp", "uptime", "pci"]:
        assert word not in text, word


# Ground truth --------------------------------------------------------------------------------


def test_questionnaire_a_shape():
    assert [q["qid"] for q in TRUTH_A] == [f"A-{i:03d}" for i in range(1, 61)]
    assert sum(q["answerable"] for q in TRUTH_A) == 52
    covered = {f for q in TRUTH_A for f in q["facts"]}
    assert covered == {f["id"] for f in FACTS}
    unanswerable = [q["question"] for q in TRUTH_A if not q["answerable"]]
    assert sorted(unanswerable) == sorted(SPEC_UNANSWERABLE)


def test_questionnaire_a_spec_examples_exact():
    by_qid = {q["qid"]: q for q in TRUTH_A}
    for qid, (question, short, keys, forbidden, facts) in SPEC_EXAMPLES.items():
        q = by_qid[qid]
        assert (q["question"], q["short_answer"], q["key_phrases"]) == (question, short, keys)
        assert (q["forbidden_phrases"], q["facts"]) == (forbidden, facts)


def test_questionnaire_b_shape():
    assert [q["qid"] for q in TRUTH_B] == [f"B-{i:03d}" for i in range(1, 41)]
    assert Counter(q["sheet"] for q in TRUTH_B) == {"Security": 25, "Privacy": 15}
    assert sum(not q["answerable"] for q in TRUTH_B) == 5
    a_by = {q["qid"]: q for q in TRUTH_A}
    a_questions = {q["question"] for q in TRUTH_A}
    for q in TRUTH_B:
        src = a_by[q["reworded_from"]]
        assert q["facts"] == src["facts"] and q["answerable"] == src["answerable"]
        assert q["question"] not in a_questions, "B must reword, not copy"


@pytest.mark.parametrize("q", TRUTH_A + TRUTH_B, ids=lambda q: q["qid"])
def test_truth_entry_consistent(q):
    if not q["answerable"]:
        assert q["facts"] == [] and q["sources"] == [] and q["short_answer"] is None
        assert q["reference_answer"] is None and q["unanswerable_case"]
        return
    assert q["short_answer"] in {"yes", "no", "partially", "text"}
    expected = []
    for fid in q["facts"]:
        f = FACT_BY_ID[fid]
        src = {"policy_id": f["policy_id"], "version": f["version"], "section": f["section"]}
        if src not in expected:
            expected.append(src)
    assert q["sources"] == expected
    cited = " ".join(norm(CURRENT[s["policy_id"]].section_text(s["section"])) for s in q["sources"])
    for phrase in q["key_phrases"]:
        assert phrase_in(phrase, cited), f"key phrase {phrase!r} not in cited sections"
        assert phrase_in(phrase, q["reference_answer"]), f"{phrase!r} not in reference answer"
    for phrase in q["forbidden_phrases"]:
        assert not phrase_in(phrase, cited)
        assert not phrase_in(phrase, q["reference_answer"])


# Generated files -----------------------------------------------------------------------------


@pytest.fixture(scope="module")
def generated(tmp_path_factory):
    out = tmp_path_factory.mktemp("gen")
    return {"xlsx": make_all(out), "policies": render_all(out_dir=out), "dir": out}


def test_questionnaire_a_excel_layout(generated):
    wb = load_workbook(generated["xlsx"][A_NAME])
    assert wb.sheetnames == [A_SHEET]
    ws = wb[A_SHEET]
    assert {str(r) for r in ws.merged_cells.ranges} == {"A1:E1", "A2:E2"}
    assert all(c.value is None for c in ws[3])
    assert [c.value for c in ws[4]] == ["ID", "Domain", "Question", "Response", "Comments"]
    assert ws.max_row == 64
    assert [ws.cell(5 + i, 3).value for i in range(60)] == [q["question"] for q in TRUTH_A]


def test_questionnaire_b_excel_layout(generated):
    wb = load_workbook(generated["xlsx"][B_NAME])
    assert wb.sheetnames == ["Security", "Privacy"]
    questions = []
    for ws in wb:
        assert [c.value for c in ws[1]] == ["#", "Control question", "Yes/No/N.A.", "Explanation"]
        questions += [ws.cell(r, 2).value for r in range(2, ws.max_row + 1)]
    assert questions == [q["question"] for q in TRUTH_B]


def test_rendered_policies(generated):
    by_id = {e["policy_id"]: e for e in generated["policies"]}
    assert {pid: Path(e["file"]).suffix for pid, e in by_id.items()} == {
        "incident-response": ".pdf",
        "business-continuity": ".pdf",
        "vendor-management": ".docx",
    }
    for pid in ["incident-response", "business-continuity"]:
        assert (generated["dir"] / by_id[pid]["file"]).read_bytes().startswith(b"%PDF")
    docx = Document(str(generated["dir"] / by_id["vendor-management"]["file"]))
    headings = [p.text for p in docx.paragraphs if p.style.name == "Heading 2"]
    assert headings == [name for name, _ in CURRENT["vendor-management"].sections]


EM_DASH = chr(0x2014)
SKIP_DIRS = {".git", ".venv", "__pycache__", ".pytest_cache", ".ruff_cache"}
TEXT_SUFFIXES = {".md", ".py", ".yaml", ".yml", ".toml", ".sql", ".txt", ""}


def test_no_em_dashes_in_repo_text_files():
    repo = DATA.parent
    bad = []
    for path in repo.rglob("*"):
        if SKIP_DIRS.intersection(path.parts):
            continue
        if path.is_file() and path.suffix in TEXT_SUFFIXES:
            try:
                if EM_DASH in path.read_text(encoding="utf-8"):
                    bad.append(str(path.relative_to(repo)))
            except UnicodeDecodeError:
                continue
    assert bad == []
