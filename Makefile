# Recipes are single commands with no shell-specific syntax, so each line also runs as-is in
# PowerShell. On Windows run `make` from Git Bash.

.PHONY: up down seed run test eval lint demo

up:
	docker compose up -d --wait

down:
	docker compose down -v

seed:
	uv run python -m data.seed

run:
	uv run python -m qc.run_all

test:
	uv run pytest -m "not live"

eval:
	uv run python -m qc.evaluate

lint:
	uv run ruff check .
	uv run ruff format --check .

demo: up seed run
