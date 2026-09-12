"""Key hypothesis: amount_safe_to_pay = balance - min_balance on request_date,
but adjusted for today's pending debits and immediate settled events.
Test: what if we just compute balance_at_request_date - minimum, adjusted for same-day events?"""
import sys
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

    # For request_05 and request_10, the expected safe > 0 but baseline is not safe.
    # Let me check what the truth safe amount actually corresponds to:
    
    for rid in ['request_05', 'request_10']:
        truth = SAMPLE_GROUND_TRUTH[rid]
        req = requests[rid]
        profile = profiles[req.user_id]
        trace = traces.get(rid, {})
        balances = trace.get('baseline_balances', {})
        
        minimum = cents(profile.minimum_balance_to_keep)
        requested = cents(req.requested_amount)
        
        # Day-0 balance after same-day events
        day0_bal = round(balances[req.request_date] * 100)
        avail_day0 = day0_bal - minimum
        safe_day0 = max(0, min(requested, avail_day0)) / 100
        
        # Show the trajectory around the minimum point
        min_day = min(balances, key=lambda d: balances[d])
        
        print(f"\n{rid}: expected_safe={truth['safe']}")
        print(f"  balance={profile.current_available_balance}, min_balance={profile.minimum_balance_to_keep}")
        print(f"  day0_bal={day0_bal/100:.2f}, avail_day0={avail_day0/100:.2f}, safe_day0={safe_day0:.2f}")
        print(f"  min_day={min_day}, min_bal={balances[min_day]:.2f}")
        
        # What if the expected safe amount represents the available balance
        # on the day BEFORE the first salary, computed differently?
        # For request_05: expected=737, which is suspiciously close to a small amount
        # For request_10: expected=12700, which is round
        
        # Let me check if expected = balance - sum(committed_debits_today_through_some_date) - minimum
        # Actually, let me check: expected_safe = balance - minimum - sum_of_specific_events
        
        # Balance on request_date: profile.current_available_balance (already has all settled history)
        # Then we subtract same-day events:
        events = trace.get('canonical_events', [])
        same_day = [e for e in events if e.get('cash_date', e['settlement_date']) == req.request_date and e['direction'] == 'debit']
        same_day_total = sum(e['amount'] for e in same_day)
        
        adjusted_bal = cents(profile.current_available_balance) - round(same_day_total * 100)
        avail_adjusted = adjusted_bal - minimum
        safe_adjusted = max(0, min(requested, avail_adjusted)) / 100
        
        print(f"  same_day_debits={same_day_total:.2f}, adjusted_bal={adjusted_bal/100:.2f}")
        print(f"  avail_adjusted={avail_adjusted/100:.2f}, safe_adjusted={safe_adjusted:.2f}")
        
        # What does truth['safe'] correspond to?
        # For request_05: safe=737
        # balance = 46475.10, min = 13100
        # If we look at what the balance would be at some specific point...
        # 46475.10 - 13100 = 33375.10 available before any debits
        # 737 is much less than that, so it's balance AFTER many debits
        # 46475.10 - 737 - 13100 = 32638.10 in debits needed
        # Our debits = 38123.24, which is too many by 5485.14
        
        # What if the issue is that some events we project shouldn't be there?
        # Let me check: 5485.14 / 737 is about 7.4 - this isn't a simple multiple
        
        # For request_10: safe=12700
        # balance = 750155, min = 225400
        # available = 524755 before debits
        # 12700 means 524755 - 12700 = 512055 in debits needed
        # Our debits = 558622.85, too many by 46567.85

if __name__ == '__main__':
    main()
