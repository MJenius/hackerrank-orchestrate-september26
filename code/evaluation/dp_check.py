import sys, os
sys.path.insert(0, '.')
from code.data.loader import load_financial_events
events = load_financial_events('dataset/financial_events.csv')

# Fast check for user_22: target = 157.00
u22 = [e for e in events if e.user_id == 'user_22' and e.status == 'settled' and e.direction == 'debit']
# Convert to integer cents
target_cents = 15700
cents_list = [(round(e.amount * 100), e) for e in u22]

# DP to find subset summing to target_cents
dp = {0: []}
for c, e in cents_list:
    new_dp = {}
    for s, subset in dp.items():
        if s + c <= target_cents and s + c not in dp:
            new_dp[s + c] = subset + [e]
    dp.update(new_dp)
    if target_cents in dp:
        print("FOUND EXACT MATCH FOR 157.00!")
        for item in dp[target_cents]:
            print(f"  {item.settlement_date} | {item.amount:>8.2f} | {item.category:15s} | {item.description}")
        break
else:
    print("No exact subset of historical events sums to 157.00")
