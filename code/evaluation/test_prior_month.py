"""
Test hypothesis: Did recurrence roll forward the previous month's exact events?
"""
import sys, os
sys.path.insert(0, '.')
from datetime import datetime
from code.data.loader import *

df = pd.read_csv('dataset/sample_requests.csv')
profs = load_profiles('dataset/financial_profiles.csv')
events = load_financial_events('dataset/financial_events.csv')

for req_id in ['request_03', 'request_06', 'request_07', 'request_08', 'request_14', 'request_18', 'request_21', 'request_22']:
    row = df[df['request_id'] == req_id].iloc[0]
    uid = row['user_id']
    req_date = row['request_date']
    bal = profs[uid].current_available_balance
    m = profs[uid].minimum_balance_to_keep
    safe = row['amount_safe_to_pay']
    target = (bal - m) - safe
    
    u_evts = [e for e in events if e.user_id == uid and e.status == 'settled' and e.direction == 'debit']
    # Prior month:
    req_dt = datetime.strptime(req_date, '%Y-%m-%d')
    # Let's see what debits occurred between req_day and 15 in the prior month:
    req_day = req_dt.day
    # Prior month string:
    pm_year = req_dt.year if req_dt.month > 1 else req_dt.year - 1
    pm_month = req_dt.month - 1 if req_dt.month > 1 else 12
    pm_str = f"{pm_year:04d}-{pm_month:02d}"
    
    pm_evts = [e for e in u_evts if e.settlement_date.startswith(pm_str) and req_day <= int(e.settlement_date.split('-')[2]) <= 15]
    pm_sum = sum(e.amount for e in pm_evts)
    
    # Also check pending debits around req_date:
    pending_evts = [e for e in events if e.user_id == uid and e.status == 'pending' and e.settlement_date >= req_date]
    pend_sum = sum(e.amount for e in pending_evts)
    
    print(f"{req_id} ({uid}): Target={target:>10.2f} | PriorMonth({pm_str})={pm_sum:>10.2f} | Pending={pend_sum:>8.2f} | PM+Pend={pm_sum+pend_sum:>10.2f} | Diff={target - (pm_sum+pend_sum):>8.2f}")
