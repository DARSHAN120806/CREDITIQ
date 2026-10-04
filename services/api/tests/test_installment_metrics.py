from copy import deepcopy
from datetime import date, timedelta
import pytest
from pydantic import ValidationError
from app.schemas.installments import HistoryImportRequest
from app.services.installment_metrics import calculate


def history():
    return dict(label='Test history',source_kind='USER_DECLARED',currency='INR',as_of='2026-10-01',
        window_start='2026-01-01',schedule_complete=True,payments_complete=True,effective_schedule_confirmed=True,
        schedules=[dict(account_ref='loan',installment_ref='1',schedule_version='1',due_date='2026-08-01',amount='100.00'),
                   dict(account_ref='loan',installment_ref='2',schedule_version='1',due_date='2026-09-01',amount='100.00')],
        payments=[dict(event_ref='a',account_ref='loan',installment_ref='1',paid_date='2026-07-30',amount='40.00'),
                  dict(event_ref='b',account_ref='loan',installment_ref='1',paid_date='2026-08-05',amount='60.00')])


def run(body=None):
    return calculate(HistoryImportRequest.model_validate(body or history()))


def test_partial_reconciliation_and_existing_aggregate_parity():
    r=run(); m=r['metrics']; a=r['aggregates']
    assert m['late_payment_count']==1 and m['missed_payment_count']==1
    assert m['average_delay_days']==4 and m['worst_delay_days']==30
    assert m['payment_reliability_percent']==20 and m['on_time_percent']==0
    assert m['recovery_30d_percent']==50
    assert a['installment_late_count']==m['late_payment_count']+m['outstanding_overdue_count']
    assert a['installment_due_count']==2 and a['installment_mean_paid_ratio']==.5
    assert m['discipline_score'] is None


def test_missing_payment_events_are_valid_but_not_assumed_complete():
    b=history(); b['payments']=[]
    assert run(b)['metrics']['missed_payment_count']==2
    b['payments_complete']=False
    r=run(b)
    assert r['metrics']['missed_payment_count'] is None
    assert r['metrics']['on_time_percent'] is None and r['aggregates']=={}
    assert all(x['status']=='UNKNOWN' for x in r['installments'])


def test_early_completion_and_partial_outstanding_are_distinct():
    b=history(); b['payments'][1]['paid_date']='2026-07-31'
    b['payments'].append(dict(event_ref='c',account_ref='loan',installment_ref='2',paid_date='2026-09-03',amount='20.00'))
    m=run(b)['metrics']
    assert m['on_time_percent']==50 and m['late_payment_count']==0
    assert m['partial_overdue_count']==1 and m['missed_payment_count']==0
    assert m['average_delay_days'] is None


def test_due_today_and_future_payment_do_not_enter_lateness():
    b=history(); b['as_of']='2026-08-01'
    r=run(b)
    assert r['metrics']['due_count']==0 and r['metrics']['on_time_percent'] is None
    assert r['coverage']['excluded_future_payments']==1


def test_duplicate_identity_idempotent_but_conflict_rejected():
    b=history(); b['payments'].append(deepcopy(b['payments'][0]))
    assert run(b)==run()
    b['payments'][-1]['amount']='41.00'
    with pytest.raises(ValidationError,match='Conflicting duplicate'):
        HistoryImportRequest.model_validate(b)


@pytest.mark.parametrize('kind',['schedule','orphan','zero','negative','version','extra','currency','missing_date'])
def test_invalid_contracts(kind):
    b=history()
    if kind in ('schedule','version'):
        s=deepcopy(b['schedules'][0]);s['schedule_version']='2';b['schedules'].append(s)
    elif kind=='orphan': b['payments'][0]['installment_ref']='unknown'
    elif kind=='zero': b['schedules'][0]['amount']='0'
    elif kind=='negative': b['payments'][0]['amount']='-10'
    elif kind=='extra': b['predicted_score']=99
    elif kind=='currency': b['currency']='USD'
    elif kind=='missing_date': b['payments'][0]['paid_date']=None
    with pytest.raises(ValidationError): HistoryImportRequest.model_validate(b)


def long_history():
    b=history(); b['schedules']=[]; b['payments']=[]
    for i in range(12):
        due=date(2026,10,1)-timedelta(days=350-i*30)
        b['schedules'].append(dict(account_ref='a',installment_ref=str(i),due_date=due.isoformat(),amount='100'))
        b['payments'].append(dict(event_ref=str(i),account_ref='a',installment_ref=str(i),paid_date=(due+timedelta(days=5 if i<6 else 0)).isoformat(),amount='100'))
    b['window_start']='2025-10-01'
    return b


def test_score_and_comparable_improvement_window():
    b=long_history();r=run(b)
    assert r['metrics']['discipline_score']==50
    assert r['metrics']['recent_improvement_pp']==0  # both most recent 90-day windows are on-time
    assert r['metrics']['payment_consistency_days']==2.5
    b['schedule_complete']=False
    assert run(b)['metrics']['discipline_score'] is None
    assert run(b)['metrics']['recent_improvement_pp'] is None


def test_selected_window_cannot_fake_observed_span():
    b=long_history()
    for s in b['schedules']: s['due_date']='2026-09-01'
    assert run(b)['metrics']['discipline_score'] is None


def test_recovery_requires_mature_followup():
    b=history();b['schedules']=b['schedules'][:1];b['payments']=[]
    b['schedules'][0]['due_date']='2026-09-20'
    assert run(b)['metrics']['recovery_eligible_count']==0
    assert run(b)['metrics']['recovery_30d_percent'] is None

