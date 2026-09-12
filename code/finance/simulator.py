"""Fixed-horizon cash simulation. Money is accumulated in integer cents."""
from datetime import date, timedelta
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from typing import Dict, List, Tuple

from code.data.models import FinancialProfile
from code.finance.currency import CurrencyConverter


def cents(value) -> int:
    """Reject missing/nonfinite money at the simulation boundary."""
    try:
        amount = Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise ValueError(f'Invalid money amount: {value!r}') from exc
    if not amount.is_finite() or amount < 0:
        raise ValueError(f'Invalid money amount: {value!r}')
    return int((amount * 100).quantize(Decimal('1'), rounding=ROUND_HALF_UP))


class BalanceSimulator:
    def __init__(self, converter: CurrencyConverter):
        self.converter = converter

    def simulate_trajectory(
        self, profile: FinancialProfile, request_date: str, events: List[Dict],
        payment_schedule: Dict[str, float], horizon_days: int = 90,
    ) -> Tuple[bool, float, Dict[str, float]]:
        start = date.fromisoformat(request_date)
        if horizon_days < 0:
            raise ValueError('Forecast horizon cannot be negative')
        days = [(start + timedelta(days=i)).isoformat() for i in range(horizon_days + 1)]
        deltas = dict.fromkeys(days, 0)
        for event in events:
            status = event.get('status', 'scheduled')
            direction = event.get('direction', 'debit')
            if status in ('cancelled', 'failed', 'unrealized') or direction == 'non_cash':
                continue
            if direction == 'credit' and status == 'pending':
                continue
            if direction not in ('credit', 'debit'):
                raise ValueError(f'Invalid cash direction: {direction}')
            settlement = event['settlement_date']
            date.fromisoformat(settlement)
            cash_date = event.get('cash_date', settlement)
            # Pending debits are committed cash, reserved before optional payments.
            if status == 'pending' and direction == 'debit':
                cash_date = request_date
            if cash_date not in deltas:
                continue
            cents(event['amount'])
            currency = event.get('currency', profile.home_currency)
            amount = self.converter.convert(event['amount'], currency, profile.home_currency, settlement)
            deltas[cash_date] += cents(amount) * (1 if direction == 'credit' else -1)

        for payment_date, amount in payment_schedule.items():
            if payment_date not in deltas:
                raise ValueError(f'Payment {payment_date} is outside the forecast')
            deltas[payment_date] -= cents(amount)

        balance = cents(profile.current_available_balance)
        minimum = cents(profile.minimum_balance_to_keep)
        lowest = balance
        balances = {}
        for day in days:
            # Dated settlements precede the requested payment on the same day.
            balance += deltas[day]
            lowest = min(lowest, balance)
            balances[day] = balance / 100
        return lowest >= minimum, lowest / 100, balances
