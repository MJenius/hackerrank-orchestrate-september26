"""
Find the exact future net outflow before salary for all 25 sample requests.
"""
import sys, os
sys.path.insert(0, '.')
import pandas as pd
from code.data.loader import *

df = pd.read_csv('dataset/sample_requests.csv')
profs = load_profiles('dataset/financial_profiles.csv')

print("Request | User | Bal | Min | Bal-Min | ReqAmt | SafeAmt | TargetOutflow (Bal-Min-Safe)")
for _, row in df.iterrows():
    p = profs[row['user_id']]
    bal = p.current_available_balance
    m = p.minimum_balance_to_keep
    req = row['requested_amount']
    safe = row['amount_safe_to_pay']
    outflow = (bal - m) - safe
    print(f"{row['request_id']} | {row['user_id']} | {bal:>10.2f} | {m:>10.2f} | {bal-m:>10.2f} | {req:>10.2f} | {safe:>10.2f} | {outflow:>10.2f}")
