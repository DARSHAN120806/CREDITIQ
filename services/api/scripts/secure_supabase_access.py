"""Operator-only, atomic lockdown of CreditIQ's backend-only public schema.

Default is read-only. --apply requires the active Supabase operator connection.
No policies grant Data API access: CreditIQ authorization lives in FastAPI.
"""
import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import create_engine, text
from sqlalchemy.pool import NullPool

from app.core.config import Settings
from app.db import models  # noqa: F401
from app.db.base import Base

ROLES = ("anon", "authenticated", "service_role")
TABLES = sorted([t.name for t in Base.metadata.tables.values()] + ["alembic_version"])


def audit(c):
    tables = [dict(r) for r in c.execute(text("""
        SELECT relname, relrowsecurity, relforcerowsecurity, relacl::text,
               pg_get_userbyid(relowner) AS owner
        FROM pg_class WHERE relnamespace='public'::regnamespace AND relkind='r'
        ORDER BY relname
    """)).mappings()]
    permissions = {}
    for role in ROLES:
        permissions[role] = {
            "schema_usage": c.scalar(text("SELECT has_schema_privilege(:r,'public','USAGE')"), {"r": role}),
            "tables": {},
        }
        rows = c.execute(text("""
            SELECT relname, p, has_table_privilege(:r, oid, p) AS allowed
            FROM pg_class CROSS JOIN unnest(ARRAY['SELECT','INSERT','UPDATE',
                'DELETE','TRUNCATE','REFERENCES','TRIGGER']) p
            WHERE relnamespace='public'::regnamespace AND relkind='r'
        """), {"r": role})
        for table, privilege, allowed in rows:
            permissions[role]["tables"].setdefault(table, {})[privilege] = allowed
    return {"tables": tables, "permissions": permissions,
            "policies": [dict(r) for r in c.execute(text("SELECT * FROM pg_policies WHERE schemaname='public'")).mappings()],
            "schema_acl": c.scalar(text("SELECT nspacl::text FROM pg_namespace WHERE nspname='public'")),
            "defaults": [dict(r) for r in c.execute(text("SELECT pg_get_userbyid(defaclrole) AS owner, defaclnamespace::regnamespace::text AS schema, defaclobjtype, defaclacl::text FROM pg_default_acl")).mappings()]}


def fingerprints(c):
    c.execute(text("SET LOCAL TIME ZONE 'UTC'"))
    c.execute(text("SET LOCAL extra_float_digits=3"))
    result = {}
    for table in TABLES:
        rows = sorted(c.execute(text(f'SELECT row_to_json(t)::text FROM public."{table}" t')).scalars())
        result[table] = {"rows": len(rows), "sha256": hashlib.sha256(json.dumps(rows).encode()).hexdigest()}
    return result


