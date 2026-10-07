"""Fail-closed deployment validation; return only safe, allowlisted log fields."""
from ipaddress import ip_network
import os
from urllib.parse import urlsplit


def render_managed_https(settings):
    # Render redirects public HTTP to HTTPS, then forwards HTTP to this web service.
    return (settings.app_env in ('staging', 'production')
            and os.environ.get('RENDER') == 'true'
            and os.environ.get('RENDER_SERVICE_TYPE') == 'web')


def validate_startup_environment(settings):
    settings.validate_auth()
    settings.validate_database()
    if settings.app_env in ('staging', 'production'):
        for label, value in [('API origin', settings.api_origin), ('Frontend origin', settings.frontend_origin)]:
            parsed = urlsplit(value or '')
            if (parsed.scheme != 'https' or not parsed.hostname or parsed.username or parsed.password
                    or parsed.path or parsed.query or parsed.fragment or '<' in value
                    or parsed.hostname in ('localhost', '127.0.0.1', '::1')):
                raise ValueError(label + ' must be an explicit public HTTPS origin without a path')
        if settings.auth_origins != [settings.frontend_origin]:
            raise ValueError('Deployment AUTH_ORIGINS must contain exactly FRONTEND_ORIGIN for the same-origin frontend proxy')
        if render_managed_https(settings):
            if settings.trusted_proxy_ips:
                raise ValueError('Do not configure TRUSTED_PROXY_IPS on Render; proxy headers are disabled')
        else:
            if not settings.trusted_proxy_ips:
                raise ValueError('Explicit TRUSTED_PROXY_IPS is required')
            for entry in settings.trusted_proxy_ips.split(','):
                network = ip_network(entry.strip(), strict=False)
                if network.prefixlen == 0:
                    raise ValueError('Unrestricted trusted proxy networks are forbidden')
        secret = settings.jwt_secret.get_secret_value()
        if (len(set(secret)) < 12 or '<' in secret or
                any(word in secret.lower() for word in ('changeme', 'replace_me', 'your_secret')) or
                any(secret == secret[:n] * (len(secret) // n) for n in range(1, len(secret)//2 + 1) if len(secret) % n == 0)):
            raise ValueError('JWT secret must be independently generated, not a placeholder or repeated pattern')
        if settings.migration_database_url is not None:
            raise ValueError('Operator migration credentials must not be loaded into the runtime service')
    return dict(environment=settings.app_env, database_target=f'{settings.pg_host}:{settings.pg_port}/{settings.pg_database}',
                runtime_role=settings.pg_user.split('.')[0], ssl_mode=settings.pg_sslmode,
                cookie_secure=settings.cookie_secure, api_origin=settings.api_origin,
                https_enforcement='render_edge' if render_managed_https(settings) else 'application',
                frontend_origin=settings.frontend_origin)
