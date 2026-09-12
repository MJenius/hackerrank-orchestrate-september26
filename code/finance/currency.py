from typing import Dict, Optional

class CurrencyConverter:
    def __init__(self, rates: Dict[str, float]):
        self.rates = rates

    def convert(self, amount: float, from_currency: str, to_currency: str, rate_date: str) -> float:
        if from_currency == to_currency:
            return amount
        key = f"{rate_date}_{from_currency}_{to_currency}"
        if key in self.rates:
            return amount * self.rates[key]
        raise ValueError(f"No exact exchange rate found for {from_currency} -> {to_currency} on {rate_date}")
