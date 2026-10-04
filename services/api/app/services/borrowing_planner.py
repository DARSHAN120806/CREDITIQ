"""Decimal-only amortization, cash-flow and scenario ranking. No persistence or ML."""
from decimal import Decimal, ROUND_HALF_UP

from app.schemas.planner import PlannerRequest

ZERO = Decimal('0')
ONE = Decimal('1')
CENT = Decimal('0.01')
STRESS_LEVELS = (0, 10, 20, 30)
WEIGHTS = {
    'LOWER_EMI': (Decimal('.70'), Decimal('.30')),
    'LOWER_TOTAL_INTEREST': (Decimal('.30'), Decimal('.70')),
    'BALANCED': (Decimal('.50'), Decimal('.50')),
}


def money(value: Decimal) -> str:
    return str(value.quantize(CENT, rounding=ROUND_HALF_UP))


def ratio(numerator: Decimal, denominator: Decimal) -> float | None:
    return float(numerator / denominator) if denominator > ZERO else None


def clamp(value: Decimal, low: Decimal = ZERO, high: Decimal = ONE) -> Decimal:
    return max(low, min(high, value))


def emi(principal: Decimal, term_months: int, annual_rate_percent: Decimal) -> Decimal:
    if annual_rate_percent == ZERO:
        return (principal / term_months).quantize(CENT, rounding=ROUND_HALF_UP)
    monthly_rate = annual_rate_percent / Decimal('1200')
    discount = (ONE + monthly_rate) ** (-term_months)
    payment = principal * monthly_rate / (ONE - discount)
    return payment.quantize(CENT, rounding=ROUND_HALF_UP)


def fit_score(income: Decimal, existing_debt: Decimal, proposed_emi: Decimal,
              residual: Decimal) -> tuple[int, float, float]:
    burden = (existing_debt + proposed_emi) / income
    burden_points = (Decimal('60') if burden <= Decimal('.20') else ZERO
                     if burden >= Decimal('.40') else
                     Decimal('60') * (Decimal('.40') - burden) / Decimal('.20'))
    residual_points = Decimal('40') * clamp(residual / income / Decimal('.30'))
    score = (burden_points + residual_points).quantize(Decimal('1'), rounding=ROUND_HALF_UP)
    return int(score), float(burden_points.quantize(CENT)), float(residual_points.quantize(CENT))


def _scenario(request: PlannerRequest, term: int) -> dict:
    payment = emi(request.requested_amount, term, request.annual_rate_percent)
    total = payment * term
    interest = max(ZERO, total - request.requested_amount)
    residual = request.monthly_take_home_income - request.monthly_essential_expenses - request.existing_monthly_debt_payments - payment
    goal_residual = residual - request.monthly_savings_goal if request.monthly_savings_goal is not None else None
    debt_service = request.existing_monthly_debt_payments + payment
    score, burden_points, residual_points = fit_score(
        request.monthly_take_home_income, request.existing_monthly_debt_payments, payment, residual)
    stresses = []
    for drop in STRESS_LEVELS:
        stressed_income = request.monthly_take_home_income * (Decimal(100 - drop) / Decimal(100))
        stressed_residual = stressed_income - request.monthly_essential_expenses - request.existing_monthly_debt_payments - payment
        stressed_goal_residual = (stressed_residual - request.monthly_savings_goal
                                  if request.monthly_savings_goal is not None else None)
        stresses.append({
            'income_drop_percent': drop,
            'stressed_take_home_income': money(stressed_income),
            'debt_service_ratio': ratio(debt_service, stressed_income),
            'stressed_residual': money(stressed_residual),
            'goal_adjusted_residual': money(stressed_goal_residual) if stressed_goal_residual is not None else None,
        })
    current_dti = (ratio(request.existing_monthly_debt_payments, request.monthly_gross_income)
                   if request.monthly_gross_income is not None else None)
    proposed_dti = (ratio(debt_service, request.monthly_gross_income)
                    if request.monthly_gross_income is not None else None)
    budget_residual = goal_residual if goal_residual is not None else residual
    return {
        'term_months': term,
        'annual_rate_percent': str(request.annual_rate_percent),
        'emi': money(payment),
        'total_repayment': money(total),
        'total_interest': money(interest),
        'current_debt_burden_monthly': money(request.existing_monthly_debt_payments),
        'current_dti': current_dti,
        'proposed_debt_to_income_ratio': proposed_dti,
        'current_take_home_payment_ratio': ratio(request.existing_monthly_debt_payments, request.monthly_take_home_income),
        'proposed_take_home_payment_ratio': ratio(debt_service, request.monthly_take_home_income),
        'residual_monthly_income': money(residual),
        'goal_adjusted_residual': money(goal_residual) if goal_residual is not None else None,
        'additional_emi_headroom': (money(max(ZERO, request.monthly_take_home_income - request.monthly_essential_expenses
                                               - request.existing_monthly_debt_payments - request.monthly_savings_goal))
                                    if request.monthly_savings_goal is not None else None),
        'planning_fit_score': score,
        'score_components': {'payment_burden': burden_points, 'residual_cash_flow': residual_points},
        'fits_stated_budget': budget_residual >= ZERO,
        'savings_goal_fit': (goal_residual >= ZERO if goal_residual is not None else None),
        'stress': stresses,
    }


