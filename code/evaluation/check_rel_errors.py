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

errors = []
for req_id, truth in SAMPLE_GROUND_TRUTH.items():
    req = sample_requests[req_id]
    prof = profiles[req.user_id]
    u_evts = [e for e in events if e.user_id == req.user_id]
    u_msgs = [m for m in messages if m.user_id == req.user_id]
    
    fut = build_refined_future(req.user_id, prof, req.request_date, u_evts, u_msgs, conv)
    is_safe_0, min_bal_0, _ = sim.simulate_trajectory(prof, req.request_date, fut, {})
    calc_safe = max(0.0, min(req.requested_amount, min_bal_0 - prof.minimum_balance_to_keep))
    
    t_safe = truth['safe']
    diff = abs(calc_safe - t_safe)
    rel_err = diff / max(1.0, t_safe)
    errors.append((req_id, req.user_id, t_safe, calc_safe, diff, rel_err))
    print(f"{req_id} ({req.user_id}): exp={t_safe:>10.2f}, got={calc_safe:>10.2f}, diff={diff:>10.2f}, rel_err={rel_err*100:>6.2f}%")
