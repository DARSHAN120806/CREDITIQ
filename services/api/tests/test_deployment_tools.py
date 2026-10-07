import importlib.util
from pathlib import Path
from unittest.mock import MagicMock

import pytest

ROOT = Path(__file__).resolve().parents[3]


def module(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / 'deploy' / (name + '.py'))
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


def test_monitor_healthy_and_failure_alert(monkeypatch, capsys):
    monitor = module('monitor')
    monkeypatch.setenv('MONITOR_API_ORIGIN', 'https://api.example.com')
    monkeypatch.setenv('MONITOR_FRONTEND_ORIGIN', 'https://app.example.com')
    monkeypatch.setenv('ALERT_WEBHOOK_URL', 'https://alerts.example.com/private-token')
    response = MagicMock()
    response.__enter__.return_value.status = 200
    response.__enter__.return_value.url = 'https://api.example.com/health/ready'
    frontend = MagicMock()
    frontend.__enter__.return_value.status = 200
    frontend.__enter__.return_value.url = 'https://app.example.com/login'
    opener = MagicMock(side_effect=[response, frontend])
    monkeypatch.setattr(monitor, 'urlopen', opener)
    assert monitor.check() == 0
    opener.side_effect = [TimeoutError('private-token'), frontend, response]
    assert monitor.check() == 1
    assert opener.call_args.args[0].get_method() == 'POST'
    assert 'private-token' not in capsys.readouterr().out


def test_provider_missing_config_does_not_deploy(monkeypatch):
    deploy = module('deploy')
    monkeypatch.setattr(deploy.sys, 'argv', ['deploy.py', 'railway'])
    monkeypatch.delenv('RAILWAY_PROJECT_ID', raising=False)
    run = MagicMock()
    monkeypatch.setattr(deploy.subprocess, 'run', run)
    with pytest.raises(ValueError):
        deploy.main()
    run.assert_not_called()
