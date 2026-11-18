# Sources

Documentation read before using a tool, SDK or flag, with the date read and the version pinned.

## Phase 1 (read 2026-11-18)

| Topic | Source | What it confirmed |
| --- | --- | --- |
| uv dependency groups | https://docs.astral.sh/uv/concepts/projects/dependencies/ | `[dependency-groups] dev = [...]`; the dev group is installed by default |
| uv sync | https://docs.astral.sh/uv/concepts/projects/sync/ | `uv sync --locked` fails instead of updating a stale lockfile |
| uv project config | https://docs.astral.sh/uv/concepts/projects/config/ | The project is installed only when `[build-system]` is declared |
| uv build backend | https://docs.astral.sh/uv/concepts/build-backend/ | `uv_build>=0.13.9,<0.14`; `module-name = "qc"`, `module-root = ""` for a flat layout |
| uv_build version | https://pypi.org/pypi/uv-build/json | Latest 0.13.9, same as installed uv |
| pgvector | https://github.com/pgvector/pgvector | Image tag `pgvector/pgvector:pg16`; `CREATE EXTENSION vector`; latest 0.8.7 (also confirmed in the running container) |
| Docker Compose `--wait` | `docker compose up --help` (Compose v5.6.1, local) | `--wait` waits for services to be healthy |
| GitHub service containers | https://docs.github.com/en/actions/use-cases-and-examples/using-containerized-services/creating-postgresql-service-containers | `services:` with `--health-cmd` options and `ports` for jobs on the runner host |
| setup-uv | https://github.com/astral-sh/setup-uv and the GitHub releases API | Latest v10.3.3, pinned by commit `68559e99cc807c1eb7e9238fd43a15bba460eec2`; input `enable-cache` |
| actions/checkout | GitHub releases API | Latest v7.0.1 (2026-07-20) |

Not re-read for Phase 1. These libraries are used only through long-stable calls, and the tests
check the output files directly: openpyxl (`merge_cells`, `DataValidation`), reportlab platypus
(`SimpleDocTemplate`, `rl_config.invariant`), python-docx (`add_heading`, `core_properties`),
psycopg 3 (`connect`, `execute`, `executemany`, `Jsonb`).

## Pinned versions (uv.lock, Phase 1)

| Package | Version |
| --- | --- |
| Python | 3.12.16 (uv-managed) |
| uv / uv_build | 0.13.9 |
| psycopg, psycopg-binary | 3.3.9 |
| pydantic | 2.14.3 |
| pydantic-settings | 2.16.3 |
| openpyxl | 3.1.5 |
| reportlab | 5.1.0 |
| python-docx | 1.2.0 |
| pyyaml | 6.0.3 |
| pytest | 9.2.0 |
| ruff | 0.17.5 |
| pgvector extension (Docker) | 0.8.7 |
