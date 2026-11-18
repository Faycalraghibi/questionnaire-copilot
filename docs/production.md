# Production Architecture Notes

Questionnaire Copilot is a standalone MVP built for local single-team evaluation with synthetic data. Moving to a multi-user production deployment requires the additions below.

## 1. Authentication and SSO

- **Current MVP:** No user login; reviewer names come from the `REVIEWERS` environment variable (`D13`).
- **Production:** Place the API and UI behind OIDC/SAML SSO (Okta, Microsoft Entra ID, or Google Workspace). Map SSO claims to roles (`admin`, `reviewer`, `viewer`) and record the authenticated user's subject ID in `reviews.reviewer` and `answer_library.approved_by`.

## 2. Policy and Questionnaire Connectors

- **Current MVP:** Manual file upload (PDF, DOCX, Markdown, XLSX, CSV) stored on local disk (`var/uploads/`).
- **Production:**
  - Read-only connectors to Google Drive, SharePoint, or Confluence via webhooks/scheduled sync so policy updates trigger automatic re-ingestion and staleness flagging.
  - Store uploaded files and exported spreadsheets in encrypted object storage (AWS S3 or GCS) with pre-signed download URLs instead of local filesystem paths.

## 3. Hosting and Scaling

- **Current MVP:** `make run` starts a single FastAPI process and Streamlit app on localhost backed by Docker PostgreSQL 16 (`pgvector`).
- **Production:**
  - Managed PostgreSQL 16 with `pgvector` (e.g., AWS RDS or Cloud SQL) with HNSW/IVFFlat vector indexes on `chunks.embedding` and `answer_library.embedding`.
  - Run FastAPI behind a reverse proxy/load balancer and offload batch `Draft all` jobs to a background worker queue (Celery, Dramatiq, or Cloud Tasks) so large 300-question spreadsheets do not block HTTP requests.
  - Cache `intfloat/multilingual-e5-small` in a dedicated inference container or GPU/CPU embedding service.

## 4. Data Handling and Security

- **Encryption:** TLS 1.2+ in transit; KMS-managed encryption at rest for database volumes, backups, and object storage.
- **Tenant isolation:** Add `tenant_id` to `policies`, `chunks`, `questionnaires`, `drafts`, `answer_library`, and `run_steps` with PostgreSQL Row-Level Security (RLS) if hosting multiple customers.
- **Model data privacy:** Route LLM calls through zero-data-retention enterprise endpoints (OpenAI Enterprise / Azure OpenAI / Anthropic Commercial) and redact PII before logging `run_steps.input`.
- **Auditability:** `run_steps` and `reviews` provide an immutable audit trail of every prompt, retrieved chunk, token count, cost, and human approval.
