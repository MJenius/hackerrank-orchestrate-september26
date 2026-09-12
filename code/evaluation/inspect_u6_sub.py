import sys, os
sys.path.insert(0, '.')
from code.data.loader import *
from code.finance.test_refined_builder import build_refined_future
from code.finance.currency import CurrencyConverter

profiles = load_profiles('dataset/financial_profiles.csv')
sample_requests = load_requests('dataset/sample_requests.csv')
events = load_financial_events('dataset/financial_events.csv')
rates = load_exchange_rates('dataset/exchange_rates.csv')
messages = load_messages('dataset/messages.csv')
conv = CurrencyConverter(rates)

prof = profiles['user_06']
req = sample_requests['request_06']
u_evts = [e for e in events if e.user_id == 'user_06']
u_msgs = [m for m in messages if m.user_id == 'user_06']

fut = build_refined_future('user_06', prof, req.request_date, u_evts, u_msgs, conv)
fut_stopped = [e for e in fut if e.get('category') != 'streaming']
sub = [e for e in fut_stopped if e['settlement_date'] <= '2026-01-15' and e['direction'] == 'debit']
tot = sum(e['amount'] for e in sub)
print('Total debits before salary:', tot)
for e in sorted(sub, key=lambda x: x['settlement_date']):
    print(e['settlement_date'], e['amount'], e['category'], e['description'])
