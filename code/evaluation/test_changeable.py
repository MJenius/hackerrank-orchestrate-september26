import sys, os
sys.path.insert(0, '.')
from code.data.loader import *
from code.finance.currency import CurrencyConverter
from code.finance.simulator import BalanceSimulator
from code.finance.optimizer import FinancialOptimizer
from code.finance.spending_changes import SpendingChangeOptimizer
from code.finance.test_refined_builder import build_refined_future
from code.evaluation.sample_truth import SAMPLE_GROUND_TRUTH

profiles = load_profiles('dataset/financial_profiles.csv')
sample_requests = load_requests('dataset/sample_requests.csv')
events = load_financial_events('dataset/financial_events.csv')
rates = load_exchange_rates('dataset/exchange_rates.csv')
messages = load_messages('dataset/messages.csv')
options = load_payment_options('dataset/request_payment_options.csv')

conv = CurrencyConverter(rates)
sim = BalanceSimulator(conv)
opt = FinancialOptimizer(sim)
spend_opt = SpendingChangeOptimizer(sim)

for req_id in ['request_06', 'request_11', 'request_21']:
    req = sample_requests[req_id]
    prof = profiles[req.user_id]
    truth = SAMPLE_GROUND_TRUTH[req_id]
    u_evts = [e for e in events if e.user_id == req.user_id]
    u_msgs = [m for m in messages if m.user_id == req.user_id]
    
    fut = build_refined_future(req.user_id, prof, req.request_date, u_evts, u_msgs, conv)
    
    # Changeable events in fut
    changeable = spend_opt._find_changeable_events(fut, prof)
    print(f"\n=== {req_id} ({req.user_id}) ===")
    print(f"Requested: {req.requested_amount}, Date: {req.request_date}, Desired: {req.desired_completion_date}")
    print(f"Willing stop: {prof.expense_categories_user_is_willing_to_stop}")
    print(f"Willing reduce: {prof.expense_categories_user_is_willing_to_reduce}")
    print("Changeable events found:")
    for c in changeable:
        print(f"  {c['source_event_id']} | {c['category']} | {c['amount']} | stop:{c['can_stop']} reduce:{c['can_reduce']} min:{c['minimum_allowed_amount']}")
    print("Expected spending changes:", truth['changes'])
