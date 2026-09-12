"""
Find what formula or aggregation produces the target outflow across all 25 users.
"""
import sys, os
sys.path.insert(0, '.')
import pandas as pd
from datetime import datetime
from code.data.loader import *

df = pd.read_csv('dataset/sample_requests.csv')
profs = load_profiles('dataset/financial_profiles.csv')
events = load_financial_events('dataset/financial_events.csv')
messages = load_messages('dataset/messages.csv')

for _, row in df.iterrows():
    req_id = row['request_id']
    uid = row['user_id']
    req_date = row['request_date']
    bal = profs[uid].current_available_balance
    m = profs[uid].minimum_balance_to_keep
    safe = row['amount_safe_to_pay']
    target = (bal - m) - safe
    
    u_evts = [e for e in events if e.user_id == uid and e.status == 'settled' and e.settlement_date < req_date]
    
    # Check total spend in last 30 days
    dt = datetime.strptime(req_date, '%Y-%m-%d')
    last_30 = [e for e in u_evts if (dt - datetime.strptime(e.settlement_date, '%Y-%m-%d')).days <= 30 and e.direction == 'debit']
    s_30 = sum(e.amount for e in last_30)
    
    # Check debits between day of req_date and day 15 (next salary)
    req_day = dt.day
    # Check fixed vs variable
    fixed = [e for e in last_30 if e.category in ('rent', 'utilities', 'insurance', 'debt_repayment', 'education', 'streaming', 'cloud_storage', 'music_subscription', 'delivery_membership', 'gym', 'family_support')]
    s_fixed = sum(e.amount for e in fixed)
    
    print(f"{req_id} ({uid}) | req_date={req_date} | Target={target:>10.2f} | last_30_debit={s_30:>10.2f} | last_30_fixed={s_fixed:>10.2f}")
