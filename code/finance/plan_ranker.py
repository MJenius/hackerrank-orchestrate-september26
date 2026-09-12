from dataclasses import dataclass
from typing import List, Optional
from code.data.models import FinancialEvent, RequestPaymentOption

@dataclass
class CandidatePlan:
    plan_type: str  # full_payment, installments, partial_payment, wait, not_recommended
    payment_plan_str: str  # e.g. '2024-03-03:25256' or 'none'
    earliest_date_for_full_payment: Optional[str]
    spending_changes_needed: str  # e.g. 'none' or 'stop:event_476'
    total_amount_paid: float
    first_payment_date: Optional[str]
    number_of_payments: int
    payment_option_id: Optional[str]
    completes_by_desired_date: bool
    requires_spending_changes: bool
    affordability_status: str  # affordable_now, affordable_with_plan, affordable_later, not_affordable
    explanation: str = ''

def rank_candidates(candidates: List[CandidatePlan]) -> List[CandidatePlan]:
    # Requirement 9: Any candidate that does not complete by desired_completion_date must be rejected, not merely ranked lower.
    eligible = [c for c in candidates if c.completes_by_desired_date]
    if not eligible:
        return []

    def sort_key(c: CandidatePlan):
        # Tie breakers per rule:
        # 1. Complete the full request by desired_completion_date (all eligible are True)
        rule_1 = 0
        # 2. Require no spending changes (False before True)
        rule_2 = 1 if c.requires_spending_changes else 0
        # 3. Minimize total amount paid
        rule_3 = round(c.total_amount_paid, 2)
        # 4. Start payment earlier
        rule_4 = c.first_payment_date if c.first_payment_date else '9999-99-99'
        # 5. Use fewer payments
        rule_5 = c.number_of_payments
        # 6. Use lowest payment_option_id
        rule_6 = c.payment_option_id if c.payment_option_id else 'zzzz'
        return (rule_1, rule_2, rule_3, rule_4, rule_5, rule_6)

    return sorted(eligible, key=sort_key)
