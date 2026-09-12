import sys, os
sys.path.insert(0, '.')
from datetime import datetime
from code.data.loader import *

df = pd.read_csv('dataset/sample_requests.csv')
profs = load_profiles('dataset/financial_profiles.csv')
events = load_financial_events('dataset/financial_events.csv')

print("User | ReqDate | Payday | Days | MonthlyDebit | (Monthly*Days/30) | TargetOutflow | Ratio")
for _, row in df.iterrows():
    uid = row['user_id']
    req_date = row['request_date']
    bal = profs[uid].current_available_balance
    m = profs[uid].minimum_balance_to_keep
    safe = row['amount_safe_to_pay']
    target = (bal - m) - safe
    
    u_evts = [e for e in events if e.user_id == uid and e.status == 'settled' and e.direction == 'debit']
    # Total monthly debit across ~5 months:
    total_debit = sum(e.amount for e in u_evts)
    # Months span:
    min_d = datetime.strptime(min(e.settlement_date for e in u_evts), '%Y-%m-%d')
    max_d = datetime.strptime(max(e.settlement_date for e in u_evts), '%Y-%m-%d')
    months = max(1.0, (max_d - min_d).days / 30.0)
    monthly_debit = total_debit / months
    
    # Days to payday (15th of month or next 15th):
    req_dt = datetime.strptime(req_date, '%Y-%m-%d')
    if req_dt.day <= 15:
        days = 15 - req_dt.day
    else:
        days = (30 - req_dt.day) + 15
        
    scaled = (monthly_debit * days) / 30.0
    ratio = target / max(1.0, scaled) if scaled > 0 else 0
    print(f"{uid:8s} | {req_date} | day 15 | {days:2d}d | {monthly_debit:>10.2f} | {scaled:>10.2f} | {target:>10.2f} | {ratio:.2f}")
