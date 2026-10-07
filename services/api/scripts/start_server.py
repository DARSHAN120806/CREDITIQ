"""Shared Railway/Render/Coolify/container/systemd entrypoint. No shell interpolation."""
import os
import uvicorn
from app.core.config import Settings
from app.core.startup_environment_validator import render_managed_https, validate_startup_environment


if __name__ == '__main__':
    settings = Settings()
    validate_startup_environment(settings)
    if settings.app_env not in ('staging', 'production'):
        raise SystemExit('Deployment entrypoint requires staging or production')
    use_proxy_headers = not render_managed_https(settings)
    uvicorn.run('app.main:app', host=os.environ.get('BIND_HOST', '0.0.0.0'),
                port=int(os.environ.get('PORT', '8000')), workers=1, access_log=False,
                proxy_headers=use_proxy_headers,
                forwarded_allow_ips=settings.trusted_proxy_ips if use_proxy_headers else '127.0.0.1')
