"""Deep dive into request_25: trace the exact events that cause the 1.2M IDR delta."""
import sys
from pathlib import Path
from datetime import date, timedelta
from statistics import median
from collections import defaultdict, Counter

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from code.data.loader import load_financial_events, load_profiles, load_requests
from code.finance.recurrence import RecurrenceEngine, monthly_history
from code.finance.lifecycle import EventLifecycle

def main():
    events = load_financial_events(ROOT / 'dataset' / 'financial_events.csv')
    profiles = load_profiles(ROOT / 'dataset' / 'financial_profiles.csv')
    requests = load_requests(ROOT / 'dataset' / 'sample_requests.csv')
    
    req = requests['request_25']
    user_events = [e for e in events if e.user_id == req.user_id]
    start = date.fromisoformat(req.request_date)
    
    # Expected safe=1,425,000, actual=221,174.45
    # Delta = -1,203,825.55 (our safe is too LOW -> too many debits)
    # min_day = 2024-03-14, min_balance = 23,600,274.45
    # Need min_balance = 23,379,100 + 1,425,000 = 24,804,100
    # So we need debits = 32,063,050 - 24,804,100 = 7,258,950
    # But we have debits = 32,063,050 - 23,600,274.45 = 8,462,775.55
    # Extra debits = 8,462,775.55 - 7,258,950 = 1,203,825.55
    
    print("request_25 analysis:")
    print(f"  Need to REMOVE {1203825.55:.2f} IDR of debits before 2024-03-14")
    print()
    
    # Show ALL historical settled debits for variable categories
    for cat in ['dining', 'groceries', 'transport']:
        history = [e for e in user_events 
                  if e.status == 'settled' and e.direction == 'debit'
                  and e.category == cat and e.settlement_date < req.request_date]
        
        amounts = [e.amount for e in history if e.amount is not None]
        dates = sorted([date.fromisoformat(e.settlement_date) for e in history])
        gaps = [(b - a).days for a, b in zip(dates, dates[1:])]
        
        recent_90 = [e for e in history 
                    if date.fromisoformat(e.settlement_date) >= start - timedelta(days=90)
                    and e.amount is not None]
        
        cadence_count = Counter(gaps)
        most_common_gap = cadence_count.most_common(1)[0] if gaps else (0, 0)
        
        print(f"  {cat}: {len(history)} events, gaps={cadence_count.most_common(3)}")
        print(f"    median_all={round(median(amounts), 2) if amounts else 'N/A'}")
        print(f"    median_90d={round(median([e.amount for e in recent_90]), 2) if recent_90 else 'N/A'}")
        print(f"    last_date={dates[-1] if dates else 'N/A'}")
        
        # What does RecurrenceEngine project?
        projected = RecurrenceEngine.project_recurring_events(user_events, req.request_date, 90)
        cat_proj = [p for p in projected if p['category'] == cat]
        print(f"    projected: {len(cat_proj)} events, amount={cat_proj[0]['amount'] if cat_proj else 'N/A'}")
        
        # How many projected events fall before 2024-03-14?
        before_min = [p for p in cat_proj if p['settlement_date'] <= '2024-03-14']
        print(f"    before min_day (2024-03-14): {len(before_min)} events, total={sum(p['amount'] for p in before_min):.2f}")
    
    print()
    
    # Also check monthly/fixed events
    for cat in ['utilities', 'insurance', 'streaming', 'cloud_storage', 'shopping', 'entertainment']:
        history = [e for e in user_events 
                  if e.status == 'settled' and e.direction == 'debit'
                  and e.category == cat and e.settlement_date < req.request_date]
        
        projected = RecurrenceEngine.project_recurring_events(user_events, req.request_date, 90)
        cat_proj = [p for p in projected if p['category'] == cat]
        before_min = [p for p in cat_proj if p['settlement_date'] <= '2024-03-14']
        
        if before_min:
            print(f"  {cat}: {len(before_min)} proj before min_day, total={sum(p['amount'] for p in before_min):.2f}, amount={before_min[0]['amount']}")

if __name__ == '__main__':
    main()
