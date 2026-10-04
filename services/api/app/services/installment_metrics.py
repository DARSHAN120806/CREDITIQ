"""Retrospective calculations. No trained model, target or probability is created."""
from collections import defaultdict
from datetime import timedelta
from decimal import Decimal
from statistics import mean, pstdev
import math
import pandas as pd
from app.services.lite_model import ML_ROOT  # establishes the pinned read-only package path
from creditiq_ml.features import installments_features

VERSION = 'installment-intelligence-v1'
TOLERANCE = Decimal('0.01')


def percentage(numerator, denominator):
    return round(100 * float(numerator) / float(denominator), 2) if denominator else None


def calculate(body):
    events = defaultdict(list)
    ignored = 0
    for p in body.payments:
        if p.paid_date <= body.as_of:
            events[(p.account_ref, p.installment_ref)].append(p)
        else:
            ignored += 1
    rows = []
    schedule_records, payment_records = [], []
    accounts = {v: i + 1 for i, v in enumerate(sorted({s.account_ref for s in body.schedules}))}
    for index, s in enumerate(body.schedules):
        if not body.window_start <= s.due_date < body.as_of:
            continue  # Due today is not overdue; future schedules never enter denominators.
        payments = sorted(events[(s.account_ref, s.installment_ref)], key=lambda p: (p.paid_date, p.event_ref))
        total, by_due, completion = Decimal(0), Decimal(0), None
        for p in payments:
            total += p.amount
            if p.paid_date <= s.due_date:
                by_due += p.amount
            if completion is None and total >= s.amount - TOLERANCE:
                completion = p.paid_date
        delay = (completion - s.due_date).days if completion else None
        # Incomplete event coverage cannot establish first completion or absence of payments.
        known = body.payments_complete
        status = ('ON_TIME' if delay is not None and delay <= 0 else 'LATE' if delay is not None
                  else 'PARTIAL' if total > 0 else 'MISSED') if known else 'UNKNOWN'
        rows.append(dict(account_ref=s.account_ref, installment_ref=s.installment_ref,
            due_date=s.due_date.isoformat(), scheduled_amount=str(s.amount), paid_amount=str(total),
            funded_by_due=str(min(s.amount, by_due)), completion_date=completion.isoformat() if completion and known else None,
            delay_days=delay if known else None,
            overdue_days=max(0, delay if delay is not None else (body.as_of-s.due_date).days) if known else None,
            shortfall=str(max(Decimal(0), s.amount-total)) if known else None, status=status))
        key = dict(SK_ID_CURR=1, SK_ID_PREV=accounts[s.account_ref],
                   NUM_INSTALMENT_NUMBER=index+1, NUM_INSTALMENT_VERSION=1)
        # This is a supplied-record retrospective projection, NOT evidence of historical availability.
        schedule_records.append(dict(**key, DAYS_INSTALMENT=(s.due_date-body.as_of).days,
                                     AMT_INSTALMENT=float(s.amount), DAYS_AVAILABLE=0))
        for p in payments:
            payment_records.append(dict(**key, PAYMENT_ID=p.event_ref,
                DAYS_ENTRY_PAYMENT=(p.paid_date-body.as_of).days, AMT_PAYMENT=float(p.amount), DAYS_AVAILABLE=0))
    rows.sort(key=lambda r: (r['due_date'], r['account_ref'], r['installment_ref']))
    aggregates = {}
    if schedule_records and body.payments_complete:
        columns = ['SK_ID_CURR','SK_ID_PREV','NUM_INSTALMENT_NUMBER','NUM_INSTALMENT_VERSION',
                   'PAYMENT_ID','DAYS_ENTRY_PAYMENT','AMT_PAYMENT','DAYS_AVAILABLE']
        payment_frame = pd.DataFrame(payment_records, columns=columns).astype({c: 'float64' for c in columns if c != 'PAYMENT_ID'})
        existing = installments_features(payment_frame,
                                         pd.DataFrame(schedule_records)).iloc[0].to_dict()
        aggregates = {k: (None if not math.isfinite(float(v)) else float(v))
                      for k, v in existing.items() if k != 'SK_ID_CURR'}
    count = len(rows)
    known = body.payments_complete
    on_time = sum(r['status']=='ON_TIME' for r in rows)
    late = [r for r in rows if r['status']=='LATE']
    completed = [r for r in rows if r['status'] in ('ON_TIME','LATE')]
    on_time_pct = percentage(on_time, count) if known else None
    span = (body.as_of - body.window_start).days
    observed_span = (max(s.due_date for s in body.schedules if body.window_start <= s.due_date < body.as_of) - min(s.due_date for s in body.schedules if body.window_start <= s.due_date < body.as_of)).days if count else 0
    score_available = known and body.schedule_complete and count >= 6 and observed_span >= 90
    metrics = dict(discipline_score=on_time_pct if score_available else None,
        on_time_percent=on_time_pct,
        payment_reliability_percent=percentage(sum(Decimal(r['funded_by_due']) for r in rows),
            sum(Decimal(r['scheduled_amount']) for r in rows)) if known else None,
        average_delay_days=round(mean(r['delay_days'] for r in late),2) if late else None,
        worst_delay_days=aggregates.get('installment_max_overdue_days'),
        payment_consistency_days=round(pstdev(r['delay_days'] for r in completed),2) if len(completed)>=2 else None,
        due_count=count, on_time_count=on_time if known else None,
        late_payment_count=len(late) if known else None,
        missed_payment_count=sum(r['status']=='MISSED' for r in rows) if known else None,
        partial_overdue_count=sum(r['status']=='PARTIAL' for r in rows) if known else None,
        outstanding_overdue_count=sum(r['status'] in ('MISSED','PARTIAL') for r in rows) if known else None)
    # Recovery uses only overdue obligations with 30 days of observable follow-up.
    cutoff30 = (body.as_of-timedelta(days=30)).isoformat()
    matured = [r for r in rows if r['due_date'] <= cutoff30 and r['status'] in ('LATE','MISSED','PARTIAL')]
    metrics['recovery_30d_percent'] = percentage(sum(r['status']=='LATE' and r['delay_days']<=30 for r in matured), len(matured)) if known else None
    metrics['recovery_eligible_count'] = len(matured) if known else None
    recent_start, prior_start = body.as_of-timedelta(days=90), body.as_of-timedelta(days=180)
    recent = [r for r in rows if recent_start.isoformat() <= r['due_date']]
    prior = [r for r in rows if prior_start.isoformat() <= r['due_date'] < recent_start.isoformat()]
    comparable = known and body.schedule_complete and body.window_start <= prior_start and len(recent)>=3 and len(prior)>=3
    delta = round(percentage(sum(r['status']=='ON_TIME' for r in recent),len(recent))-
                  percentage(sum(r['status']=='ON_TIME' for r in prior),len(prior)),2) if comparable else None
    metrics['recent_improvement_pp'] = delta
    metrics['recent_improvement'] = ('IMPROVING' if delta>0 else 'DECLINING' if delta<0 else 'UNCHANGED') if delta is not None else 'INSUFFICIENT_HISTORY'
    timeline = []
    for month in sorted({r['due_date'][:7] for r in rows}):
        monthly = [r for r in rows if r['due_date'].startswith(month)]
        recovered = [r for r in matured if r['due_date'].startswith(month)]
        timeline.append(dict(month=month, due_count=len(monthly),
            on_time=sum(r['status']=='ON_TIME' for r in monthly), late=sum(r['status']=='LATE' for r in monthly),
            missed=sum(r['status']=='MISSED' for r in monthly), partial=sum(r['status']=='PARTIAL' for r in monthly),
            unknown=sum(r['status']=='UNKNOWN' for r in monthly),
            on_time_percent=percentage(sum(r['status']=='ON_TIME' for r in monthly),len(monthly)) if known else None,
            recovery_30d_percent=percentage(sum(r['status']=='LATE' and r['delay_days']<=30 for r in recovered),len(recovered)) if known else None,
            recovery_eligible_count=len(recovered) if known else None))
    coverage = dict(source_kind=body.source_kind, basis='DEMONSTRATION' if body.source_kind=='DEMO' else 'SELF_REPORTED',
        schedule_complete=body.schedule_complete, payments_complete=body.payments_complete,
        status='DECLARED_COMPLETE' if body.schedule_complete and known else 'LIMITED',
        independently_verified=False, historical_availability_verified=False,
        observed_installments=count, accounts=len(accounts), window_days=span, observed_span_days=observed_span,
        excluded_schedules=len(body.schedules)-count, excluded_future_payments=ignored,
        score_available=score_available,
        score_rule='Six eligible installments over at least 90 days, with declared complete schedule and payments.',
        interpretation='Retrospective behavior in supplied records; not a probability, credit-bureau score or lending decision.',
        consistency_definition='Population standard deviation of completed-payment timing in days; lower means less variation.',
        missed_definition='Past-due installment with no payment, conditional on declared complete payment coverage.')
    return dict(metrics=metrics, coverage=coverage, timeline=timeline, installments=rows, aggregates=aggregates)


