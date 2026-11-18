# Product 1: Questionnaire Copilot

**Answer security questionnaires in hours instead of days, from your current policies, with a source for every answer.**

Repository: `questionnaire-copilot` · Package: `qc` · Effort: 25-30 hours · Read `00-AGENT-RULES.md` first.

---

## 1. The client need

Every B2B software company that sells to larger customers receives security questionnaires: Excel
files of 50 to 300 questions ("Do you encrypt data at rest?", "How quickly do you notify customers
of a breach?"). Someone senior answers them by hand, copying from old questionnaires and policy
documents. Three things go wrong:

1. Answers come from **outdated policies** (last year's retention period, an old TLS version).
2. Answers **cannot be traced** to a source, so reviewers re-check everything.
3. Questions with **no documented answer** get guessed instead of escalated.

Upwork evidence (September to November 2026): a US SaaS team built a questionnaire assistant that
"pulls answers from old policy documents" and "cites the wrong page"; a Malta B2B team's assistant
"gives wrong answers with full confidence" and they "don't have a way to measure answer quality"; a
UK company asked for a knowledge base where "every answer cites the source"; a US benefits platform
($256k spent on Upwork) wants answers "without the fear of hallucination".

## 2. Users

| User | Job to be done |
| --- | --- |
| Security or compliance lead | Keep policies current; approve answers; never send a wrong one |
| Sales engineer or founder | Get a questionnaire back to a prospect fast |
| Reviewer (any team member) | Check each drafted answer against its source in seconds |

## 3. What the product does (MVP)

1. **Policy library.** Upload policies (PDF, DOCX, Markdown). Each has a version and an effective
   date. Only the current version is used for new answers; older ones are kept for history.
2. **Questionnaire import.** Upload an Excel or CSV questionnaire. The product finds the header row and
   the question column, even when the file has a title block, merged cells or several sheets.
3. **Drafting.** For each question: reuse an approved answer if one matches closely; otherwise draft
   from the current policies. Every draft has a short answer (Yes, No, Partially, or text), an
   explanation, citations (policy, version, section), and a confidence level. If the documents do
   not answer the question, the draft says **"Needs input"** instead of guessing.
4. **Review.** A table of all questions with filters by status and confidence. Clicking a row shows
   the draft next to the cited passages. Approve, edit then approve, or reject.
5. **Answer library.** Approved answers are saved with the policy versions they relied on. When a
   policy gets a new version, answers that relied on the old one are flagged **"Policy changed since
   approval"** and are not reused until re-approved.
6. **Export.** Writes the answers back into the original Excel file, in its own layout, plus a
   "Source" and a "Status" column.
7. **Quality page.** Shows the built-in evaluation (section 9): correctness, citation accuracy,
   "Needs input" detection, reuse rate, cost per questionnaire.

## 4. Pitch

**One paragraph (README, portfolio):** Questionnaire Copilot turns a 60-question security
questionnaire into a reviewed, sourced answer file in under an hour. It drafts only from your current
policies, cites the exact section for every answer, says "Needs input" instead of guessing, and
learns from every answer you approve. When a policy changes, it tells you which approved answers are
now out of date.

**Proposal opening line (RAG and knowledge-assistant postings):** "I built a product that answers
security questionnaires from a company's own policies: it only uses current policy versions, cites
the exact section, refuses when the documents are silent, and measures its own accuracy (link).
Your [problem from their post] is the same problem."

**Video (3 minutes):** see section 13.

## 5. Scope

In: everything in section 3, synthetic company data, evaluation, Docker setup.
Out (listed in README as production additions): user accounts and SSO, connectors to Google Drive or
SharePoint, multi-tenant hosting, Word or PDF questionnaires (Excel and CSV only).

## 6. Synthetic company and data

Company: **Northbeam Cloud**, a fictional 80-person B2B SaaS for logistics teams, hosted in AWS in the EU.

### 6.1 Policies and facts (ground truth)

Write each policy as a Markdown file in `data/policies/` with front matter (`policy_id`, `title`,
`version`, `effective_date`) and `##` sections named exactly as below. Render two of them to PDF and
one to DOCX (`data/render.py`) so all import paths are exercised. 200 to 600 words per policy;
the facts below must appear exactly once in the current version.

| Fact id | policy_id (version, effective date) | Section | Fact |
| --- | --- | --- | --- |
| F01 | infosec-policy (v2, 2026-01-10) | Governance | The security program is owned by the Head of Security and reviewed by the CEO annually |
| F02 | infosec-policy (v2) | Governance | All security policies are reviewed at least once a year |
| F03 | infosec-policy (v2) | Training | Security awareness training at hire and every year after |
| F04 | infosec-policy (v2) | Training | Phishing simulations run every quarter |
| F05 | access-control (v1, 2025-05-01) | Authentication | SSO with multi-factor authentication is required for all production and admin systems |
| F06 | access-control (v1) | Access reviews | User access is reviewed every quarter |
| F07 | access-control (v1) | Offboarding | Access is revoked within 24 hours of departure |
| F08 | access-control (v1) | Privileged access | Production admin access is granted just in time, for at most 4 hours, with approval |
| F09 | access-control (v1) | Authorization | Role-based access following least privilege |
| F10 | encryption-standard (v2, 2025-10-01) | Data at rest | AES-256 encryption at rest for databases, backups and object storage |
| F11 | encryption-standard (v2) | Data in transit | TLS 1.2 or higher for all external traffic; TLS 1.3 preferred |
| F12 | encryption-standard (v2) | Key management | Keys managed in AWS KMS and rotated every 12 months |
| F13 | data-retention (v3, 2026-03-01) | Customer data | Customer data is deleted within 30 days after contract end |
| F14 | data-retention (v3) | Backups | Backups are kept for 35 days |
| F15 | data-retention (v3) | Logs | Security logs are kept for 1 year |
| F16 | incident-response (v1, 2025-06-01) | Notification | Affected customers are notified within 72 hours of a confirmed breach |
| F17 | incident-response (v1) | Testing | The incident response plan is tested once a year with a tabletop exercise |
| F18 | incident-response (v1) | On-call | A security on-call rotation covers 24/7 |
| F19 | business-continuity (v1, 2025-04-01) | Objectives | RPO 4 hours, RTO 8 hours |
| F20 | business-continuity (v1) | Testing | Disaster recovery is tested twice a year |
| F21 | business-continuity (v1) | Hosting | Production runs in AWS eu-west-1 (Ireland) across multiple availability zones; backups in eu-central-1 (Frankfurt) |
| F22 | vendor-management (v1, 2025-07-01) | Assessment | Critical vendors are assessed every year |
| F23 | vendor-management (v1) | Subprocessors | The subprocessor list is published on the website and customers are notified 30 days before changes |
| F24 | vendor-management (v1) | Contracts | A data processing agreement is signed with every subprocessor |
| F25 | secure-sdlc (v1, 2025-08-01) | Code review | Every change requires review by a second engineer |
| F26 | secure-sdlc (v1) | Testing | Static analysis runs on every pull request; dependencies are scanned daily |
| F27 | secure-sdlc (v1) | Penetration testing | An independent penetration test is performed every year; the last one was in February 2026 |
| F28 | logging-monitoring (v1, 2025-05-15) | Logging | Logs are centralized and alerts are monitored 24/7 |
| F29 | hr-security (v1, 2025-03-01) | Screening | Background checks for all employees where legally permitted |
| F30 | hr-security (v1) | Agreements | Confidentiality agreements are signed at hire |
| F31 | compliance (v1, 2026-07-15) | Certifications | SOC 2 Type II report available under NDA, period ending 2026-06-30 |
| F32 | compliance (v1) | Certifications | Not ISO 27001 certified; certification planned for 2027 |
| F33 | compliance (v1) | Data location | Customer data is stored and processed in the EU only |

**Older versions (must exist, must read naturally, must never be cited for new answers):**

| policy_id | Old version | Old fact that differs |
| --- | --- | --- |
| infosec-policy | v1, 2024-03-01 | policies reviewed every 2 years; training at hire only; no phishing simulations |
| encryption-standard | v1, 2023-09-01 | keys rotated every 24 months |
| data-retention | v2, 2025-02-01 | customer data deleted within 90 days; backups kept 90 days |

### 6.2 Questionnaires

Write both as real-looking Excel files with `openpyxl` (`data/make_questionnaires.py`), and their
ground truth as YAML.

**Questionnaire A** (`data/questionnaires/acme_vendor_security_2026.xlsx`): one sheet, a 2-row title
block with merged cells, a blank row, header row at row 4: `ID | Domain | Question | Response |
Comments`. 60 questions: 52 answerable (every fact F01 to F33 at least once, some facts asked twice
in different words) and 8 unanswerable (6.3). Wording is original; do not copy any published
questionnaire.

**Questionnaire B** (`data/questionnaires/globex_supplier_review.xlsx`): two sheets ("Security",
"Privacy"), header at row 1: `#`, `Control question`, `Yes/No/N.A.`, `Explanation`. 40 questions
reworded from A (so approved answers from A should be reused), including 5 unanswerable.

Ground truth per question (`data/truth/<file>.yaml`):

```yaml
- qid: A-017
  question: "How quickly do you notify customers after a confirmed security breach?"
  facts: [F16]
  answerable: true
  short_answer: text          # yes | no | partially | text
  key_phrases: ["72 hours"]
  forbidden_phrases: []
  source: {policy_id: incident-response, version: 1, section: Notification}
```

Examples to write exactly (the agent writes the remaining questions in the same style):

| qid | Question | Answer key |
| --- | --- | --- |
| A-001 | Do you encrypt customer data at rest? If so, with what algorithm? | yes; "AES-256"; F10 |
| A-004 | How often is user access reviewed? | text; "quarter"; F06 |
| A-009 | How long are customer data retained after contract termination? | text; "30 days"; forbidden "90 days"; F13 |
| A-012 | How often are encryption keys rotated? | text; "12 months"; forbidden "24 months"; F12 |
| A-017 | How quickly do you notify customers after a confirmed security breach? | text; "72 hours"; F16 |
| A-021 | What are your RPO and RTO? | text; "4 hours", "8 hours"; F19 |
| A-026 | Is MFA enforced for administrative access? | yes; "multi-factor"; F05 |
| A-033 | Do you conduct phishing simulations? | yes; "quarter"; F04 |
| A-040 | Are you ISO 27001 certified? | no; "2027"; F32 |
| A-044 | Where is customer data hosted? | text; "EU"; F21, F33 |

### 6.3 Unanswerable questions (no fact supports them; expected status "Needs input")

1. What is the coverage amount of your cyber insurance policy?
2. Do you support customer-managed encryption keys (BYOK)?
3. Are your offices protected by 24/7 security guards?
4. Are you FedRAMP authorized?
5. How many employees have production database access?
6. Do you allow customers to perform their own penetration tests?
7. What is your data center's Uptime Institute tier?
8. Do you hold PCI DSS certification?

(Questionnaire B reuses 5 of them in different words.)

## 7. Architecture

```
ui/ (Streamlit)  ->  qc/api.py (FastAPI)  ->  services  ->  PostgreSQL + pgvector
                                                   |
   qc/ingest.py      parse PDF, DOCX, MD -> sections -> chunks -> embeddings
   qc/xlsx_io.py     detect header and question column; write answers back
   qc/retrieve.py    hybrid search over current policy chunks + answer library
   qc/draft.py       model drafts a structured answer from retrieved evidence
   qc/checks.py      code checks: citations valid, versions current, confidence rules
   qc/library.py     approved answers, staleness detection
   qc/evaluate.py    built-in evaluation and report
```

### 7.1 Database (`qc/sql/`)

```sql
policies(policy_id PK, title)
policy_versions(policy_id FK, version, effective_date, source_file, is_current, PRIMARY KEY(policy_id, version))
chunks(id PK, policy_id, version, section, text, tsv tsvector, embedding vector(384))
questionnaires(id PK, name, file_path, sheet_map jsonb, created_at)
questions(id PK, questionnaire_id FK, qid, sheet, row, col_question, col_answer, text)
drafts(id PK, question_id FK, run_id, source TEXT CHECK (source IN ('library','policies','none')),
       short_answer, explanation, citations jsonb, confidence, status, created_at)
       -- status: drafted | needs_input | approved | rejected | edited
reviews(id PK, draft_id FK, reviewer, action, final_answer, final_explanation, created_at)
answer_library(id PK, question_text, embedding vector(384), short_answer, explanation,
               citations jsonb, policy_versions jsonb, approved_by, approved_at, stale BOOLEAN DEFAULT FALSE)
run_steps(...)   -- see 00-AGENT-RULES section 7
```

### 7.2 Excel import (`qc/xlsx_io.py`)

- For each sheet, scan the first 15 rows; a header row is the first row with at least 3 non-empty
  text cells. Score each header cell against question-like names ("question", "control", "requirement",
  "description") and answer-like names ("response", "answer", "yes/no", "explanation", "comments").
- If scoring is ambiguous, ask the model once with the header row values (structured output: question
  column, answer column, explanation column or null).
- A question row is a row under the header whose question cell has 15+ characters.
- Store `sheet`, `row`, `col_question`, `col_answer` per question so export writes into the right cells.
- Export: copy the original file, write short answer into the answer column (or "Yes"/"No"/"N.A."
  when that column is a Yes/No column), explanation into the explanation or comments column, add
  "Source" and "Status" columns at the end of the header row. Never change other cells.

### 7.3 Retrieval (`qc/retrieve.py`)

1. **Library first:** cosine similarity between the question and approved, non-stale library entries;
   if >= `REUSE_THRESHOLD` (calibrate; start at 0.90), return that entry as the draft (source `library`).
2. **Policies:** hybrid score = 0.6 x vector similarity + 0.4 x normalized full-text rank, over chunks
   of current versions only; top 6.
3. If the best hybrid score is below `MIN_EVIDENCE` (calibrate), status `needs_input` without calling
   the model.

### 7.4 Drafting (`qc/draft.py`)

Structured output:

```python
class Draft(BaseModel):
    can_answer: bool
    short_answer: Literal["yes", "no", "partially", "text"] | None
    answer_text: str | None          # 1 sentence for text answers
    explanation: str | None          # 1 to 3 sentences, plain business language
    citation_chunk_ids: list[int]
    confidence: Literal["high", "medium", "low"]
```

System prompt rules: use only the given passages; cite chunk ids; if the passages do not fully answer,
set `can_answer=false`; write for a customer's security reviewer; never promise anything the passages
do not state.

### 7.5 Code checks (`qc/checks.py`), run after every draft

- Every cited chunk id must be among the retrieved chunks, and its version must be current; otherwise
  downgrade to `needs_input` and log the reason.
- `can_answer=false` or no citation means `needs_input`.
- Confidence is capped at `medium` if the cited passages come from more than 2 policies, and at `low`
  if the model's answer contains a number not present in the cited passages (simple regex check).

### 7.6 Staleness (`qc/library.py`)

When a new policy version is ingested, mark `stale = true` on every library entry whose
`policy_versions` contains an older version of that policy, and show a banner on the Library page:
"3 approved answers rely on a policy that changed".

## 8. User interface (Streamlit, `ui/`)

| Page | Contents |
| --- | --- |
| Library | Upload a policy file with version and effective date; list of policies and versions; current version marked; stale-answer banner |
| Questionnaires | Upload Excel or CSV; detected sheets and columns shown for confirmation; "Draft all" with a progress bar |
| Review | Table: qid, question, short answer, status, confidence, source; filters; side panel with draft and cited passages highlighted; Approve, Edit, Reject; reviewer name selector |
| Answer library | Approved answers, the policy versions behind them, stale flag, re-approve button |
| Export | Download the filled Excel |
| Quality | The latest `evals/report.md` rendered, plus key numbers as metrics |

## 9. Built-in evaluation (`make eval`)

Run end to end on the synthetic data:

1. Reset the database; ingest all policies (including old versions).
2. Draft Questionnaire A with an empty library.
3. Auto-approve every draft that matches ground truth (simulating a perfect reviewer), so the library
   fills as it would in real use. Count how many needed edits.
4. Draft Questionnaire B.
5. Ingest a new version of `data-retention` (v4: backups kept 30 days) and check that every library
   answer citing v3 is flagged stale.

Metrics (per questionnaire):

| Metric | Definition | Target |
| --- | --- | --- |
| Answer correctness | answerable questions whose answer contains all key phrases and no forbidden phrase | 90%+ |
| Citation correctness | cited policy, version and section equal ground truth | 90%+ |
| Stale-version citations | citations to non-current versions | 0 |
| Needs-input recall | unanswerable questions marked `needs_input` | 100% |
| Needs-input precision | `needs_input` drafts that are truly unanswerable | 85%+ |
| Edit rate | answerable drafts a reviewer had to edit | report |
| Reuse rate (B only) | B questions answered from the library | report |
| Staleness detection | stale flags raised in step 5 versus expected | 100% |
| Cost and time per questionnaire | from `run_steps` | report |

Report: `evals/report.md` with one table per questionnaire, the failures list (qid, expected, got,
reason), and the staleness check. Cost cap: `MAX_EVAL_COST_USD=1.00`.

## 10. Tests (offline)

| File | Checks |
| --- | --- |
| `test_ingest.py` | PDF, DOCX and MD produce sections with correct names; versions and `is_current` correct |
| `test_xlsx_detect.py` | header and columns found in A (title block, merged cells) and B (two sheets) |
| `test_xlsx_export.py` | answers land in the right cells; other cells unchanged; Source and Status added |
| `test_retrieve.py` | only current-version chunks returned; library hit above threshold returned first |
| `test_checks.py` | citation outside retrieved set downgraded; old-version citation downgraded; number not in passage caps confidence |
| `test_staleness.py` | new policy version flags exactly the dependent library entries |
| `test_needs_input.py` | below-evidence-threshold questions never call the model (stub call count 0) |
| `test_api.py` | upload, draft, review, export endpoints with the stub model |

## 11. Phases

### Phase 1: Skeleton and data (4 h)
Repo, Docker (pgvector), migrations, policies with old versions, renders to PDF and DOCX, both
questionnaires and their ground truth.
Acceptance: `make seed` prints 11 policies, 14 versions, 60 + 40 questions; the agent lists in
`PROGRESS.md` which facts each question covers; Faycal reviews 10 random questions.

### Phase 2: Ingestion and retrieval (4 h)
Acceptance: `test_ingest.py`, `test_retrieve.py` green; a script prints the top 3 chunks for 5 sample
questions with their versions.

### Phase 3: Excel import and export (3 h)
Acceptance: `test_xlsx_detect.py`, `test_xlsx_export.py` green; the exported A file opens in Excel or
LibreOffice with answers in the Response column.

### Phase 4: Drafting and checks (4 h)
Acceptance: `test_checks.py`, `test_needs_input.py` green; live run on 10 questions of A recorded in
`PROGRESS.md`.

### Phase 5: Library and staleness (2.5 h)
Acceptance: `test_staleness.py` green.

### Phase 6: API and UI (5 h)
Acceptance: `make demo` opens the UI; a full flow (upload A, draft, approve 5, export) works by hand.

### Phase 7: Evaluation (3 h)
Calibrate `REUSE_THRESHOLD` and `MIN_EVIDENCE` on A only (record values in `docs/decisions.md`), then
run the full `make eval`.
Acceptance: `evals/report.md` complete; Quality page shows it.

### Phase 8: Docs and polish (2.5 h)
README (template in rules file) with real results, architecture image, `docs/user-guide.md`
(one page for a non-technical reviewer), `docs/production.md` (SSO, connectors, hosting, data
handling).

## 12. What runs on a model and what does not

| Step | Model | Code |
| --- | --- | --- |
| Find header and question column | only when the heuristic is unsure | default |
| Retrieve evidence | | yes |
| Decide "Needs input" when evidence is weak | | yes (before any model call) |
| Draft answer and explanation | yes | |
| Validate citations, versions, numbers | | yes |
| Reuse approved answers | | yes |
| Staleness after a policy update | | yes |

## 13. Video script (3 minutes)

1. (0:00) The problem in one sentence over the Excel file of 60 questions.
2. (0:20) Upload policies; show that data-retention has 3 versions and only v3 is current.
3. (0:40) Upload the questionnaire; columns detected; "Draft all".
4. (1:10) Review page: a drafted answer with its cited section highlighted; a "Needs input" question
   (cyber insurance) that was not guessed.
5. (1:50) Approve and export; open the filled Excel.
6. (2:15) Upload Questionnaire B: most answers come from the library instantly.
7. (2:35) Upload a new retention policy: approved answers that relied on it are flagged.
8. (2:50) Quality page numbers.

## 14. Definition of done

- [ ] `make demo` works from a fresh clone in under 15 minutes
- [ ] All offline tests green in CI
- [ ] `evals/report.md` with real numbers; README results match it
- [ ] User guide and production notes written
- [ ] Video recorded
