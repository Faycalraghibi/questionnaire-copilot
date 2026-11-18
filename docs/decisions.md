# Decisions

Decisions approved before Phase 1 keep the numbers of the pre-build review (D1 to D22). Later
decisions continue from D23. Each entry says when it takes effect.

## Contradictions in the spec

- **D1 (Phase 1).** Phase 1 acceptance asks `make seed` for counts that need ingestion (Phase 2) and
  Excel detection (Phase 3). In Phase 1 the seed registers policies and versions from Markdown front
  matter and the render manifest, and reads questions with the generator's known layouts
  (`data/make_questionnaires.py: LAYOUTS`). Phases 2 and 3 switch the seed to the real ingest and
  import code.
- **D2 (Phase 2).** Hybrid retrieval uses an absolute full-text score, `ts_rank_cd(tsv, query, 32)`
  (rank / (rank + 1), range 0 to 1), not min-max normalization per query, so `MIN_EVIDENCE` can
  trigger. The text query uses OR semantics between terms (`plainto_tsquery` would AND every word).
- **D3 (Phase 3).** Header scoring uses three name groups: question (question, control, requirement,
  description), answer (response, answer, yes/no), explanation (explanation, comments).
- **D4 (Phase 7, 8).** Thresholds are calibrated on Questionnaire A, so the report and README label A
  "calibration set" and B "held-out".

## Gaps in the spec

- **D5 (Phase 1).** PDF and DOCX policies get their version and effective date from
  `data/policies/manifest.yaml`, written by `data/render.py`; the UI asks for them on upload.
  incident-response and business-continuity are rendered to PDF, vendor-management to DOCX. Their
  Markdown sources live in `data/policies_src/` and are never ingested, so no fact is duplicated.
- **D6 (Phase 2).** PDF section headings are detected by font size with `pdfplumber`.
- **D7 (Phase 1, 7).** data-retention v4 lives in `data/policies_updates/data-retention-v4.md`,
  effective 2026-11-01, identical to v3 except "Backups are kept for 30 days". The seed never loads
  it; only the evaluation step 5 does.
- **D8 (Phase 1, 7).** Ground truth uses `sources: [...]` (a list). A citation is correct when at
  least one truth source is cited and no cited source falls outside the truth set.
- **D9 (Phase 1, 7).** Ground truth has a `reference_answer` for every answerable question. The
  simulated reviewer in the evaluation: answerable and correct, approve; answerable but wrong or
  `needs_input`, edit to the reference answer and truth citations, approve, count as an edit;
  unanswerable and `needs_input`, not added to the library; unanswerable but answered, reject.
- **D10 (Phase 3).** Export to a Yes/No/N.A. column: yes to "Yes", no to "No", partially to
  "Partially"; a text answer leaves the cell blank and its text goes to the explanation column;
  `needs_input` leaves it blank. Questionnaire B questions are worded as yes/no where natural (34 of
  the 35 answerable questions; B-040 is a text question).
- **D11 (Phase 7).** Key and forbidden phrases match case-insensitively against short answer, answer
  text and explanation together. When the truth short answer is yes or no, the drafted short answer
  must also be equal.
- **D12 (Phase 6).** Re-approving a stale answer is a simple side-by-side view inside the Answer
  library page (old answer next to the same section of the current policy version), not a separate
  screen. Saving records the current versions.
- **D13 (Phase 1, 3, 6).** Questionnaire B qids are `B-001` to `B-040` across both sheets in order.
  Reviewer names come from a `REVIEWERS` environment variable with three synthetic names. CSV
  questionnaires export as CSV with Source and Status columns added.
- **D14 (Phase 8).** Phase 8 acceptance: `make lint`, `make test`, no em dash in the repo, and every
  README number equal to `evals/report.md`.

## Risks

- **D15 (Phase 2, 7).** e5 embeddings are used with the `query: ` prefix on both sides for
  question-to-question similarity; `REUSE_THRESHOLD` starts at 0.90 and is calibrated in Phase 7.
- **D16 (Phase 4).** Near-miss unanswerable questions (BYOK near F12, customer pentests near F27,
  production database access count near F08, PCI near F31 and F32) get a prompt rule "absence of a
  statement is not a No" and one test fixture each.
- **D17 (Phase 2).** torch is installed from the CPU-only index through `[tool.uv.sources]` to keep
  `make demo` small.
- **D18 (Phase 2).** Unit tests use a deterministic fake embedder. Tests with the real embedding
  model are marked `slow` and run in CI too, with the Hugging Face cache restored between runs.
- **D19 (Phase 1).** `.gitattributes` forces LF line endings (the Windows machine has
  `core.autocrlf=true`).
- **D20 (Phase 1).** The database host port comes from `POSTGRES_PORT`, default 5433.
- **D21 (Phase 6).** `make run` starts FastAPI and Streamlit through a Python launcher
  (`qc/run_all.py`) so it behaves the same in Git Bash, PowerShell and CI.
- **D22 (Phase 4, 7).** The model wrapper tracks spend and stops the evaluation at
  `MAX_EVAL_COST_USD=1.00`.

## Decisions made during the build

- **D23 (Phase 1).** YAML front matter is parsed in `qc/markdown.py` with `pyyaml`; no
  python-frontmatter dependency (not approved).
- **D24 (Phase 1, 7).** A key phrase may list alternatives as `"a | b"`; either one matches. Used where
  a model may say the same thing in different words ("once a year | annual", "eu-west-1 | Ireland").
  The spec's own examples are unchanged. Approved in Phase 1 review; the Phase 7 correctness check
  must apply these alternatives.
- **D25 (Phase 1).** Generated files (rendered PDF and DOCX, `manifest.yaml`, both `.xlsx`
  questionnaires) are git-ignored and rebuilt by `make seed`. The sources are the Markdown policies
  and `data/truth/*.yaml`.
- **D26 (Phase 1).** `data/truth/*.yaml` is the single source for questions and answers; the Excel
  files are built from it.
- **D27 (Phase 1).** `data/facts.yaml` lists each fact with exact marker phrases, so a test can prove
  that each fact appears exactly once in the current version of its policy and section, and in no
  other current policy.
- **D28 (Phase 1).** Policies contain extra sections (Purpose, Scope, Exceptions and similar) besides
  the sections the spec names, so they read like real policies and reach 200 to 600 words. None of
  them states anything about the 8 unanswerable topics; a test checks this by keyword.
- **D29 (Phase 1).** Database tests share the development database and the seed resets it. They skip
  when the database is not running, except in CI where `QC_REQUIRE_DB=1` makes that a failure.
- **D30 (Phase 1).** `specs/` is excluded from ruff, because ruff formats code blocks inside Markdown
  and was rewriting the spec files.
- **D31 (Phase 1 review).** `secure-sdlc` v1 `effective_date` changed from `2025-08-01` to
  `2026-03-01` so it is not earlier than fact F27 ("the last one was in February 2026"). Facts are
  kept unchanged.
- **D32 (Phase 7).** Calibrated thresholds on Questionnaire A only (D4): `MIN_EVIDENCE = 0.541`
  (lowest answerable score on A is `0.5423`, catching 4 of 8 unanswerable questions without an LLM
  call) and `REUSE_THRESHOLD = 0.92` (highest cosine similarity between different-fact questions on
  A is `0.9164` for A-016 vs A-020).
