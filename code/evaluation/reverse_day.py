"""Reverse-engineer: for each sample, which trajectory day produces the expected safe amount?"""
import sys
from decimal import Decimal
from pathlib import Path
from datetime import date, timedelta

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from code.main import generate_predictions
from code.evaluation.sample_truth import SAMPLE_GROUND_TRUTH
from code.data.loader import load_profiles, load_requests
from code.finance.simulator import cents

def main():
    traces = {}
    actual = generate_predictions(ROOT / 'dataset', 'sample_requests.csv', diagnostics=traces)
    profiles = load_profiles(ROOT / 'dataset' / 'financial_profiles.csv')
    requests = load_requests(ROOT / 'dataset' / 'sample_requests.csv')

    for rid in sorted(SAMPLE_GROUND_TRUTH.keys()):
        truth = SAMPLE_GROUND_TRUTH[rid]
        safe_expected = truth['safe']
        expected_cents = cents(safe_expected)
        trace = traces.get(rid, {})
        req = requests[rid]
        profile = profiles[req.user_id]
        minimum = cents(profile.minimum_balance_to_keep)
        requested = cents(req.requested_amount)
        balances = trace.get('baseline_balances', {})
        
        if not balances:
            continue
        
        # For each day, compute: balance - minimum
        # Find which day's (balance - minimum) == expected_safe
        # But if expected_safe == requested, it could be any day where balance >= requested + minimum
        
        if expected_cents == requested:
            # Find the first day where balance - minimum >= requested
            for d in sorted(balances):
                bal_cents = round(balances[d] * 100)
                if bal_cents - minimum >= requested:
                    break
            print(f"{rid}: safe=FULL_AMOUNT (balance always sufficient)")
            continue
        
        # Find which day matches
        found_days = []
        for d in sorted(balances):
            bal_cents = round(balances[d] * 100)
            avail = bal_cents - minimum
            clamped = max(0, min(requested, avail))
            if abs(clamped - expected_cents) <= 1:
                found_days.append((d, bal_cents/100, avail/100))
        
        if found_days:
            for d, bal, avail in found_days:
                offset = (date.fromisoformat(d) - date.fromisoformat(req.request_date)).days
                print(f"{rid}: day={d} (offset={offset}), balance={bal:.2f}, avail={avail:.2f}, expected_safe={safe_expected}")
        else:
            # Maybe the safe amount is computed differently - try balance on request_date minus sum of debits
            print(f"{rid}: NO MATCHING DAY FOUND, expected_safe={safe_expected}")
            # Show the closest match
            closest = None
            closest_diff = float('inf')
            for d in sorted(balances):
                bal_cents = round(balances[d] * 100)
                avail = bal_cents - minimum
                clamped = max(0, min(requested, avail))
                diff = abs(clamped - expected_cents)
                if diff < closest_diff:
                    closest_diff = diff
                    closest = (d, bal_cents/100, avail/100, clamped/100)
            if closest:
                d, bal, avail, clamped = closest
                offset = (date.fromisoformat(d) - date.fromisoformat(req.request_date)).days
                print(f"  closest: day={d} (offset={offset}), balance={bal:.2f}, avail={avail:.2f}, clamped={clamped:.2f}, diff={closest_diff/100:.2f}")

if __name__ == '__main__':
    main()
