"""Test: what if variable expenses used the full-history median instead of 90-day?
Compute the effect on trajectory minimum for each request."""
import sys
from pathlib import Path
from datetime import date, timedelta
from statistics import median
from collections import defaultdict

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from code.data.loader import load_financial_events, load_profiles, load_requests
from code.finance.simulator import cents
from code.evaluation.sample_truth import SAMPLE_GROUND_TRUTH

def main():
    events = load_financial_events(ROOT / 'dataset' / 'financial_events.csv')
    profiles = load_profiles(ROOT / 'dataset' / 'financial_profiles.csv')
    requests = load_requests(ROOT / 'dataset' / 'sample_requests.csv')
    
    traces = {}
    from code.main import generate_predictions
    actual = generate_predictions(ROOT / 'dataset', 'sample_requests.csv', diagnostics=traces)
    
    for rid in sorted(SAMPLE_GROUND_TRUTH.keys()):
        truth = SAMPLE_GROUND_TRUTH[rid]
        req = requests[rid]
        profile = profiles[req.user_id]
        start = date.fromisoformat(req.request_date)
        
        trace = traces.get(rid, {})
        canonical = trace.get('canonical_events', [])
        
        # For each variable projected event, compute what its amount would be
        # with full-history median vs 90-day median
        user_events = [e for e in events if e.user_id == req.user_id]
        
        delta_sum = 0.0
        for cat in ['groceries', 'transport', 'dining']:
            history = [e for e in user_events 
                      if e.status == 'settled' and e.direction == 'debit'
                      and e.category == cat and e.settlement_date < req.request_date
                      and e.amount is not None]
            if not history:
                continue
            
            recent_90 = [e for e in history 
                        if date.fromisoformat(e.settlement_date) >= start - timedelta(days=90)]
            
            all_amounts = [e.amount for e in history]
            recent_amounts = [e.amount for e in recent_90]
            
            if not recent_amounts:
                continue
                
            med_90 = round(median(recent_amounts), 2)
            med_all = round(median(all_amounts), 2)
            
            # Count projected events of this category
            proj_count = len([e for e in canonical 
                            if e.get('is_projected') and e.get('category') == cat])
            
            diff_per = med_all - med_90
            total_diff = diff_per * proj_count
            delta_sum += total_diff
        
        safe_actual = float(actual.set_index('request_id').to_dict(orient='index')[rid]['amount_safe_to_pay'])
        safe_expected = truth['safe']
        
        # With full-history median, the safe amount would change by -delta_sum
        # (more debits = lower trajectory minimum = lower safe amount)
        projected_safe = safe_actual - delta_sum / 100 if delta_sum else safe_actual
        
        if abs(safe_actual - safe_expected) >= 0.005:
            improvement = abs(projected_safe - safe_expected) < abs(safe_actual - safe_expected)
            print(f"{rid}: actual={safe_actual:.2f}, expected={safe_expected:.2f}, projected_with_all_median={projected_safe:.2f} {'BETTER' if improvement else 'WORSE'}")

if __name__ == '__main__':
    main()
