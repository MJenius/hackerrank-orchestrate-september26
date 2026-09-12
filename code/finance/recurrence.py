"""Evidence-based calendar and category-cadence expense projections."""
from calendar import monthrange
from collections import Counter, defaultdict
from datetime import date, timedelta
from statistics import median

from code.finance.lifecycle import EventLifecycle


def next_month(day, anchor_day=None):
    year, month = (day.year + 1, 1) if day.month == 12 else (day.year, day.month + 1)
    return date(year, month, min(anchor_day or day.day, monthrange(year, month)[1]))


def monthly_history(events):
    dates = sorted({date.fromisoformat(e.settlement_date) for e in events})
    if len(dates) < 2:
        return False
    return all(next_month(a, max(d.day for d in dates)) == b for a, b in zip(dates, dates[1:]))


class RecurrenceEngine:
    @staticmethod
    def project_recurring_events(events, request_date, horizon_days=90):
        start = date.fromisoformat(request_date)
        end = start + timedelta(days=horizon_days)
        groups = defaultdict(list)
        for event in EventLifecycle.normalize(events):
            if not EventLifecycle.is_valid_cash_event(event):
                continue
            EventLifecycle.get_effective_amount(event)
            if event.status != 'settled' or event.direction != 'debit' or event.settlement_date >= request_date:
                continue
            if not event.amount:
                continue
            variable = event.category in ('groceries', 'transport', 'dining')
            key = (event.user_id, event.category, event.currency, '' if variable else event.description)
            groups[key].append(event)

        projected = []
        for (_, category, _, _), history in groups.items():
            history.sort(key=lambda e: (e.settlement_date, e.event_id))
            variable = category in ('groceries', 'transport', 'dining')
            cadence = None
            if variable:
                dates = sorted({date.fromisoformat(e.settlement_date) for e in history})
                gaps = [(b - a).days for a, b in zip(dates, dates[1:])]
                if not gaps:
                    continue
                cadence, count = Counter(gaps).most_common(1)[0]
                if count < 2 or count * 2 < len(gaps):
                    continue
                if len(history) < 3:
                    continue
            elif not monthly_history(history):
                continue

            source = history[-1]
            last_day = date.fromisoformat(source.settlement_date)
            anchor = max(date.fromisoformat(e.settlement_date).day for e in history)
            due = last_day + timedelta(days=cadence) if cadence else next_month(last_day, anchor)
            # Missing a whole expected cycle is evidence that an old habit stopped.
            if due < start:
                continue
            recent = [e.amount for e in history if date.fromisoformat(e.settlement_date) >= start - timedelta(days=90)]
            # ponytail: a recent median estimates variable spending, not its worst
            # case; replace with a calibrated reserve when more history exists.
            amount = round(median(recent or [source.amount]), 2) if variable else source.amount
            while due <= end:
                projected.append({
                    'event_id': f'proj_{source.event_id}_{due:%Y%m%d}',
                    'source_event_id': source.event_id,
                    'amount': amount, 'currency': source.currency,
                    'direction': 'debit', 'settlement_date': due.isoformat(),
                    'status': 'projected', 'category': source.category,
                    'description': source.description, 'flexibility': source.flexibility,
                    'minimum_allowed_amount': source.minimum_allowed_amount,
                    'is_projected': True, 'is_recurring': True,
                    'recurrence_evidence_ids': [e.event_id for e in history],
                })
                due = due + timedelta(days=cadence) if cadence else next_month(due, anchor)
        return projected
