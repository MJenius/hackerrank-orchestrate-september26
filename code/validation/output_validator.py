"""Validate serialized predictions independently of candidate generation and ranking."""
from datetime import date, timedelta
from decimal import Decimal, InvalidOperation
from typing import Any, Dict, List, Optional

import pandas as pd

REQUIRED_COLUMNS = [
    'request_id', 'amount_safe_to_pay', 'affordability_status',
    'recommended_payment_method', 'payment_plan', 'earliest_date_for_full_payment',
    'spending_changes_needed', 'decision_explanation',
]
ALLOWED_STATUSES = {'affordable_now', 'affordable_with_plan', 'affordable_later', 'not_affordable'}
ALLOWED_METHODS = {'full_payment', 'partial_payment', 'installments', 'wait', 'not_recommended'}
CENT = Decimal('0.01')


def _money(value: Any) -> Decimal:
    amount = Decimal(str(value))
    if not amount.is_finite() or amount < 0 or amount != amount.quantize(CENT):
        raise ValueError('amount must be finite, nonnegative, and have at most two decimal places')
    return amount


def _date(value: Any) -> str:
    parsed = date.fromisoformat(str(value))
    if parsed.isoformat() != value:
        raise ValueError('date must use YYYY-MM-DD')
    return value


class OutputValidator:
    @staticmethod
    def validate_row(
        row: Dict,
        requested_amount: float,
        request_date: str,
        profile: Optional[Any] = None,
        options: Optional[List[Any]] = None,
        desired_completion_date: Optional[str] = None,
        events_by_id: Optional[Dict[str, Any]] = None,
        allows_partial_payment: Optional[bool] = None,
        future_events: Optional[List[Dict]] = None,
        simulator: Optional[Any] = None,
    ) -> List[str]:
        errors = []
        req_id = row.get('request_id', 'unknown')

        def fail(message):
            errors.append(f'{req_id}: {message}')

        for column in REQUIRED_COLUMNS:
            if column not in row:
                fail(f'Missing column {column}')
        if errors:
            return errors
        try:
            requested = _money(requested_amount)
            safe = _money(row['amount_safe_to_pay'])
            if safe > requested:
                fail('amount_safe_to_pay exceeds requested_amount')
            _date(request_date)
            end_date = (date.fromisoformat(request_date) + timedelta(days=90)).isoformat()
            deadline = _date(desired_completion_date) if desired_completion_date else end_date
        except (ValueError, TypeError, InvalidOperation) as exc:
            fail(f'Invalid amount or request date: {exc}')
            return errors

        status = row['affordability_status']
        method = row['recommended_payment_method']
        if status not in ALLOWED_STATUSES:
            fail(f'Invalid affordability_status {status!r}')
        if method not in ALLOWED_METHODS:
            fail(f'Invalid recommended_payment_method {method!r}')
        explanation = row['decision_explanation']
        if not isinstance(explanation, str) or not explanation.strip():
            fail('decision_explanation must be nonempty text')
        earliest_value = row['earliest_date_for_full_payment']
        earliest = '' if pd.isna(earliest_value) else str(earliest_value)
        if earliest:
            try:
                _date(earliest)
                if not request_date <= earliest <= end_date:
                    fail('earliest_date_for_full_payment falls outside the 90-day forecast')
            except (ValueError, TypeError):
                fail('Invalid earliest_date_for_full_payment')

        payments = []
        plan = row['payment_plan']
        if plan != 'none':
            try:
                for part in str(plan).split('|'):
                    payment_date, amount_text = part.split(':')
                    amount = _money(amount_text)
                    _date(payment_date)
                    if amount <= 0:
                        fail('Every recommended payment must be positive')
                    if not request_date <= payment_date <= end_date:
                        fail('Payment date falls outside the 90-day forecast')
                    if payment_date > deadline:
                        fail('Payment plan exceeds desired_completion_date')
                    payments.append((payment_date, amount))
                if [d for d, _ in payments] != sorted(d for d, _ in payments):
                    fail('payment_plan must be chronological')
                if len({d for d, _ in payments}) != len(payments):
                    fail('payment_plan has duplicate payment dates')
            except (ValueError, TypeError, InvalidOperation):
                fail('Invalid payment_plan date or amount syntax')
        if method == 'not_recommended':
            if plan != 'none' or row['spending_changes_needed'] != 'none':
                fail('not_recommended requires payment_plan and spending_changes_needed to be none')
        elif not payments:
            fail('A recommended payment method requires a payment_plan')

        if profile is not None and method in ALLOWED_METHODS - {'not_recommended'}:
            accepted_method = 'full_payment' if method == 'wait' else method
            if accepted_method not in profile.payment_methods_user_will_consider:
                fail(f'Payment method {method!r} conflicts with user preferences')

        changes = {}
        change_text = row['spending_changes_needed']
        if change_text != 'none':
            parts = str(change_text).split('|')
            if len(parts) > 3:
                fail('More than three spending changes')
            for part in parts:
                tokens = part.split(':')
                action = tokens[0]
                if action not in ('stop', 'reduce_to') or len(tokens) != (2 if action == 'stop' else 3):
                    fail(f'Invalid spending change syntax {part!r}')
                    continue
                target = tokens[1]
                if not target or target in changes:
                    fail(f'Empty or duplicate spending change target {target!r}')
                    continue
                try:
                    new_amount = Decimal(0) if action == 'stop' else _money(tokens[2])
                except (ValueError, TypeError, InvalidOperation):
                    fail(f'Invalid spending change amount {part!r}')
                    continue
                changes[target] = (action, new_amount)
                if events_by_id is None:
                    continue
                event = events_by_id.get(target)
                if event is None:
                    fail(f'Spending change event {target} does not exist')
                    continue
                if event.direction != 'debit' or event.status in ('cancelled', 'failed', 'unrealized'):
                    fail(f'Spending change event {target} is not a valid debit')
                if profile is not None:
                    if event.user_id != profile.user_id:
                        fail(f'Spending change event {target} belongs to another user')
                    if event.category in profile.expense_categories_to_protect:
                        fail(f'Spending change event {target} is protected')
                    permitted = (profile.expense_categories_user_is_willing_to_stop if action == 'stop'
                                 else profile.expense_categories_user_is_willing_to_reduce)
                    if event.category not in permitted:
                        fail(f'Spending change category {event.category!r} is not permitted for {action}')
                legal_flex = ('stoppable', 'reducible_or_stoppable') if action == 'stop' else ('reducible', 'reducible_or_stoppable')
                if event.flexibility not in legal_flex:
                    fail(f'Event {target} flexibility does not permit {action}')
                try:
                    if action == 'reduce_to':
                        if new_amount >= _money(event.amount):
                            fail(f'reduce_to must lower event {target} amount')
                        if event.minimum_allowed_amount is not None and new_amount < _money(event.minimum_allowed_amount):
                            fail(f'reduce_to is below minimum_allowed_amount for {target}')
                    if future_events is not None:
                        occurrences = [e for e in future_events if e.get('source_event_id') == target
                                       and e.get('is_recurring') and e.get('direction') == 'debit']
                        if not occurrences:
                            fail(f'Spending change event {target} has no proven future recurrence')
                        if action == 'reduce_to' and any(new_amount >= _money(e['amount']) for e in occurrences):
                            fail(f'reduce_to does not lower every future occurrence of {target}')
                except (ValueError, TypeError, InvalidOperation):
                    fail(f'Unresolved or invalid original amount for spending change {target}')

        expected_status = {
            'full_payment': 'affordable_with_plan' if changes else 'affordable_now',
            'partial_payment': 'affordable_with_plan',
            'installments': 'affordable_with_plan',
            'wait': 'affordable_with_plan' if changes else 'affordable_later',
            'not_recommended': 'not_affordable',
        }.get(method)
        if expected_status and status != expected_status:
            fail('Status is inconsistent with method and spending changes')
        if status == 'affordable_now' and (earliest != request_date or safe != requested):
            fail('affordable_now requires full baseline capacity and earliest date equal to request_date')
        if method in ('full_payment', 'wait') and payments:
            if len(payments) != 1 or payments[0][1] != requested:
                fail('full_payment/wait requires one payment equal to requested_amount')
            if method == 'full_payment' and payments[0][0] != request_date:
                fail('full_payment must start on request_date')
            if method == 'wait' and (payments[0][0] <= request_date or payments[0][0] != earliest):
                fail('wait must pay on earliest_date_for_full_payment after request_date')
        if method == 'partial_payment':
            if allows_partial_payment is False:
                fail('Request does not allow partial_payment')
            if not 0 < safe < requested:
                fail('partial_payment requires 0 < amount_safe_to_pay < requested_amount')
            if len(payments) != 2 or payments != [(request_date, safe), (earliest, requested - safe)]:
                fail('partial_payment must pay safe amount today and exact remainder on earliest full-payment date')
            if not earliest or earliest <= request_date or earliest > deadline:
                fail('partial_payment earliest date must be after request_date and by the deadline')

        if method == 'installments' and options is not None:
            matched = False
            for option in options:
                if option.request_id != req_id or option.payment_method != 'installments':
                    continue
                try:
                    count = int(option.number_of_payments)
                    frequency = int(option.payment_frequency_days or 0)
                    if count < 2 or count != option.number_of_payments or frequency <= 0 or frequency != option.payment_frequency_days:
                        continue
                    first = date.fromisoformat(_date(option.first_payment_date))
                    expected = [((first + timedelta(days=i * frequency)).isoformat(), _money(option.payment_amount))
                                for i in range(count)]
                    total = _money(option.total_payable_amount)
                    if payments == expected and sum(a for _, a in payments) == total and total == requested + _money(option.financing_fee):
                        matched = True
                except (ValueError, TypeError, InvalidOperation, OverflowError):
                    continue
            if not matched:
                fail('Installment plan does not exactly match a supplied option, total, and financing fee')
            if profile is not None:
                limit = profile.max_installment_months
                try:
                    if limit is None or not payments or Decimal(
                        (date.fromisoformat(payments[-1][0]) - date.fromisoformat(payments[0][0])).days
                    ) > Decimal(str(limit)) * 30:
                        fail('Installment schedule exceeds max_installment_months or installments are disabled')
                except (ValueError, TypeError, InvalidOperation):
                    fail('Invalid installment duration or max_installment_months')

        # Read back submitted amounts/actions, never a planner CandidatePlan.
        # Share the cash-flow engine, but independently apply spending changes.
        if profile is not None and future_events is not None and simulator is not None and not errors:
            try:
                if safe > 0:
                    is_safe, _, _ = simulator.simulate_trajectory(profile, request_date, future_events, {request_date: float(safe)})
                    if not is_safe:
                        fail('amount_safe_to_pay is unsafe over the full 90-day forecast')
                if safe + CENT <= requested:
                    is_safe, _, _ = simulator.simulate_trajectory(profile, request_date, future_events, {request_date: float(safe + CENT)})
                    if is_safe:
                        fail('amount_safe_to_pay is not the maximum safe amount')
                actual_earliest = ''
                for offset in range(91):
                    target_date = (date.fromisoformat(request_date) + timedelta(days=offset)).isoformat()
                    is_safe, _, _ = simulator.simulate_trajectory(profile, request_date, future_events, {target_date: float(requested)})
                    if is_safe:
                        actual_earliest = target_date
                        break
                if earliest != actual_earliest:
                    fail(f'earliest_date_for_full_payment should be {actual_earliest!r} before optional spending changes')
                modified_events = []
                for event in future_events:
                    target = event.get('source_event_id')
                    if target in changes and event.get('is_recurring'):
                        action, new_amount = changes[target]
                        if action == 'stop':
                            continue
                        event = dict(event, amount=float(new_amount))
                    modified_events.append(event)
                if payments:
                    schedule = {d: float(a) for d, a in payments}
                    is_safe, minimum, _ = simulator.simulate_trajectory(profile, request_date, modified_events, schedule)
                    if not is_safe:
                        fail(f'Payment plan violates minimum balance: projected minimum {minimum}')
            except (ValueError, TypeError, KeyError, InvalidOperation) as exc:
                fail(f'Financial safety validation failed: {exc}')
        return errors

    @staticmethod
    def validate_dataframe(
        df: pd.DataFrame,
        requests: Dict,
        profiles: Optional[Dict] = None,
        options: Optional[Dict] = None,
        events_by_id: Optional[Dict] = None,
        future_events_by_request: Optional[Dict] = None,
        simulator: Optional[Any] = None,
    ) -> List[str]:
        errors = []
        if list(df.columns) != REQUIRED_COLUMNS:
            errors.append(f'Columns must exactly equal {REQUIRED_COLUMNS}')
        if 'request_id' not in df:
            return errors
        ids = df['request_id'].astype(str)
        for rid in sorted(set(ids[ids.duplicated()])):
            errors.append(f'Duplicate request_id: {rid}')
        for rid in sorted(set(requests) - set(ids)):
            errors.append(f'Missing request_id: {rid}')
        for rid in sorted(set(ids) - set(requests)):
            errors.append(f'Unknown request_id: {rid}')
        if len(df) != len(requests):
            errors.append(f'Row count mismatch: expected {len(requests)}, got {len(df)}')
        for row in df.to_dict('records'):
            rid = str(row.get('request_id', ''))
            if rid not in requests:
                continue
            request = requests[rid]
            if profiles is not None and request.user_id not in profiles:
                errors.append(f'{rid}: Missing financial profile')
            if future_events_by_request is not None and rid not in future_events_by_request:
                errors.append(f'{rid}: Missing canonical future events')
            errors.extend(OutputValidator.validate_row(
                row, request.requested_amount, request.request_date,
                profile=profiles.get(request.user_id) if profiles is not None else None,
                options=options.get(rid, []) if options is not None else None,
                desired_completion_date=request.desired_completion_date,
                events_by_id=events_by_id,
                allows_partial_payment=request.allows_partial_payment,
                future_events=future_events_by_request.get(rid) if future_events_by_request is not None else None,
                simulator=simulator,
            ))
        return errors
