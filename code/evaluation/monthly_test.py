"""Hypothesis: The truth model uses monthly aggregate rates for variable expenses.
Test: compute total monthly outflow per category, then compute trajectory using monthly aggregates."""
import sys
from pathlib import Path
from datetime import date, timedelta
from statistics import median
from collections import defaultdict

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from code.data.loader import load_financial_events, load_profiles, load_requests
from code.finance.simulator import cents
from code.evaluation.sample_truth import SAMPLE_GROUND_TRUTH

def main():
    events = load_financial_events(ROOT / 'dataset' / 'financial_events.csv')
    profiles = load_profiles(ROOT / 'dataset' / 'financial_profiles.csv')
    requests = load_requests(ROOT / 'dataset' / 'sample_requests.csv')
    
    for rid in ['request_25', 'request_04', 'request_02', 'request_03']:
        truth = SAMPLE_GROUND_TRUTH[rid]
        req = requests[rid]
        profile = profiles[req.user_id]
        start = date.fromisoformat(req.request_date)
        user_events = [e for e in events if e.user_id == req.user_id]
        
        # Compute monthly totals for each category from settled history
        monthly_totals = defaultdict(list)
        for e in user_events:
            if e.status != 'settled' or e.direction != 'debit' or e.settlement_date >= req.request_date:
                continue
            if e.amount is None:
                continue
            d = date.fromisoformat(e.settlement_date)
            month_key = (d.year, d.month)
            cat = e.category
            monthly_totals[(cat, month_key)] = monthly_totals.get((cat, month_key), 0) + e.amount
        
        # Get the most recent N months of data for each category
        cat_monthly = defaultdict(list)
        for (cat, month_key), total in monthly_totals.items():
            cat_monthly[cat].append((month_key, total))
        
        print(f"\n{'='*60}")
        print(f"{rid}: expected_safe={truth['safe']}")
        print(f"  balance={profile.current_available_balance}, min={profile.minimum_balance_to_keep}")
        
        total_monthly_outflow = 0
        for cat in sorted(cat_monthly.keys()):
            months = sorted(cat_monthly[cat])
            recent = months[-3:] if len(months) >= 3 else months
            monthly_avg = sum(t for _, t in recent) / len(recent)
            monthly_med = median([t for _, t in recent])
            total_monthly_outflow += monthly_avg
            
            if monthly_avg > 100:  # Skip tiny amounts
                print(f"  {cat}: monthly_avg={monthly_avg:.2f}, monthly_med={monthly_med:.2f} (from {len(recent)} months)")
        
        print(f"  TOTAL monthly outflow (avg): {total_monthly_outflow:.2f}")
        
        # Compute the expected outflow before payday (day 15 typically)
        # If request_date is day X, outflow before day 15 = (15-X)/30 * monthly
        req_day = start.day
        days_to_payday = 15 - req_day if req_day < 15 else 30 - req_day + 15
        fraction = days_to_payday / 30
        expected_outflow = total_monthly_outflow * fraction
        expected_min_balance = profile.current_available_balance - expected_outflow
        expected_safe = max(0, min(req.requested_amount, expected_min_balance - profile.minimum_balance_to_keep))
        
        print(f"  req_day={req_day}, days_to_payday={days_to_payday}, fraction={fraction:.3f}")
        print(f"  expected_outflow={expected_outflow:.2f}")
        print(f"  expected_min_balance={expected_min_balance:.2f}")
        print(f"  computed_safe={expected_safe:.2f}")
        print(f"  truth_safe={truth['safe']}")

if __name__ == '__main__':
    main()
