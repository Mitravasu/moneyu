# MoneyU Discord Bot V1 Specification

MoneyU is a Discord bot for managing shared trip expenses inside a Discord server. It lets server members create trip groups, add members, record expenses and repayments, and compute balances and optimized settlement suggestions.

## Scope

V1 supports:

- Server-scoped trip groups.
- Active trip membership.
- One currency per trip group.
- Expense creation, editing, deletion, listing, and detail view.
- Payment recording, deletion, and listing.
- Computed status with net balances and optimized settlement suggestions.
- Soft-delete/audit logging for successful mutations.
- PostgreSQL-backed persistence.
- Slash-command-first Discord UI.

V1 does not support:

- Multi-currency trips.
- Receipt attachments.
- Bulk member add.
- Trip archive/close.
- Payment counterparty approval.
- Mixed fixed-plus-even split mode.
- Generic history command.
- Exposed audit command.

## Server And Group Model

Trip groups are scoped to a single Discord guild. A group created in one guild is inaccessible from any other guild.

Group names are unique per guild, case-insensitive. Names are normalized by trimming leading/trailing whitespace and collapsing repeated whitespace. Group names may contain spaces and punctuation and are limited to 80 characters.

Groups have exactly one ISO 4217 currency code such as `CAD`, `USD`, or `EUR`. The currency is stored uppercase. The currency can be set at group creation and may only be changed while the group has no expenses.

The creator of a group is automatically added as its first active member.

## Membership

Only active trip members can perform actions for a trip.

Trip membership is unique per group and Discord user ID. Adding an already active user is idempotent. Adding an inactive user reactivates the existing membership row.

`/trip remove-member` marks a member inactive. It is allowed only when the user has no active ledger involvement and no nonzero balance. Users with active expenses, active payments, or unresolved balances must be manually rebalanced first through expense edits/deletes and payment changes.

Inactive members:

- Do not count as "all members."
- Cannot run trip commands.
- Cannot be selected for new expenses or payments.
- Are hidden from normal `/trip members` and `/status` output.
- Remain available in historical/audit data.

If a Discord user leaves the server, their historical records remain intact. New records should involve active trip members only.

## Permissions

Trip actions are intentionally open within the trip. Any active trip member can:

- Add or remove members, subject to validation.
- Add, edit, or delete expenses.
- View status.
- View expenses/payments.

Payment operations are stricter:

- Recording a payment requires the actor to be either the `from` user or the `to` user.
- Deleting a payment requires the actor to be either the `from` user or the `to` user.

Server admins are not special in v1.

## Money

All money is stored as integer cents.

Examples:

- `12345` means `123.45`.
- `100` means `1.00`.

All entered monetary values must be positive and have at most two decimal places. V1 uses two decimal places for all currencies.

Postgres `money`, floats, and arbitrary decimal storage should not be used for persisted amounts.

## Expenses

An expense has:

- Group.
- Required name, max 80 characters.
- Optional description, max 500 characters.
- Payer, who must be an active trip member.
- Split mode: `even` or `custom`.
- Participant shares.
- Soft-delete metadata.

The payer defaults to the command user, but the command can specify another active trip member as payer.

The payer does not need to be included in the split participants. For example, Alice can pay for Bob and Carol only.

If no custom participant selection is made, expenses default to all active trip members.

All expense shares must be positive. Zero and negative shares are not allowed.

### Even Splits

In an even split, the total amount is split across selected participants.

If cents do not divide evenly:

- If the payer is included in the split, the payer absorbs the positive rounding remainder.
- If the payer is not included, the remainder is assigned among split participants using a fair cent-absorption rotation.

Cent absorption tracks only positive extra cents. It is tracked per group and user, and only users involved in the current split are candidates. When the payer is excluded, extra cents go to the participant with the lowest prior cent absorption count, tie-broken deterministically by Discord user ID.

Payer-absorbed extra cents also count toward that payer's cent-absorption total.

### Custom Splits

