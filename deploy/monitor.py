"""One external monitor check; scheduler runs every minute. No credentials in logs."""
import json
import os
from urllib.parse import urlsplit
from urllib.request import Request, urlopen


def check():
    failures = []
    for variable, path in [('MONITOR_API_ORIGIN', '/health/ready'), ('MONITOR_FRONTEND_ORIGIN', '/login')]:
        origin = os.environ.get(variable, '')
        if urlsplit(origin).scheme != 'https' or '<' in origin:
            raise ValueError('HTTPS monitor origins are required')
        try:
            with urlopen(origin + path, timeout=10) as response:
                if response.status != 200 or not response.url.startswith(origin + '/'):
                    failures.append(variable)
        except Exception:
            failures.append(variable)
    hook = os.environ.get('ALERT_WEBHOOK_URL', '')
    if urlsplit(hook).scheme != 'https' or '<' in hook:
        raise ValueError('Configure an HTTPS alert webhook before enabling the monitor')
    if failures:
        # Generic JSON receiver; configure delivery/escalation with your monitoring provider.
        payload = json.dumps({'service': 'CreditIQ', 'status': 'unavailable', 'checks': failures}).encode()
        with urlopen(Request(hook, data=payload, headers={'Content-Type': 'application/json'}), timeout=10) as response:
            if not 200 <= response.status < 300:
                raise RuntimeError('Alert delivery failed')
    print(json.dumps({'healthy': not failures, 'failed_checks': failures}))
    return int(bool(failures))


if __name__ == '__main__':
    try:
        raise SystemExit(check())
    except Exception as exc:
        print(json.dumps({'monitor_error': type(exc).__name__}))
        raise SystemExit(2)
