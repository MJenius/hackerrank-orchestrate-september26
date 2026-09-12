import sys, os
from datetime import date
sys.path.insert(0, os.path.abspath('.'))
from code.finance.currency import CurrencyConverter
from code.finance.lifecycle import EventLifecycle
from code.finance.plan_ranker import CandidatePlan, rank_candidates
from code.validation.output_validator import OutputValidator
from code.data.models import FinancialEvent, Request, FinancialProfile, RequestPaymentOption
from code.data.loader import load_requests
from code.finance.recurrence import RecurrenceEngine
from code.finance.simulator import BalanceSimulator
from code.evidence.message_resolver import MessageResolver, MessageFact
from code.data.models import Message
from code.finance.future_state import FutureStateBuilder

def test_all():
    print('Testing Boolean CSV Parsing...')
    import tempfile
    with tempfile.NamedTemporaryFile('w', delete=False, suffix='.csv') as tf:
        tf.write('request_id,user_id,request_date,request_type,requested_amount,desired_completion_date,allows_partial_payment,request_text\n')
        tf.write('r1,u1,2025-01-01,purchase,100.0,2025-01-10,true,test\n')
        tf.write('r2,u2,2025-01-01,purchase,100.0,2025-01-10,false,test\n')
        tf.write('r3,u3,2025-01-01,purchase,100.0,2025-01-10,1,test\n')
        tf.write('r4,u4,2025-01-01,purchase,100.0,2025-01-10,0,test\n')
        temp_path = tf.name
    try:
        reqs = load_requests(temp_path)
        assert reqs['r1'].allows_partial_payment is True
        assert reqs['r2'].allows_partial_payment is False
        assert reqs['r3'].allows_partial_payment is True
        assert reqs['r4'].allows_partial_payment is False
    finally:
        os.remove(temp_path)
    print('  -> Boolean CSV Parsing OK')

    print('Testing FX Conversion...')
    rates = {'2025-01-01_USD_EUR': 0.9}
    conv = CurrencyConverter(rates)
    assert conv.convert(100.0, 'USD', 'EUR', '2025-01-01') == 90.0
    assert conv.convert(50.0, 'USD', 'USD', '2025-01-01') == 50.0
    try:
        conv.convert(100.0, 'EUR', 'USD', '2025-01-01')
        assert False, 'Expected ValueError for missing exact rate'
    except ValueError:
        pass
    print('  -> FX OK')

    print('Testing Lifecycle Filtering...')
    e_cancel = FinancialEvent('e1', 'u1', 'expense', 'desc', 'cat', 'debit', 10.0, 'USD', '2025-01-01', '2025-01-01', 'cancelled', None, 'fixed', None)
    assert not EventLifecycle.is_valid_cash_event(e_cancel)
    e_fail = FinancialEvent('e1b', 'u1', 'expense', 'desc', 'cat', 'debit', 10.0, 'USD', '2025-01-01', '2025-01-01', 'failed', None, 'fixed', None)
    assert not EventLifecycle.is_valid_cash_event(e_fail)
    e_unreal = FinancialEvent('e1c', 'u1', 'investment', 'desc', 'cat', 'non_cash', 10.0, 'USD', '2025-01-01', '2025-01-01', 'unrealized', None, 'fixed', None)
    assert not EventLifecycle.is_valid_cash_event(e_unreal)
    e_pend_credit = FinancialEvent('e2', 'u1', 'income', 'desc', 'cat', 'credit', 10.0, 'USD', '2025-01-01', '2025-01-01', 'pending', None, 'fixed', None)
    assert not EventLifecycle.is_valid_cash_event(e_pend_credit)
    e_pend_debit = FinancialEvent('e3', 'u1', 'expense', 'desc', 'cat', 'debit', 10.0, 'USD', '2025-01-01', '2025-01-01', 'pending', None, 'fixed', None)
    assert EventLifecycle.is_valid_cash_event(e_pend_debit)
    print('  -> Lifecycle OK')

    print('Testing Blank Amount Enforcement...')
    e_blank = FinancialEvent('e4', 'u1', 'expense', 'desc', 'cat', 'debit', None, 'USD', '2025-01-01', '2025-01-01', 'settled', None, 'fixed', None)
    try:
        EventLifecycle.get_effective_amount(e_blank)
        assert False, 'Expected ValueError for unresolved amount'
    except ValueError:
        pass
    print('  -> Blank Amount Safety OK')

    print('Testing Recurrence Projection...')
    history = [
        FinancialEvent('r1', 'u1', 'expense', 'Gym Membership', 'fitness', 'debit', 50.0, 'USD', '2024-01-01', '2024-01-01', 'settled', None, 'stoppable', None),
        FinancialEvent('r2', 'u1', 'expense', 'Gym Membership', 'fitness', 'debit', 50.0, 'USD', '2024-02-01', '2024-02-01', 'settled', None, 'stoppable', None),
        FinancialEvent('r3', 'u1', 'expense', 'Gym Membership', 'fitness', 'debit', 50.0, 'USD', '2024-03-01', '2024-03-01', 'settled', None, 'stoppable', None),
    ]
    proj = RecurrenceEngine.project_recurring_events(history, '2024-03-05', horizon_days=60)
    assert len(proj) >= 1
    assert proj[0]['amount'] == 50.0
    print('  -> Recurrence Projection OK')

    print('Testing Message Facts Extraction...')
    msgs = [
        Message('m1', 'u1', None, None, '2024-03-01T09:00:00Z', 'sms', 'Your temporary monthly pay is EUR 1500.00 starting 2024-03-15.')
    ]
    facts = MessageResolver.extract_facts(msgs, 'u1')
    assert len(facts) == 1
    assert facts[0].amount == 1500.0
    assert facts[0].currency == 'EUR'
    print('  -> Message Facts Extraction OK')

    print('Testing Salary End Does Not Drop Confirmed Scheduled Salary...')
    salary_events = [
        FinancialEvent('s1', 'u4', 'income', 'Payroll', 'salary', 'credit', 1000.0, 'USD', '2024-01-15', '2024-01-15', 'settled', None, 'fixed', None),
        FinancialEvent('s2', 'u4', 'income', 'Payroll', 'salary', 'credit', 1000.0, 'USD', '2024-02-15', '2024-02-15', 'settled', None, 'fixed', None),
        FinancialEvent('s3', 'u4', 'income', 'Payroll', 'salary', 'credit', 1000.0, 'USD', '2024-03-15', '2024-03-15', 'scheduled', None, 'fixed', None),
    ]
    facts = [MessageFact('m_end', 'u4', 'salary_end', effective_date='2024-03-20', sent_at='2024-02-28T09:00:00Z')]
    salary_proj = FutureStateBuilder._salary_events(salary_events, facts, date(2024, 3, 1), date(2024, 5, 30), 'USD')
    dates = [e['settlement_date'] for e in salary_proj]
    assert '2024-03-15' in dates
    assert '2024-04-15' not in dates
    print('  -> Salary End Handling OK')

    print('Testing Balance Simulator and Minimum-Balance Safety...')
    conv = CurrencyConverter({})
    sim = BalanceSimulator(conv)
    prof = FinancialProfile('u1', 'USD', 1000.0, 500.0, 'savings', [], [], [], ['full_payment'], 12.0)
    fut_events = [
        {'event_id': 'f1', 'amount': 200.0, 'currency': 'USD', 'direction': 'debit', 'settlement_date': '2025-01-05', 'status': 'scheduled'}
    ]
    # Balance trajectory: start=1000, 2025-01-05 drops to 800. Min keep=500.
    is_safe, min_bal, _ = sim.simulate_trajectory(prof, '2025-01-01', fut_events, {'2025-01-01': 400.0})
    # 1000 - 400 = 600, then -200 = 400 < 500 -> unsafe!
    assert is_safe is False
    assert min_bal == 400.0

    is_safe2, min_bal2, _ = sim.simulate_trajectory(prof, '2025-01-01', fut_events, {'2025-01-01': 200.0})
    # 1000 - 200 = 800, then -200 = 600 >= 500 -> safe!
    assert is_safe2 is True
    assert min_bal2 == 600.0
    print('  -> Balance Simulator OK')

    print('Testing Plan Ranking Priority Rules...')
    c1 = CandidatePlan('installments', '...', None, 'none', 100.0, '2025-01-01', 3, 'opt1', True, False, 'affordable_with_plan')
    c2 = CandidatePlan('full_payment', '...', None, 'none', 90.0, '2025-01-01', 1, 'opt2', True, False, 'affordable_now')
    ranked = rank_candidates([c1, c2])
    assert ranked[0].plan_type == 'full_payment'
    print('  -> Plan Ranking OK')

    print('Testing Output Validator...')
    row = {
        'request_id': 'req_01',
        'amount_safe_to_pay': 100.0,
        'affordability_status': 'affordable_now',
        'recommended_payment_method': 'full_payment',
        'payment_plan': '2025-01-01:100',
        'earliest_date_for_full_payment': '2025-01-01',
        'spending_changes_needed': 'none',
        'decision_explanation': 'Looks safe'
    }
    errs = OutputValidator.validate_row(row, 100.0, '2025-01-01')
    assert len(errs) == 0
    print('  -> Output Validator OK')

    print('Testing Spending Change Safety (No 85% Approximation)...')
    from code.finance.spending_changes import SpendingChangeOptimizer
    from code.data.models import Request
    # User with balance=1000, min_keep=800. Available=200.
    # Request=300. Shortfall=100.
    # Event: streaming stoppable with savings=90.
    # 200 + 90 = 290 >= 300 * 0.85 (which is 255).
    # BUT 1000 - 300 = 700 < 800 (breaches min_keep)!
    # The spending-change optimizer MUST reject it because actual simulation breaches minimum balance.
    prof_sc = FinancialProfile('u_sc', 'USD', 1000.0, 800.0, 'savings', [], [], ['streaming'], ['full_payment'], 12.0)
    req_sc = Request('req_sc', 'u_sc', '2025-01-01', 'purchase', 300.0, '2025-01-10', False, 'Test request')
    fut_sc = [
        {
            'event_id': 'evt_str',
            'source_event_id': 'evt_str',
            'category': 'streaming',
            'amount': 90.0,
            'currency': 'USD',
            'direction': 'debit',
            'settlement_date': '2025-01-05',
            'status': 'projected',
            'flexibility': 'stoppable',
            'minimum_allowed_amount': None,
            'is_projected': True
        }
    ]
    spend_opt = SpendingChangeOptimizer(sim)
    sc_candidates = spend_opt.generate_spending_change_candidates(
        prof_sc, req_sc, fut_sc, {'2025-01-01': 300.0}, '2025-01-01'
    )
    # Must be empty because stopping streaming only frees 90 on Jan 5, but on Jan 1 paying 300 drops balance to 700 < 800!
    assert len(sc_candidates) == 0
    print('  -> Spending Change Simulation Safety OK (85% shortcut strictly rejected)')

    print('\nALL UNIT TESTS PASSED!')

if __name__ == '__main__':
    test_all()
