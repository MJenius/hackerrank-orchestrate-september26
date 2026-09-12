"""Comprehensive ablation: for each mismatched sample, try removing one projected source
at a time and check which removals bring us closer to the expected safe amount."""
import sys
from pathlib import Path
from datetime import date, timedelta
from collections import defaultdict

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from code.main import generate_predictions
from code.evaluation.sample_truth import SAMPLE_GROUND_TRUTH
from code.data.loader import load_profiles, load_requests, load_exchange_rates
from code.finance.simulator import BalanceSimulator, cents
from code.finance.currency import CurrencyConverter

def compute_safe(profile, request_date, events, requested_amount, converter):
    sim = BalanceSimulator(converter)
    _, _, balances = sim.simulate_trajectory(profile, request_date, events, {})
    minimum = cents(profile.minimum_balance_to_keep)
    requested = cents(requested_amount)
    available = min(round(b * 100) - minimum for b in balances.values())
    return max(0, min(requested, available)) / 100

def main():
    traces = {}
    actual = generate_predictions(ROOT / 'dataset', 'sample_requests.csv', diagnostics=traces)
    profiles = load_profiles(ROOT / 'dataset' / 'financial_profiles.csv')
    requests = load_requests(ROOT / 'dataset' / 'sample_requests.csv')
    rates = load_exchange_rates(ROOT / 'dataset' / 'exchange_rates.csv')
    converter = CurrencyConverter(rates)

    for rid in sorted(SAMPLE_GROUND_TRUTH.keys()):
        truth = SAMPLE_GROUND_TRUTH[rid]
        safe_expected = truth['safe']
        safe_actual = float(actual.set_index('request_id').to_dict(orient='index')[rid]['amount_safe_to_pay'])
        if abs(safe_actual - safe_expected) < 0.005:
            continue

        req = requests[rid]
        profile = profiles[req.user_id]
        trace = traces.get(rid, {})
        events = trace.get('canonical_events', [])
        delta = safe_actual - safe_expected

        # Group projected events by source
        source_groups = defaultdict(list)
        for e in events:
            if e.get('is_projected', False) and e['direction'] == 'debit':
                source_groups[e.get('source_event_id', e['event_id'])].append(e)

        results = []

        if delta < -0.005:  # Too low -> remove debits
            for source_id, group in source_groups.items():
                modified = [e for e in events if not (e.get('is_projected', False) and e['direction'] == 'debit' and e.get('source_event_id', e['event_id']) == source_id)]
                try:
                    new_safe = compute_safe(profile, req.request_date, modified, req.requested_amount, converter)
                    improvement = abs(new_safe - safe_expected) - abs(safe_actual - safe_expected)
                    cat = group[0].get('category', '?')
                    desc = group[0].get('description', '')[:30]
                    results.append((improvement, f"REMOVE {source_id} ({cat} '{desc}', {len(group)} evts, each={group[0]['amount']}) -> safe={new_safe:.2f}, improvement={improvement:.2f}"))
                except:
                    pass
        elif delta > 0.005:  # Too high -> we need more debits
            # Try increasing each variable-category projected amount
            for source_id, group in source_groups.items():
                cat = group[0].get('category', '?')
                if cat in ('groceries', 'transport', 'dining'):
                    # Try doubling the amount
                    modified = []
                    for e in events:
                        if e.get('is_projected', False) and e['direction'] == 'debit' and e.get('source_event_id', e['event_id']) == source_id:
                            e_copy = dict(e)
                            e_copy['amount'] = e['amount'] * 1.5
                            modified.append(e_copy)
                        else:
                            modified.append(e)
                    try:
                        new_safe = compute_safe(profile, req.request_date, modified, req.requested_amount, converter)
                        improvement = abs(new_safe - safe_expected) - abs(safe_actual - safe_expected)
                        desc = group[0].get('description', '')[:30]
                        results.append((improvement, f"INCREASE_50% {source_id} ({cat} '{desc}', {len(group)} evts) -> safe={new_safe:.2f}, improvement={improvement:.2f}"))
                    except:
                        pass

        # Sort by improvement (most negative = best improvement)
        results.sort()
        print(f"\n{rid}: delta={delta:+.2f}")
        for imp, desc in results[:5]:
            print(f"  {desc}")

if __name__ == '__main__':
    main()
