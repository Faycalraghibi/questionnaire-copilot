# 00-AGENT-RULES: How the coding agent works on every product

This file is a working method. It is not a shared codebase: every product repository is complete on
its own and copies whatever small helpers it needs.

---

## 1. Context

Each product spec describes a complete, standalone product that answers a real client need. The
repository is public and is used to win freelance contracts: a client must be able to clone it, run
one command, and use the product in under 15 minutes with synthetic data.

## 2. Working rules

1. **Phases.** Each spec has numbered phases. Finish one phase, run its acceptance commands, then stop
   for review. Never start the next phase without the message `Continue with Phase <n>.`
2. **`PROGRESS.md`** at the repo root. After each phase, append: date, phase, what was built,
   acceptance output (trimmed), decisions, open questions. Never delete earlier entries.
3. **One commit per task**, Conventional Commits (`feat:`, `fix:`, `test:`, `docs:`, `chore:`).
4. **No invented facts.** Synthetic data values that tests depend on are given in the spec; use them
   exactly. When the spec is silent, choose the simplest option and record it in `PROGRESS.md`.
5. **No secrets in git.** Keys only in `.env` (git-ignored); `.env.example` lists every variable.
6. **Check current documentation** before using any SDK, API, model name or CLI flag that may have
   changed. Record the pages read in `docs/sources.md` and pin installed versions.
7. **Ask before adding a dependency** not listed in the spec; record any addition and why.
8. **Offline tests.** `make test` never calls a paid API. Code that calls a model goes through the
   wrapper in section 6, which has a `stub` provider for tests and CI. Live tests are marked
   `@pytest.mark.live`.
9. **No em dashes** in any file, including README, docs and comments.
10. **Real numbers only.** README results come from the product's own evaluation report. If a target
    is missed, the README says so.

## 3. Repository layout

```
<repo>/
  README.md  PROGRESS.md  Makefile  pyproject.toml  docker-compose.yml  .env.example  .gitignore
  <package>/        # the product code (name given in the spec)
  ui/               # user interface if the spec has one
  tests/            # pytest
  evals/            # built-in quality evaluation and its report
  data/             # synthetic data and the scripts that generate it
  docs/             # architecture.png, decisions.md, sources.md, user guide
  .github/workflows/ci.yml
```

## 4. Default stack

| Concern | Choice |
| --- | --- |
| Python | 3.12 with `uv` |
| Lint and format | `ruff` |
| Tests | `pytest` (markers `live`, `slow`) |
| API | `fastapi`, `uvicorn` |
| Models and config | `pydantic` v2, `pydantic-settings` |
| Database | PostgreSQL 16 (`pgvector/pgvector:pg16` when vectors are needed), `psycopg[binary]` v3 |
| Embeddings (when needed) | `sentence-transformers` with `intfloat/multilingual-e5-small` (384 dims, local, handles Arabic) |
| UI | `streamlit` (multipage) unless the spec says otherwise |

## 5. Makefile targets (every repo)

```
make up      # start containers, wait for health
make down    # stop and remove volumes
make seed    # generate and load synthetic data
make run     # start the product
make test    # offline tests
make eval    # run the built-in evaluation, write evals/report.md
make lint    # ruff check and format check
make demo    # up + seed + run: the one command a client runs
```

## 6. Model wrapper (`<package>/llm.py`)

```python
@dataclass
class LLMUsage:
    input_tokens: int
    output_tokens: int
    cost_usd: float      # from a price table in config, dated
    latency_ms: int
    model: str

class LLM(Protocol):
    def complete(self, system: str, messages: list[dict], *, max_tokens: int = 800) -> tuple[str, LLMUsage]: ...
    def structured(self, system: str, messages: list[dict], schema: type[BaseModel], *, max_tokens: int = 1500) -> tuple[BaseModel, LLMUsage]: ...
    def vision_structured(self, system: str, image_bytes: bytes, schema: type[BaseModel]) -> tuple[BaseModel, LLMUsage]: ...  # only where the spec needs images

def get_llm() -> LLM: ...   # LLM_PROVIDER = openai | anthropic | stub; LLM_MODEL from env
```

The `stub` provider reads canned outputs from `tests/fixtures/stub/*.json`. Default model: the
cheapest current general model of the chosen provider; look it up and record it.

## 7. Run log

Every product that calls a model writes one row per step to a `run_steps` table (or SQLite table):
`run_id, item_id, step, input (json), output (json), tokens_in, tokens_out, cost_usd, latency_ms,
error, created_at`. The product's own UI and evaluation read from it. This is how a client sees why
the system did what it did.

## 8. README template (product framing)

```markdown
# <Product name>: <one-line promise>

<Two sentences: who it is for and what it saves them.>
Video (3 min): <link>

## The problem
## What it does
## Results (from evals/report.md)
| Metric | Value |
## How it works
![architecture](docs/architecture.png)
## Run it
    cp .env.example .env    # add one API key
    make demo
## What runs on a model and what does not
## Limits and what a production version adds
## About
Built by Faycal Raghibi with synthetic data. Not client work. Available for custom versions on Upwork: <link>
```

## 9. Kickoff prompt

```
You are building a complete product repository. Read specs/00-AGENT-RULES.md, then specs/<SPEC FILE>.
Follow the working rules in section 2 exactly. Start with Phase 1 only. When its acceptance commands
pass, update PROGRESS.md, commit, and stop. Summarize what you built and anything you were unsure of.
```

## 10. Honesty rules

- Synthetic or public data only; licences in `data/LICENSES.md`.
- Nothing from Oracle, the research internship or any client in any repo.
- No claim of client results anywhere.
- Anything that sends messages runs in draft or sandbox mode by default.
