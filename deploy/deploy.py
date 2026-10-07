"""Thin deployment adapters. Requires preconfigured provider resources and private env values.

Usage: python deploy/deploy.py {railway,render,coolify,compose,systemd} [api|web]
Never invokes training, data migration, or automatic Alembic upgrades.
"""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]


def required(key):
    value = os.environ.get(key)
    if not value or '<' in value:
        raise ValueError('Required deployment variable missing: ' + key)
    return value


def request(url, headers=None, method='POST'):
    parsed = urlsplit(url)
    if parsed.scheme != 'https' or not parsed.hostname or parsed.username or parsed.password:
        raise ValueError('Provider endpoint must use HTTPS without URL credentials')
    with urlopen(Request(url, headers=headers or {}, method=method, data=b''), timeout=30) as result:
        if not 200 <= result.status < 300:
            raise RuntimeError('Provider rejected request')
    print('Deployment requested; verify provider completion and run deployment_validation.py.')


def railway_context(component):
    """Upload an explicit clean context, never the working tree with --no-gitignore."""
    target = ROOT / '.deployment-context'
    target.mkdir(exist_ok=False)
    directories = ['services/api/app', 'ml/creditiq_ml', 'apps/web', '.deployment-assets', 'deploy']
    for name in directories:
        source = ROOT / name
        if any(p.is_symlink() for p in source.rglob('*')):
            raise ValueError('Symlinks are forbidden in deployment sources')
        shutil.copytree(source, target / name, ignore=shutil.ignore_patterns(
            '.env*', '*.env', '.postgres', '.venv', '__pycache__', 'node_modules', '.next*',
            'test-results', 'playwright-report', 'tests', '*.tsbuildinfo', '.git'))
    for name in ['.dockerignore', 'services/api/requirements-lock.txt', 'ml/requirements-lock.txt',
                 'services/api/scripts/start_server.py', 'services/api/scripts/__init__.py']:
        destination = target / name
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / name, destination)
    shutil.copyfile(ROOT / f'deploy/railway-{component}.json', target / 'railway.json')
    return target


def main():
    provider = sys.argv[1]
    component = sys.argv[2] if len(sys.argv) > 2 else 'api'
    if component not in ('api', 'web'):
        raise ValueError('Component must be api or web')
    if provider == 'railway':
        # Read required values before preparing/uploading anything.
        project, service, environment = [required(k) for k in ('RAILWAY_PROJECT_ID', 'RAILWAY_SERVICE_ID', 'RAILWAY_ENVIRONMENT')]
        subprocess.run(['railway', 'up', str(railway_context(component)), '--path-as-root', '--no-gitignore',
                        '--project', project, '--service', service, '--environment', environment, '--ci'], check=True)
    elif provider == 'render':
        url = required('RENDER_DEPLOY_HOOK')
        if urlsplit(url).hostname != 'api.render.com':
            raise ValueError('Expected a Render deployment hook')
        request(url)
    elif provider == 'coolify':
        request(required('COOLIFY_ORIGIN').rstrip('/') + '/api/v1/applications/' + required('COOLIFY_APPLICATION_UUID') + '/start',
                {'Authorization': 'Bearer ' + required('COOLIFY_TOKEN')})
    elif provider == 'compose':
        command = ['docker', 'compose', '-f', str(ROOT / 'deploy/compose.yaml')]
        subprocess.run(command + ['config', '--quiet'], check=True)
        subprocess.run(command + ['pull'], check=True)
        subprocess.run(command + ['up', '-d', '--wait'], check=True)
    elif provider == 'systemd':
        # Operator prepares /opt/creditiq/current and /etc/creditiq first; no blind file overwrite.
        subprocess.run(['systemctl', 'daemon-reload'], check=True)
        subprocess.run(['systemctl', 'restart', 'creditiq-' + component], check=True)
        subprocess.run(['systemctl', 'is-active', '--quiet', 'creditiq-' + component], check=True)
    else:
        raise ValueError('Unknown provider')


if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        # Provider hooks can contain secrets in URLs: never print raw exception text.
        print(json.dumps({'deployment_requested': False, 'error_type': type(exc).__name__}))
        raise SystemExit(1)
