import sys, os
sys.path.insert(0, '.')
from code.data.loader import load_financial_events
events = load_financial_events('dataset/financial_events.csv')

# Targets:
# user_22: 157.00 (request date 2024-12-05)
# user_21: 568.00 (request date 2026-04-03)
# user_08: 452.00 (request date 2025-02-07)
# user_18: 624.00 (request date 2026-07-07)
# user_06: 539.10 (request date 2026-01-03)

cases = [
    ('user_22', '2024-12-05', 157.00),
    ('user_21', '2026-04-03', 568.00),
    ('user_08', '2025-02-07', 452.00),
    ('user_18', '2026-07-07', 624.00),
    ('user_06', '2026-01-03', 539.10),
]

for uid, req_date, target in cases:
    print(f'================ {uid}: TARGET = {target} (req_date={req_date}) ================')
    u_evts = [e for e in events if e.user_id == uid and e.status == 'settled']
    
    # Check prior month events between day of req_date and day 15 (when salary arrives)
    # E.g., for user_22 (2024-12-05), check days 5 to 15 of Nov 2024:
    req_d = int(req_date.split('-')[2])
    print(f'Checking events between day {req_d} and day 15 in past months:')
    for m in sorted(list({e.settlement_date[:7] for e in u_evts}))[-3:]:
        sub = [e for e in u_evts if e.settlement_date.startswith(m) and req_d <= int(e.settlement_date.split('-')[2]) <= 15 and e.direction == 'debit']
        s = sum(e.amount for e in sub)
        print(f'  {m} (days {req_d}-15): sum={s:.2f}')
        for e in sub:
            print(f'     {e.settlement_date} | {e.amount:>8.2f} | {e.category:12s} | {e.description}')
