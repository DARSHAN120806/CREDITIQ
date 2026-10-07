# CreditIQ Supabase schema migration report

Date: 2026-10-07  
Mode: `RESEARCH_ONLY`  
`release_ready=false`

## Result

**Schema migration succeeded.** Supabase Session Pooler authenticated with SQLAlchemy over
TLS (`verify-full`) to PostgreSQL 17.11. Alembic applied the existing migration chain through
`20261003_0003` to an empty `public` schema. No application data was transferred.

## Migration review

The Alembic graph is linear:

| Revision | Upgrade operations | Safety notes |
|---|---|---|
| `20261003_0001` | Creates the initial 24 application tables, indexes, constraints, three helper functions, and integrity/immutability triggers. | Upgrade contains schema creation; destructive `DROP` operations are in `downgrade()`. No extension installation or data rewrite. |
| `20261003_0002` | Adds three authentication/audit indexes. | No table or row changes. |
| `20261003_0003` | Creates four installment tables, an index, and immutability triggers. | No data rewrite. |

The mapped SQLAlchemy schema contains 28 application tables. The SQL uses PostgreSQL
features supported by 17.11 (UUIDs, JSONB, partial indexes, PL/pgSQL, constraints and
triggers); no external extension is requested by the migration chain. The target was
rechecked immediately before execution: no public base tables and no
`public.alembic_version` existed. That satisfied the empty-target precondition.

## Verification

- SQLAlchemy authentication/query: **passed**.
- Target server: **PostgreSQL 17.11**.
- Alembic upgrade: **passed**; current revision is `20261003_0003`.
- `public.alembic_version`: **exists**, with revision `20261003_0003`.
- Application tables: **28 created**, matching all 28 registered SQLAlchemy tables.
- Total public base tables: **29** (28 application tables plus `alembic_version`).
- Missing or extra application tables: **none**.
- Alembic metadata check: **passed**, “No new upgrade operations detected.”
- Exact row-count check across the 28 application tables: **all empty**.
- Data migration: **not performed**.

The earlier local PostgreSQL inspection found revision `20261003_0003` and 28 application
tables. Supabase now matches that migration head and mapped table inventory. This migration
execution report verifies names/counts and Alembic metadata consistency against the current
models; the local PostgreSQL server was stopped during this session, so no fresh live
source-to-target column-by-column database diff was run.

## Scope and next gate

No application code, models, authentication, ML artifacts, or data were modified. Only the
Supabase schema and this report were written. Keep local PostgreSQL as the data source of
truth until a separate, reviewed data-transfer plan is executed and source/target counts,
hashes, constraints, indexes, triggers, and auth records are validated.

The database still contains no users or application records. Runtime application flows
against the new Supabase schema have not yet been tested. `mode=RESEARCH_ONLY` and
`release_ready=false` remain unchanged.
