import sys, os
sys.path.insert(0, os.path.abspath('.'))
import pandas as pd
from code.data.loader import load_requests
from code.finance.optimizer import FinancialOptimizer
from code.finance.plan_ranker import CandidatePlan

def run_regression():
    df = pd.read_csv('dataset/sample_requests.csv')
    total = len(df)
    print(f'Inspecting all {total} ground truth samples:')
    
    for idx, r in df.iterrows():
        req_id = r['request_id']
        safe = r['amount_safe_to_pay']
        status = r['affordability_status']
        method = r['recommended_payment_method']
        plan = r['payment_plan']
        earliest = r['earliest_date_for_full_payment']
        changes = r['spending_changes_needed']
        
        print(f'{req_id}: safe={safe} | status={status} | method={method} | earliest={earliest} | changes={changes}')

if __name__ == '__main__':
    run_regression()
