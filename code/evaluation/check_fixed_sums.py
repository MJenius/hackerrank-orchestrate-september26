import sys, os
sys.path.insert(0, '.')
import pandas as pd
from code.data.loader import *

df = pd.read_csv('dataset/sample_requests.csv')
profs = load_profiles('dataset/financial_profiles.csv')
events = load_financial_events('dataset/financial_events.csv')

for _, row in df.iterrows():
    req_id = row['request_id']
    uid = row['user_id']
    req_date = row['request_date']
    bal = profs[uid].current_available_balance
    m = profs[uid].minimum_balance_to_keep
    safe = row['amount_safe_to_pay']
    target = (bal - m) - safe
    
    # Check if target is close to sum of fixed recurring debits
    u_evts = [e for e in events if e.user_id == uid and e.status == 'settled' and e.direction == 'debit']
    # Find monthly events: rent, utilities, insurance, subscriptions, debt_repayment
    fixed_cats = ('rent', 'housing', 'utilities', 'insurance', 'debt_repayment', 'education', 'family_support', 'streaming', 'cloud_storage', 'music_subscription', 'delivery_membership', 'gym')
    
    # Check recent month fixed sum
    recent_fixed = [e for e in u_evts if e.category in fixed_cats]
    print(f"{req_id} ({uid}): Target={target:>10.2f}")
