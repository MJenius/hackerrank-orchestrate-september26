import sys, os
sys.path.insert(0, '.')
import pandas as pd
from code.data.loader import *
from code.finance.future_state import FutureStateBuilder
from code.finance.currency import CurrencyConverter
from code.finance.simulator import BalanceSimulator
from code.finance.optimizer import FinancialOptimizer
from code.finance.spending_changes import SpendingChangeOptimizer
from code.evaluation.sample_truth import SAMPLE_GROUND_TRUTH
from code.evidence.image_extractor import ImageEvidenceExtractor

profiles = load_profiles('dataset/financial_profiles.csv')
events = load_financial_events('dataset/financial_events.csv')
messages = load_messages('dataset/messages.csv')
rates = load_exchange_rates('dataset/exchange_rates.csv')
options = load_payment_options('dataset/request_payment_options.csv')
sample_requests = load_requests('dataset/sample_requests.csv')
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
fb = FutureStateBuilder(events, messages)

for req_id, truth in SAMPLE_GROUND_TRUTH.items():
    req = sample_requests[req_id]
    prof = profiles[req.user_id]
    opts = options.get(req_id, [])
    fut = fb.build(req.user_id, prof, req.request_date)
    safe_amt, plan = opt.evaluate_request(prof, req, opts, fut)
    
    diff_safe = safe_amt - truth['safe']
    diff_st = plan.affordability_status == truth['status']
    diff_m = plan.plan_type == truth['method']
    pred_earliest = '' if not plan.earliest_date_for_full_payment or plan.plan_type == 'not_recommended' else str(plan.earliest_date_for_full_payment)
    diff_e = pred_earliest == truth['earliest']
    print(f"{req_id} ({req.user_id}) | Safe: got={safe_amt:>10.2f}, exp={truth['safe']:>10.2f}, diff={diff_safe:>10.2f} | st:{diff_st} m:{diff_m} e:{diff_e} | exp_m={truth['method']} got_m={plan.plan_type}")
