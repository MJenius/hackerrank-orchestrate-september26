"""
Reverse engineer the exact formula for amount_safe_to_pay.
"""
import sys, os
sys.path.insert(0, '.')
import pandas as pd
from code.data.loader import *

df = pd.read_csv('dataset/sample_requests.csv')
profs = load_profiles('dataset/financial_profiles.csv')
events = load_financial_events('dataset/financial_events.csv')
messages = load_messages('dataset/messages.csv')
options = load_payment_options('dataset/request_payment_options.csv')

print("Analyzing safe amounts...")
for _, row in df.iterrows():
    req_id = row['request_id']
    uid = row['user_id']
    req_date = row['request_date']
    bal = profs[uid].current_available_balance
    m = profs[uid].minimum_balance_to_keep
    req = row['requested_amount']
    safe = row['amount_safe_to_pay']
    outflow = (bal - m) - safe
    
    # Check what options exist
    opts = options.get(req_id, [])
    opt_amts = [o.payment_amount for o in opts]
    
    # Let's inspect user events around request_date
    u_evts = [e for e in events if e.user_id == uid]
    
    print(f"{req_id}: safe={safe}, req={req}, bal-min={bal-m:.2f}, outflow={outflow:.2f}")
