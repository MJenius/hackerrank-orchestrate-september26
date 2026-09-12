"""For each mismatched sample, compute what EACH projected event's correct amount 
should be, by examining the historical event amounts more carefully.
Focus on variable categories (groceries, transport, dining) where median calculation matters."""
import sys
from pathlib import Path
from datetime import date, timedelta
from statistics import median
from collections import defaultdict

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from code.data.loader import load_financial_events, load_profiles, load_requests
from code.evaluation.sample_truth import SAMPLE_GROUND_TRUTH

def main():
    events = load_financial_events(ROOT / 'dataset' / 'financial_events.csv')
    profiles = load_profiles(ROOT / 'dataset' / 'financial_profiles.csv')
    requests = load_requests(ROOT / 'dataset' / 'sample_requests.csv')
    
    # For each request, look at variable categories and compute different median variants
    for rid in sorted(SAMPLE_GROUND_TRUTH.keys()):
        truth = SAMPLE_GROUND_TRUTH[rid]
        req = requests[rid]
        profile = profiles[req.user_id]
        start = date.fromisoformat(req.request_date)
        
        user_events = [e for e in events if e.user_id == req.user_id]
        
        # Look at variable categories
        for cat in ['groceries', 'transport', 'dining']:
            history = [e for e in user_events 
                      if e.status == 'settled' and e.direction == 'debit'
                      and e.category == cat and e.settlement_date < req.request_date]
            if not history:
                continue
            
            # Current: median of last 90 days
            recent_90 = [e for e in history 
                        if date.fromisoformat(e.settlement_date) >= start - timedelta(days=90)]
            all_amounts = [e.amount for e in history]
            recent_amounts = [e.amount for e in recent_90]
            
            if recent_amounts:
                med_recent = round(median(recent_amounts), 2)
            else:
                med_recent = history[-1].amount
            
            med_all = round(median(all_amounts), 2)
            
            # Also try last 30 days
            recent_30 = [e for e in history
                        if date.fromisoformat(e.settlement_date) >= start - timedelta(days=30)]
            med_30 = round(median([e.amount for e in recent_30]), 2) if recent_30 else None
            
            if med_recent != med_all or (med_30 and med_30 != med_recent):
                print(f"{rid} {cat}: med_all={med_all}, med_90d={med_recent}, med_30d={med_30}, count_all={len(all_amounts)}, count_90={len(recent_amounts)}")

if __name__ == '__main__':
    main()
