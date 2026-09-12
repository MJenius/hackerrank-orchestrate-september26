import sys, os
sys.path.insert(0, '.')
from code.data.loader import *
from code.evidence.image_extractor import ImageEvidenceExtractor
from code.finance.currency import CurrencyConverter
from code.finance.simulator import BalanceSimulator
from code.finance.optimizer import FinancialOptimizer
from code.finance.spending_changes import SpendingChangeOptimizer
from code.finance.test_refined_builder import build_refined_future
from code.evaluation.sample_truth import SAMPLE_GROUND_TRUTH

profiles = load_profiles('dataset/financial_profiles.csv')
sample_requests = load_requests('dataset/sample_requests.csv')
events = load_financial_events('dataset/financial_events.csv')
options = load_payment_options('dataset/request_payment_options.csv')
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
spend_opt = SpendingChangeOptimizer(sim)

total = len(sample_requests)
safe_matches = 0
status_matches = 0
method_matches = 0
plan_matches = 0
earliest_matches = 0
changes_matches = 0
exact_matches = 0

for req_id, truth in SAMPLE_GROUND_TRUTH.items():
    req = sample_requests[req_id]
    prof = profiles[req.user_id]
    opts = options.get(req_id, [])
    u_evts = [e for e in events if e.user_id == req.user_id]
    u_msgs = [m for m in messages if m.user_id == req.user_id]
    
    fut = build_refined_future(req.user_id, prof, req.request_date, u_evts, u_msgs, conv)
    safe_amt, plan = opt.evaluate_request(prof, req, opts, fut)
    
    # Spending changes
    if plan.plan_type == 'not_recommended' or plan.affordability_status == 'not_affordable' or (plan.plan_type == 'wait' and 'full_payment' in prof.payment_methods_user_will_consider):
        sc_result = spend_opt.find_spending_changes(prof, req, fut, {req.request_date: req.requested_amount})
        if sc_result is not None:
            sc_str, modified_fut = sc_result
            if sc_str != 'none':
                safe_amt_sc, plan_sc = opt.evaluate_request(prof, req, opts, modified_fut)
                if plan_sc.plan_type != 'not_recommended':
                    from code.finance.plan_ranker import CandidatePlan
                    plan = CandidatePlan(
                        plan_type=plan_sc.plan_type,
                        payment_plan_str=plan_sc.payment_plan_str,
                        earliest_date_for_full_payment=plan_sc.earliest_date_for_full_payment,
                        spending_changes_needed=sc_str,
                        total_amount_paid=plan_sc.total_amount_paid,
                        first_payment_date=plan_sc.first_payment_date,
                        number_of_payments=plan_sc.number_of_payments,
                        payment_option_id=plan_sc.payment_option_id,
                        completes_by_desired_date=plan_sc.completes_by_desired_date,
                        requires_spending_changes=True,
                        affordability_status='affordable_with_plan'
                    )
                    safe_amt = safe_amt_sc

    safe_diff = abs(safe_amt - truth['safe'])
    safe_ok = (safe_diff <= 0.05) or (abs(safe_amt - truth['safe']) / max(1.0, truth['safe']) < 0.0001)
    st_ok = (plan.affordability_status == truth['status'])
    m_ok = (plan.plan_type == truth['method'])
    p_ok = (plan.payment_plan_str == truth['plan'])
    pred_earliest = '' if not plan.earliest_date_for_full_payment or plan.plan_type == 'not_recommended' else str(plan.earliest_date_for_full_payment)
    e_ok = (pred_earliest == truth['earliest'])
    c_ok = (plan.spending_changes_needed == truth['changes'])

    if safe_ok: safe_matches += 1
    if st_ok: status_matches += 1
    if m_ok: method_matches += 1
    if p_ok: plan_matches += 1
    if e_ok: earliest_matches += 1
    if c_ok: changes_matches += 1

    is_exact = safe_ok and st_ok and m_ok and p_ok and e_ok and c_ok
    if is_exact:
        exact_matches += 1
        print(f"[{req_id}] [PASS]")
    else:
        print(f"[{req_id}] [FAIL] safe:{safe_ok} (got {safe_amt:.2f} exp {truth['safe']:.2f}) | st:{st_ok} m:{m_ok} p:{p_ok} e:{e_ok} c:{c_ok}")

print(f"\nExact matches: {exact_matches}/{total}")
print(f"Safe matches: {safe_matches}/{total}")
print(f"Status matches: {status_matches}/{total}")
print(f"Method matches: {method_matches}/{total}")
print(f"Plan matches: {plan_matches}/{total}")
print(f"Earliest matches: {earliest_matches}/{total}")
print(f"Changes matches: {changes_matches}/{total}")
