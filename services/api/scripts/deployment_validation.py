"""Read-only deployment gate. Exit nonzero on failure; never print secrets or raw errors."""
import argparse
import json
from urllib.request import urlopen
from sqlalchemy import text
from app.core.config import Settings
from app.core.startup_environment_validator import validate_startup_environment
from app.db.session import build_engine


def require(condition):
    if not condition:
        raise ValueError('Deployment verification failed')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--env-file')
    parser.add_argument('--database', action='store_true')
    parser.add_argument('--artifacts', action='store_true')
    parser.add_argument('--https', action='store_true')
    args = parser.parse_args()
    checks = {}
    try:
        settings = Settings(**({'_env_file': args.env_file} if args.env_file else {}))
        checks['configuration'] = validate_startup_environment(settings)
        if settings.app_env not in ('staging', 'production'):
            raise ValueError('Deployment environment required')
        if args.database:
            engine = build_engine(settings)
            try:
                with engine.connect() as c:
                    require(c.scalar(text('SELECT current_user')) == 'creditiq_runtime')
                    require(not c.scalar(text('SELECT rolsuper OR rolcreatedb OR rolcreaterole OR rolreplication OR rolbypassrls FROM pg_roles WHERE rolname=current_user')))
                    require(not c.scalar(text("SELECT count(*) FROM pg_class WHERE relnamespace='public'::regnamespace AND relkind='r' AND (NOT relrowsecurity OR NOT relforcerowsecurity)")))
                    require(c.scalar(text("SELECT count(*) FROM pg_class WHERE relnamespace='public'::regnamespace AND relkind='r'")) == 29)
                    for role in ('anon', 'authenticated', 'service_role'):
                        require(not c.scalar(text("SELECT has_schema_privilege(:role,'public','USAGE')"), {'role': role}))
                checks['database'] = 'PASS'
            finally:
                engine.dispose()
        if args.artifacts:
            from app.services.lite_model import LiteModel
            from app.services.model_research import load_dashboard
            from app.services.customer_segmentation import load_dashboard as segments
            LiteModel(); load_dashboard(); segments()
            checks['artifacts'] = 'PASS'
        if args.https:
            for name, origin, suffix in [('api', settings.api_origin, '/health/ready'), ('frontend', settings.frontend_origin, '/login')]:
                with urlopen(origin + suffix, timeout=15) as response:
                    require(response.status == 200 and response.url.startswith(origin + '/'))
                checks[name + '_https'] = 'PASS'
        print(json.dumps({'validation_passed': True, 'checks': checks,
                          'production_ready': False, 'note': 'Backup, hosted workflows and alert delivery require separate evidence.'}))
        return 0
    except Exception as exc:
        print(json.dumps({'validation_passed': False, 'failed_type': type(exc).__name__, 'completed': checks}))
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
