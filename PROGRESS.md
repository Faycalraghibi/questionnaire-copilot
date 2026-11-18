# PROGRESS

## 2026-11-18: Phase 1, skeleton and data

### What was built

- Repo skeleton: `pyproject.toml` (uv, Python 3.12, `uv_build` backend, package `qc`), `uv.lock`,
  `Makefile` with all 8 targets (`run` and `eval` print a "built in Phase 6/7" message and exit 1),
  `.env.example`, `.gitignore`, `.gitattributes` (LF), stub `README.md`.
- `docker-compose.yml` with `pgvector/pgvector:pg16` on host port 5433 and a healthcheck;
  `make up` uses `docker compose up -d --wait`.
- `qc/sql/001_init.sql`: every table from spec 7.1 plus `run_steps` (rules section 7), the `vector`
  extension, a generated `tsv` column with a GIN index, and a partial unique index allowing one
  current version per policy. `qc/db.py` applies migrations once (`schema_migrations` table) and
  resets data.
- Policies: 11 policies, 14 versions as Markdown with front matter in `data/policies/`. Three are
  sourced from `data/policies_src/` and rendered by `data/render.py`: incident-response and
  business-continuity to PDF, vendor-management to DOCX, with `manifest.yaml`. data-retention v4
  (evaluation only) is in `data/policies_updates/`.
- `data/facts.yaml`: F01 to F33 with exact marker phrases per fact.
- Ground truth: `data/truth/acme_vendor_security_2026.yaml` (60 questions, 52 answerable, 8
  unanswerable) and `data/truth/globex_supplier_review.yaml` (40 questions on Security and Privacy
  sheets, 35 answerable, 5 unanswerable, each with `reworded_from`). Every answerable question has
  `sources` and a `reference_answer`.
- `data/make_questionnaires.py` builds both `.xlsx` files from the truth YAML (A: merged 2-row
  title block, blank row, header at row 4; B: two sheets, header at row 1, Yes/No/N.A. dropdown).
- `data/seed.py` (`make seed`): render, build questionnaires, migrate, reset, load policies,
  versions and questions, print counts.
- Tests (167, offline except 3 that need the Docker database):
  - `tests/test_data.py`:
    - policy versions and dates match the spec, and each policy has 200 to 600 words;
    - each fact marker appears exactly once in its current section and in no other current policy;
    - old versions hold the old facts, and v4 differs from v3 only in Backups;
    - no current policy mentions the unanswerable topics;
    - A and B counts are right, every fact is covered, and the spec examples and unanswerable texts
      are exact;
    - truth sources match the facts, and key phrases are present in the cited sections and the
      reference answers;
    - the Excel layouts, PDF and DOCX outputs are as specified;
    - no file in the repo contains an em dash.
  - `tests/test_seed.py`: seed counts, current flags, and question cells.
- CI (`.github/workflows/ci.yml`): pgvector service, `uv sync --locked`, lint, seed, test, with
  `QC_REQUIRE_DB=1` so the database tests cannot silently skip. The workflow has not run yet because
  the repo has no remote.
- Docs: `docs/decisions.md` (D1 to D30), `docs/sources.md`, `data/LICENSES.md`.

### Acceptance output (fresh volume, generated files deleted first)

```
$ make down && make up
 Container questionnaire-copilot-db-1 Healthy
$ make seed
uv run python -m data.seed
11 policies, 14 versions, 60 + 40 questions
$ make lint
All checks passed!
31 files already formatted
$ make test
============================= 167 passed in 5.60s =============================
```

`make seed` was also run twice in a row with the same output (idempotent).

### Decisions

All approved decisions are logged in `docs/decisions.md` with their numbers. The ones that took
effect in Phase 1: D1, D5, D7, D8, D9 (reference answers written), D10 (B worded as yes/no where
natural), D13 (B qids), D19, D20. New in Phase 1:

- D23: front matter parsed in-house.
- D24: key phrase alternatives `"a | b"`.
- D25: generated binaries are git-ignored and rebuilt by seed.
- D26: truth YAML is the single source of the questionnaires.
- D27: fact marker registry.
- D28: extra realistic policy sections.
- D29: database tests skip locally when the database is down, but fail in CI.
- D30: `specs/` excluded from ruff, after `ruff format` rewrote code blocks inside the spec
  Markdown. That change was reverted, and the specs are unchanged.

