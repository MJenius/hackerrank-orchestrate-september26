"""Analyze future state for key sample users to diagnose regression failures."""
import sys, os
sys.path.insert(0, os.path.abspath('.'))
from code.data.loader import *
from code.finance.future_state import FutureStateBuilder
from code.finance.currency import CurrencyConverter
from code.finance.simulator import BalanceSimulator
from code.finance.optimizer import FinancialOptimizer
from code.evidence.image_extractor import ImageEvidenceExtractor

profiles = load_profiles('dataset/financial_profiles.csv')
events = load_financial_events('dataset/financial_events.csv')
messages = load_messages('dataset/messages.csv')
images = load_image_mappings('dataset/images.csv')
rates = load_exchange_rates('dataset/exchange_rates.csv')

img_ext = ImageEvidenceExtractor()
event_by_id = {e.event_id: e for e in events}
for img_id, m in images.items():
    if m.related_event_id and m.related_event_id in event_by_id:
        evt = event_by_id[m.related_event_id]
        if evt.amount is None:
            fact = img_ext.extract_fact(img_id)
            if fact:
                evt.amount = fact.amount

fb = FutureStateBuilder(events, messages)
converter = CurrencyConverter(rates)
sim = BalanceSimulator(converter)

# Analyze key failing users
test_cases = [
    ('user_01', '2024-03-03', 25256.0, 'Should be affordable_now, safe=25256'),
    ('user_05', '2025-11-06', 737.0, 'Should be not_affordable, safe=737'),
    ('user_06', '2026-01-03', 603.3, 'Needs spending changes, safe=603.3'),
    ('user_10', '2024-12-06', 12700.0, 'Not affordable, safe=12700'),
    ('user_13', '2024-03-07', 433.4, 'Affordable later, safe=433.4'),
    ('user_25', '2024-03-06', 1425000.0, 'Not affordable, safe=1,425,000'),
]

for user_id, req_date, exp_safe, note in test_cases:
    prof = profiles[user_id]
    fut = fb.build(user_id, prof, req_date)
    
    print(f'\n{"="*60}')
    print(f'{user_id} | request_date={req_date} | expected safe={exp_safe}')
    print(f'Note: {note}')
    print(f'Balance: {prof.current_available_balance} | Min: {prof.minimum_balance_to_keep} | Currency: {prof.home_currency}')
    
    credits = [e for e in fut if e['direction'] == 'credit']
    debits = [e for e in fut if e['direction'] == 'debit']
    total_credit = sum(e['amount'] for e in credits)
    total_debit = sum(e['amount'] for e in debits)
    print(f'Future events: {len(credits)} credits ({total_credit:.2f}), {len(debits)} debits ({total_debit:.2f})')
    
    # Simulate with 0 payment to see baseline trajectory
    is_safe0, min_bal0, _ = sim.simulate_trajectory(prof, req_date, fut, {})
    print(f'Baseline (no payment): safe={is_safe0}, min_balance={min_bal0:.2f}')
    
    # Available for payment = balance - min_balance - projected_net_outflow
    avail = prof.current_available_balance - prof.minimum_balance_to_keep
    print(f'Simple available = balance - min = {avail:.2f}')
    print(f'Net future flow = {total_credit - total_debit:.2f}')
    
    # Show all events
    for e in sorted(fut, key=lambda x: x['settlement_date']):
        proj = ' [PROJ]' if e.get('is_projected') else ''
        print(f'  {e["settlement_date"]} {e["direction"]:6s} {e["amount"]:>12.2f} {e.get("currency","")} {e.get("description","")[:40]}{proj}')
    
    # Parse amendments
    user_msgs = [m for m in messages if m.user_id == user_id]
    amendments = fb._parse_messages(user_msgs, req_date)
    important = {k: v for k, v in amendments.items() if v and v != False}
    if important:
        print(f'  Amendments: {important}')
