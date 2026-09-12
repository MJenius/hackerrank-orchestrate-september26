"""For request_25, examine the actual event data and compare with projected events."""
import sys, csv
from pathlib import Path
from datetime import date, timedelta
from collections import defaultdict

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from code.data.loader import load_financial_events, load_profiles, load_requests
from code.finance.recurrence import RecurrenceEngine, monthly_history
from code.finance.lifecycle import EventLifecycle

def analyze_user(user_id, request_date):
    events = load_financial_events(ROOT / 'dataset' / 'financial_events.csv')
    user_events = [e for e in events if e.user_id == user_id]
    profiles = load_profiles(ROOT / 'dataset' / 'financial_profiles.csv')
    profile = profiles[user_id]
    
    print(f"User: {user_id}, Currency: {profile.home_currency}")
    print(f"Request date: {request_date}")
    
    # Group historical settled debits by category+description
    groups = defaultdict(list)
    for e in user_events:
        if e.status == 'settled' and e.direction == 'debit' and e.settlement_date < request_date:
            variable = e.category in ('groceries', 'transport', 'dining')
            key = (e.category, '' if variable else e.description)
            groups[key].append(e)
    
    print(f"\nHistorical debit groups (settled, before {request_date}):")
    for (cat, desc), evts in sorted(groups.items()):
        dates = sorted([e.settlement_date for e in evts])
        amounts = [e.amount for e in evts]
        print(f"  {cat} '{desc[:50]}': {len(evts)} events, amounts={sorted(set(amounts))}, dates={dates}")
    
    # Now check what RecurrenceEngine projects
    projected = RecurrenceEngine.project_recurring_events(user_events, request_date, 90)
    print(f"\nProjected recurring events ({len(projected)}):")
    for p in sorted(projected, key=lambda e: e['settlement_date']):
        print(f"  {p['settlement_date']} {p['category']} {p['amount']} [{p['event_id']}] {p.get('description','')[:50]}")

# Analyze request_25 (user_25)
requests = load_requests(ROOT / 'dataset' / 'sample_requests.csv')
req = requests['request_25']
analyze_user(req.user_id, req.request_date)

# Also do request_04 which has the largest delta
print("\n" + "="*80)
req4 = requests['request_04']
analyze_user(req4.user_id, req4.request_date)