### Questions

1. **F27 date.** The spec gives secure-sdlc v1 an effective date of 2025-08-01 but its fact says
   "the last one was in February 2026", which is after the effective date. Kept exactly as the spec
   says. Simplest fix if you want it: a later effective date for secure-sdlc v1 (would not change
   any test count).
2. **F19 wording.** The fact is kept verbatim as "RPO 4 hours, RTO 8 hours" inside a sentence. It
   reads slightly terse but makes the exact-once check simple.
3. **Key phrase alternatives (D24).** "a | b" is an extension of the spec's YAML format. It is used
   on 16 questions (10 in A, 6 in B); the 10 spec examples do not use it.
4. **Windows note.** uv and make were installed after this terminal session started, so this session
   called them by full path. A new Git Bash window finds them on PATH normally.

### Fact coverage per question

Key phrases: "/" separates accepted alternatives (written "|" in the YAML). Unanswerable rows show the spec 6.3 case (U1 to U8).

| qid | Question | Facts | Answerable | Key phrases | Source |
| --- | --- | --- | --- | --- | --- |
| A-001 | Do you encrypt customer data at rest? If so, with what algorithm? | F10 | yes | AES-256 | encryption-standard v2 Data at rest |
| A-002 | Is there a named owner of your information security program? | F01 | yes | Head of Security | infosec-policy v2 Governance |
| A-003 | How frequently are your security policies reviewed and updated? | F02 | yes | once a year / annual | infosec-policy v2 Governance |
| A-004 | How often is user access reviewed? | F06 | yes | quarter | access-control v1 Access reviews |
| A-005 | Do you provide security awareness training to employees? How often? | F03 | yes | hire, every year / annual | infosec-policy v2 Training |
| A-006 | Is access removed promptly when an employee leaves? Within what timeframe? | F07 | yes | 24 hours | access-control v1 Offboarding |
| A-007 | How is privileged access to production systems granted? | F08 | yes | just in time, 4 hours | access-control v1 Privileged access |
| A-008 | Do you follow the principle of least privilege when assigning permissions? | F09 | yes | least privilege | access-control v1 Authorization |
| A-009 | How long are customer data retained after contract termination? | F13 | yes | 30 days | data-retention v3 Customer data |
| A-010 | What protocol and version protect data in transit over public networks? | F11 | yes | TLS 1.2 | encryption-standard v2 Data in transit |
| A-011 | Where are encryption keys stored and managed? | F12 | yes | KMS | encryption-standard v2 Key management |
| A-012 | How often are encryption keys rotated? | F12 | yes | 12 months | encryption-standard v2 Key management |
| A-013 | How long are backups retained? | F14 | yes | 35 days | data-retention v3 Backups |
| A-014 | How long do you keep security logs? | F15 | yes | 1 year / one year / 12 months | data-retention v3 Logs |
| A-015 | What is the coverage amount of your cyber insurance policy? | - | no | - | needs input (U1) |
| A-016 | Do you have a documented incident response plan, and is it tested? | F17 | yes | tabletop | incident-response v1 Testing |
| A-017 | How quickly do you notify customers after a confirmed security breach? | F16 | yes | 72 hours | incident-response v1 Notification |
| A-018 | Is there round-the-clock coverage for responding to security incidents? | F18 | yes | 24/7 | incident-response v1 On-call |
| A-019 | Do you support customer-managed encryption keys (BYOK)? | - | no | - | needs input (U2) |
| A-020 | Is there a disaster recovery plan, and how often is it tested? | F20 | yes | twice | business-continuity v1 Testing |
| A-021 | What are your RPO and RTO? | F19 | yes | 4 hours, 8 hours | business-continuity v1 Objectives |
| A-022 | Are your offices protected by 24/7 security guards? | - | no | - | needs input (U3) |
| A-023 | Which cloud provider and region host your production environment? | F21 | yes | AWS, eu-west-1 / Ireland | business-continuity v1 Hosting |
| A-024 | Where are backups stored? | F21 | yes | eu-central-1 / Frankfurt | business-continuity v1 Hosting |
| A-025 | Do you assess the security of your critical vendors? How often? | F22 | yes | every year / annual | vendor-management v1 Assessment |
| A-026 | Is MFA enforced for administrative access? | F05 | yes | multi-factor | access-control v1 Authentication |
| A-027 | Do you publish a list of your subprocessors? | F23 | yes | website | vendor-management v1 Subprocessors |
| A-028 | Are customers notified before a new subprocessor is added? | F23 | yes | 30 days | vendor-management v1 Subprocessors |
| A-029 | Are data processing agreements in place with your subprocessors? | F24 | yes | data processing agreement | vendor-management v1 Contracts |
| A-030 | Are you FedRAMP authorized? | - | no | - | needs input (U4) |
| A-031 | Are code changes peer reviewed before they are merged? | F25 | yes | second engineer | secure-sdlc v1 Code review |
| A-032 | Do you use static code analysis? | F26 | yes | pull request | secure-sdlc v1 Testing |
| A-033 | Do you conduct phishing simulations? | F04 | yes | quarter | infosec-policy v2 Training |
| A-034 | How often are third-party dependencies scanned for vulnerabilities? | F26 | yes | daily | secure-sdlc v1 Testing |
| A-035 | Do you engage an independent firm for penetration testing? When was the most recent test? | F27 | yes | February 2026 | secure-sdlc v1 Penetration testing |
| A-036 | How many employees have production database access? | - | no | - | needs input (U5) |
| A-037 | Are logs collected centrally and monitored? | F28 | yes | 24/7 | logging-monitoring v1 Logging |
| A-038 | Do you perform background checks on new employees? | F29 | yes | background check | hr-security v1 Screening |
| A-039 | Do employees sign confidentiality or non-disclosure agreements? | F30 | yes | hire | hr-security v1 Agreements |
| A-040 | Are you ISO 27001 certified? | F32 | yes | 2027 | compliance v1 Certifications |
| A-041 | Do you have a SOC 2 Type II report? | F31 | yes | NDA | compliance v1 Certifications |
| A-042 | Do you allow customers to perform their own penetration tests? | - | no | - | needs input (U6) |
| A-043 | Is customer data ever stored or processed outside the EU? | F33 | yes | EU | compliance v1 Data location |
| A-044 | Where is customer data hosted? | F21, F33 | yes | EU | business-continuity v1 Hosting; compliance v1 Data location |
| A-045 | Who reviews the information security program at executive level? | F01 | yes | CEO | infosec-policy v2 Governance |
| A-046 | What is your data center's Uptime Institute tier? | - | no | - | needs input (U7) |
| A-047 | Is production deployed across multiple availability zones? | F21 | yes | availability zones | business-continuity v1 Hosting |
| A-048 | Is multi-factor authentication required for everyone who accesses production systems? | F05 | yes | multi-factor | access-control v1 Authentication |
| A-049 | Do you use role-based access control? | F09 | yes | role-based | access-control v1 Authorization |
| A-050 | What is your breach notification timeline for affected customers? | F16 | yes | 72 hours | incident-response v1 Notification |
| A-051 | Do you hold PCI DSS certification? | - | no | - | needs input (U8) |
| A-052 | Do you enforce a minimum TLS version for external connections? | F11 | yes | 1.2 | encryption-standard v2 Data in transit |
| A-053 | Are backups encrypted? | F10 | yes | AES-256 | encryption-standard v2 Data at rest |
| A-054 | After a customer leaves, how soon is their data purged from your systems? | F13 | yes | 30 days | data-retention v3 Customer data |
| A-055 | Is there a formal annual review of your security policies? | F02 | yes | once a year / annual | infosec-policy v2 Governance |
| A-056 | How often do you test your disaster recovery procedures? | F20 | yes | twice | business-continuity v1 Testing |
| A-057 | Is security awareness training repeated every year? | F03 | yes | every year / annual | infosec-policy v2 Training |
| A-058 | How frequently is the incident response plan exercised? | F17 | yes | once a year / annual | incident-response v1 Testing |
| A-059 | Are security alerts monitored outside business hours? | F28 | yes | 24/7 | logging-monitoring v1 Logging |
| A-060 | Do you have a process for assessing vendor security risk? | F22 | yes | every year / annual | vendor-management v1 Assessment |
| B-001 | Is all customer data encrypted while stored, including backups? (from A-001) | F10 | yes | AES-256 | encryption-standard v2 Data at rest |
| B-002 | Are user access rights re-certified on a periodic basis? (from A-004) | F06 | yes | quarter | access-control v1 Access reviews |
| B-003 | Is multi-factor authentication mandatory for administrator accounts? (from A-026) | F05 | yes | multi-factor | access-control v1 Authentication |
| B-004 | Are the accounts of leavers disabled within one business day? (from A-006) | F07 | yes | 24 hours | access-control v1 Offboarding |
| B-005 | Is privileged access to production time-limited and approved? (from A-007) | F08 | yes | 4 hours | access-control v1 Privileged access |
| B-006 | Are cryptographic keys rotated at least once a year? (from A-012) | F12 | yes | 12 months | encryption-standard v2 Key management |
| B-007 | Is TLS 1.2 or later required for connections from the internet? (from A-010) | F11 | yes | TLS 1.2 | encryption-standard v2 Data in transit |
| B-008 | Do all staff complete security awareness training every year? (from A-057) | F03 | yes | every year / annual | infosec-policy v2 Training |
| B-009 | Do you run simulated phishing campaigns against your staff? (from A-033) | F04 | yes | quarter | infosec-policy v2 Training |
| B-010 | Is there a written incident response plan that is exercised regularly? (from A-016) | F17 | yes | tabletop | incident-response v1 Testing |
| B-011 | Will you inform us within 72 hours if a confirmed breach affects our data? (from A-017) | F16 | yes | 72 hours | incident-response v1 Notification |
| B-012 | Is a member of the security team on call at all times? (from A-018) | F18 | yes | 24/7 | incident-response v1 On-call |
| B-013 | Are disaster recovery tests performed at least annually? (from A-056) | F20 | yes | twice | business-continuity v1 Testing |
| B-014 | Is your recovery point objective 4 hours or less? (from A-021) | F19 | yes | 4 hours | business-continuity v1 Objectives |
| B-015 | Is source code peer reviewed before it is merged? (from A-031) | F25 | yes | second engineer | secure-sdlc v1 Code review |
| B-016 | Are automated code security scans run on every pull request? (from A-032) | F26 | yes | static analysis | secure-sdlc v1 Testing |
| B-017 | Has an independent penetration test been completed in the last 12 months? (from A-035) | F27 | yes | February 2026 | secure-sdlc v1 Penetration testing |
| B-018 | Are security logs retained for at least 12 months? (from A-014) | F15 | yes | 1 year / one year / 12 months | data-retention v3 Logs |
| B-019 | Is security monitoring performed around the clock? (from A-059) | F28 | yes | 24/7 | logging-monitoring v1 Logging |
| B-020 | Are employees background checked before they start? (from A-038) | F29 | yes | background check | hr-security v1 Screening |
| B-021 | What limit does your cyber liability insurance provide? (from A-015) | - | no | - | needs input (U1) |
| B-022 | Can customers bring their own encryption keys to your platform? (from A-019) | - | no | - | needs input (U2) |
| B-023 | Does your service hold a FedRAMP authorization at any impact level? (from A-030) | - | no | - | needs input (U4) |
| B-024 | Are backups stored in a different region from production? (from A-024) | F21 | yes | eu-central-1 / Frankfurt | business-continuity v1 Hosting |
| B-025 | Is production hosted across more than one availability zone? (from A-047) | F21 | yes | availability zones | business-continuity v1 Hosting |
| B-026 | Is customer data held only within the European Union? (from A-043) | F33 | yes | EU | compliance v1 Data location |
| B-027 | Is customer data deleted within 30 days of contract termination? (from A-009) | F13 | yes | 30 days | data-retention v3 Customer data |
| B-028 | Are backups containing customer data deleted within 35 days? (from A-013) | F14 | yes | 35 days | data-retention v3 Backups |
| B-029 | Is a list of your subprocessors publicly available? (from A-027) | F23 | yes | website | vendor-management v1 Subprocessors |
| B-030 | Do you give customers advance notice of subprocessor changes? (from A-028) | F23 | yes | 30 days | vendor-management v1 Subprocessors |
| B-031 | Is a DPA signed with each of your subprocessors? (from A-029) | F24 | yes | data processing agreement | vendor-management v1 Contracts |
| B-032 | Are critical suppliers reviewed for security every year? (from A-025) | F22 | yes | every year / annual | vendor-management v1 Assessment |
| B-033 | Do employees sign confidentiality agreements when they join? (from A-039) | F30 | yes | hire | hr-security v1 Agreements |
| B-034 | Can you share a current SOC 2 Type II report with us? (from A-041) | F31 | yes | NDA | compliance v1 Certifications |
| B-035 | Do you hold an ISO 27001 certification? (from A-040) | F32 | yes | 2027 | compliance v1 Certifications |
| B-036 | Are your security policies reviewed by management every year? (from A-055) | F02 | yes | once a year / annual | infosec-policy v2 Governance |
| B-037 | Is access granted on a least-privilege, role-based model? (from A-049) | F09 | yes | least privilege | access-control v1 Authorization |
| B-038 | Are you certified against the PCI DSS standard? (from A-051) | - | no | - | needs input (U8) |
| B-039 | May our security team run its own penetration test against your service? (from A-042) | - | no | - | needs input (U6) |
| B-040 | In which region is your primary production environment hosted? (from A-023) | F21 | yes | eu-west-1 / Ireland | business-continuity v1 Hosting |

