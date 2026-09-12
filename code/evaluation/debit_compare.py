"""Compare: how much do our projected debits differ from what's needed?
For each request, compute what the total debits-to-min-day SHOULD be."""
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
        safe_actual = float(actual.set_index('request_id').to_dict(orient='index')[rid]['amount_safe_to_pay'])
        delta = safe_actual - safe_expected
        if abs(delta) < 0.005:
            continue

        trace = traces.get(rid, {})
        req = requests[rid]
        profile = profiles[req.user_id]
        minimum = cents(profile.minimum_balance_to_keep)
        requested = cents(req.requested_amount)
        balances = trace.get('baseline_balances', {})
        events = trace.get('canonical_events', [])
        
        # Expected min trajectory balance
        expected_safe_cents = cents(safe_expected)
        baseline_safe = trace.get('baseline_safe', False)
        if not baseline_safe and safe_expected > 0:
            # Special case: need different min computation
            need_min = expected_safe_cents + minimum
        elif expected_safe_cents >= requested:
            need_min = requested + minimum
        else:
            need_min = expected_safe_cents + minimum
        
        # What debits-to-min should be:
        # need_min = balance + credits_to_min - debits_to_min_needed
        # debits_to_min_needed = balance + credits_to_min - need_min
        
        min_day = min(balances, key=lambda d: balances[d])
        credits_to_min = sum(e['amount'] for e in events 
                            if e['direction'] == 'credit' 
                            and e.get('cash_date', e['settlement_date']) <= min_day)
        debits_to_min = sum(e['amount'] for e in events 
                           if e['direction'] == 'debit' 
                           and e.get('cash_date', e['settlement_date']) <= min_day)
        
        debits_needed = cents(profile.current_available_balance) + round(credits_to_min * 100) - need_min
        debits_actual = round(debits_to_min * 100)
        debit_delta = debits_actual - debits_needed
        
        # Classify: delta > 0 means we need MORE debits (we're missing some)
        # delta < 0 means we have too many debits
        print(f"{rid}: safe_delta={delta:+.2f}")
        print(f"  debits_actual={debits_actual/100:.2f}, debits_needed={debits_needed/100:.2f}, debit_delta={debit_delta/100:+.2f}")
        
        # Look for likely culprits: projected events that seem wrong
        projected = [e for e in events if e.get('is_projected', False) 
                    and e['direction'] == 'debit'
                    and e.get('cash_date', e['settlement_date']) <= min_day]
        explicit = [e for e in events if not e.get('is_projected', False) 
                   and e['direction'] == 'debit'
                   and e.get('cash_date', e['settlement_date']) <= min_day]
        
        proj_total = sum(e['amount'] for e in projected)
        expl_total = sum(e['amount'] for e in explicit)
        
        print(f"  projected_debits_to_min={proj_total:.2f} ({len(projected)} events)")
        print(f"  explicit_debits_to_min={expl_total:.2f} ({len(explicit)} events)")
        
        # If delta is positive (too high safe), we need more debits -> missing projected events
        # Show what categories of projected events we have
        from collections import Counter
        cats = Counter(e.get('category', 'unknown') for e in projected)
        print(f"  projected categories: {dict(cats)}")

if __name__ == '__main__':
    main()
