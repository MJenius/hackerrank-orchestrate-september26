"""Normalize lifecycles without equating a link with a duplicate."""
from dataclasses import replace
from math import isfinite


class EventLifecycle:
    @staticmethod
    def is_valid_cash_event(event):
        if event.status not in ('settled', 'pending', 'scheduled', 'failed', 'cancelled', 'unrealized'):
            raise ValueError(f"Unknown status on {event.event_id}: {event.status}")
        if event.direction not in ('credit', 'debit', 'non_cash'):
            raise ValueError(f"Unknown direction on {event.event_id}: {event.direction}")
        return (event.status not in ('failed', 'cancelled', 'unrealized')
                and event.direction != 'non_cash'
                and not (event.direction == 'credit' and event.status == 'pending'))

    @staticmethod
    def get_effective_amount(event):
        if event.amount is None or not isfinite(event.amount) or event.amount < 0:
            raise ValueError(f"Unresolved or invalid amount on event {event.event_id}")
        return event.amount

    @staticmethod
    def normalize(events):
        by_id = {}
        for event in events:
            if event.event_id in by_id and event != by_id[event.event_id]:
                raise ValueError(f"Conflicting duplicate event_id: {event.event_id}")
            by_id[event.event_id] = replace(event)
        superseded = set()
        for event in by_id.values():
            prior = by_id.get(event.linked_event_id)
            if prior is None:
                continue
            if prior.user_id != event.user_id:
                raise ValueError(f"Cross-user lifecycle link on {event.event_id}")
            # A posted debit replaces its authorization. A disputed possible
            # duplicate remains reserved until its cancellation actually posts.
            if (event.direction == prior.direction
                    and prior.status in ('pending', 'scheduled', 'failed')
                    and event.status in ('settled', 'cancelled')
                    and event.currency == prior.currency
                    and event.amount == prior.amount):
                superseded.add(prior.event_id)
        return [e for e in by_id.values() if e.event_id not in superseded]
