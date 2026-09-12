"""For each mismatched request, show ALL explicit events (non-projected) in the future state
and look for events we might be filtering out incorrectly."""
import sys
from pathlib import Path
from datetime import date, timedelta

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from code.data.loader import load_financial_events, load_profiles, load_requests
from code.finance.lifecycle import EventLifecycle
from code.evaluation.sample_truth import SAMPLE_GROUND_TRUTH

def main():
    events = load_financial_events(ROOT / 'dataset' / 'financial_events.csv')
    profiles = load_profiles(ROOT / 'dataset' / 'financial_profiles.csv')
    requests = load_requests(ROOT / 'dataset' / 'sample_requests.csv')
    
    for rid in ['request_04', 'request_02', 'request_25', 'request_06', 'request_05', 'request_10']:
        req = requests[rid]
        profile = profiles[req.user_id]
        user_events = [e for e in events if e.user_id == req.user_id]
        
        start = date.fromisoformat(req.request_date)
        end = start + timedelta(days=90)
        
        print(f"\n{'='*60}")
        print(f"{rid}: user={req.user_id}, request_date={req.request_date}")
        print(f"  balance={profile.current_available_balance}, min_balance={profile.minimum_balance_to_keep}")
        
        # Show ALL events with settlement_date in the 90-day window
        # regardless of status
        future = [e for e in user_events 
                  if e.settlement_date >= req.request_date 
                  and e.settlement_date <= end.isoformat()]
        
        print(f"\n  ALL events in [{req.request_date}, {end.isoformat()}] ({len(future)}):")
        for e in sorted(future, key=lambda x: (x.settlement_date, x.event_id)):
            valid = EventLifecycle.is_valid_cash_event(e)
            print(f"    {e.settlement_date} {e.direction} {e.status} {e.category} {e.amount} {e.currency} [{e.event_id}] valid={valid} flex={e.flexibility} desc={e.description[:50]}")
        
        # Also show events that might be missed: scheduled credits we skip
        scheduled_credits = [e for e in future if e.direction == 'credit' and e.status == 'scheduled']
        if scheduled_credits:
            print(f"\n  SCHEDULED CREDITS (may be skipped):")
            for e in scheduled_credits:
                print(f"    {e.settlement_date} {e.category} {e.amount} {e.currency} [{e.event_id}] {e.description[:60]}")

if __name__ == '__main__':
    main()
