import uuid
import pytest
from sqlalchemy import select, func, update
from sqlalchemy.orm import Session
from app.db import models as M
from app.services.lite_model import LiteModel
from test_authentication import api, owner_engine, signed_in, register, login, EMAIL

BODY = dict(age_years=35, employment_type='WORKING', years_employed=8,
    annual_income='180000.00', requested_amount='450000.00', term_months=36,
    education_level='HIGHER', household_size=3, dependent_children=1,
    occupation='CORE_STAFF', housing_status='OWN_OR_APARTMENT', research_acknowledged=True)


@pytest.fixture(scope='module')
def model():
    return LiteModel()


def submit(client, body=None, key=None):
    token = client.get('/api/v1/auth/csrf').json()['csrf_token']
    return client.post('/api/v1/applications', json=BODY if body is None else body,
        headers={'X-CSRF-Token': token, 'Idempotency-Key': str(key or uuid.uuid4())})


def test_real_prediction_persistence_history_and_idempotency(api, model):
    client, _, engine = api
    client.app.state.lite_model = model
    signed_in(client)
    key = uuid.uuid4()
    response = submit(client, key=key)
    assert response.status_code == 201, response.text
    data = response.json(); identity = data['id']; result = data['result']
    assert 0 <= result['probability'] <= 1 and result['model_version'] == model.metadata['run_id']
    assert result['risk_score'] == round(100*result['probability'], 2)
    assert result['decision_status'] == 'NOT_A_LENDING_DECISION'
    assert result['release_ready'] is False and data['quote']['illustrative']
    assert client.get(f'/api/v1/applications/{identity}/result').json() == result
    assert len(client.get(f'/api/v1/applications/{identity}/history').json()) == 1
    assert client.get('/api/v1/applications').json()['total'] == 1
    assert submit(client, key=key).json()['id'] == identity
    assert submit(client, {**BODY, 'term_months': 48}, key).status_code == 409
    with Session(engine) as db:
        assert db.scalar(select(func.count()).select_from(M.Prediction)) == 1
        features = db.scalar(select(M.FeatureSnapshot)).feature_values_json
        assert len(features) == 17
        assert db.scalar(select(M.Decision)).kind == 'RECOMMENDATION'


def test_ownership_and_admin_read_only(api, model):
    client, _, engine = api
    client.app.state.lite_model = model
    signed_in(client)
    identity = submit(client).json()['id']
    register(client, email='other@example.com'); login(client, email='other@example.com')
    assert client.get('/api/v1/applications').json()['total'] == 0
    for suffix in ('', '/result', '/history'):
        assert client.get(f'/api/v1/applications/{identity}{suffix}').status_code == 404
    assert client.get('/api/v1/admin/users').status_code == 403
    assert client.get('/api/v1/admin/model-research').status_code == 403
    with engine.begin() as c:
        c.execute(update(M.User).where(M.User.normalized_email == 'other@example.com').values(role='ADMIN'))
    assert submit(client).status_code == 403  # ADMIN is business-read-only, even through user routes.
    assert client.get('/api/v1/admin/statistics').json()['total_predictions'] == 1
    research = client.get('/api/v1/admin/model-research')
    assert research.status_code == 200, research.text
    dashboard = research.json()
    assert dashboard['mode'] == 'RESEARCH_ONLY' and dashboard['release_ready'] is False
    assert [(item['name'], item['feature_count']) for item in dashboard['metrics']] == [
        ('Lite', 17), ('FULL_RESEARCH_V1_NO_EXT', 22)]
    assert dashboard['metrics'][0]['values']['roc_auc'] == pytest.approx(0.7007798513)
    assert dashboard['metrics'][1]['values']['roc_auc'] == pytest.approx(0.7047402078)
    assert len(dashboard['calibration']['bins']) == 20
    assert dashboard['shap']['top_features'][0]['feature'] == 'payment_principal_ratio'
    assert len(dashboard['ablation']) == 4
    assert client.get('/api/v1/admin/applications').json()['total'] == 1
    assert client.get(f'/api/v1/admin/applications/{identity}').status_code == 200
    users = client.get('/api/v1/admin/users').json()['items']
    assert len(users) == 2 and 'password_hash' not in str(users)
    assert client.get('/api/v1/admin/users/'+users[0]['id']).status_code == 200
    assert client.get('/api/v1/admin/users/'+str(uuid.uuid4())).status_code == 404
    routes = client.get('/openapi.json').json()['paths']
    assert all(set(methods) == {'get'} for path, methods in routes.items() if '/admin/' in path)


