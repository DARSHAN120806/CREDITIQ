"""Read-only migration verification; emits counts/digests, never row contents or URLs."""
import argparse
import hashlib
import json
from pathlib import Path

from sqlalchemy import create_engine, text
from sqlalchemy.pool import NullPool

from app.core.config import Settings
from app.db.base import Base
from app.db import models  # noqa: F401


def snapshot(connection):
    connection.execute(text("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY"))
    connection.execute(text("SET LOCAL TIME ZONE 'UTC'"))
    connection.execute(text("SET LOCAL extra_float_digits = 3"))
    result = {
        "server_version": connection.execute(text("SHOW server_version")).scalar_one(),
        "revision": connection.execute(text("SELECT version_num FROM public.alembic_version")).scalar_one(),
        "tables": {},
    }
    for table in sorted(Base.metadata.tables.values(), key=lambda value: value.name):
        # Names come exclusively from repository metadata, never command-line input.
        order = ', '.join('"' + col.name + '"' for col in table.primary_key.columns)
        digest, count = hashlib.sha256(), 0
        rows = connection.execution_options(stream_results=True).execute(text(
            f'SELECT row_to_json(t)::text FROM public."{table.name}" t ORDER BY {order}'
        ))
        for row in rows:
            value = row[0].encode('utf-8')
            digest.update(len(value).to_bytes(8, 'big'))
            digest.update(value)
            count += 1
        rows.close()
        result["tables"][table.name] = {"rows": count, "sha256": digest.hexdigest()}
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    engine = create_engine(Settings().migration_url, poolclass=NullPool,
                           hide_parameters=True, connect_args={"connect_timeout": 5})
    try:
        with engine.connect() as connection:
            result = snapshot(connection)
        # Refuse to overwrite an earlier verification record.
        with args.output.open('x', encoding='utf-8') as output:
            json.dump(result, output, indent=2)
    finally:
        engine.dispose()


if __name__ == '__main__':
    main()
