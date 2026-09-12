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

    # Test variable recurring expense with varying dates and amounts (e.g. groceries off-cycle by 1 day)
    var_history = [
        FinancialEvent('vg1', 'u_var', 'expense', 'Supermarket', 'groceries', 'debit', 50.0, 'USD', '2024-01-01', '2024-01-01', 'settled', None, 'fixed', None),
        FinancialEvent('vg2', 'u_var', 'expense', 'Supermarket', 'groceries', 'debit', 55.0, 'USD', '2024-01-08', '2024-01-08', 'settled', None, 'fixed', None),
        FinancialEvent('vg3', 'u_var', 'expense', 'Supermarket', 'groceries', 'debit', 52.0, 'USD', '2024-01-16', '2024-01-16', 'settled', None, 'fixed', None),
        FinancialEvent('vg4', 'u_var', 'expense', 'Supermarket', 'groceries', 'debit', 48.0, 'USD', '2024-01-23', '2024-01-23', 'settled', None, 'fixed', None),
    ]
    var_proj = RecurrenceEngine.project_recurring_events(var_history, '2024-01-25', horizon_days=30)
    assert len(var_proj) >= 3, 'Variable expense with slightly varying dates must not be discarded'
    assert var_proj[0]['category'] == 'groceries'
    assert var_proj[0]['settlement_date'] == '2024-01-30'
    assert var_proj[0]['amount'] == 51.0  # median([50, 55, 52, 48]) = 51.0
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
            'is_projected': True,
            'is_recurring': True
        }
    ]
    spend_opt = SpendingChangeOptimizer(sim)
    sc_candidates = spend_opt.generate_spending_change_candidates(
        prof_sc, req_sc, fut_sc, {'2025-01-01': 300.0}, '2025-01-01'
    )
    # Must be empty because stopping streaming only frees 90 on Jan 5, but on Jan 1 paying 300 drops balance to 700 < 800!
    assert len(sc_candidates) == 0
    print('  -> Spending Change Simulation Safety OK (85% shortcut strictly rejected)')

    print('Testing Pending Debit Timing and Pending Credit Exclusion...')
    # 1. Pending debit with future settlement date reserves on settlement date
    # 2. Pending debit without future settlement date reserves on request date
    # 3. Pending credit is never treated as available cash
    sim_test = BalanceSimulator(conv)
    prof_sim = FinancialProfile('u_pend', 'USD', 1000.0, 500.0, 'savings', [], [], [], ['full_payment'], 12.0)
    fut_pend = [
        {'event_id': 'd_future', 'amount': 200.0, 'currency': 'USD', 'direction': 'debit', 'settlement_date': '2025-01-10', 'status': 'pending'},
        {'event_id': 'd_now', 'amount': 100.0, 'currency': 'USD', 'direction': 'debit', 'settlement_date': '2024-12-28', 'status': 'pending'},
        {'event_id': 'c_pend', 'amount': 500.0, 'currency': 'USD', 'direction': 'credit', 'settlement_date': '2025-01-02', 'status': 'pending'},
    ]
    is_safe, min_bal, bal_map = sim_test.simulate_trajectory(prof_sim, '2025-01-01', fut_pend, {})
    # d_now reserves on 2025-01-01 -> balance 900
    # c_pend is pending credit -> excluded, not credited!
    # d_future reserves on 2025-01-10 -> balance drops to 700
    assert bal_map['2025-01-01'] == 900.0
    assert bal_map['2025-01-09'] == 900.0
    assert bal_map['2025-01-10'] == 700.0
    assert min_bal == 700.0
    print('  -> Pending Timing & Credit Exclusion OK')

    print('Testing Salary End Safeguard...')
    from code.finance.future_state import FutureStateBuilder
    all_events = [
        FinancialEvent('sal_sched', 'u_sal', 'income', 'Monthly Salary', 'salary', 'credit', 2000.0, 'USD', '2025-01-15', '2025-01-15', 'scheduled', None, 'fixed', None),
        FinancialEvent('sal_sched_later', 'u_sal', 'income', 'Monthly Salary', 'salary', 'credit', 2000.0, 'USD', '2025-02-15', '2025-02-15', 'scheduled', None, 'fixed', None),
    ]
    # Message ending salary sent on 2025-01-20: Jan 15 salary occurs before contract end and is kept; Feb 15 occurs after and must be removed
    sal_msgs = [
        Message('m_end', 'u_sal', None, None, '2025-01-20T10:00:00Z', 'employer', 'The current seasonal contract has ended. No off-season income or renewal has been confirmed.')
    ]
    builder_sal = FutureStateBuilder(all_events, sal_msgs)
    prof_sal = FinancialProfile('u_sal', 'USD', 1000.0, 500.0, 'savings', [], [], [], ['full_payment'], 12.0)
    fut_sal = builder_sal.build('u_sal', prof_sal, '2025-01-25')
    sal_dates = [e['settlement_date'] for e in fut_sal if e.get('category') == 'salary' or 'salary' in str(e.get('description', '')).lower()]
    assert '2025-01-15' not in sal_dates, 'Jan 15 is before request_date 2025-01-25'
    assert '2025-02-15' not in sal_dates, 'Salary after end date must be removed'

    # Now verify when request_date is 2025-01-10 (before Jan 15), but message ending salary is 2025-01-10 with effective date 2025-01-20:
    sal_msgs_dated = [
        Message('m_end2', 'u_sal', None, None, '2025-01-10T10:00:00Z', 'employer', 'Your contract has ended effective 2025-01-20.')
    ]
    builder_sal2 = FutureStateBuilder(all_events, sal_msgs_dated)
    fut_sal2 = builder_sal2.build('u_sal', prof_sal, '2025-01-10')
    sal_dates2 = [e['settlement_date'] for e in fut_sal2 if e.get('category') == 'salary' or 'salary' in str(e.get('description', '')).lower()]
    assert '2025-01-15' in sal_dates2, 'Jan 15 salary on or before end date 2025-01-20 should be kept'
    assert '2025-02-15' not in sal_dates2, 'Feb 15 salary after end date 2025-01-20 must be removed'
    print('  -> Salary End Safeguard OK')

    print('Testing Non-Recurring Spending Change Rejection...')
    # If is_recurring is False, spending change optimizer must reject it even if flexibility is stoppable
    fut_non_rec = [
        {
            'event_id': 'evt_onetime',
            'source_event_id': 'evt_onetime',
            'category': 'streaming',
            'amount': 50.0,
            'currency': 'USD',
            'direction': 'debit',
            'settlement_date': '2025-01-05',
            'status': 'projected',
            'flexibility': 'stoppable',
            'minimum_allowed_amount': None,
            'is_recurring': False
        }
    ]
    prof_nr = FinancialProfile('u_nr', 'USD', 1000.0, 500.0, 'savings', [], [], ['streaming'], ['full_payment'], 12.0)
    req_nr = Request('req_nr', 'u_nr', '2025-01-01', 'purchase', 600.0, '2025-01-10', False, 'Test request')
    sc_nr = spend_opt.generate_spending_change_candidates(prof_nr, req_nr, fut_non_rec, {'2025-01-01': 600.0}, '2025-01-01')
    assert len(sc_nr) == 0, 'Non-recurring events must never be eligible for spending changes'
    print('  -> Non-Recurring Spending Change Rejection OK')

    print('Testing Request-Scoped Message Facts...')
    msgs_scoped = [
        Message('m_req1', 'u_scope', 'r_01', None, '2025-01-01T09:00:00Z', 'sms', 'Payment approved for EUR 50.00.'),
        Message('m_req2', 'u_scope', 'r_02', None, '2025-01-01T09:00:00Z', 'sms', 'Payment approved for EUR 75.00.')
    ]
    facts_r1 = MessageResolver.extract_facts(msgs_scoped, 'u_scope', '2025-01-01', request_id='r_01')
    assert len(facts_r1) == 1
    assert facts_r1[0].amount == 50.0
    facts_r2 = MessageResolver.extract_facts(msgs_scoped, 'u_scope', '2025-01-01', request_id='r_02')
    assert len(facts_r2) == 1
    assert facts_r2[0].amount == 75.0
    print('Testing Multi-Stream and Freelance/Gig Recurring Income Projections...')
    # Test 1: 5+ months freelance income with varying descriptions projected
    freelance_events = [
        FinancialEvent(f'fl_{m}', 'u_fl', 'income', f'Freelance project {m}', 'salary', 'credit', 1000.0 + m * 50, 'USD', f'2024-0{m}-07', f'2024-0{m}-07', 'settled', None, 'fixed', None)
        for m in range(1, 6)
    ]
    fl_builder = FutureStateBuilder(freelance_events, [])
    fl_prof = FinancialProfile('u_fl', 'USD', 1000.0, 500.0, 'savings', [], [], [], ['full_payment'], 12.0)
    fut_fl = fl_builder.build('u_fl', fl_prof, '2024-06-01', horizon_days=60)
    fl_sal = [e for e in fut_fl if e.get('category') == 'salary']
    assert len(fl_sal) >= 2, 'Freelance recurring stream must be projected'
    assert fl_sal[0]['settlement_date'] == '2024-06-07'

    # Test 2: Gig/platform weekly income cadence projected every 7 days
    weekly_dates = ['2024-05-04', '2024-05-11', '2024-05-18', '2024-05-25', '2024-06-04', '2024-06-11', '2024-06-18', '2024-06-25']
    gig_events = [
        FinancialEvent(f'gig_{i}', 'u_gig', 'income', 'Delivery platform payout', 'salary', 'credit', 500.0, 'USD', dt, dt, 'settled', None, 'fixed', None)
        for i, dt in enumerate(weekly_dates)
    ]
    gig_builder = FutureStateBuilder(gig_events, [])
    gig_prof = FinancialProfile('u_gig', 'USD', 1000.0, 500.0, 'savings', [], [], [], ['full_payment'], 12.0)
    fut_gig = gig_builder.build('u_gig', gig_prof, '2024-07-01', horizon_days=30)
    gig_sal = [e for e in fut_gig if e.get('category') == 'salary']
    assert len(gig_sal) >= 4, 'Gig weekly stream must project every 7 days'
    gaps = [(date.fromisoformat(gig_sal[i+1]['settlement_date']) - date.fromisoformat(gig_sal[i]['settlement_date'])).days for i in range(len(gig_sal)-1)]
    assert all(g == 7 for g in gaps), f'Projected weekly salary must step by 7 days, got gaps {gaps}'

    # Test 3: Irregular one-off bonus/reimbursement not projected
    bonus_events = [
        FinancialEvent('b1', 'u_bonus', 'income', 'Annual bonus', 'salary', 'credit', 5000.0, 'USD', '2024-01-15', '2024-01-15', 'settled', None, 'fixed', None),
        FinancialEvent('b2', 'u_bonus', 'income', 'Travel reimbursement', 'salary', 'credit', 300.0, 'USD', '2024-02-15', '2024-02-15', 'settled', None, 'fixed', None),
    ]
    bonus_builder = FutureStateBuilder(bonus_events, [])
    fut_bonus = bonus_builder.build('u_bonus', fl_prof, '2024-03-01', horizon_days=60)
    bonus_sal = [e for e in fut_bonus if e.get('category') == 'salary']
    assert len(bonus_sal) == 0, 'Irregular bonus/reimbursement must not be projected'

    # Test 4: Confirmed termination stops stream after effective date
    term_msgs = [
        Message('m_term', 'u_term', None, None, '2024-05-20T10:00:00Z', 'employer', 'Your contract has ended effective 2024-05-25.')
    ]
    sal_term_events = [
        FinancialEvent(f'sal_t_{m}', 'u_term', 'income', 'Base salary', 'salary', 'credit', 2000.0, 'USD', f'2024-0{m}-15', f'2024-0{m}-15', 'settled', None, 'fixed', None)
        for m in range(1, 6)
    ] + [
        FinancialEvent('sal_sched_term', 'u_term', 'income', 'Base salary', 'salary', 'credit', 2000.0, 'USD', '2024-06-15', '2024-06-15', 'scheduled', None, 'fixed', None)
    ]
    term_builder = FutureStateBuilder(sal_term_events, term_msgs)
    fut_term = term_builder.build('u_term', fl_prof, '2024-05-21', horizon_days=60)
    term_sal = [e for e in fut_term if e.get('category') == 'salary']
    assert all(e['settlement_date'] <= '2024-05-25' for e in term_sal), 'Salary after termination must be stopped'

    # Test 5: Multiple simultaneous streams kept separate
    multi_stream_events = [
        FinancialEvent(f'ms1_{m}', 'u_ms', 'income', 'Day 8 payout', 'salary', 'credit', 1000.0, 'USD', f'2024-0{m}-08', f'2024-0{m}-08', 'settled', None, 'fixed', None)
        for m in range(1, 6)
    ] + [
        FinancialEvent(f'ms2_{m}', 'u_ms', 'income', 'Day 22 payout', 'salary', 'credit', 1200.0, 'USD', f'2024-0{m}-22', f'2024-0{m}-22', 'settled', None, 'fixed', None)
        for m in range(1, 6)
    ]
    ms_builder = FutureStateBuilder(multi_stream_events, [])
    fut_ms = ms_builder.build('u_ms', fl_prof, '2024-06-01', horizon_days=60)
    ms_sal = [e for e in fut_ms if e.get('category') == 'salary']
    ms_days = {e['settlement_date'][-2:] for e in ms_sal}
    assert '08' in ms_days and '22' in ms_days, 'Both recurring income streams must be projected independently'

    print('  -> Multi-Stream and Irregular Salary Logic OK')

    print('Testing Spending Change Intermediate/Floor Reduction Search...')
    # Candidate with can_reduce can reduce down to floor
    fut_red = [
        {
            'event_id': 'evt_red',
            'source_event_id': 'evt_red',
            'category': 'dining',
            'amount': 100.0,
            'currency': 'USD',
            'direction': 'debit',
            'settlement_date': '2025-01-05',
            'status': 'projected',
            'flexibility': 'reducible',
            'minimum_allowed_amount': 50.0,
            'is_recurring': True
        }
    ]
    # Opening balance: 1000. Min keep: 800.
    # Without reduction, balance on Jan 5 is 1000 - 100 = 900.
    # On Jan 10 paying 150: 900 - 150 = 750 < 800 (unsafe!).
    # Reducing evt_red on Jan 5 from 100 to 50: balance becomes 950.
    # On Jan 10 paying 150: 950 - 150 = 800 >= 800 (safe!).
    prof_red = FinancialProfile('u_red', 'USD', 1000.0, 800.0, 'savings', [], ['dining'], [], ['full_payment'], 12.0)
    req_red = Request('req_red', 'u_red', '2025-01-01', 'purchase', 150.0, '2025-01-10', False, 'Test request')
    sc_red = spend_opt.generate_spending_change_candidates(
        prof_red, req_red, fut_red, {'2025-01-10': 150.0}, '2025-01-10'
    )
    assert len(sc_red) >= 1
    assert 'reduce_to:evt_red:' in sc_red[0].spending_changes_needed
    print('  -> Spending Change Reduction Search OK')

    print('Testing Income Uncertainty Safeguard...')
    # Weekly gig income should not be projected as recurring when service provider indicates payout is uncertain/pending
    gig_events = [
        FinancialEvent(f'gig_{i}', 'u_gig', 'income', 'Weekly app earnings', 'salary', 'credit', 250.0, 'USD',
                       f'2025-01-{i*7:02d}', f'2025-01-{i*7:02d}', 'settled', None, 'fixed', None)
        for i in range(1, 5)
    ]
    gig_prof = FinancialProfile('u_gig', 'USD', 500.0, 300.0, 'savings', [], [], [], ['full_payment'], 12.0)
    # Case 1: Without uncertainty message, weekly salary is projected
    gig_builder_normal = FutureStateBuilder(gig_events, [])
    fut_gig_normal = gig_builder_normal.build('u_gig', gig_prof, '2025-01-30', horizon_days=30)
    gig_proj_normal = [e for e in fut_gig_normal if e.get('category') == 'salary']
    assert len(gig_proj_normal) > 0, 'Weekly gig income should be projected when certain'

    # Case 2: With uncertainty message, weekly gig income is NOT projected as guaranteed recurring salary
    gig_msgs = [
        Message('m_unc', 'u_gig', None, None, '2025-01-24T12:00:00Z', 'service_provider',
                'Your payout is still pending and earnings shown in the app can change before payout processing completes.')
    ]
    gig_builder_unc = FutureStateBuilder(gig_events, gig_msgs)
    fut_gig_unc = gig_builder_unc.build('u_gig', gig_prof, '2025-01-30', horizon_days=30)
    gig_proj_unc = [e for e in fut_gig_unc if e.get('category') == 'salary']
    assert len(gig_proj_unc) == 0, 'Uncertain gig income must not be projected as guaranteed recurring cash'
    print('  -> Income Uncertainty Safeguard OK')

    print('\nALL UNIT TESTS PASSED!')

if __name__ == '__main__':
    test_all()
