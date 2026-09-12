"""Test different safe-amount formulas against all 25 samples."""
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

    # For each sample, try different formulas for safe amount
    print(f"{'rid':<12} {'expected':>14} {'f_day0':>14} {'f_min':>14} {'f_day0_abs':>14}")
    for rid in sorted(SAMPLE_GROUND_TRUTH.keys()):
        truth = SAMPLE_GROUND_TRUTH[rid]
        safe_expected = truth['safe']
        trace = traces.get(rid, {})
        req = requests[rid]
        profile = profiles[req.user_id]
        minimum = cents(profile.minimum_balance_to_keep)
        requested = cents(req.requested_amount)
        balances = trace.get('baseline_balances', {})
        
        if not balances:
            continue
        
        # Formula 1: day-0 balance minus minimum
        day0_balance = round(balances[req.request_date] * 100)
        f_day0 = max(0, min(requested, day0_balance - minimum)) / 100
        
        # Formula 2: min over trajectory (current)
        min_balance = min(round(b * 100) for b in balances.values())
        baseline_safe = min_balance >= minimum
        f_min = max(0, min(requested, min_balance - minimum)) / 100 if baseline_safe else 0.0
        
        # Formula 3: day-0 balance minus minimum (absolute, even if negative)
        f_day0_abs = max(0, min(requested, day0_balance - minimum)) / 100
        
        match_d0 = "<<" if abs(f_day0 - safe_expected) < 0.01 else ""
        match_min = "<<" if abs(f_min - safe_expected) < 0.01 else ""
        
        print(f"{rid:<12} {safe_expected:>14.2f} {f_day0:>14.2f}{match_d0:3s} {f_min:>14.2f}{match_min:3s} {f_day0_abs:>14.2f}")

if __name__ == '__main__':
    main()
