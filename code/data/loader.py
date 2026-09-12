import os
import pandas as pd
from typing import Dict, List, Optional, Any
from code.data.models import (
    FinancialProfile,
    Request,
    FinancialEvent,
    RequestPaymentOption,
    ExchangeRate,
    Message,
    ImageMapping,
)

def _parse_list(val: Any) -> List[str]:
    if pd.isna(val) or not val:
        return []
    val_str = str(val).strip()
    if not val_str:
        return []
    # Can be separated by '|' or ','
    items = []
    for chunk in val_str.replace('|', ',').split(','):
        if chunk.strip():
            items.append(chunk.strip())
    return items

def load_profiles(filepath: str) -> Dict[str, FinancialProfile]:
    df = pd.read_csv(filepath)
    profiles = {}
    for _, r in df.iterrows():
        p = FinancialProfile(
            user_id=str(r['user_id']),
            home_currency=str(r['home_currency']),
            current_available_balance=float(r['current_available_balance']),
            minimum_balance_to_keep=float(r['minimum_balance_to_keep']),
            financial_priorities=str(r.get('financial_priorities', '')),
            expense_categories_to_protect=_parse_list(r.get('expense_categories_to_protect')),
            expense_categories_user_is_willing_to_reduce=_parse_list(r.get('expense_categories_user_is_willing_to_reduce')),
            expense_categories_user_is_willing_to_stop=_parse_list(r.get('expense_categories_user_is_willing_to_stop')),
            payment_methods_user_will_consider=_parse_list(r.get('payment_methods_user_will_consider')),
            max_installment_months=float(r['max_installment_months']) if pd.notna(r.get('max_installment_months')) else None
        )
        profiles[p.user_id] = p
    return profiles

def load_requests(filepath: str) -> Dict[str, Request]:
    df = pd.read_csv(filepath)
    requests = {}
    for _, r in df.iterrows():
        req = Request(
            request_id=str(r['request_id']),
            user_id=str(r['user_id']),
            request_date=str(r['request_date']),
            request_type=str(r['request_type']),
            requested_amount=float(r['requested_amount']),
            desired_completion_date=str(r['desired_completion_date']),
            allows_partial_payment=str(r['allows_partial_payment']).strip().lower() in ('true', '1', 'yes', 't'),
            request_text=str(r['request_text'])
        )
        requests[req.request_id] = req
    return requests

def load_financial_events(filepath: str) -> List[FinancialEvent]:
    df = pd.read_csv(filepath)
    events = []
    for _, r in df.iterrows():
        evt = FinancialEvent(
            event_id=str(r['event_id']),
            user_id=str(r['user_id']),
            event_type=str(r['event_type']),
            description=str(r['description']),
            category=str(r['category']),
            direction=str(r['direction']),
            amount=float(r['amount']) if pd.notna(r.get('amount')) else None,
            currency=str(r['currency']),
            event_date=str(r['event_date']),
            settlement_date=str(r['settlement_date']),
            status=str(r['status']),
            linked_event_id=str(r['linked_event_id']) if pd.notna(r.get('linked_event_id')) else None,
            flexibility=str(r['flexibility']),
            minimum_allowed_amount=float(r['minimum_allowed_amount']) if pd.notna(r.get('minimum_allowed_amount')) else None
        )
        events.append(evt)
    return events

def load_payment_options(filepath: str) -> Dict[str, List[RequestPaymentOption]]:
    df = pd.read_csv(filepath)
    options_by_req = {}
    for _, r in df.iterrows():
        opt = RequestPaymentOption(
            payment_option_id=str(r['payment_option_id']),
            request_id=str(r['request_id']),
            payment_method=str(r['payment_method']),
            payment_amount=float(r['payment_amount']),
            number_of_payments=int(r['number_of_payments']),
            first_payment_date=str(r['first_payment_date']),
            payment_frequency_days=float(r['payment_frequency_days']) if pd.notna(r.get('payment_frequency_days')) else None,
            financing_fee=float(r['financing_fee']),
            total_payable_amount=float(r['total_payable_amount'])
        )
        if opt.request_id not in options_by_req:
            options_by_req[opt.request_id] = []
        options_by_req[opt.request_id].append(opt)
    return options_by_req

def load_exchange_rates(filepath: str) -> Dict[str, float]:
    df = pd.read_csv(filepath)
    rates = {}
    for _, r in df.iterrows():
        key = f"{r['rate_date']}_{r['from_currency']}_{r['to_currency']}"
        rates[key] = float(r['rate'])
    return rates

def load_messages(filepath: str) -> List[Message]:
    df = pd.read_csv(filepath)
    messages = []
    for _, r in df.iterrows():
        msg = Message(
            message_id=str(r['message_id']),
            user_id=str(r['user_id']),
            request_id=str(r['request_id']) if pd.notna(r.get('request_id')) else None,
            related_event_id=str(r['related_event_id']) if pd.notna(r.get('related_event_id')) else None,
            sent_at=str(r['sent_at']),
            source_type=str(r['source_type']),
            message_text=str(r['message_text'])
        )
        messages.append(msg)
    return messages

def load_image_mappings(filepath: str) -> Dict[str, ImageMapping]:
    df = pd.read_csv(filepath)
    mappings = {}
    for _, r in df.iterrows():
        m = ImageMapping(
            image_id=str(r['image_id']),
            user_id=str(r['user_id']),
            request_id=str(r['request_id']) if pd.notna(r.get('request_id')) else None,
            related_event_id=str(r['related_event_id']) if pd.notna(r.get('related_event_id')) else None
        )
        mappings[m.image_id] = m
    return mappings
