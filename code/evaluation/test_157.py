import sys, os
sys.path.insert(0, '.')
from code.data.loader import load_financial_events
events = load_financial_events('dataset/financial_events.csv')

# Let's check user_22:
u22 = [e for e in events if e.user_id == 'user_22' and e.status == 'settled' and e.direction == 'debit']
print("User 22 unique amounts:")
for e in sorted(u22, key=lambda x: x.amount):
    print(f"  {e.amount:>8.2f} | {e.category:15s} | {e.description}")

# Can any combination of amounts for user_22 sum to 157.00?
from itertools import combinations
amts = [e.amount for e in u22]
found = []
for r in range(1, 8):
    for c in combinations(amts, r):
        if sum(c) == 157.00:
            found.append(c)
print(f"Found {len(found)} combinations summing to 157.00 for user_22:")
for f in found[:3]:
    print(" ", f)
