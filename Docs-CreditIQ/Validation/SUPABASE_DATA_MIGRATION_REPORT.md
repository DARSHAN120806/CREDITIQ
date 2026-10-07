# CreditIQ local PostgreSQL to Supabase data migration

Date: 2026-10-07  
Source: local PostgreSQL 18.6, `creditiq`, Alembic `20261003_0003`  
Target: Supabase PostgreSQL 17.11 via Session Pooler, database `postgres`  
Target revision after migration: `20261003_0003`

## Outcome

**Data migration and read-only validation succeeded.** All 28 application tables were
transferred. Local and Supabase row counts match table-by-table (280 rows total), and
deterministic content fingerprints match for every table. The source database and its
records were retained. No application code, authentication logic, model, or ML artifact
was modified.

## Backup and export

A complete custom-format `pg_dump` of the local `creditiq` database was created and its
archive listing verified before any Supabase data write:

- `.postgres/backups/creditiq-local-pre-supabase-20261007.dump`
- 134,562 bytes; SHA-256 `2ea617f267be5e42eeba5abf70a15ea7ea9b5d613cafe61c2b484bd962391ee7`
- Contains 29 table-data entries: 28 application tables and `alembic_version`.

A separate data-only archive was created for the 28 application tables. Its archive
listing was verified to contain all 28 table-data entries:

- `.postgres/backups/creditiq-application-data-20261007.dump`
- 37,011 bytes; SHA-256 `64c37061442329bfe1a9894fcf93b230ad7b0de793683192da77f75a1c0584bd`

The data import used `pg_restore --single-transaction --exit-on-error`; Alembic state was
not included in the data-only import. The target was checked immediately beforehand and
had the expected revision with zero rows in all 28 application tables.

## Table-by-table row counts

| Application table | Local | Supabase | Match |
|---|---:|---:|:---:|
| `application_history` | 8 | 8 | Yes |
| `application_versions` | 8 | 8 | Yes |
| `audit_events` | 103 | 103 | Yes |
| `auth_sessions` | 29 | 29 | Yes |
| `data_consents` | 0 | 0 | Yes |
| `decisions` | 8 | 8 | Yes |
| `explanations` | 0 | 0 | Yes |
| `feature_snapshot_sources` | 0 | 0 | Yes |
| `feature_snapshots` | 8 | 8 | Yes |
| `installment_analyses` | 2 | 2 | Yes |
| `installment_imports` | 2 | 2 | Yes |
| `installment_payments` | 42 | 42 | Yes |
| `installment_schedules` | 24 | 24 | Yes |
| `loan_applications` | 8 | 8 | Yes |
| `loan_outcomes` | 0 | 0 | Yes |
| `loan_quotes` | 8 | 8 | Yes |
| `model_deployments` | 0 | 0 | Yes |
| `model_versions` | 1 | 1 | Yes |
| `outbox_events` | 0 | 0 | Yes |
| `policy_versions` | 1 | 1 | Yes |
| `predictions` | 8 | 8 | Yes |
| `reports` | 0 | 0 | Yes |
| `risk_scores` | 8 | 8 | Yes |
| `scoring_jobs` | 8 | 8 | Yes |
| `segment_assignments` | 0 | 0 | Yes |
| `source_snapshots` | 0 | 0 | Yes |
| `user_profiles` | 2 | 2 | Yes |
| `users` | 2 | 2 | Yes |
| **Total** | **280** | **280** | **Yes** |

The `alembic_version` table remains at `20261003_0003` on Supabase. The target has 28
application tables plus that migration table. No row-count mismatches were found.

## Read-only validation

- Confirmed target revision `20261003_0003` after import.
- Compared all 28 table names and exact row counts; all match.
- Compared deterministic row-content SHA-256 fingerprints, sorting by primary key and
  canonicalizing UUIDs, timestamps, decimals, JSON and binary values; all 28 match.
- During the first fingerprint pass, prediction floats appeared different because the
  pooler session used `extra_float_digits=0` and rounded text output. Repeated both
  read-only snapshots with `SET LOCAL extra_float_digits=3`; all prediction values and
  all other table fingerprints then matched. No data was changed during this check.
- Alembic metadata check: **no new upgrade operations detected**.
- Unvalidated public constraints: **0**.
- Import was atomic: one transaction, exit-on-error; the import completed successfully.

## Limits and next steps

This confirms database-level copy fidelity and constraints, not end-to-end application
login or frontend behavior against Supabase. The local database remains intact as the
source copy. Keep the backup and both archives private; they contain authentication and
application records. Perform application smoke tests and decide on a controlled runtime
cutover separately. Status remains `mode=RESEARCH_ONLY`, `release_ready=false`.
