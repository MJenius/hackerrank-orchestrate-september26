"""Generate legal schedules, simulate them, and apply the six published rules."""
from dataclasses import asdict
from datetime import date, timedelta
from typing import Dict, List, Optional, Tuple

from code.data.models import FinancialProfile, Request, RequestPaymentOption
from code.finance.simulator import BalanceSimulator, cents
from code.finance.plan_ranker import CandidatePlan, rank_candidates


def format_plan_amount(amount: float) -> str:
    value = cents(amount)
    return str(value // 100) if value % 100 == 0 else f'{value / 100:.2f}'


class FinancialOptimizer:
    def __init__(self, simulator: BalanceSimulator):
        self.simulator = simulator

    def evaluate_request(
        self, profile: FinancialProfile, request: Request,
        options: List[RequestPaymentOption], future_events: List[Dict],
        diagnostics: Optional[Dict] = None,
    ) -> Tuple[float, CandidatePlan]:
        from code.finance.spending_changes import SpendingChangeOptimizer

        requested = cents(request.requested_amount)
        minimum = cents(profile.minimum_balance_to_keep)
        start = date.fromisoformat(request.request_date)
        end = (start + timedelta(days=90)).isoformat()
        date.fromisoformat(request.desired_completion_date)
        baseline_safe, low, balances = self.simulator.simulate_trajectory(
            profile, request.request_date, future_events, {})

        # A payment today shifts every later balance by precisely that amount.
        # Opening balance is checked independently, before same-day settlements.
        available = min(round(balance * 100) - minimum for balance in balances.values())
        safe_amount = max(0, min(requested, available)) / 100 if baseline_safe else 0.0

        # The earliest safe full-payment date is a property of the full 90-day
        # trajectory and must not depend on whether paying today is already safe.
        # Search the whole horizon conservatively: after paying the full request on
        # day d, every subsequent day must still remain above the minimum balance.
        suffix_low = float('inf')
        earliest = None
        for day, balance in reversed(list(balances.items())):
            suffix_low = min(suffix_low, round(balance * 100))
            if suffix_low - requested >= minimum:
                earliest = day

        candidates = []
        rejected = []
        spend = SpendingChangeOptimizer(self.simulator)

        def consider(method, payments, option_id=None):
            dates = list(payments)
            if (not dates or dates != sorted(dates) or dates[0] < request.request_date
                    or dates[-1] > min(end, request.desired_completion_date)):
                rejected.append({'method': method, 'option': option_id, 'reason': 'dates/deadline/horizon'})
                return
            plan = CandidatePlan(
                plan_type=method,
                payment_plan_str='|'.join(f'{day}:{format_plan_amount(amount)}' for day, amount in payments.items()),
                earliest_date_for_full_payment=earliest,
                spending_changes_needed='none',
                total_amount_paid=sum(cents(amount) for amount in payments.values()) / 100,
                first_payment_date=dates[0], number_of_payments=len(payments),
                payment_option_id=option_id, completes_by_desired_date=True,
                requires_spending_changes=False,
                affordability_status=('affordable_now' if method == 'full_payment' else
                                      'affordable_later' if method == 'wait' else 'affordable_with_plan'),
            )
            safe, lowest, _ = self.simulator.simulate_trajectory(
                profile, request.request_date, future_events, payments)
            if safe:
                candidates.append(plan)
            else:
                rejected.append({'method': method, 'option': option_id, 'reason': 'minimum balance',
                                 'lowest_balance': lowest, 'schedule': payments})
                # A safe unchanged schedule dominates every changed version of
                # itself, so only failed schedules need spending-change search.
                candidates.extend(spend.generate_spending_change_candidates(
                    profile, request, future_events, payments, earliest, base_plan=plan))

        methods = profile.payment_methods_user_will_consider
        if 'full_payment' in methods:
            consider('full_payment', {request.request_date: requested / 100})

        if 'installments' in methods:
            for option in options:
                if option.payment_method != 'installments':
                    continue
                reason = None
                frequency = option.payment_frequency_days
                n = option.number_of_payments
                if profile.max_installment_months is None:
                    reason = 'installments disabled by blank maximum'
                elif n < 2 or frequency is None or frequency <= 0 or frequency != int(frequency):
                    reason = 'invalid installment count/frequency'
                elif (n - 1) * frequency > profile.max_installment_months * 30:
                    reason = 'maximum installment duration'
                elif option.request_id != request.request_id:
                    reason = 'option belongs to another request'
                elif cents(option.payment_amount) * n != cents(option.total_payable_amount):
                    reason = 'option total does not match schedule'
                elif cents(option.total_payable_amount) != requested + cents(option.financing_fee):
                    reason = 'option total does not match request plus fee'
                if reason:
                    rejected.append({'method': 'installments', 'option': option.payment_option_id, 'reason': reason})
                    continue
                first = date.fromisoformat(option.first_payment_date)
                payments = {(first + timedelta(days=i * int(frequency))).isoformat(): option.payment_amount
                            for i in range(n)}
                consider('installments', payments, option.payment_option_id)

        if (request.allows_partial_payment and 'partial_payment' in methods
                and 0 < cents(safe_amount) < requested and earliest
                and earliest > request.request_date):
            consider('partial_payment', {request.request_date: safe_amount,
                                       earliest: (requested - cents(safe_amount)) / 100})

        if 'full_payment' in methods and earliest and earliest > request.request_date:
            consider('wait', {earliest: requested / 100})

        ranked = rank_candidates(candidates)
        best = ranked[0] if ranked else CandidatePlan(
            'not_recommended', 'none', earliest, 'none', 0.0, request.request_date,
            0, None, False, False, 'not_affordable')
        if diagnostics is not None:
            diagnostics.update(starting_balance=profile.current_available_balance,
                               minimum_balance=profile.minimum_balance_to_keep,
                               canonical_events=future_events, baseline_balances=balances,
                               baseline_safe=baseline_safe, baseline_minimum=low,
                               amount_safe_to_pay=safe_amount, earliest_full_date=earliest,
                               candidates=[dict(asdict(p), ranking=[0, int(p.requires_spending_changes),
                                           p.total_amount_paid, p.first_payment_date, p.number_of_payments,
                                           p.payment_option_id or 'zzzz']) for p in ranked],
                               rejected_candidates=rejected)
        return safe_amount, best