def _normalize(values: list[Decimal], reverse: bool) -> list[Decimal]:
    low, high = min(values), max(values)
    if high == low:
        return [Decimal('100')] * len(values)
    return [((high - value) if reverse else (value - low)) * Decimal('100') / (high - low)
            for value in values]


def _difference(value: Decimal, other: Decimal) -> str:
    delta = abs(value - other)
    if delta == ZERO:
        return 'the same'
    return f"₹{money(delta)} {'lower' if value < other else 'higher'}"


def _rank_explanation(row: dict, above: dict | None, below: dict | None,
                      priority: str, monthly_weight: Decimal, interest_weight: Decimal,
                      has_fit: bool) -> str:
    preference = {
        'LOWER_EMI': 'lower monthly payments',
        'LOWER_TOTAL_INTEREST': 'lower total interest',
        'BALANCED': 'a balance of monthly payments and total interest',
    }[priority]
    explanation = (
        f"Ranks #{row['rank']} for {preference} with a combined rank score of {row['rank_score']:.1f}/100 "
        f"({int(monthly_weight * 100)}% monthly room, {int(interest_weight * 100)}% interest saving). "
        f"It earns a monthly-room score of {row['monthly_room_score']:.1f} and an interest-saving score "
        f"of {row['interest_saving_score']:.1f}."
    )
    if has_fit and not row['fits_stated_budget']:
        explanation += ' It ranks after scenarios that fit your stated budget.'
    elif row['fits_stated_budget']:
        explanation += ' It fits your stated budget.'

    for neighbor, position in ((above, 'above'), (below, 'below')):
        if neighbor is None:
            continue
        emi_delta = _difference(Decimal(row['emi']), Decimal(neighbor['emi']))
        interest_delta = _difference(Decimal(row['total_interest']), Decimal(neighbor['total_interest']))
        explanation += (
            f" Compared with the {neighbor['term_months']}-month option ranked {position}, "
            f"its monthly EMI is {emi_delta} and its total interest is {interest_delta}."
        )
    if above is None:
        explanation += ' It is the highest-ranked scenario.'
    if below is None:
        explanation += ' It is the lowest-ranked scenario.'
    return explanation


