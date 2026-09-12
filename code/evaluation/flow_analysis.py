"""For each mismatched sample, compute what the correct set of debits/credits should look like.
Focus on the DELTA between our trajectory minimum and the required minimum."""
import sys, csv
from decimal import Decimal
from pathlib import Path
from datetime import date, timedelta
from collections import defaultdict

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from code.main import generate_predictions
from code.evaluation.sample_truth import SAMPLE_GROUND_TRUTH
from code.data.loader import (load_profiles, load_requests, load_financial_events,
                               load_exchange_rates)
from code.finance.simulator import cents
from code.finance.currency import CurrencyConverter

def main():
    traces = {}
    actual = generate_predictions(ROOT / 'dataset', 'sample_requests.csv', diagnostics=traces)
    profiles = load_profiles(ROOT / 'dataset' / 'financial_profiles.csv')
    requests = load_requests(ROOT / 'dataset' / 'sample_requests.csv')
    all_events = load_financial_events(ROOT / 'dataset' / 'financial_events.csv')
    rates = load_exchange_rates(ROOT / 'dataset' / 'exchange_rates.csv')
    converter = CurrencyConverter(rates)

    for rid in sorted(SAMPLE_GROUND_TRUTH.keys()):
        truth = SAMPLE_GROUND_TRUTH[rid]
        safe_expected = truth['safe']
        safe_actual = float(actual.set_index('request_id').to_dict(orient='index')[rid]['amount_safe_to_pay'])
        if abs(safe_actual - safe_expected) < 0.005:
            continue

        trace = traces.get(rid, {})
        req = requests[rid]
        profile = profiles[req.user_id]
        delta_cents = cents(safe_actual) - cents(safe_expected)
        
        # Get the future events and compute cumulative sum
        events = trace.get('canonical_events', [])
        
        # The minimum trajectory point determines safe amount
        balances = trace.get('baseline_balances', {})
        min_day = min(balances, key=lambda d: balances[d])
        
        # Sum all events up to min_day
        credits_to_min = []
        debits_to_min = []
        for e in events:
            sd = e.get('cash_date', e['settlement_date'])
            if sd <= min_day:
                if e['direction'] == 'credit':
                    credits_to_min.append(e)
                else:
                    debits_to_min.append(e)
        
        total_credits = sum(e['amount'] for e in credits_to_min)
        total_debits = sum(e['amount'] for e in debits_to_min)
        
        print(f"\n{rid}: delta={delta_cents/100:.2f} (actual-expected)")
        print(f"  min_day={min_day}")
        print(f"  balance={profile.current_available_balance}, credits_to_min={total_credits:.2f}, debits_to_min={total_debits:.2f}")
        print(f"  net_flow={total_credits - total_debits:.2f}")
        print(f"  computed_min_bal={profile.current_available_balance + total_credits - total_debits:.2f}")
        print(f"  actual_min_bal={balances[min_day]:.2f}")
        
        # Cross-currency events might explain differences - check for FX
        fx_events = [e for e in events if e.get('currency', profile.home_currency) != profile.home_currency]
        if fx_events:
            print(f"  ** HAS {len(fx_events)} CROSS-CURRENCY EVENTS")
            for e in fx_events:
                print(f"    {e['settlement_date']} {e['direction']} {e['amount']} {e['currency']} [{e['event_id']}]")
                # Check the FX conversion
                converted = converter.convert(e['amount'], e['currency'], profile.home_currency, e['settlement_date'])
                print(f"      -> {converted:.2f} {profile.home_currency}")

if __name__ == '__main__':
    main()
