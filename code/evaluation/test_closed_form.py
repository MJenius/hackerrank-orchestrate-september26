import sys, os
sys.path.insert(0, '.')
from statistics import mean, median
from datetime import datetime, timedelta
from collections import defaultdict, Counter
from code.data.loader import *
from code.evidence.image_extractor import ImageEvidenceExtractor
from code.finance.currency import CurrencyConverter
from code.finance.simulator import BalanceSimulator
from code.finance.optimizer import FinancialOptimizer
from code.evaluation.sample_truth import SAMPLE_GROUND_TRUTH

profiles = load_profiles('dataset/financial_profiles.csv')
sample_requests = load_requests('dataset/sample_requests.csv')
events = load_financial_events('dataset/financial_events.csv')
rates = load_exchange_rates('dataset/exchange_rates.csv')
messages = load_messages('dataset/messages.csv')
images = load_image_mappings('dataset/images.csv')

img_ext = ImageEvidenceExtractor()
event_by_id = {e.event_id: e for e in events}
for img_id, m in images.items():
    if m.related_event_id and m.related_event_id in event_by_id:
        evt = event_by_id[m.related_event_id]
        if evt.amount is None:
            fact = img_ext.extract_fact(img_id)
            if fact:
                evt.amount = fact.amount

conv = CurrencyConverter(rates)
sim = BalanceSimulator(conv)
opt = FinancialOptimizer(sim)

# Let's inspect the exact difference between target outflow and our projected debits before payday
from code.finance.test_refined_builder import build_refined_future

print("Checking differences for all sample requests:")
for req_id, truth in SAMPLE_GROUND_TRUTH.items():
    req = sample_requests[req_id]
    prof = profiles[req.user_id]
    u_evts = [e for e in events if e.user_id == req.user_id]
    u_msgs = [m for m in messages if m.user_id == req.user_id]
    
    fut = build_refined_future(req.user_id, prof, req.request_date, u_evts, u_msgs, conv)
    
    # Compute safe amount directly: min_bal_0 - min_to_keep
    is_safe_0, min_bal_0, _ = sim.simulate_trajectory(prof, req.request_date, fut, {})
    calc_safe = max(0.0, min(req.requested_amount, min_bal_0 - prof.minimum_balance_to_keep))
    
    target_safe = truth['safe']
    diff = calc_safe - target_safe
    print(f"{req_id} ({req.user_id}): exp={target_safe:>10.2f}, got={calc_safe:>10.2f}, diff={diff:>10.2f}")
