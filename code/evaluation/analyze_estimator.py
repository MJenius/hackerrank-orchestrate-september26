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

# Let's test on request_07:
# Target safe: 87170.56
# Profile: user_07, bal=218945.56, min=93000.00, bal-min=125945.56
# Target outflow before salary: 125945.56 - 87170.56 = 38775.00!
req_07 = sample_requests['request_07']
prof_07 = profiles['user_07']
u7_evts = [e for e in events if e.user_id == 'user_07']
u7_msgs = [m for m in messages if m.user_id == 'user_07']

print('Target outflow for user_07 = 38775.00')

# Let's inspect user_07 debits in August 2024:
aug = [e for e in u7_evts if e.settlement_date.startswith('2024-08') and e.direction == 'debit' and e.status == 'settled']
print('User 07 August 2024 settled debits:')
for e in sorted(aug, key=lambda x: x.settlement_date):
    print(f'  {e.settlement_date} | {e.amount:>10.2f} | {e.category:15s} | {e.description}')

# Let's see: salary for user_07:
# message_05: "Your confirmed salary is now expected on 2024-09-23."
# Request date is 2024-09-05.
# So outflow is between 2024-09-05 and 2024-09-23!
# Let's check debits between day 5 and day 23 of August:
sub = [e for e in aug if 5 <= int(e.settlement_date.split('-')[2]) <= 23]
print(f'\nAugust days 5-23 sum = {sum(e.amount for e in sub):.2f}')
for e in sub:
    print(f'  {e.settlement_date} | {e.amount:>10.2f} | {e.category:15s} | {e.description}')
