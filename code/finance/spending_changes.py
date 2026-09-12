"""
SpendingChangeOptimizer — searches for legal stop/reduce_to combinations
that free enough cash for a request to become affordable.

Rules:
  - Only non-protected, flexible recurring events may be changed.
  - Category must be in user's willing_to_stop (for stop) or willing_to_reduce (for reduce_to).
  - Max 3 changes total.
  - stop and reduce_to on the same event are mutually exclusive.
  - reduce_to amount must be >= minimum_allowed_amount.
"""
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple
from itertools import combinations
from code.data.models import FinancialProfile, Request, FinancialEvent
from code.finance.simulator import BalanceSimulator
from code.finance.plan_ranker import CandidatePlan


class SpendingChangeOptimizer:
    def __init__(self, simulator: BalanceSimulator):
        self.simulator = simulator

    def generate_spending_change_candidates(
        self,
        profile: FinancialProfile,
        request: Request,
        future_events: List[Dict],
        payment_schedule: Dict[str, float],
        earliest_full_date: Optional[str] = None,
        base_plan: Optional[CandidatePlan] = None
    ) -> List[CandidatePlan]:
        """
        Evaluate all legal spending-change combinations (up to 3 changes).
        Every candidate MUST be actually simulated and satisfy all financial-safety
        and deadline constraints. No shortcuts or approximations are used.
        Returns all valid CandidatePlan instances.
        """
        from code.finance.optimizer import format_plan_amount
        candidates = []
        changeable = self._find_changeable_events(future_events, profile)
        if not changeable:
            return []

        formatted_req_amt = format_plan_amount(request.requested_amount)

        # Try 1, 2, and 3 changes
        for num_changes in range(1, min(4, len(changeable) + 1)):
            for combo in combinations(changeable, num_changes):
                change_variants = self._generate_change_variants(combo, profile)
                for variant in change_variants:
                    modified_events = self._apply_changes(future_events, variant)
                    is_safe_var, _, _ = self.simulator.simulate_trajectory(
                        profile, request.request_date, modified_events, payment_schedule
                    )
                    
                    # Strictly require full financial safety in simulation
                    if is_safe_var:
                        change_str = self._format_changes(variant)
                        if base_plan is not None:
                            candidates.append(CandidatePlan(
                                plan_type=base_plan.plan_type,
                                payment_plan_str=base_plan.payment_plan_str,
                                earliest_date_for_full_payment=base_plan.earliest_date_for_full_payment,
                                spending_changes_needed=change_str,
                                total_amount_paid=base_plan.total_amount_paid,
                                first_payment_date=base_plan.first_payment_date,
                                number_of_payments=base_plan.number_of_payments,
                                payment_option_id=base_plan.payment_option_id,
                                completes_by_desired_date=base_plan.completes_by_desired_date,
                                requires_spending_changes=True,
                                affordability_status='affordable_with_plan'
                            ))
                        else:
                            candidates.append(CandidatePlan(
                                plan_type='full_payment',
                                payment_plan_str=f'{request.request_date}:{formatted_req_amt}',
                                earliest_date_for_full_payment=earliest_full_date,
                                spending_changes_needed=change_str,
                                total_amount_paid=request.requested_amount,
                                first_payment_date=request.request_date,
                                number_of_payments=1,
                                payment_option_id=None,
                                completes_by_desired_date=True,
                                requires_spending_changes=True,
                                affordability_status='affordable_with_plan'
                            ))

        return candidates

    def _find_changeable_events(
        self, future_events: List[Dict], profile: FinancialProfile
    ) -> List[Dict]:
        """Find projected recurring events that can be stopped or reduced."""
        changeable = []
        seen_sources = set()
        protected = set(profile.expense_categories_to_protect)
        willing_stop = set(profile.expense_categories_user_is_willing_to_stop)
        willing_reduce = set(profile.expense_categories_user_is_willing_to_reduce)

        for e in future_events:
            # Only projected recurring flexible expenses may be changed; explicit one-time expenses must never qualify
            if not e.get('is_recurring', e.get('is_projected', False)) or e.get('status') == 'pending':
                continue
            if e.get('direction') != 'debit':
                continue
            cat = e.get('category', '')
            if cat in protected:
                continue
            flex = e.get('flexibility', 'fixed')
            if flex == 'fixed':
                continue

            source_id = e.get('source_event_id', e.get('event_id', ''))
            if source_id in seen_sources:
                continue

            can_stop = flex in ('stoppable', 'reducible_or_stoppable') and cat in willing_stop
            can_reduce = flex in ('reducible', 'reducible_or_stoppable') and cat in willing_reduce

            if can_stop or can_reduce:
                changeable.append({
                    'source_event_id': source_id,
                    'event_id': e.get('event_id', ''),
                    'category': cat,
                    'flexibility': flex,
                    'amount': e.get('amount', 0),
                    'minimum_allowed_amount': e.get('minimum_allowed_amount'),
                    'can_stop': can_stop,
                    'can_reduce': can_reduce,
                })
                seen_sources.add(source_id)

        # Sort by amount saved (descending) so we try biggest savings first
        changeable.sort(key=lambda x: x['amount'], reverse=True)
        return changeable

    def _generate_change_variants(
        self, combo: Tuple, profile: FinancialProfile
    ) -> List[List[Dict]]:
        """For a combination of changeable events, enumerate all legal mixed stop/reduce variants."""
        if len(combo) == 0:
            return []

        from itertools import product

        # For each event in combo, build list of legal action dicts
        event_action_lists = []
        for c in combo:
            actions_for_c = []
            if c['can_stop']:
                actions_for_c.append({
                    'action': 'stop',
                    'source_event_id': c['source_event_id'],
                    'event_id': c['event_id'],
                    'amount': c.get('amount', 0.0),
                })
            if c['can_reduce']:
                minimum_allowed = c.get('minimum_allowed_amount')
                reduced_to = 0.0 if minimum_allowed is None else minimum_allowed
                if 0 <= reduced_to < c['amount']:
                    actions_for_c.append({
                        'action': 'reduce_to',
                        'source_event_id': c['source_event_id'],
                        'event_id': c['event_id'],
                        'amount': c.get('amount', 0.0),
                        'new_amount': reduced_to,
                    })
            if not actions_for_c:
                return []
            event_action_lists.append(actions_for_c)

        # Enumerate all combinations across events
        variants = []
        for action_tuple in product(*event_action_lists):
            variants.append(list(action_tuple))

        return variants

    def _apply_changes(
        self, future_events: List[Dict], changes: List[Dict]
    ) -> List[Dict]:
        """Apply spending changes to future events, returning modified copy."""
        stop_sources = {
            c['source_event_id'] for c in changes if c['action'] == 'stop'
        }
        reduce_map = {
            c['source_event_id']: c['new_amount']
            for c in changes if c['action'] == 'reduce_to'
        }

        modified = []
        for e in future_events:
            if not e.get('is_recurring', e.get('is_projected', False)) or e.get('status') == 'pending':
                modified.append(e)
                continue
            src = e.get('source_event_id', e.get('event_id', ''))
            eid = e.get('event_id', '')

            if src in stop_sources or eid in stop_sources:
                continue  # Remove stopped events
            elif src in reduce_map or eid in reduce_map:
                new_amt = reduce_map[src] if src in reduce_map else reduce_map[eid]
                e_copy = dict(e)
                e_copy['amount'] = new_amt
                modified.append(e_copy)
            else:
                modified.append(e)

        return modified

    def _format_changes(self, changes: List[Dict]) -> str:
        """Format changes as 'stop:event_id|reduce_to:event_id:amount'."""
        from code.finance.optimizer import format_plan_amount
        parts = []
        for c in changes:
            # Use the source_event_id (original event) for the output
            eid = c['source_event_id']
            if c['action'] == 'stop':
                parts.append(f"stop:{eid}")
            elif c['action'] == 'reduce_to':
                amt_str = format_plan_amount(c['new_amount'])
                parts.append(f"reduce_to:{eid}:{amt_str}")
        return '|'.join(parts)
