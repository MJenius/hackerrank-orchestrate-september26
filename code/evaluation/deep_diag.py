"""Deep diagnostic: for each mismatched sample, dump the future events and balance trajectory."""
import csv, json, sys
from decimal import Decimal
from pathlib import Path
from datetime import date, timedelta

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from code.main import generate_predictions
from code.evaluation.sample_truth import SAMPLE_GROUND_TRUTH
from code.data.loader import load_profiles, load_requests
from code.finance.simulator import cents

FIELDS = ['amount_safe_to_pay', 'affordability_status', 'recommended_payment_method',
          'payment_plan', 'earliest_date_for_full_payment', 'spending_changes_needed']

def main():
    traces = {}
    actual = generate_predictions(ROOT / 'dataset', 'sample_requests.csv', diagnostics=traces)
    actual_by_id = actual.set_index('request_id').to_dict(orient='index')
    profiles = load_profiles(ROOT / 'dataset' / 'financial_profiles.csv')
    requests = load_requests(ROOT / 'dataset' / 'sample_requests.csv')

    for rid, truth in SAMPLE_GROUND_TRUTH.items():
        pred = actual_by_id[rid]
        safe_expected = truth['safe']
        safe_actual = float(pred['amount_safe_to_pay'])
        diff = safe_actual - safe_expected

        if abs(diff) < 0.005:
            continue

        trace = traces.get(rid, {})
        req = requests[rid]
        profile = profiles[req.user_id]

        print(f"\n{'='*80}")
        print(f"{rid}: expected_safe={safe_expected}, actual_safe={safe_actual}, diff={diff:.2f}")
        print(f"  user={req.user_id}, currency={profile.home_currency}")
        print(f"  balance={profile.current_available_balance}, min_balance={profile.minimum_balance_to_keep}")
        print(f"  requested_amount={req.requested_amount}, request_date={req.request_date}")
        print(f"  desired_completion={req.desired_completion_date}")

        # Show the formula result
        minimum = cents(profile.minimum_balance_to_keep)
        requested = cents(req.requested_amount)
        balances = trace.get('baseline_balances', {})
        if balances:
            balance_values = list(balances.values())
            min_balance_cents = min(round(b * 100) for b in balance_values)
            available = min_balance_cents - minimum
            formula_safe = max(0, min(requested, available)) / 100
            baseline_safe = trace.get('baseline_safe', False)
            print(f"  min_trajectory_cents={min_balance_cents}, minimum_cents={minimum}")
            print(f"  available_cents={available}, formula_safe={formula_safe}")
            print(f"  baseline_safe={baseline_safe}")

            # Find the day that produces the minimum balance
            min_day = min(balances, key=lambda d: balances[d])
            print(f"  min_day={min_day}, min_day_balance={balances[min_day]}")

        # Show future events summary
        events = trace.get('canonical_events', [])
        credits = [e for e in events if e.get('direction') == 'credit']
        debits = [e for e in events if e.get('direction') == 'debit']
        print(f"  future_events: {len(events)} total, {len(credits)} credits, {len(debits)} debits")

        # Show each credit
        print(f"  CREDITS:")
        for e in sorted(credits, key=lambda x: x.get('settlement_date', '')):
            proj = 'PROJ' if e.get('is_projected') else 'EXPL'
            rec = 'REC' if e.get('is_recurring') else ''
            print(f"    {e['settlement_date']} {proj} {rec} {e.get('category','')} {e['amount']} {e['currency']} [{e['event_id']}] {e.get('description','')[:60]}")

        # Show each debit
        print(f"  DEBITS:")
        for e in sorted(debits, key=lambda x: x.get('settlement_date', '')):
            proj = 'PROJ' if e.get('is_projected') else 'EXPL'
            rec = 'REC' if e.get('is_recurring') else ''
            stat = e.get('status', '')
            print(f"    {e['settlement_date']} {proj} {rec} {stat} {e.get('category','')} {e['amount']} {e['currency']} [{e['event_id']}] {e.get('description','')[:60]}")

        # Show first 10 days of trajectory
        print(f"  TRAJECTORY (first 10 and min area):")
        days = sorted(balances.keys())
        for d in days[:10]:
            print(f"    {d}: {balances[d]:.2f}")
        if min_day not in days[:10]:
            idx = days.index(min_day)
            for d in days[max(0,idx-2):idx+3]:
                print(f"    {d}: {balances[d]:.2f} {'<-- MIN' if d == min_day else ''}")

        # Show expected vs actual for all 6 fields
        print(f"  FIELD COMPARISON:")
        for field in FIELDS:
            want = truth.get(field.replace('amount_safe_to_pay', 'safe').replace('affordability_status', 'status').replace('recommended_payment_method', 'method').replace('spending_changes_needed', 'changes'), '')
            got = pred.get(field, '')
            match = 'OK' if str(got) == str(want) else 'XX'
            print(f"    {match} {field}: expected={want}, actual={got}")

if __name__ == '__main__':
    main()
