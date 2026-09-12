import sys, os
sys.path.insert(0, '.')
from code.data.loader import *
import pandas as pd
df = pd.read_csv('dataset/sample_requests.csv')
profs = load_profiles('dataset/financial_profiles.csv')

for _, row in df.iterrows():
    p = profs[row['user_id']]
    bal = p.current_available_balance
    m = p.minimum_balance_to_keep
    req = row['requested_amount']
    safe = row['amount_safe_to_pay']
    status = row['affordability_status']
    method = row['recommended_payment_method']
    print(f"{row['request_id']} | {row['user_id']} | bal={bal:>12.2f} | min={m:>10.2f} | bal-min={bal-m:>12.2f} | req={req:>12.2f} | safe={safe:>12.2f} | st={status:20s} | m={method:15s}")
