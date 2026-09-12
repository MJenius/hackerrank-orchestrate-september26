"""The authoritative evidence -> lifecycle -> recurrence -> future cash stream."""
from calendar import monthrange
from collections import Counter, defaultdict
from dataclasses import asdict, replace
from datetime import date, timedelta
from statistics import median
import re

from code.data.models import FinancialEvent
from code.evidence.message_resolver import MessageResolver
from code.finance.lifecycle import EventLifecycle
from code.finance.recurrence import RecurrenceEngine, monthly_history, next_month


def _cash(event, **extra):
    return dict(asdict(event), source_event_id=event.event_id,
                is_recurring=False, is_projected=False, **extra)


def _regular_salary(event):
    irregular = r'bonus|commission|arrears|reimbursement|prize|reversal|refund'
    return (event.direction == 'credit' and event.category == 'salary'
            and not re.search(irregular, event.description, re.I))


class FutureStateBuilder:
    def __init__(self, events, messages):
        self._all_events = events
        self._all_messages = messages

    def build(self, user_id, profile, request_date, horizon_days=90, request_id=None):
        start = date.fromisoformat(request_date)
        end = start + timedelta(days=horizon_days)
        events = EventLifecycle.normalize([e for e in self._all_events if e.user_id == user_id])
        facts = MessageResolver.extract_facts(self._all_messages, user_id, request_date, request_id)
        by_id = {e.event_id: e for e in events}
        for fact in facts:
            event = by_id.get(fact.related_event_id)
            if not event:
                continue
            if fact.fact_type == 'event_cancel':
                event.status = 'cancelled'
            elif fact.fact_type == 'credit_pending' and event.direction == 'credit' and event.status != 'settled':
                event.status = 'pending'
            elif fact.fact_type == 'event_settled':
                event.status = 'settled'
                event.settlement_date = fact.effective_date or fact.sent_at[:10]
            elif fact.fact_type == 'event_retry' and event.status == 'failed':
                retries = [e for e in events if e.linked_event_id == event.event_id and e.status in ('scheduled', 'pending', 'settled')]
                if not retries:
                    # The bill remains owed; reserve it now when no retry date exists.
                    events.append(replace(event, event_id=f'retry_{event.event_id}', status='pending', linked_event_id=event.event_id))
        events = EventLifecycle.normalize(events)
        for event in events:
            if EventLifecycle.is_valid_cash_event(event):
                EventLifecycle.get_effective_amount(event)
                date.fromisoformat(event.settlement_date)

        explicit = []
        for event in events:
            if not EventLifecycle.is_valid_cash_event(event) or not event.amount:
                continue
            if event.status == 'settled' and event.settlement_date <= request_date:
                continue  # The starting available balance already includes settled history.
            if event.direction == 'credit':
                if event.status == 'scheduled' and event.category != 'salary':
                    continue  # Estimated refunds, prizes and bonuses are not salary.
                if _regular_salary(event) and event.status == 'scheduled':
                    continue  # Salary amendments are applied in the single salary path below.
            if event.settlement_date > end.isoformat():
                continue
            if event.direction == 'credit' and event.settlement_date < request_date:
                continue
            explicit.append(_cash(event, cash_date=max(event.settlement_date, request_date)))

        projected = RecurrenceEngine.project_recurring_events(events, request_date, horizon_days)
        for item in projected:
            source = by_id[item['source_event_id']]
            for fact in facts:
                if (fact.fact_type == 'rent_increase' and item['category'] == 'rent'
                        and item['settlement_date'] >= (fact.effective_date or request_date)
                        and source.settlement_date < (fact.effective_date or fact.sent_at[:10])):
                    item['amount'] = round(source.amount * (1 + fact.details['percentage']), 2)
                    item['evidence_message_id'] = fact.message_id

        # Suppress only the same known obligation, never another account in its category.
        for item in projected:
            matching = [e for e in explicit if e['direction'] == 'debit' and e['currency'] == item['currency']
                        and e['settlement_date'] == item['settlement_date']
                        and (e['description'] == item['description'] or e.get('linked_event_id') in item['recurrence_evidence_ids'])]
            for event in matching:
                event['is_recurring'] = True
                event['source_event_id'] = item['source_event_id']
                event['recurrence_evidence_ids'] = item['recurrence_evidence_ids']
        projected = [item for item in projected if not any(
            e.get('source_event_id') == item['source_event_id'] and e['settlement_date'] == item['settlement_date']
            for e in explicit)]
        incomes = self._salary_events(events, facts, start, end, profile.home_currency)
        return sorted(explicit + projected + incomes, key=lambda e: (e.get('cash_date', e['settlement_date']), e['event_id']))

    @staticmethod
    def _salary_events(events, facts, start, end, home_currency):
        salary_facts = [f for f in facts if f.fact_type.startswith('salary_')]
        latest = {f.fact_type: f for f in salary_facts}
        end_fact = latest.get('salary_end')
        restart = next((f for f in reversed(salary_facts) if f.fact_type in ('salary_start', 'salary_resume')), None)
        ended = end_fact and (restart is None or restart.sent_at <= end_fact.sent_at)
        regular = [e for e in events if _regular_salary(e) and e.status in ('settled', 'scheduled')]
        if any('final' in e.description.lower() for e in regular if e.settlement_date < start.isoformat()) and restart is None:
            ended = True

        result = []
        groups = defaultdict(list)
        remaining = latest.get('salary_remaining')
        settled_regular = [e for e in regular if e.status == 'settled']
        settled_dates = sorted(set(date.fromisoformat(e.settlement_date) for e in settled_regular))
        gaps = [(b - a).days for a, b in zip(settled_dates, settled_dates[1:])] if len(settled_dates) >= 2 else []
        med_gap = sorted(gaps)[len(gaps)//2] if gaps else 30
        is_weekly = (med_gap <= 8 and len(settled_dates) >= 4 and max(gaps) <= 12)

        settled_days = [date.fromisoformat(e.settlement_date).day for e in settled_regular]
        day_counts = Counter(settled_days)
        multi_days = [d for d, cnt in day_counts.items() if cnt >= 3]
        has_second = any('second household' in e.description.lower() for e in regular)

        if is_weekly and not has_second:
            for event in regular:
                groups[(event.currency, 'weekly')].append(event)
        elif len(multi_days) > 1 and not has_second:
            for d in sorted(multi_days):
                for event in regular:
                    if date.fromisoformat(event.settlement_date).day == d:
                        groups[(event.currency, f'day_{d}')].append(event)
        else:
            for event in regular:
                if remaining and 'second household' in event.description.lower():
                    continue
                name = 'second' if 'second household' in event.description.lower() else 'main'
                groups[(event.currency, name)].append(event)
        # A dated employer assertion can supply a missing first/confirmed salary row.
        for fact in salary_facts:
            if fact.amount is not None and fact.currency and not any(key[0] == fact.currency for key in groups):
                groups[(fact.currency, 'main')] = []

        end_date = (date.fromisoformat(end_fact.effective_date) if (end_fact and end_fact.effective_date)
                    else (date.fromisoformat(end_fact.sent_at[:10]) if (end_fact and end_fact.sent_at) else None))

        has_income_uncertain = any(f.fact_type == 'income_uncertain' for f in facts)

        for (currency, group_name), group in groups.items():
            group.sort(key=lambda e: (e.settlement_date, e.event_id))
            applicable = [f for f in salary_facts if f.currency in (None, currency)] if group_name in ('main', 'weekly') else []
            is_weekly_group = (group_name == 'weekly')
            days = [date.fromisoformat(e.settlement_date).day for e in group]
            pay_day = Counter(days).most_common(1)[0][0] if days else None
            # Preserve the established salary date when a one-off payslip is later.
            history = [e for e in group if e.status == 'settled' and e.settlement_date < start.isoformat()
                       and (is_weekly_group or date.fromisoformat(e.settlement_date).day == pay_day)]
            scheduled = [e for e in group if e.status == 'scheduled' and e.settlement_date >= start.isoformat()]
            dated = [f for f in applicable if f.effective_date and f.fact_type != 'salary_end']
            recurring = (is_weekly_group and not has_income_uncertain) or monthly_history(history) or monthly_history(history + scheduled)
            recurring = recurring or any(f.fact_type in ('salary_resume', 'salary_regular', 'salary_base', 'salary_remaining', 'salary_increase') and f.amount is not None for f in applicable)
            source = history[-1] if history else (group[-1] if group else None)
            amount = source.amount if source else None
            if history:
                hist_amts = [e.amount for e in history if e.amount is not None]
                if hist_amts and (is_weekly_group or len(set(hist_amts)) > 1):
                    amount = round(median(hist_amts), 2)
            if scheduled:
                due = date.fromisoformat(scheduled[0].settlement_date)
                amount = scheduled[0].amount
                pay_day = due.day
            elif history:
                if is_weekly_group:
                    due = date.fromisoformat(history[-1].settlement_date) + timedelta(days=7)
                else:
                    due = next_month(date.fromisoformat(history[-1].settlement_date), pay_day)
            elif dated:
                due = date.fromisoformat(dated[-1].effective_date)
                pay_day = due.day
            else:
                continue
            if dated:
                last_dated = dated[-1]
                if last_dated.fact_type in ('salary_delay', 'salary_start', 'salary_resume', 'salary_confirmed'):
                    due = date.fromisoformat(last_dated.effective_date)
                    pay_day = due.day
            if due < start:
                # A specified historical effective date changes the future rate,
                # but does not justify inventing a missed salary payment.
                if not applicable and not is_weekly_group:
                    continue
                while due < start:
                    due = (due + timedelta(days=7)) if is_weekly_group else next_month(due, pay_day)
            if not recurring and not scheduled and not dated:
                continue
            first_due = due
            while due <= end:
                day_str = due.isoformat()
                if ended and end_date and due > end_date:
                    break
                matching = next((e for e in scheduled if e.settlement_date == day_str), None)
                if ended and matching is None:
                    break
                cash_amount = matching.amount if matching else amount
                used_fact = None
                for fact in applicable:
                    if fact.amount is None or fact.fact_type in ('salary_end', 'salary_delay'):
                        continue
                    effective = fact.effective_date or first_due.isoformat()
                    if day_str < effective:
                        continue
                    if fact.fact_type in ('salary_next', 'salary_temporary', 'salary_confirmed') and due != first_due:
                        continue
                    cash_amount, used_fact = fact.amount, fact
                if cash_amount is not None and cash_amount > 0:
                    event_id = matching.event_id if matching else f'proj_sal_{currency}_{group_name}_{due:%Y%m%d}'
                    result.append({
                        'event_id': event_id, 'source_event_id': source.event_id if source else None,
                        'amount': cash_amount, 'currency': currency, 'direction': 'credit',
                        'settlement_date': day_str, 'status': 'scheduled' if matching or used_fact else 'projected',
                        'category': 'salary', 'description': 'Confirmed or recurring salary',
                        'is_projected': matching is None, 'is_recurring': recurring,
                        'recurrence_evidence_ids': [e.event_id for e in history],
                        'evidence_message_id': used_fact.message_id if used_fact else None,
                    })
                if not recurring:
                    break
                due = (due + timedelta(days=7)) if is_weekly_group else next_month(due, pay_day)

        # Only the approved invoice is forecast; other project earnings are contingent.
        for fact in facts:
            if fact.fact_type != 'confirmed_invoice' or fact.amount is None or not fact.effective_date:
                continue
            if start.isoformat() <= fact.effective_date <= end.isoformat():
                if not any(e.direction == 'credit' and e.amount == fact.amount and e.currency == fact.currency
                           and e.settlement_date == fact.effective_date and e.status in ('settled', 'scheduled') for e in events):
                    result.append({'event_id': f'msg_{fact.message_id}', 'source_event_id': None,
                                   'amount': fact.amount, 'currency': fact.currency or home_currency,
                                   'direction': 'credit', 'settlement_date': fact.effective_date,
                                   'status': 'scheduled', 'category': 'salary', 'is_recurring': False,
                                   'is_projected': False, 'evidence_message_id': fact.message_id,
                                   'description': 'Confirmed one-time invoice payment'})
        return result