In a custom split, each selected participant has an explicit positive amount.

The expense total is derived from the sum of participant shares. There is no separate total amount field for custom splits.

Custom split entry uses a Discord modal with a multiline amount field prefilled with participant labels and current values when editing. The bot maps submitted lines to the selected Discord user IDs in order, not by trusting display names. The submission is rejected if the expected line count/order is invalid or any amount is invalid.

### Expense UI Flow

Expense creation starts with:

`/expense add group split_mode payer?`

Then:

1. Bot sends an ephemeral participant confirmation message defaulted to all active trip members.
2. User can click `Continue`, `Change`, or `Cancel`.
3. `Change` edits the ephemeral message to show a trip-member-only multi-select.
4. `Continue` opens the relevant modal.

Even split modal fields:

- Name.
- Optional description.
- Total amount.

Custom split modal fields:

- Name.
- Optional description.
- Multiline participant amounts.

Expense editing reuses the same flow, prefilled with existing values.

## Payments

A payment has:

- Group.
- `from` active trip member.
- `to` active trip member.
- Positive amount in cents.
- Optional note, max 500 characters.
- Soft-delete metadata.

Payments are separate ledger records. They do not mutate or mark individual expenses as paid.

`/payment record` defaults `from` to the command user. If `from` is explicitly provided, the actor must still be either `from` or `to`.

Payments must follow the current optimized settlement suggestions:

- There must be a current suggested payment edge from `from` to `to`.
- The recorded amount must be less than or equal to the current suggested amount.
- Partial payments are allowed.
- Overpayments are rejected.
- Payments between unrelated users or in the wrong direction are rejected.

Payment validation recomputes current settlement suggestions immediately before insert.

Payments are not editable in v1. Incorrect payments should be soft-deleted and re-recorded.

## Balances And Status

Balances are computed on demand from active expenses, active expense shares, and active payments. Settlement suggestions are derived state and are not stored.

Balance aggregation:

- Expense payer is credited for the total expense.
- Each participant is debited for their share.
- Payment `from` is credited.
- Payment `to` is debited.

Settlement suggestions use debtor-creditor matching in the style of Splitwise:

1. Compute each active member's net balance.
2. Users with negative net balances are debtors.
3. Users with positive net balances are creditors.
4. Greedily match debtors to creditors until all balances are zero.

`/status group` always includes both:

- Net balances.
- Optimized settlement suggestions.

Private status prioritizes the caller's own relevant debts/credits at the top, followed by the full group summary.

Public status starts with the group summary.

If the trip is fully settled, status shows a distinct settled message. Embeds use green for settled and yellow for in-progress.

Large status outputs should paginate.

## Discord Commands

V1 commands:

- `/trip create name currency`
- `/trip list`
- `/trip add-member group user`
- `/trip remove-member group user`
- `/trip members group`
- `/expense add group split_mode payer?`
- `/expense list group public?`
- `/expense show group expense`
- `/expense edit group expense`
- `/expense delete group expense`
- `/payment record group to amount from? note?`
- `/payment list group public?`
- `/payment delete group payment`
- `/status group public?`
- owner-only `/sync`

Group selection uses string autocomplete scoped to the current guild.

Expense/payment selection for edit/delete/show uses autocomplete scoped to the selected group.

`/status`, `/expense list`, and `/payment list` are ephemeral by default and accept `public:true`.

Ledger-changing command confirmations are public by default. Validation errors and UI selection flows are ephemeral.

`/trip list` and `/trip members` are public by default.

List commands show active records only. Deleted records are hidden from normal lists.

`/expense list` shows compact expense rows with payer and aggregate participant count. It omits creator metadata.

`/expense show` displays full expense details, including payer, participants, shares, description, and timestamps.

`/payment list` shows payment rows with from, to, amount, optional truncated note, and timestamp. There is no `/payment show` in v1.

## Discord Command Sync

Slash commands must be explicitly synced.

Configuration supports:

