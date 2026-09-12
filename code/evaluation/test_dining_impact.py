import sys, os
sys.path.insert(0, '.')
from code.data.loader import *
from code.finance.test_refined_builder import build_refined_future
from code.finance.currency import CurrencyConverter
from code.finance.simulator import BalanceSimulator
from code.finance.optimizer import FinancialOptimizer
from code.evaluation.sample_truth import SAMPLE_GROUND_TRUTH

profiles = load_profiles('dataset/financial_profiles.csv')
sample_requests = load_requests('dataset/sample_requests.csv')
events = load_financial_events('dataset/financial_events.csv')
rates = load_exchange_rates('dataset/exchange_rates.csv')
messages = load_messages('dataset/messages.csv')
conv = CurrencyConverter(rates)
sim = BalanceSimulator(conv)
opt = FinancialOptimizer(sim)

for req_id in ['request_06', 'request_11', 'request_21']:
    req = sample_requests[req_id]
    prof = profiles[req.user_id]
    truth = SAMPLE_GROUND_TRUTH[req_id]
    u_evts = [e for e in events if e.user_id == req.user_id]
    u_msgs = [m for m in messages if m.user_id == req.user_id]
    
    fut = build_refined_future(req.user_id, prof, req.request_date, u_evts, u_msgs, conv)
    
    # Check safe amount with all events
    safe_all, _ = opt.evaluate_request(prof, req, [], fut)
    
    # Check safe amount without dining
    fut_no_dining = [e for e in fut if e.get('category') != 'dining']
    safe_no_dining, _ = opt.evaluate_request(prof, req, [], fut_no_dining)
    
    print(f"{req_id}: Expected safe={truth['safe']}")
    print(f"   Safe with all: {safe_all:.2f}")
    print(f"   Safe without dining: {safe_no_dining:.2f}")
