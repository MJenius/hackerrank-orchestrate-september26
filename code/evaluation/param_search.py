"""
Parameter search to find the exact recurrence & expense model matching sample truth.
"""
import sys, os
sys.path.insert(0, '.')
import numpy as np
from datetime import datetime, timedelta
from collections import defaultdict, Counter
from code.data.loader import *
from code.evidence.image_extractor import ImageEvidenceExtractor
from code.finance.currency import CurrencyConverter
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

# Let's inspect target outflow for each sample request
# Target outflow = (balance - min_balance) - safe_amount
targets = {}
for req_id, truth in SAMPLE_GROUND_TRUTH.items():
    req = sample_requests[req_id]
    prof = profiles[req.user_id]
    bal = prof.current_available_balance
    m = prof.minimum_balance_to_keep
    safe = truth['safe']
    target = (bal - m) - safe
    targets[req_id] = {
        'user_id': req.user_id,
        'request_date': req.request_date,
        'target_outflow': target,
        'safe': safe,
        'req_amt': req.requested_amount,
        'status': truth['status'],
        'method': truth['method']
    }

print("Loaded 25 targets. Ready for parameter testing.")
