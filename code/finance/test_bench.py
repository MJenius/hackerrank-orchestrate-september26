import pandas as pd
import numpy as np
from datetime import datetime
from typing import Dict, List, Tuple
from code.data.loader import (
    load_profiles, load_requests, load_financial_events,
    load_payment_options, load_exchange_rates, load_messages, load_image_mappings
)
from code.evidence.image_extractor import ImageEvidenceExtractor
from code.evidence.message_resolver import MessageResolver
from code.finance.currency import CurrencyConverter
from code.finance.lifecycle import EventLifecycle
from code.finance.simulator import BalanceSimulator
from code.finance.plan_ranker import CandidatePlan, rank_candidates

profiles = load_profiles('dataset/financial_profiles.csv')
sample_df = pd.read_csv('dataset/sample_requests.csv')
events = load_financial_events('dataset/financial_events.csv')
options = load_payment_options('dataset/request_payment_options.csv')
rates = load_exchange_rates('dataset/exchange_rates.csv')
messages = load_messages('dataset/messages.csv')
images = load_image_mappings('dataset/images.csv')

img_extractor = ImageEvidenceExtractor()
converter = CurrencyConverter(rates)
sim = BalanceSimulator(converter)

# Pre-populate missing event amounts from images
event_by_id = {e.event_id: e for e in events}
for img_id, m in images.items():
    if m.related_event_id and m.related_event_id in event_by_id:
        fact = img_extractor.extract_fact(img_id)
        if fact:
            event_by_id[m.related_event_id].amount = fact.amount

print('Setup completed successfully.')