def rank_scenarios(scenarios: list[dict], priority: str) -> list[dict]:
    """Rank fitting budgets first, then weighted preference, then specified tie-breaks."""
    if not scenarios:
        return []
    monthly_scores = _normalize([Decimal(row['emi']) for row in scenarios], reverse=True)
    interest_scores = _normalize([Decimal(row['total_interest']) for row in scenarios], reverse=True)
    monthly_weight, interest_weight = WEIGHTS[priority]
    for row, monthly, interest in zip(scenarios, monthly_scores, interest_scores):
        row['monthly_room_score'] = float(monthly.quantize(CENT, rounding=ROUND_HALF_UP))
        row['interest_saving_score'] = float(interest.quantize(CENT, rounding=ROUND_HALF_UP))
        row['rank_score'] = float((monthly * monthly_weight + interest * interest_weight)
                                  .quantize(CENT, rounding=ROUND_HALF_UP))
    has_fit = any(row['fits_stated_budget'] for row in scenarios)
    scenarios.sort(key=lambda row: (
        0 if row['fits_stated_budget'] or not has_fit else 1,
        -Decimal(row['rank_score']) if has_fit else
        max(ZERO, -Decimal(row['goal_adjusted_residual'] or row['residual_monthly_income'])),
        -Decimal(row['rank_score']),
        -Decimal(row['goal_adjusted_residual'] or row['residual_monthly_income']),
        Decimal(row['total_interest']),
        int(row['term_months']),
    ))
    for rank, row in enumerate(scenarios, 1):
        row['rank'] = rank
        row['rank_explanation'] = _rank_explanation(
            row, scenarios[rank - 2] if rank > 1 else None,
            scenarios[rank] if rank < len(scenarios) else None,
            priority, monthly_weight, interest_weight, has_fit,
        )
        row['ranking_policy_version'] = 'borrowing-rank-v1'
    return scenarios


def calculate(request: PlannerRequest) -> dict:
    scenarios = rank_scenarios([_scenario(request, term) for term in request.terms_months], request.planning_priority)
    savings_buffer = (ratio(request.liquid_savings, request.monthly_essential_expenses)
                      if request.liquid_savings is not None and request.monthly_essential_expenses > ZERO else None)
    headroom_before_goal = max(ZERO, request.monthly_take_home_income - request.monthly_essential_expenses
                               - request.existing_monthly_debt_payments)
    headroom_after_goal = (max(ZERO, headroom_before_goal - request.monthly_savings_goal)
                           if request.monthly_savings_goal is not None else None)
    warnings = [
        'Illustrative planning estimate, not a loan offer or eligibility decision.',
        'Inputs are user-declared and unverified; no fees, taxes, insurance, or lender-specific terms are included.',
        'Stress tests reduce take-home income while holding expenses and debt payments fixed.',
        'Planning Fit Score is an unvalidated research heuristic, not a lending score.',
    ]
    if request.monthly_savings_goal is None:
        warnings.append('Monthly savings goal was not supplied; goal-adjusted residual and goal-based headroom are unavailable.')
    if request.monthly_gross_income is None:
        warnings.append('Gross monthly income was not supplied; conventional debt-to-income ratios are unavailable.')
    if any(Decimal(row['residual_monthly_income']) < ZERO for row in scenarios):
        warnings.append('One or more scenarios produce negative residual monthly income.')
    return {
        'calculation_version': 'borrowing-planner-v1',
        'mode': 'RESEARCH_ONLY', 'release_ready': False,
        'currency': request.currency, 'as_of': request.as_of.isoformat(), 'inputs_basis': 'USER_DECLARED',
        'current_debt_burden_monthly': money(request.existing_monthly_debt_payments),
        'current_dti': (ratio(request.existing_monthly_debt_payments, request.monthly_gross_income)
                        if request.monthly_gross_income is not None else None),
        'current_take_home_payment_ratio': ratio(request.existing_monthly_debt_payments, request.monthly_take_home_income),
        'total_outstanding_debt': money(request.total_outstanding_debt) if request.total_outstanding_debt is not None else None,
        'liquid_savings': money(request.liquid_savings) if request.liquid_savings is not None else None,
        'monthly_essential_expenses': money(request.monthly_essential_expenses),
        'monthly_savings_goal': money(request.monthly_savings_goal) if request.monthly_savings_goal is not None else None,
        'additional_emi_headroom': money(headroom_after_goal) if headroom_after_goal is not None else None,
        'additional_emi_headroom_before_savings_goal': money(headroom_before_goal),
        'savings_buffer_months': savings_buffer,
        'planning_priority': request.planning_priority,
        'ranking_weights': {'monthly_room': float(WEIGHTS[request.planning_priority][0]),
                            'interest_saving': float(WEIGHTS[request.planning_priority][1])},
        'scenarios': scenarios,
        'warnings': warnings,
    }
