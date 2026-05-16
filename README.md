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

Required environment variables:

- `DISCORD_TOKEN`: bot token from the Discord Developer Portal.
- `DATABASE_URL`: async SQLAlchemy URL, for example `postgresql+asyncpg://moneyu:moneyu@localhost:5432/moneyu`.
- `OWNER_USER_IDS`: comma-separated Discord user IDs allowed to run `/sync`.

Optional:

- `DEV_GUILD_ID`: Discord server ID for fast guild-scoped command sync during development.

Run Postgres and apply migrations:

```sh
docker compose up -d postgres
uv run alembic upgrade head
```

Start the bot:

```sh
uv run python -m moneyu.bot
```

The bot validates config and verifies that the database is at the Alembic head revision on startup. It does not run migrations automatically. Logs are written to stdout/stderr and include startup, migration checks, command execution, autocomplete failures, and expense modal submissions.

## Docker

`docker-compose.yml` overrides `DATABASE_URL` for the `bot` service to use `postgres` as the database host. Keep `localhost` in `.env` for local commands like `uv run alembic upgrade head`; inside Compose, `localhost` would point at the bot container instead of the Postgres container.

Start Postgres:

```sh
docker compose up -d postgres
```

Run migrations from the app image:

```sh
docker compose run --rm bot uv run --no-dev alembic upgrade head
```

Start the bot:

```sh
docker compose up bot
```

Stop services:

```sh
docker compose stop
```

## Discord Setup

1. Create a Discord application and bot in the Discord Developer Portal.
2. Invite the bot to your server with `applications.commands` and bot permissions.
3. Put the bot token in `.env` as `DISCORD_TOKEN`.
4. Put your Discord user ID in `OWNER_USER_IDS`.
5. For development, set `DEV_GUILD_ID` to your test server ID so commands sync quickly.
6. Start the bot, then run `/sync` if commands need to be refreshed.

## Slash Command Usage

Create and inspect trips:

```text
/trip create name:"Montreal Weekend" currency:"CAD"
/trip list
/trip members group:"Montreal Weekend"
```

Manage members:

```text
/trip add-member group:"Montreal Weekend" user:@Alice
/trip remove-member group:"Montreal Weekend" user:@Alice
```

Add expenses:

```text
/expense add group:"Montreal Weekend" split_mode:even
/expense add group:"Montreal Weekend" split_mode:custom payer:@Alice
```

The bot opens an ephemeral participant confirmation. Use `Continue` to open the modal, `Change` to select participants, or `Cancel` to stop. Even expenses ask for name, description, and total amount. Custom expenses ask for name, description, and one amount line per selected participant.

Review and edit expenses:

```text
/expense list group:"Montreal Weekend"
/expense show group:"Montreal Weekend" expense:"1: Dinner"
/expense edit group:"Montreal Weekend" expense:"1: Dinner"
/expense delete group:"Montreal Weekend" expense:"1: Dinner"
```

Check balances:

```text
/status group:"Montreal Weekend"
/status group:"Montreal Weekend" public:true
```

Record payments:

```text
/payment record group:"Montreal Weekend" to:@Alice amount:"25.00"
/payment record group:"Montreal Weekend" from_user:@Bob to:@Alice amount:"25.00" note:"settlement"
/payment list group:"Montreal Weekend"
/payment delete group:"Montreal Weekend" payment:"1: Bob -> Alice"
```

Payments must match the current optimized settlement suggestion and may be partial up to the suggested amount.

## Development Notes

Useful checks:

```sh
uv run ruff format --check
uv run ruff check
uv run pytest
uv run ty check
```

Current known gaps:

- List/status pagination is not implemented yet.
- DB-backed integration tests are still needed.
- Live Discord smoke testing requires a real bot token and test server.