def verify(c):
    result = audit(c)
    assert all(t["relrowsecurity"] and t["relforcerowsecurity"] for t in result["tables"])
    # Only the explicitly provisioned backend role may have access policies.
    assert all(p["roles"] == ["creditiq_runtime"] and
               p["policyname"] in {"creditiq_runtime_select", "creditiq_runtime_insert", "creditiq_runtime_update"}
               for p in result["policies"])
    assert not c.scalar(text("""
        SELECT count(*) FROM information_schema.column_privileges
        WHERE table_schema='public' AND grantee IN ('PUBLIC','anon','authenticated','service_role')
    """))
    assert not c.scalar(text("""
        SELECT count(*) FROM pg_proc p CROSS JOIN
            unnest(ARRAY['anon','authenticated','service_role']) r
        WHERE pronamespace='public'::regnamespace AND has_function_privilege(r,p.oid,'EXECUTE')
    """))
    for role, access in result["permissions"].items():
        assert not access["schema_usage"], role
        assert not any(any(v.values()) for v in access["tables"].values()), role
        # Real role-switched SQL, not merely inspection of ACL strings.
        for table in TABLES:
            with c.begin_nested() as savepoint:
                c.execute(text(f'SET LOCAL ROLE "{role}"'))
                try:
                    c.execute(text(f'SELECT * FROM public."{table}" LIMIT 0'))
                except Exception as exc:
                    if getattr(exc.orig, "sqlstate", None) != "42501":
                        raise
                    savepoint.rollback()
                else:
                    raise AssertionError(f"Unexpected access: {role}/{table}")
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise SystemExit("Refusing to overwrite existing evidence")
    settings = Settings()
    assert settings.db_hosting == "supabase"
    engine = create_engine(settings.migration_url, poolclass=NullPool, hide_parameters=True,
                           connect_args={"connect_timeout": 5})
    evidence = {"timestamp": datetime.now(timezone.utc).isoformat(), "applied": args.apply}
    try:
        with engine.begin() as c:
            c.execute(text("SET LOCAL lock_timeout='5s'"))
            c.execute(text("SET LOCAL statement_timeout='30s'"))
            evidence["before"] = audit(c)
            assert sorted(t["relname"] for t in evidence["before"]["tables"]) == TABLES
            assert c.scalar(text("SELECT version_num FROM public.alembic_version")) == "20261003_0003"
            assert c.scalar(text("SELECT current_user")) == "postgres"
            assert all(p["roles"] == ["creditiq_runtime"] and p["policyname"].startswith("creditiq_runtime_")
                       for p in evidence["before"]["policies"]), "Review unexpected policies before changing access"
            assert not c.scalar(text("SELECT count(*) FROM pg_class WHERE relnamespace='public'::regnamespace AND relkind IN ('v','m','S','f')")), "Review additional public relations"
            assert sorted(c.execute(text("SELECT proname FROM pg_proc WHERE pronamespace='public'::regnamespace")).scalars()) == [
                "creditiq_protect_explanation", "creditiq_reject_mutation", "creditiq_touch_updated_at"
            ], "Review additional public functions"
            if args.apply:
                c.execute(text("LOCK TABLE " + ",".join(f'public."{t}"' for t in TABLES) + " IN ACCESS EXCLUSIVE MODE"))
                evidence["data_before"] = fingerprints(c)
                c.execute(text("REVOKE ALL ON SCHEMA public FROM PUBLIC, anon, authenticated, service_role"))
                for table in TABLES:
                    c.execute(text(f'ALTER TABLE public."{table}" ENABLE ROW LEVEL SECURITY'))
                    c.execute(text(f'ALTER TABLE public."{table}" FORCE ROW LEVEL SECURITY'))
                    c.execute(text(f'REVOKE ALL ON TABLE public."{table}" FROM PUBLIC, anon, authenticated, service_role'))
                    columns = c.execute(text("SELECT attname FROM pg_attribute WHERE attrelid=CAST(:t AS regclass) AND attnum>0 AND NOT attisdropped"), {"t": "public." + table}).scalars().all()
                    names = ",".join('"' + n + '"' for n in columns)
                    c.execute(text(f'REVOKE ALL ({names}) ON TABLE public."{table}" FROM PUBLIC, anon, authenticated, service_role'))
                c.execute(text("REVOKE ALL ON ALL FUNCTIONS IN SCHEMA public FROM PUBLIC, anon, authenticated, service_role"))
                c.execute(text("REVOKE ALL ON ALL SEQUENCES IN SCHEMA public FROM PUBLIC, anon, authenticated, service_role"))
                for kind in ("TABLES", "SEQUENCES", "FUNCTIONS"):
                    c.execute(text(f"ALTER DEFAULT PRIVILEGES FOR ROLE postgres IN SCHEMA public REVOKE ALL ON {kind} FROM PUBLIC, anon, authenticated, service_role"))
                c.execute(text("ALTER DEFAULT PRIVILEGES FOR ROLE postgres REVOKE EXECUTE ON FUNCTIONS FROM PUBLIC"))
                evidence["after"] = verify(c)
                evidence["data_after"] = fingerprints(c)
                assert evidence["data_before"] == evidence["data_after"], "Data changed; rolling back"
                c.execute(text("NOTIFY pgrst, 'reload schema'"))
        if args.apply:
            with engine.begin() as c:
                evidence["committed_verification"] = verify(c)
                evidence["revision"] = c.scalar(text("SELECT version_num FROM public.alembic_version"))
        with args.output.open("x", encoding="utf-8") as f:
            json.dump(evidence, f, indent=2)
        print(json.dumps({"applied": args.apply, "tables": len(TABLES), "revision": evidence.get("revision"), "evidence": str(args.output)}))
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()

