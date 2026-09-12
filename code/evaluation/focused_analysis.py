"""Focused analysis: compute what safe amount formula must produce, and reverse-engineer the correct formula."""
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
    actual_by_id = actual.set_index('request_id').to_dict(orient='index')
    profiles = load_profiles(ROOT / 'dataset' / 'financial_profiles.csv')
    requests = load_requests(ROOT / 'dataset' / 'sample_requests.csv')

    print(f"{'rid':<12} {'expected':>14} {'actual':>14} {'diff':>12} {'bal':>14} {'min_bal':>14} {'req_amt':>14} {'min_traj':>14} {'avail':>14} {'safe_flg':>8}")
    for rid in sorted(SAMPLE_GROUND_TRUTH.keys()):
        truth = SAMPLE_GROUND_TRUTH[rid]
        pred = actual_by_id[rid]
        safe_expected = truth['safe']
        safe_actual = float(pred['amount_safe_to_pay'])
        trace = traces.get(rid, {})
        req = requests[rid]
        profile = profiles[req.user_id]
        minimum = cents(profile.minimum_balance_to_keep)
        requested = cents(req.requested_amount)
        balances = trace.get('baseline_balances', {})
        baseline_safe = trace.get('baseline_safe', False)
        
        if balances:
            min_balance_cents = min(round(b * 100) for b in balances.values())
            available = min_balance_cents - minimum
            formula_safe = max(0, min(requested, available)) / 100 if baseline_safe else 0.0
            diff = safe_actual - safe_expected
            
            # What available cents would produce the expected safe amount?
            expected_cents = cents(safe_expected)
            needed_avail = expected_cents  # since safe = min(requested, available) / 100
            if expected_cents >= requested:
                needed_avail_str = f">={requested}"
            else:
                needed_avail_str = str(expected_cents)
            
            print(f"{rid:<12} {safe_expected:>14.2f} {safe_actual:>14.2f} {diff:>12.2f} {profile.current_available_balance:>14.2f} {profile.minimum_balance_to_keep:>14.2f} {req.requested_amount:>14.2f} {min_balance_cents/100:>14.2f} {available/100:>14.2f} {'SAFE' if baseline_safe else 'FAIL':>8}")
        
    # Now let's look at what events are MISSING or EXTRA
    print("\n\nMISSING/EXTRA EVENT ANALYSIS:")
    for rid in sorted(SAMPLE_GROUND_TRUTH.keys()):
        truth = SAMPLE_GROUND_TRUTH[rid]
        safe_expected = truth['safe']
        pred = actual_by_id[rid]
        safe_actual = float(pred['amount_safe_to_pay'])
        if abs(safe_actual - safe_expected) < 0.005:
            continue
        
        trace = traces.get(rid, {})
        req = requests[rid]
        profile = profiles[req.user_id]
        minimum = cents(profile.minimum_balance_to_keep)
        balances = trace.get('baseline_balances', {})
        diff_cents = cents(safe_actual) - cents(safe_expected)
        
        # The diff in available cents = diff in safe amount * 100
        # positive diff means we compute MORE available than truth expects
        # this means either: (a) we're MISSING some debit, or (b) we have an EXTRA credit
        
        if diff_cents > 0:
            cause = f"TOO HIGH by {diff_cents} cents - missing a debit or extra credit"
        else:
            cause = f"TOO LOW by {-diff_cents} cents - extra debit or missing credit"
        
        print(f"\n{rid}: {cause}")
        
        # For requests where baseline_safe is False but expected safe > 0,
        # the formula clips to 0 incorrectly
        baseline_safe = trace.get('baseline_safe', False)
        if not baseline_safe and safe_expected > 0:
            print(f"  ** BASELINE NOT SAFE but expected safe={safe_expected} > 0")
            min_balance_cents = min(round(b * 100) for b in balances.values())
            avail = min_balance_cents - minimum
            print(f"  min_trajectory={min_balance_cents/100:.2f}, minimum={minimum/100:.2f}, available={avail/100:.2f}")

if __name__ == '__main__':
    main()