@pytest.mark.parametrize('change', [dict(age_years=17), dict(annual_income='0'), dict(years_employed=80),
    dict(dependent_children=3), dict(term_months=0), dict(employment_type='invented'),
    dict(quoted_monthly_payment=1), dict(research_acknowledged=False)])
def test_invalid_payload(api, change):
    client, _, _ = api
    signed_in(client)
    assert submit(client, {**BODY, **change}).status_code == 422


def test_unauthorized_and_csrf(api):
    client, _, _ = api
    assert client.get('/api/v1/applications').status_code == 401
    assert client.get('/api/v1/admin/statistics').status_code == 401
    assert submit(client).status_code == 401
    signed_in(client)
    assert client.post('/api/v1/applications', json=BODY).status_code == 403


def test_model_failure_rolls_back_everything(api, model, monkeypatch):
    client, _, engine = api
    signed_in(client)
    client.app.state.lite_model = model
    def fail(*args):
        raise RuntimeError('injected scoring failure')
    monkeypatch.setattr(model, 'score', fail)
    with pytest.raises(RuntimeError, match='injected'):
        submit(client)
    with Session(engine) as db:
        for table in (M.LoanApplication, M.ApplicationVersion, M.LoanQuote, M.ModelVersion,
                      M.FeatureSnapshot, M.Prediction, M.PolicyVersion, M.ApplicationHistory):
            assert db.scalar(select(func.count()).select_from(table)) == 0


def test_disabled_model_returns_503(api):
    client, _, _ = api
    signed_in(client)
    assert submit(client).status_code == 503


def test_late_failure_rolls_back_prediction_and_history(api, model, monkeypatch):
    from app.services import applications as service
    client, _, engine = api
    signed_in(client)
    client.app.state.lite_model = model
    def fail(*args):
        raise RuntimeError('injected response failure')
    monkeypatch.setattr(service, 'application_view', fail)
    with pytest.raises(RuntimeError, match='injected'):
        submit(client)
    with Session(engine) as db:
        for table in (M.LoanApplication, M.ApplicationVersion, M.FeatureSnapshot, M.Prediction,
                      M.RiskScore, M.Decision, M.ApplicationHistory):
            assert db.scalar(select(func.count()).select_from(table)) == 0


def test_checksum_failure_blocks_loading(monkeypatch):
    from app.services import lite_model
    monkeypatch.setattr(lite_model, 'digest', lambda path: '0'*64)
    with pytest.raises(ValueError, match='checksum'):
        LiteModel()


def test_concurrent_duplicate_submission_creates_one_prediction(api, model):
    from concurrent.futures import ThreadPoolExecutor
    client, _, engine = api
    signed_in(client)
    client.app.state.lite_model = model
    token = client.get('/api/v1/auth/csrf').json()['csrf_token']
    key = str(uuid.uuid4())
    def attempt(_):
        return client.post('/api/v1/applications', json=BODY,
            headers={'X-CSRF-Token': token, 'Idempotency-Key': key})
    with ThreadPoolExecutor(max_workers=2) as pool:
        responses = list(pool.map(attempt, range(2)))
    assert [r.status_code for r in responses] == [201, 201]
    assert responses[0].json()['id'] == responses[1].json()['id']
    with Session(engine) as db:
        assert db.scalar(select(func.count()).select_from(M.Prediction)) == 1