## 2026-11-18: Phase 1 review decisions

- **F27 date conflict (D31):** Changed `secure-sdlc` v1 `effective_date` to `2026-03-01` in
  `data/policies/secure-sdlc-v1.md` and `tests/test_data.py`; facts kept unchanged.
- **Key phrase alternatives (D24):** Approved for `"a | b"` syntax; Phase 7 correctness check must
  apply these alternatives.

## 2026-11-18: Phase 2, ingestion and retrieval

### What was built

- Dependencies: added `pdfplumber` (0.11.10), `sentence-transformers` (6.3.0), and CPU-only `torch`
  (2.15.0+cpu) via `[tool.uv.sources]` (`pytorch-cpu` index, decision D17).
- `qc/sql/002_chunk_hash.sql`: added `text_hash` column and index to `chunks`.
- `qc/embed.py`: `Embedder` protocol, `E5Embedder` (`intfloat/multilingual-e5-small` with `query: `
  and `passage: ` prefixes and `normalize_embeddings=True`), `FakeEmbedder` for deterministic offline
  unit tests (decision D18).
- `data/render.py` and `qc/ingest.py`:
  - PDF headings rendered in bold 14pt (`SectionHeading`) and detected by fontname/size via
    `pdfplumber`; DOCX headings rendered in built-in `Heading 2` and detected by style name.
  - Markdown, PDF, and DOCX parse into sections, split into paragraph-bounded chunks, and store
    SHA-256 `text_hash`. `ingest_policy` skips re-embedding when `(section, text_hash)` is
    unchanged and updates `is_current` on `policy_versions`.
