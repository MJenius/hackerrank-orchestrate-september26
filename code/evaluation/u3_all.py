import sys, os
sys.path.insert(0, '.')
from code.data.loader import load_financial_events
events = load_financial_events('dataset/financial_events.csv')

u3 = [e for e in events if e.user_id == 'user_03']
print("Searching for 2268600 or 873000 in user_03:")
for e in u3:
    print(f"{e.event_id} | {e.settlement_date} | {e.amount} | {e.category} | {e.description}")
