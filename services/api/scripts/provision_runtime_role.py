"""Provision the reviewed SQL; stage private configuration without activating it."""
import json
import re
import secrets
from pathlib import Path

from psycopg import sql
from sqlalchemy import create_engine, text
from sqlalchemy.pool import NullPool

from app.core.config import API_ROOT, Settings
from scripts.secure_supabase_access import audit, fingerprints


def main():
    settings = Settings()
    if settings.db_hosting != 'supabase' or settings.pg_user.split('.')[0] != 'postgres':
        raise SystemExit('Provision using the existing Supabase operator configuration')
    private = API_ROOT / '.postgres'
    candidate = private / 'runtime-candidate.env'
    backup = private / 'runtime-role-previous.env'
    operator = private / 'supabase-operator.env'
    evidence_path = private / 'runtime-provisioning.json'
    if any(p.exists() for p in (candidate, backup, operator, evidence_path)):
        raise SystemExit('Existing provisioning files: inspect state before retrying')
    source = (API_ROOT / '.env').read_text(encoding='utf-8-sig')
    password = secrets.token_urlsafe(48)
    username = 'creditiq_runtime.' + settings.pg_user.split('.', 1)[1]
    staged = source
    for name, value in {'CREDITIQ_PG_USER': username, 'CREDITIQ_PG_PASSWORD': password}.items():
        staged, count = re.subn(r'^' + name + r'=.*$', name + '=' + value, staged, flags=re.M)
        if count != 1:
            raise SystemExit('Expected exactly one active runtime setting: ' + name)
    staged = re.sub(r'^CREDITIQ_MIGRATION_DATABASE_URL=.*\n?', '', staged, flags=re.M)
    backup.write_text(source, encoding='utf-8')
    candidate.write_text(staged, encoding='utf-8')
    operator.write_text('CREDITIQ_MIGRATION_DATABASE_URL=' +
                        settings.database_url.render_as_string(hide_password=False) + '\n', encoding='utf-8')
    evidence = {}
    engine = create_engine(settings.database_url, poolclass=NullPool, hide_parameters=True)
    try:
        with engine.begin() as c:
            c.execute(text("SET LOCAL lock_timeout='5s'"))
            c.execute(text("SET LOCAL statement_timeout='30s'"))
            if c.scalar(text('SELECT current_user')) != 'postgres':
                raise RuntimeError('Expected operator role')
            if c.scalar(text('SELECT version_num FROM public.alembic_version')) != '20261003_0003':
                raise RuntimeError('Unexpected schema revision')
            evidence['old_role'] = dict(c.execute(text('SELECT rolname,rolsuper,rolinherit,rolcreaterole,rolcreatedb,rolcanlogin,rolreplication,rolbypassrls FROM pg_roles WHERE rolname=current_user')).mappings().one())
            evidence['old_memberships'] = c.execute(text('SELECT roleid::regrole::text FROM pg_auth_members WHERE member=(SELECT oid FROM pg_roles WHERE rolname=current_user)')).scalars().all()
            evidence['before'] = audit(c)
            evidence['data_before'] = fingerprints(c)
            if evidence['before']['policies']:
                raise RuntimeError('Expected the audited policy-free RLS state')
            raw = c.connection.driver_connection
            with raw.cursor() as cursor:
                cursor.execute(Path(__file__).with_name('runtime_role.sql').read_text())
                cursor.execute(sql.SQL('ALTER ROLE creditiq_runtime LOGIN PASSWORD {}').format(sql.Literal(password)))
            evidence['data_after'] = fingerprints(c)
            if evidence['data_before'] != evidence['data_after']:
                raise RuntimeError('Concurrent data change: provisioning rolled back')
            evidence['after'] = audit(c)
        evidence_path.write_text(json.dumps(evidence, indent=2), encoding='utf-8')
        print('Runtime role provisioned. Candidate configuration staged; active .env unchanged.')
    finally:
        engine.dispose()


if __name__ == '__main__':
    main()
