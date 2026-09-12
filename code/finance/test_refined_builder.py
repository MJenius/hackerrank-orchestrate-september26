"""
Prototype testing the refined future state logic on the 25 sample requests.
"""
import sys, os
sys.path.insert(0, '.')
from datetime import datetime, timedelta
from typing import List, Dict, Set, Optional, Tuple
from collections import defaultdict

from code.data.loader import *
from code.data.models import FinancialEvent, FinancialProfile, Message
from code.evidence.image_extractor import ImageEvidenceExtractor
from code.finance.currency import CurrencyConverter
from code.finance.simulator import BalanceSimulator
from code.finance.optimizer import FinancialOptimizer
from code.finance.lifecycle import EventLifecycle
from code.evaluation.sample_truth import SAMPLE_GROUND_TRUTH

def build_refined_future(
    user_id: str,
    profile: FinancialProfile,
    request_date: str,
    user_events: List[FinancialEvent],
    user_messages: List[Message],
    converter: CurrencyConverter,
    horizon_days: int = 90
) -> List[Dict]:
    req_dt = datetime.strptime(request_date, '%Y-%m-%d')
    end_dt = req_dt + timedelta(days=horizon_days)
    end_str = end_dt.strftime('%Y-%m-%d')
    
    # 1. Parse messages
    from code.finance.future_state import FutureStateBuilder
    fb_temp = FutureStateBuilder([], [])
    amend = fb_temp._parse_messages(user_messages, request_date)
    
    # 2. Explicit future events
    explicit = []
    explicit_dates_by_cat = defaultdict(set)
    for e in user_events:
        if not EventLifecycle.is_valid_cash_event(e):
            continue
        if e.amount is None or e.amount <= 0:
            continue
        if e.settlement_date < request_date or e.settlement_date > end_str:
            continue
        if (e.direction == 'debit' and e.status in ('scheduled', 'pending')) or \
           (e.direction == 'credit' and e.status == 'scheduled'):
            explicit.append({
                'event_id': e.event_id,
                'amount': e.amount,
                'currency': e.currency,
                'direction': e.direction,
                'settlement_date': e.settlement_date,
                'status': e.status,
                'category': e.category,
                'description': e.description,
                'flexibility': e.flexibility,
                'minimum_allowed_amount': e.minimum_allowed_amount
            })
            explicit_dates_by_cat[e.category].add(e.settlement_date)

    # 3. Settled past events
    past = [
        e for e in user_events
        if e.settlement_date < request_date
        and e.status == 'settled'
        and e.amount is not None
        and e.amount > 0
    ]

    projected = []
    
    # --- Salary Projection ---
    salary_ended = amend.get('salary_ended', False)
    past_salaries = [e for e in past if e.category == 'salary' and e.direction == 'credit']
    if past_salaries:
        past_salaries.sort(key=lambda x: x.settlement_date)
        last_sal = past_salaries[-1]
        if 'final' in last_sal.description.lower():
            salary_ended = True
            
    if not salary_ended:
        # Check if user has gig earnings instead of employer salary
        is_gig = False
        if past_salaries and any(
            any(w in s.description.lower() for w in ['driver', 'task', 'delivery platform', 'marketplace', 'freelance'])
            for s in past_salaries
        ):
            # Check if there is also regular employer salary
            has_regular = any(
                any(w in s.description.lower() for w in ['payroll', 'base salary', 'confirmed salary'])
                for s in past_salaries
            )
            if not has_regular:
                is_gig = True
                
        # If message says payout pending, don't project gig earnings
        if is_gig and (amend.get('payout_pending') or amend.get('salary_ended')):
            pass # No salary projection
        elif past_salaries or any(e['category'] == 'salary' and e['direction'] == 'credit' for e in explicit):
            # Find salary details
            all_sal = past_salaries + [e for e in user_events if e.category == 'salary' and e.direction == 'credit' and e.status == 'scheduled']
            all_sal.sort(key=lambda x: x.settlement_date)
            last_sal = all_sal[-1]
            
            sal_amt = last_sal.amount
            # Apply message amendments
            if amend.get('salary_amount') is not None:
                sal_amt = amend['salary_amount']
            elif amend.get('confirmed_salary_amt') is not None:
                sal_amt = amend['confirmed_salary_amt']
            elif amend.get('salary_temporary') is not None:
                sal_amt = amend['salary_temporary']
            elif amend.get('salary_reduced') is not None:
                sal_amt = amend['salary_reduced']
            elif amend.get('income_ended_remaining') is not None:
                sal_amt = amend['income_ended_remaining']
            elif amend.get('first_salary_amt') is not None:
                sal_amt = amend['first_salary_amt']
                
            sal_currency = last_sal.currency
            
            # Determine pay day
            last_dt = datetime.strptime(last_sal.settlement_date, '%Y-%m-%d')
            pay_day = last_dt.day
            if amend.get('salary_date'):
                pay_day = int(amend['salary_date'].split('-')[2])
                
            curr_dt = req_dt.replace(day=min(pay_day, 28))
            if curr_dt < req_dt:
                # Move to next month
                m = curr_dt.month + 1
                y = curr_dt.year
                if m > 12: m = 1; y += 1
                curr_dt = curr_dt.replace(year=y, month=m, day=min(pay_day, 28))
                
            while curr_dt <= end_dt:
                dt_str = curr_dt.strftime('%Y-%m-%d')
                # Only add if not already in explicit
                if dt_str not in explicit_dates_by_cat['salary']:
                    projected.append({
                        'event_id': f"proj_sal_{dt_str.replace('-','')}",
                        'source_event_id': last_sal.event_id,
                        'amount': sal_amt,
                        'currency': sal_currency,
                        'direction': 'credit',
                        'settlement_date': dt_str,
                        'status': 'projected',
                        'category': 'salary',
                        'description': 'Projected salary credit',
                        'is_projected': True
                    })
                m = curr_dt.month + 1
                y = curr_dt.year
                if m > 12: m = 1; y += 1
                curr_dt = curr_dt.replace(year=y, month=m, day=min(pay_day, 28))

    # --- Fixed Monthly Debits ---
    # Group by description
    debit_groups = defaultdict(list)
    for e in past:
        if e.direction == 'debit' and e.category not in ('groceries', 'transport', 'dining'):
            debit_groups[e.description].append(e)
            
    for desc, evts in debit_groups.items():
        if len(evts) < 2:
            continue
        evts.sort(key=lambda x: x.settlement_date)
        dates = [datetime.strptime(x.settlement_date, '%Y-%m-%d') for x in evts]
        diffs = [(dates[i] - dates[i-1]).days for i in range(1, len(dates))]
        avg_diff = sum(diffs) / len(diffs)
        
        # Monthly fixed bill: avg interval 25-35 days
        if 25 <= avg_diff <= 35:
            last_evt = evts[-1]
            last_dt = dates[-1]
            pay_day = min(last_dt.day, 28)
            
            amt = last_evt.amount
            if last_evt.category == 'rent' and amend.get('rent_increase_pct'):
                amt = round(amt * (1 + amend['rent_increase_pct']), 2)
                
            curr_dt = req_dt.replace(day=pay_day)
            if curr_dt < req_dt:
                m = curr_dt.month + 1
                y = curr_dt.year
                if m > 12: m = 1; y += 1
                curr_dt = curr_dt.replace(year=y, month=m, day=pay_day)
                
            while curr_dt <= end_dt:
                dt_str = curr_dt.strftime('%Y-%m-%d')
                if dt_str not in explicit_dates_by_cat[last_evt.category]:
                    projected.append({
                        'event_id': f"proj_{last_evt.event_id}_{dt_str.replace('-','')}",
                        'source_event_id': last_evt.event_id,
                        'amount': amt,
                        'currency': last_evt.currency,
                        'direction': 'debit',
                        'settlement_date': dt_str,
                        'status': 'projected',
                        'category': last_evt.category,
                        'description': desc,
                        'flexibility': last_evt.flexibility,
                        'minimum_allowed_amount': last_evt.minimum_allowed_amount,
                        'is_projected': True
                    })
                m = curr_dt.month + 1
                y = curr_dt.year
                if m > 12: m = 1; y += 1
                curr_dt = curr_dt.replace(year=y, month=m, day=pay_day)

    # --- Variable Cadence Debits (Groceries, Transport, Dining) ---
    for cat in ['groceries', 'transport', 'dining']:
        cat_evts = [e for e in past if e.category == cat and e.direction == 'debit']
        if len(cat_evts) < 2:
            continue
        cat_evts.sort(key=lambda x: x.settlement_date)
        dates = [datetime.strptime(x.settlement_date, '%Y-%m-%d') for x in cat_evts]
        diffs = [(dates[i] - dates[i-1]).days for i in range(1, len(dates))]
        # Most common diff or average diff
        from collections import Counter
        diff_counts = Counter(diffs)
        cadence_days = diff_counts.most_common(1)[0][0]
        if cadence_days not in (5, 7, 10, 14, 21, 28, 30):
            cadence_days = round(sum(diffs) / len(diffs))
            
        last_evt = cat_evts[-1]
        last_dt = dates[-1]
        # Conservative amount: average of recent settled amounts
        recent = cat_evts[-4:] if len(cat_evts) >= 4 else cat_evts
        cat_amt = round(sum(e.amount for e in recent) / len(recent), 2)
        
        curr_dt = last_dt + timedelta(days=cadence_days)
        while curr_dt <= end_dt:
            if curr_dt >= req_dt:
                dt_str = curr_dt.strftime('%Y-%m-%d')
                projected.append({
                    'event_id': f"proj_{last_evt.event_id}_{dt_str.replace('-','')}",
                    'source_event_id': last_evt.event_id,
                    'amount': cat_amt,
                    'currency': last_evt.currency,
                    'direction': 'debit',
                    'settlement_date': dt_str,
                    'status': 'projected',
                    'category': cat,
                    'description': f"Projected {cat}",
                    'flexibility': last_evt.flexibility,
                    'minimum_allowed_amount': last_evt.minimum_allowed_amount,
                    'is_projected': True
                })
            curr_dt += timedelta(days=cadence_days)

    return explicit + projected

print('Testing refined builder...')
