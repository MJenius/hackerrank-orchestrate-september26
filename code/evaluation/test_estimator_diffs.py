import sys, os
sys.path.insert(0, '.')
from statistics import median
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
images = load_image_mappings('dataset/images.csv')
from code.evidence.image_extractor import ImageEvidenceExtractor
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

# Test users:
test_uids = [
    ('request_07', 'user_07', 87170.56),
    ('request_08', 'user_08', 284.57),
    ('request_14', 'user_14', 597.74),
    ('request_17', 'user_17', 243849.58),
    ('request_22', 'user_22', 475.46),
    ('request_24', 'user_24', 13420.00),
]

print("Comparing estimators for target safe amounts:")
for req_id, uid, target in test_uids:
    req = sample_requests[req_id]
    prof = profiles[uid]
    u_evts = [e for e in events if e.user_id == uid]
    u_msgs = [m for m in messages if m.user_id == uid]
    
    fut = build_refined_future(uid, prof, req.request_date, u_evts, u_msgs, conv)
    safe_amt, plan = opt.evaluate_request(prof, req, [], fut)
    print(f"{req_id} ({uid}): exp={target:>10.2f}, got={safe_amt:>10.2f}, diff={safe_amt - target:>8.2f}")
