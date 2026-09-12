from dataclasses import dataclass
from typing import Optional, List, Dict, Any

@dataclass
class FinancialProfile:
    user_id: str
    home_currency: str
    current_available_balance: float
    minimum_balance_to_keep: float
    financial_priorities: str
    expense_categories_to_protect: List[str]
    expense_categories_user_is_willing_to_reduce: List[str]
    expense_categories_user_is_willing_to_stop: List[str]
    payment_methods_user_will_consider: List[str]
    max_installment_months: Optional[float]

@dataclass
class Request:
    request_id: str
    user_id: str
    request_date: str
    request_type: str
    requested_amount: float
    desired_completion_date: str
    allows_partial_payment: bool
    request_text: str

@dataclass
class FinancialEvent:
    event_id: str
    user_id: str
    event_type: str
    description: str
    category: str
    direction: str  # debit, credit, non_cash
    amount: Optional[float]
    currency: str
    event_date: str
    settlement_date: str
    status: str  # settled, pending, scheduled, cancelled, failed, unrealized
    linked_event_id: Optional[str]
    flexibility: str  # fixed, reducible, stoppable, reducible_or_stoppable
    minimum_allowed_amount: Optional[float]

@dataclass
class RequestPaymentOption:
    payment_option_id: str
    request_id: str
    payment_method: str  # installments, full_payment
    payment_amount: float
    number_of_payments: int
    first_payment_date: str
    payment_frequency_days: Optional[float]
    financing_fee: float
    total_payable_amount: float

@dataclass
class ExchangeRate:
    rate_date: str
    from_currency: str
    to_currency: str
    rate: float

@dataclass
class Message:
    message_id: str
    user_id: str
    request_id: Optional[str]
    related_event_id: Optional[str]
    sent_at: str
    source_type: str
    message_text: str

@dataclass
class ImageMapping:
    image_id: str
    user_id: str
    request_id: Optional[str]
    related_event_id: Optional[str]
