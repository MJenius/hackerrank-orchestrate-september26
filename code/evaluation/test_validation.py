"""Adversarial final-output gate checks; no public-answer fixtures."""
from dataclasses import replace

import pandas as pd

from code.data.models import FinancialEvent, FinancialProfile, Request, RequestPaymentOption
from code.finance.currency import CurrencyConverter
from code.finance.simulator import BalanceSimulator
from code.validation.output_validator import OutputValidator, REQUIRED_COLUMNS


def test_all():
    simulator = BalanceSimulator(CurrencyConverter({}))
    profile = FinancialProfile('user', 'USD', 300, 100, '', [], ['streaming'], ['streaming'],
                               ['full_payment', 'partial_payment', 'installments'], 1)
    request = Request('request', 'user', '2025-01-01', 'purchase', 100, '2025-02-10', True, '')
    row = dict(zip(REQUIRED_COLUMNS, [request.request_id, 100, 'affordable_now', 'full_payment',
                                     '2025-01-01:100', '2025-01-01', 'none', 'Minimum balance maintained.']))
    debit = dict(event_id='debit', amount=100, currency='USD', direction='debit',
                 settlement_date='2025-01-30', status='scheduled')
    count = 0

    def check(candidate, valid, *, prof=profile, req=request, futures=None, options=None, events=None):
        nonlocal count
        errors = OutputValidator.validate_row(
            candidate, req.requested_amount, req.request_date, profile=prof,
            options=options if options is not None else [],
            desired_completion_date=req.desired_completion_date,
            events_by_id=events if events is not None else {},
            allows_partial_payment=req.allows_partial_payment,
            future_events=futures if futures is not None else [debit], simulator=simulator,
        )
        assert bool(errors) != valid, (candidate, errors)
        count += 1

    check(row, True)
    for field, value in [
        ('amount_safe_to_pay', float('nan')), ('amount_safe_to_pay', float('inf')),
        ('amount_safe_to_pay', -1), ('amount_safe_to_pay', 100.001),
        ('payment_plan', '2025-01-01:99.99'), ('payment_plan', '2025-01-01:NaN'),
        ('payment_plan', '2025-01-01:-100'), ('payment_plan', '2025-02-30:100'),
        ('payment_plan', '20250101:100'), ('payment_plan', '2025-01-01:50|2025-01-01:50'),
        ('payment_plan', '2025-02-11:100'), ('payment_plan', '2025-04-02:100'),
        ('earliest_date_for_full_payment', '2025-01-02'),
        ('affordability_status', 'affordable_later'), ('recommended_payment_method', 'loan'),
        ('decision_explanation', ''), ('spending_changes_needed', 'stop'),
        ('spending_changes_needed', 'reduce_to:debit'),
    ]:
        check(dict(row, **{field: value}), False)
    check({key: value for key, value in row.items() if key != 'payment_plan'}, False)
    check(row, False, prof=replace(profile, payment_methods_user_will_consider=['installments']))
    check(row, False, prof=replace(profile, current_available_balance=250))

    income = dict(event_id='salary', amount=100, currency='USD', direction='credit',
                  category='salary', settlement_date='2025-01-10', status='scheduled')
    partial_profile = replace(profile, current_available_balance=150)
    partial = dict(row, amount_safe_to_pay=50, affordability_status='affordable_with_plan',
                   recommended_payment_method='partial_payment',
                   payment_plan='2025-01-01:50|2025-01-10:50', earliest_date_for_full_payment='2025-01-10')
    check(partial, True, prof=partial_profile, futures=[income])
    check(partial, False, prof=partial_profile, futures=[income], req=replace(request, allows_partial_payment=False))
    check(dict(partial, payment_plan='2025-01-01:49.99|2025-01-10:50.01'), False,
          prof=partial_profile, futures=[income])
    check(dict(partial, payment_plan='2025-01-01:50|2025-01-11:50'), False,
          prof=partial_profile, futures=[income])
    check(dict(partial, amount_safe_to_pay=49.99, payment_plan='2025-01-01:49.99|2025-01-10:50.01'), False,
          prof=partial_profile, futures=[income])
    wait = dict(partial, affordability_status='affordable_later', recommended_payment_method='wait',
                payment_plan='2025-01-10:100')
    check(wait, True, prof=replace(partial_profile, payment_methods_user_will_consider=['full_payment']), futures=[income])
    check(wait, False, prof=replace(partial_profile, payment_methods_user_will_consider=['wait']), futures=[income])
    fallback = dict(row, affordability_status='not_affordable', recommended_payment_method='not_recommended', payment_plan='none')
    check(fallback, True, prof=replace(profile, payment_methods_user_will_consider=[]))

    option = RequestPaymentOption('offer', 'request', 'installments', 50, 2, '2025-01-01', 30, 0, 100)
    installments = dict(row, affordability_status='affordable_with_plan', recommended_payment_method='installments',
                        payment_plan='2025-01-01:50|2025-01-31:50')
    check(installments, True, options=[option])
    check(installments, False)
    check(installments, False, options=[replace(option, request_id='other_request')])
    check(installments, False, options=[replace(option, financing_fee=0.01)])
    check(installments, False, options=[replace(option, payment_frequency_days=29)])
    check(installments, False, options=[option], prof=replace(profile, max_installment_months=None))
    check(installments, False, options=[option], prof=replace(profile, max_installment_months=0.5))
    check(dict(installments, payment_plan='2025-01-01:50.01|2025-01-31:49.99'), False, options=[option])

    source = FinancialEvent('source', 'user', 'expense', 'Streaming', 'streaming', 'debit', 100, 'USD',
                            '2024-12-01', '2024-12-01', 'settled', None, 'reducible_or_stoppable', 0)
    recurring = [dict(debit, event_id=f'projected_{i}', source_event_id='source', category='streaming',
                      is_recurring=True, recurrence_evidence_ids=['older', 'source'],
                      settlement_date=day, status='projected')
                 for i, day in enumerate(['2025-01-10', '2025-02-10'])]
    changed = dict(row, amount_safe_to_pay=0, affordability_status='affordable_with_plan',
                   earliest_date_for_full_payment='', spending_changes_needed='stop:source')
    check(changed, True, futures=recurring, events={'source': source})
    check(dict(changed, spending_changes_needed='reduce_to:source:0'), True, futures=recurring, events={'source': source})
    check(changed, False, futures=recurring, events={})
    check(changed, False, futures=recurring, events={'source': replace(source, user_id='other')})
    check(changed, False, futures=recurring, events={'source': source}, prof=replace(profile, expense_categories_to_protect=['streaming']))
    check(changed, False, futures=[dict(e, is_recurring=False) for e in recurring], events={'source': source})
    for change in ['stop:source|reduce_to:source:0', 'stop:source:extra', 'reduce_to:source:100',
                   'reduce_to:source:-1', 'reduce_to:source:NaN']:
        check(dict(changed, spending_changes_needed=change), False, futures=recurring, events={'source': source})
    check(dict(changed, spending_changes_needed='reduce_to:source:0'), False,
          futures=recurring, events={'source': replace(source, minimum_allowed_amount=10)})
    one_off = dict(debit, event_id='one_off', source_event_id='source', amount=150,
                   is_recurring=False, settlement_date='2025-03-10')
    check(changed, False, futures=recurring + [one_off], events={'source': source})

    frame = pd.DataFrame([row], columns=REQUIRED_COLUMNS)
    assert not OutputValidator.validate_dataframe(frame, {'request': request})
    for bad_frame in [frame.drop(columns='request_id'), frame[REQUIRED_COLUMNS[::-1]],
                      pd.concat([frame, frame]), frame.iloc[:0], frame.assign(request_id='unknown')]:
        assert OutputValidator.validate_dataframe(bad_frame, {'request': request})
        count += 1
    print(f'ALL {count} ADVERSARIAL VALIDATION CHECKS PASSED')


if __name__ == '__main__':
    test_all()
