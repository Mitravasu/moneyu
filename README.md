# MoneyU

Discord bot for shared trip expenses and settlement suggestions.

## Local Setup

```sh
cp .env.example .env
uv sync
uv run pytest
uv run ruff check
uv run ruff format --check
uv run ty check
```

Run Postgres and apply migrations:

```sh
docker compose up -d postgres
uv run alembic upgrade head
```

Start the bot:

```sh
uv run moneyu
```

The bot validates config and verifies that the database is at the Alembic head revision on startup. It does not run migrations automatically.
