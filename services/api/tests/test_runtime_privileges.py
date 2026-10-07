"""Execute the exact deployed runtime grants/RLS in an isolated, rolled-back test."""
from pathlib import Path

from sqlalchemy import text

from test_database import engine


def test_runtime_security_sql(engine):
    with engine.connect() as c:
        transaction = c.begin()
        try:
            assert c.scalar(text('SELECT current_database()')) == 'creditiq_migration_test'
            names = c.execute(text("SELECT tablename FROM pg_tables WHERE schemaname='public'")).scalars().all()
            for name in names:
                c.execute(text(f'ALTER TABLE public."{name}" ENABLE ROW LEVEL SECURITY'))
                c.execute(text(f'ALTER TABLE public."{name}" FORCE ROW LEVEL SECURITY'))
            with c.connection.driver_connection.cursor() as cursor:
                cursor.execute((Path(__file__).parents[1] / 'scripts/runtime_role.sql').read_text())
            c.execute(text('SET LOCAL ROLE creditiq_runtime'))
            flags = c.execute(text('SELECT rolsuper,rolcreatedb,rolcreaterole,rolreplication,rolbypassrls FROM pg_roles WHERE rolname=current_user')).one()
            assert not any(flags)
            assert not c.scalar(text("SELECT has_schema_privilege(current_user,'public','CREATE')"))
            assert c.scalar(text("SELECT has_column_privilege(current_user,'users','password_hash','UPDATE')"))
            assert not c.scalar(text("SELECT has_column_privilege(current_user,'users','role','UPDATE')"))
            assert c.scalar(text("SELECT count(*) FROM pg_policies WHERE schemaname='public' AND 'creditiq_runtime'=ANY(roles)")) == 41
            for table in names:
                assert not c.scalar(text("SELECT has_table_privilege(current_user,:t,'DELETE') OR has_table_privilege(current_user,:t,'TRUNCATE')"), {'t': table})
            # Actual insert under FORCE RLS exercises both grant and backend-only policy.
            identity = c.scalar(text("INSERT INTO users(normalized_email,password_hash) VALUES ('runtime-rollback@example.test','test-only') RETURNING id"))
            c.execute(text("UPDATE users SET password_hash='new-test-only' WHERE id=:id"), {'id': identity})
            for statement in ('SELECT * FROM alembic_version', 'SELECT * FROM outbox_events',
                              "UPDATE users SET role='ADMIN' WHERE false", 'DELETE FROM users WHERE false',
                              'ALTER TABLE users DISABLE ROW LEVEL SECURITY'):
                with c.begin_nested() as savepoint:
                    try:
                        c.execute(text(statement))
                    except Exception as exc:
                        assert getattr(exc.orig, 'sqlstate', None) == '42501'
                        savepoint.rollback()
                    else:
                        raise AssertionError('Forbidden runtime operation succeeded')
        finally:
            transaction.rollback()
