from typing import Optional
from code.finance.plan_ranker import CandidatePlan

class ExplanationGenerator:
    @staticmethod
    def generate(
        plan: CandidatePlan,
        currency: str,
        requested_amount: float,
        amount_safe_to_pay: float,
        minimum_balance: float,
        desired_completion_date: str
    ) -> str:
        def fmt_curr(val: float) -> str:
            if currency in ('IDR', 'INR'):
                # integer format with commas
                if val == int(val):
                    return f"{currency} {int(val):,}"
                return f"{currency} {val:,.2f}"
            else:
                return f"{currency} {val:,.2f}"

        if plan.plan_type == 'full_payment' and not plan.requires_spending_changes:
            return f"Pay {fmt_curr(requested_amount)} today. This leaves at least {fmt_curr(minimum_balance)} available over the next 90 days."
        
        elif plan.plan_type == 'installments':
            # e.g., 'Use 3 installments of IDR 15,952,906.67, starting 8 August 2025. This leaves at least IDR 29,158,400 available.'
            parts = plan.payment_plan_str.split('|')
            num_inst = len(parts)
            first_part = parts[0].split(':')
            first_date = first_part[0]
            inst_amt = float(first_part[1])
            return f"Use {num_inst} installments of {fmt_curr(inst_amt)}, starting {first_date}. This leaves at least {fmt_curr(minimum_balance)} available."

        elif plan.plan_type == 'wait':
            # e.g., 'Pay IDR 5,491,000 in full on 15 November 2019. Paying earlier would take the balance below the IDR 2,668,700 minimum.'
            return f"Pay {fmt_curr(requested_amount)} in full on {plan.earliest_date_for_full_payment}. Paying earlier would take the balance below the {fmt_curr(minimum_balance)} minimum."

        elif plan.plan_type == 'partial_payment':
            # e.g., 'Pay INR 28,820 today and the remaining INR 10,840 on 15 September 2024. This completes the full request and keeps the INR 92,800 minimum protected.'
            rem = requested_amount - amount_safe_to_pay
            return f"Pay {fmt_curr(amount_safe_to_pay)} today and the remaining {fmt_curr(rem)} on {plan.earliest_date_for_full_payment}. This completes the full request and keeps the {fmt_curr(minimum_balance)} minimum protected."

        elif plan.plan_type == 'full_payment' and plan.requires_spending_changes:
            return f"{plan.spending_changes_needed}, then pay {fmt_curr(requested_amount)} today. This leaves at least {fmt_curr(minimum_balance)} available."

        else: # not_recommended
            return f"Do not make this payment by {desired_completion_date}. None of the available options keeps the {fmt_curr(minimum_balance)} minimum protected."