- `data/seed.py`: switched to `qc.ingest` (`sync_policies`), keeping `make seed` idempotent.
- `qc/retrieve.py`: library-first cosine search (`REUSE_THRESHOLD=0.90`, non-stale only), followed
  by hybrid search (`0.6 * vec_score + 0.4 * (ft_raw / (ft_raw + 1))`) over `is_current = TRUE`
  chunks using OR-joined `websearch_to_tsquery` (decision D2), plus `search_policies_fulltext`.
- `data/check_retrieval.py`: Phase 2 acceptance script printing top 3 chunks for 5 sample questions.
- Tests: `tests/test_ingest.py` (including section-name equality across all 3 rendered files vs
  source Markdown, and hash-skip idempotency) and `tests/test_retrieve.py` (including non-current
  exclusion in both hybrid and full-text-only search, library reuse, and `@pytest.mark.slow` real
  E5 retrieval).
- `.github/workflows/ci.yml`: added `HF_HOME` and `actions/cache@v4` so slow E5 tests run in CI.

### Acceptance output

```
$ make seed   # first run
11 policies, 14 versions, 60 + 40 questions (72 chunks: 72 embedded, 0 cached)
$ make seed   # second run (idempotent)
11 policies, 14 versions, 60 + 40 questions (72 chunks: 0 embedded, 72 cached)
$ make lint
All checks passed!
38 files already formatted
$ make test
============================= 175 passed in 24.18s =============================
$ uv run python -m data.check_retrieval

A-003: How frequently are your security policies reviewed and updated?
  1. infosec-policy v2 | Governance (score=0.6660, vec=0.8877, ft=0.3333)
  2. encryption-standard v2 | Review (score=0.6146, vec=0.8761, ft=0.2222)
  3. vendor-management v1 | Assessment (score=0.6007, vec=0.8530, ft=0.2222)

A-009: How long are customer data retained after contract termination?
  1. data-retention v3 | Customer data (score=0.6663, vec=0.9054, ft=0.3077)
  2. vendor-management v1 | Contracts (score=0.5997, vec=0.8329, ft=0.2500)
  3. compliance v1 | Data location (score=0.5899, vec=0.8166, ft=0.2500)

A-012: How often are encryption keys rotated?
  1. encryption-standard v2 | Key management (score=0.6131, vec=0.8551, ft=0.2500)
  2. encryption-standard v2 | Data at rest (score=0.5649, vec=0.8165, ft=0.1875)
  3. incident-response v1 | On-call (score=0.5632, vec=0.8435, ft=0.1429)

A-019: Do you support customer-managed encryption keys (BYOK)?
  [unanswerable] best_score=0.5900
  1. encryption-standard v2 | Key management (score=0.5900, vec=0.8167, ft=0.2500)
  2. compliance v1 | Data location (score=0.5762, vec=0.8123, ft=0.2222)
  3. logging-monitoring v1 | Scope (score=0.5619, vec=0.8114, ft=0.1875)

A-044: Where is customer data hosted?
  1. compliance v1 | Data location (score=0.6131, vec=0.8552, ft=0.2500)
  2. data-retention v3 | Customer data (score=0.6079, vec=0.8313, ft=0.2727)
  3. encryption-standard v2 | Scope (score=0.5604, vec=0.8090, ft=0.1875)
```