- Optional `DEV_GUILD_ID` for fast local guild-scoped auto-sync.
- Owner-only `/sync` command for manual production/global sync.

Owner-only commands use `OWNER_USER_IDS`, configured as comma-separated Discord user IDs.

## User-Facing Output

Use Discord embeds for structured responses.

Colors:

- Green: settled/successful settled state.
- Yellow: active/in-progress status.
- Red: validation/errors.
- Neutral/blurple/gray: list pages and informational output.

User-facing output should use Discord mentions such as `<@123456789>`.

Pagination is required for expense lists, payment lists, and large status outputs. Lists default to newest first, 10 records per page.

## Data Model

Recommended v1 tables:

- `guilds`
- `trip_groups`
- `trip_members`
- `expenses`
- `expense_shares`
- `payments`
- `rounding_ledger`
- `audit_log`

Discord users do not need their own table in v1. Store Discord user IDs directly on membership, expense, share, payment, and audit rows.

Straightforward database constraints should be enforced in Postgres:

- Unique normalized trip name per guild.
- Unique membership per trip/user.
- Unique share per expense/user.
- Currency code length is 3.
- Positive amounts.
- Valid foreign keys.

Cross-table lifecycle rules, such as preventing inactive users from appearing in active ledger records, are enforced in service-layer validation.

Expenses and payments rely on the trip group currency rather than storing their own currency snapshot.

## Audit

Audit records are for successful mutations only. Failed validations are not persisted in the audit table.

Audit logging happens in the same transaction as the mutation. If the audit write fails, the mutation rolls back.

Audit snapshots store exact raw persisted values:

- IDs.
- Integer cents.
- Timestamps.
- Booleans.
- Raw JSON before/after state.

Audit rows include:

- Guild ID.
- Group ID where applicable.
- Actor Discord user ID.
- Discord interaction ID when available.
- Action: create, update, delete, reactivate, deactivate, etc.
- Record type.
- Record ID.
- Before snapshot.
- After snapshot.
- Timestamp.

## Concurrency

Mutating operations should run inside database transactions.

Ledger-affecting mutations should acquire a per-trip Postgres advisory transaction lock before validation and write:

- Expense create/edit/delete.
- Payment record/delete.
- Member remove/reactivate when ledger checks are involved.
- Currency change checks.

Read-only commands such as status and list do not need advisory locks.

## Configuration

Configuration comes from environment variables loaded from `.env`.

Commit `.env.example`; ignore `.env`.

Required:

- `DISCORD_TOKEN`
- `DATABASE_URL`
- `OWNER_USER_IDS`

Optional:

- `DEV_GUILD_ID`

Startup must fail fast with clear errors if required config is missing or malformed.

Startup must also verify that the database is migrated to the Alembic head revision. If the database is behind, the bot logs a clear error and exits.

## Stack And Tooling

V1 stack:

- Python 3.12+
- `discord.py` 2.x
- PostgreSQL
- Async SQLAlchemy
- Alembic
- `uv`
- `ruff`
- `ty`
- Docker Compose

Docker Compose should include:

- Bot service.
- Postgres service.
- Persistent named Postgres volume.

Migrations are run manually, not automatically on bot startup:

```sh
docker compose run --rm bot alembic upgrade head
```

## Architecture

Discord handlers should remain thin. They should parse Discord inputs, manage Discord UI, call service-layer functions, and format responses.

Business rules should live in service-layer modules so unit tests cover the real behavior:

- Money parsing/formatting.
- Split calculations.
- Cent absorption.
- Balance aggregation.
- Settlement optimization.
- Payment validation.
- Membership validation.
- Ledger mutations and audit logging.

## Testing

V1 prioritizes unit tests for business logic:

- Money parsing and formatting.
- Even split calculations and rounding.
- Custom split validation.
- Cent absorption rotation.
- Balance aggregation.
- Settlement optimization.
- Payment validation against current suggestions.
- Membership active/inactive validation.

Discord integration tests are not required for v1.
