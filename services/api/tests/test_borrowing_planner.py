from decimal import Decimal

import pytest
from pydantic import ValidationError
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db import models as M
from app.schemas.planner import PlannerRequest, PlannerResponse
from app.services.borrowing_planner import calculate, emi, rank_scenarios
from test_authentication import api, mutate, signed_in

pytest_plugins = ('test_authentication',)


def body(**changes):
    values = {
        'currency': 'INR', 'monthly_take_home_income': '120000.00',
        'monthly_gross_income': '150000.00', 'monthly_essential_expenses': '45000.00',
        'existing_monthly_debt_payments': '18000.00', 'monthly_savings_goal': '10000.00',
        'liquid_savings': '300000.00', 'requested_amount': '500000.00',
        'annual_rate_percent': '12.00', 'terms_months': [12, 24, 36, 48, 60],
        'planning_priority': 'BALANCED',
    }
    values.update(changes)
    return PlannerRequest(**values)


def test_zero_apr_uses_straight_line_principal():
    assert emi(Decimal('12000'), 12, Decimal('0')) == Decimal('1000.00')


def test_high_apr_remains_finite_and_increases_interest():
    low = emi(Decimal('100000'), 12, Decimal('12'))
    high = emi(Decimal('100000'), 12, Decimal('100'))
    assert high.is_finite() and high > low


def test_negative_residual_is_preserved_and_warned():
    result = calculate(body(monthly_take_home_income='50000', monthly_essential_expenses='40000',
                            existing_monthly_debt_payments='10000', monthly_savings_goal='0',
                            terms_months=[12]))
    scenario = result['scenarios'][0]
    assert Decimal(scenario['residual_monthly_income']) < 0
    assert not scenario['fits_stated_budget']
    assert any('negative residual' in warning for warning in result['warnings'])


def test_missing_gross_income_omits_dti_but_keeps_take_home_ratio():
    scenario = calculate(body(monthly_gross_income=None, terms_months=[12]))['scenarios'][0]
    assert scenario['current_dti'] is None
    assert scenario['proposed_debt_to_income_ratio'] is None
    assert scenario['proposed_take_home_payment_ratio'] is not None


def test_missing_savings_goal_stays_unknown_and_does_not_change_fit_score():
    with_goal = calculate(body(terms_months=[12]))['scenarios'][0]
    without_goal = calculate(body(monthly_savings_goal=None, terms_months=[12]))['scenarios'][0]
    assert without_goal['goal_adjusted_residual'] is None
    assert without_goal['additional_emi_headroom'] is None
    assert without_goal['savings_goal_fit'] is None
    assert without_goal['planning_fit_score'] == with_goal['planning_fit_score']


def test_zero_debt_and_expenses_are_valid():
    result = calculate(body(monthly_essential_expenses='0', existing_monthly_debt_payments='0',
                            terms_months=[12]))
    assert result['current_debt_burden_monthly'] == '0.00'
    assert result['scenarios'][0]['fits_stated_budget']


@pytest.mark.parametrize('changes', [
    {'currency': 'USD'},
    {'terms_months': [12, 12]},
    {'terms_months': []},
    {'monthly_take_home_income': '0'},
])
def test_invalid_inputs_are_rejected(changes):
    with pytest.raises(ValidationError):
        body(**changes)


def test_ranking_is_deterministic_and_uses_configured_weights():
    rows = calculate(body(planning_priority='LOWER_EMI'))['scenarios']
    first = [(r['term_months'], r['rank_score'], r['rank']) for r in rows]
    second = [(r['term_months'], r['rank_score'], r['rank'])
              for r in calculate(body(planning_priority='LOWER_EMI'))['scenarios']]
    assert first == second
    assert max(r['monthly_room_score'] for r in rows) == 100
    assert 'combined rank score of' in rows[0]['rank_explanation']
    assert 'monthly-room score of' in rows[0]['rank_explanation']
    assert 'interest-saving score of' in rows[0]['rank_explanation']
    assert '48-month option ranked below' in rows[0]['rank_explanation']
    assert '36-month option ranked above' in rows[1]['rank_explanation']
    assert '60-month option ranked below' in rows[1]['rank_explanation']
    assert '48-month option ranked above' in rows[2]['rank_explanation']
    assert 'lowest-ranked scenario' in rows[-1]['rank_explanation']


def test_rank_tie_breaks_goal_residual_then_interest_then_term():
    def row(term, residual, payment, interest):
        return {'term_months': term, 'emi': str(payment), 'total_interest': str(interest),
                'goal_adjusted_residual': str(residual), 'residual_monthly_income': str(residual),
                'fits_stated_budget': True}
    ordered = rank_scenarios([row(36, 30, 300, 0), row(24, 20, 200, 50), row(12, 20, 100, 100),
                              row(18, 20, 200, 50)], 'BALANCED')
    assert [r['term_months'] for r in ordered] == [36, 18, 24, 12]
    # Equal rank scores: residual first, lower interest second, shorter term third.


def test_stress_rows_keep_costs_fixed_and_reduce_income():
    scenario = calculate(body(terms_months=[12]))['scenarios'][0]
    rows = scenario['stress']
    assert [row['income_drop_percent'] for row in rows] == [0, 10, 20, 30]
    assert rows[0]['stressed_take_home_income'] == '120000.00'
    assert rows[2]['stressed_take_home_income'] == '96000.00'
    assert Decimal(rows[2]['stressed_residual']) == Decimal(rows[0]['stressed_residual']) - Decimal('24000')


def test_authenticated_endpoint_is_stateless_and_does_not_load_model(api):
    client, _, engine = api  # test settings disable Lite loading
    signed_in(client)
    request = body(terms_months=[12, 24]).model_dump(mode='json')
    before = {}
    with Session(engine) as db:
        for model in (M.LoanApplication, M.Prediction, M.InstallmentImport, M.Report):
            before[model.__table__.name] = db.scalar(select(func.count()).select_from(model))
    response = mutate(client, 'POST', '/api/v1/planner/plan', json=request)
    assert response.status_code == 200, response.text
    result = PlannerResponse.model_validate(response.json())
    assert result.mode == 'RESEARCH_ONLY' and result.release_ready is False
    assert len(result.scenarios) == 2
    assert client.app.state.lite_model is None
    with Session(engine) as db:
        after = {model.__table__.name: db.scalar(select(func.count()).select_from(model))
                 for model in (M.LoanApplication, M.Prediction, M.InstallmentImport, M.Report)}
    assert before == after
    no_csrf = client.post('/api/v1/planner/plan', json=request)
    assert no_csrf.status_code == 403
