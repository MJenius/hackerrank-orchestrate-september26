"""Reverse-engineer: what minimum trajectory balance is needed to produce each expected safe amount?
And compare with actual to find the event amount delta."""
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

    print(f"{'rid':<12} {'expected':>14} {'actual':>14} {'need_min':>14} {'got_min':>14} {'delta':>12} notes")
    for rid in sorted(SAMPLE_GROUND_TRUTH.keys()):
        truth = SAMPLE_GROUND_TRUTH[rid]
        safe_expected = truth['safe']
        trace = traces.get(rid, {})
        req = requests[rid]
        profile = profiles[req.user_id]
        minimum = cents(profile.minimum_balance_to_keep)
        requested = cents(req.requested_amount)
        balances = trace.get('baseline_balances', {})
        safe_actual = float(actual.set_index('request_id').to_dict(orient='index')[rid]['amount_safe_to_pay'])
        
        if not balances:
            continue
        
        got_min = min(round(b * 100) for b in balances.values())
        
        expected_safe_cents = cents(safe_expected)
        
        # If expected_safe == requested, then need_min >= requested + minimum
        # Otherwise: need_min = expected_safe + minimum
        # The formula is: safe = max(0, min(requested, need_min - minimum)) / 100
        # So: expected_safe_cents = min(requested, need_min - minimum)
        # If expected_safe_cents < requested: need_min = expected_safe_cents + minimum
        
        if expected_safe_cents >= requested:
            need_min = requested + minimum
        else:
            need_min = expected_safe_cents + minimum
        
        delta = got_min - need_min  # positive = we have too much (missing debit), negative = too little (extra debit)
        
        notes = ""
        if abs(delta) < 2:
            notes = "MATCH"
        elif delta > 0:
            notes = f"OVER by {delta/100:.2f} (miss debit or extra credit)"
        else:
            notes = f"UNDER by {-delta/100:.2f} (extra debit or miss credit)"
        
        # Special case: truth says safe > 0 but our baseline is not safe
        baseline_safe = trace.get('baseline_safe', False)
        if not baseline_safe and safe_expected > 0:
            notes += " ** BASELINE_FAIL_BUT_EXPECTED_POSITIVE **"
        
        print(f"{rid:<12} {safe_expected:>14.2f} {safe_actual:>14.2f} {need_min/100:>14.2f} {got_min/100:>14.2f} {delta/100:>12.2f} {notes}")

if __name__ == '__main__':
    main()