### Decisions and notes

- `A-019` (BYOK, unanswerable) scores `0.5900` against `encryption-standard v2 | Key management`,
  close to `A-012` (`0.6131`) and `A-044` (`0.6131`). `MIN_EVIDENCE` will catch completely off-topic
  questions, while near-miss unanswerables (BYOK, customer pentests, PCI) will also rely on the
  Phase 4 prompt rule ("absence of a statement is not a No", decision D16).
- `tests/test_data.py` updated to check `Heading 2` in rendered DOCX to match the Phase 2
  rendering rule.

### Questions

None.

## 2026-11-18: Phase 3, Excel import and export

### What was built

- `qc/xlsx_io.py`:
  - `read_questionnaire`: scans the first 15 rows per sheet for a header row (>= 3 non-empty text
    cells), scores headers across the 3 column groups (decision D3: question, answer, explanation)
    plus optional ID column, calls an optional `fallback_resolver` once when ambiguous, and extracts
    questions (15+ chars) with `sheet`, `row`, `col_question`, `col_answer`. Supports `.xlsx` and
    `.csv`.
  - `export_questionnaire`: copies the source file and writes answers into the detected answer
    column (applying decision D10 for Yes/No/N.A. columns), explanations into the explanation or
    comments column, and appends `Source` and `Status` columns at the end of the header row without
    modifying any other cells. Supports `.xlsx` and `.csv` (decision D13).
- `data/seed.py`: switched from `read_known_layout` to `qc.xlsx_io.read_questionnaire` (decision D1).
- Tests:
  - `tests/test_xlsx_detect.py` (4 tests): A layout (merged title block, header row 4, 60 questions),
    B layout (two sheets, `B-001`..`B-040`), ambiguous header fallback resolver called once, CSV
    detection.
  - `tests/test_xlsx_export.py` (3 tests): A export (answers in `Response`, `Source` and `Status`
    appended, merged title and question cells untouched), B export (Yes/No/N.A. rules per D10), CSV
    export.

### Acceptance output

```
$ make seed
11 policies, 14 versions, 60 + 40 questions (72 chunks: 0 embedded, 72 cached)
$ make lint
All checks passed!
41 files already formatted
$ make test
============================= 182 passed in 29.14s =============================
```

### Decisions and notes

- `qc/xlsx_io.py` accepts an optional `fallback_resolver` callable for ambiguous headers so Phase 3
  stays decoupled until the LLM wrapper is built in Phase 4.

### Questions

None.
