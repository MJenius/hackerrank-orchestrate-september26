import sys, os
sys.path.insert(0, os.path.abspath('.'))
import pandas as pd
from typing import Dict, List, Optional
from code.data.loader import (
    load_profiles, load_requests, load_financial_events,
    load_payment_options, load_exchange_rates, load_messages, load_image_mappings
)
from code.evidence.image_extractor import ImageEvidenceExtractor
from code.evidence.message_resolver import MessageResolver
from code.finance.currency import CurrencyConverter
from code.finance.simulator import BalanceSimulator
from code.finance.optimizer import FinancialOptimizer
from code.explanation.generator import ExplanationGenerator

def run_regression():
    profiles = load_profiles('dataset/financial_profiles.csv')
    sample_df = pd.read_csv('dataset/sample_requests.csv')
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
            fact = img_ext.extract_fact(img_id)
            if fact:
                event_by_id[m.related_event_id].amount = fact.amount

    converter = CurrencyConverter(rates)
    sim = BalanceSimulator(converter)
    opt = FinancialOptimizer(sim)

    total = len(sample_df)
    matches = 0
    print('Evaluating sample requests against ground truth:\n')

    for _, exp in sample_df.iterrows():
        req_id = exp['request_id']
        req = sample_requests[req_id]
        prof = profiles[req.user_id]
        opts = options.get(req_id, [])

        user_events = [e for e in events if e.user_id == req.user_id]
        fut = [
            {
                'event_id': e.event_id,
                'amount': e.amount,
                'currency': e.currency,
                'direction': e.direction,
                'settlement_date': e.settlement_date,
                'status': e.status
            }
            for e in user_events
            if e.settlement_date >= req.request_date and (
                (e.direction == 'debit' and e.status in ('scheduled', 'pending')) or
                (e.direction == 'credit' and e.status == 'scheduled')
            )
        ]

        safe_amt, pred = opt.evaluate_request(prof, req, opts, fut)

        st_match = (pred.affordability_status == exp['affordability_status'])
        m_match = (pred.plan_type == exp['recommended_payment_method'])
        
        exp_earliest = exp['earliest_date_for_full_payment']
        if pd.isna(exp_earliest) or str(exp_earliest).lower() == 'nan':
            e_match = (pred.earliest_date_for_full_payment is None or pred.earliest_date_for_full_payment == '')
        else:
            e_match = (str(pred.earliest_date_for_full_payment) == str(exp_earliest))

        is_perfect = st_match and m_match and e_match
        if is_perfect:
            matches += 1

        print(f"{req_id}: Status {'[PASS]' if st_match else '[FAIL]'} | Method {'[PASS]' if m_match else '[FAIL]'} | Earliest {'[PASS]' if e_match else '[FAIL]'}")

    print(f'\nTotal sample accuracy: {matches}/{total} ({matches/total*100:.1f}%)')

if __name__ == '__main__':
    run_regression()
