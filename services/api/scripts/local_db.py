"""Operate only the isolated Milestone 2 cluster, never an arbitrary database."""
import argparse
import json
import os
from pathlib import Path
import subprocess

from alembic import command
from alembic.config import Config
from sqlalchemy import URL, create_engine, text

from app.core.config import API_ROOT, Settings

HOME = API_ROOT / '.postgres'


def owner_url(database='creditiq'):
    if database not in ('creditiq', 'creditiq_migration_test'):
        raise ValueError('Only the isolated project databases are supported')
    password = json.loads((HOME / 'local-admin.json').read_text())['password']
    return URL.create('postgresql+psycopg', username='creditiq_owner', password=password,
                      host='127.0.0.1', port=55432, database=database)


def migration_config(connection=None):
    config = Config(str(API_ROOT / 'alembic.ini'))
    if connection is not None:
        config.attributes['connection'] = connection
    return config


def grant_application_access(connection):
    """Runtime grants shared by the isolated operator setup and integration tests."""
    connection.execute(text('REVOKE ALL ON SCHEMA public FROM PUBLIC'))
    connection.execute(text('GRANT USAGE ON SCHEMA public TO creditiq_app'))
    connection.execute(text('GRANT SELECT, INSERT ON ALL TABLES IN SCHEMA public TO creditiq_app'))
    connection.execute(text('REVOKE ALL ON alembic_version FROM creditiq_app'))
    connection.execute(text('GRANT UPDATE, DELETE ON users, user_profiles, auth_sessions, loan_applications, data_consents, model_deployments, scoring_jobs, explanations, reports, outbox_events TO creditiq_app'))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['start', 'stop', 'upgrade', 'verify'])
    args = parser.parse_args()
    if args.action in ('start', 'stop'):
        pg_bin = Path(os.environ.get('CREDITIQ_PG_BIN', r'C:\Program Files\PostgreSQL\18\bin'))
        cmd = [str(pg_bin / 'pg_ctl.exe'), '-D', str(HOME / 'data'), '-w']
        cmd += (['-l', str(HOME / 'server.log'), '-o', '-h 127.0.0.1 -p 55432', 'start']
                if args.action == 'start' else ['-m', 'fast', 'stop'])
        # File redirection prevents Windows child processes holding capture pipes open.
        with (HOME / 'control.log').open('a') as output:
            subprocess.run(cmd, check=True, timeout=60, stdin=subprocess.DEVNULL,
                           stdout=output, stderr=output,
                           creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        print(f'Project-local PostgreSQL {args.action} completed.')
        return
    if args.action == 'upgrade':
        engine = create_engine(owner_url(), connect_args={'connect_timeout': 5})
        try:
            with engine.begin() as connection:
                command.upgrade(migration_config(connection), 'head')
                grant_application_access(connection)
            print('Development schema upgraded; restricted application grants applied.')
        finally:
            engine.dispose()
        return
    settings = Settings()
    engine = create_engine(settings.database_url, connect_args={'connect_timeout': 5})
    try:
        with engine.connect() as connection:
            result = connection.execute(text('SELECT current_database(), current_user, version()')).one()
            count = connection.execute(text("SELECT count(*) FROM information_schema.tables WHERE table_schema='public' AND table_name <> 'alembic_version'")).scalar_one()
            print(json.dumps({'database': result[0], 'role': result[1], 'version': result[2],
                              'visible_application_tables': count, 'mode': settings.mode,
                              'release_ready': settings.release_ready}, indent=2))
    finally:
        engine.dispose()


if __name__ == '__main__':
    main()
