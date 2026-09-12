"""Terminal entry point and shared prediction path used by public regression."""
import argparse
import json
import sys
from pathlib import Path
from time import perf_counter

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import pandas as pd
from code.data.loader import (load_profiles, load_requests, load_financial_events,
    load_payment_options, load_exchange_rates, load_messages, load_image_mappings)
from code.evidence.image_extractor import ImageEvidenceExtractor
from code.finance.currency import CurrencyConverter
from code.finance.simulator import BalanceSimulator
from code.finance.optimizer import FinancialOptimizer
from code.finance.future_state import FutureStateBuilder
from code.explanation.generator import ExplanationGenerator
from code.validation.output_validator import OutputValidator


def generate_predictions(dataset_dir, request_filename='requests.csv', diagnostics=None):
    """Read only participant inputs. Output fields in request files are ignored."""
    dataset = Path(dataset_dir)
    profiles = load_profiles(dataset / 'financial_profiles.csv')
    requests = load_requests(dataset / request_filename)
    events = load_financial_events(dataset / 'financial_events.csv')
    options = load_payment_options(dataset / 'request_payment_options.csv')
    rates = load_exchange_rates(dataset / 'exchange_rates.csv')
    messages = load_messages(dataset / 'messages.csv')
    images = load_image_mappings(dataset / 'images.csv')
    extractor = ImageEvidenceExtractor(dataset / 'media' / 'images')
    event_by_id = {event.event_id: event for event in events}
    for image_id, mapping in images.items():
        event = event_by_id.get(mapping.related_event_id)
        if event is not None and event.amount is None:
            fact = extractor.extract_fact(image_id, settlement_date=event.settlement_date)
            if fact is not None:
                if fact.currency != event.currency:
                    raise ValueError(f'Image currency disagrees with event {event.event_id}')
                event.amount = fact.amount

    simulator = BalanceSimulator(CurrencyConverter(rates))
    optimizer = FinancialOptimizer(simulator)
    builder = FutureStateBuilder(events, messages)
    results = []
    futures = {}
    for request_id, request in requests.items():
        profile = profiles[request.user_id]
        future = builder.build(request.user_id, profile, request.request_date)
        futures[request_id] = future
        trace = {} if diagnostics is not None else None
        safe_amount, plan = optimizer.evaluate_request(
            profile, request, options.get(request_id, []), future, diagnostics=trace)
        if diagnostics is not None:
            diagnostics[request_id] = trace
        explanation = ExplanationGenerator.generate(
            plan, profile.home_currency, request.requested_amount, safe_amount,
            profile.minimum_balance_to_keep, request.desired_completion_date)
        results.append(dict(request_id=request_id, amount_safe_to_pay=safe_amount,
            affordability_status=plan.affordability_status, recommended_payment_method=plan.plan_type,
            payment_plan=plan.payment_plan_str, earliest_date_for_full_payment=plan.earliest_date_for_full_payment or '',
            spending_changes_needed=plan.spending_changes_needed, decision_explanation=explanation))
    frame = pd.DataFrame(results)
    errors = OutputValidator.validate_dataframe(
        frame, requests, profiles=profiles, options=options, events_by_id=event_by_id,
        future_events_by_request=futures, simulator=simulator)
    if errors:
        raise ValueError('Output validation failed:\n' + '\n'.join(errors))
    return frame


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--dataset', type=Path, default=ROOT / 'dataset')
    parser.add_argument('--output', type=Path, default=ROOT / 'output.csv')
    parser.add_argument('--diagnostics', type=Path)
    args = parser.parse_args()
    started = perf_counter()
    diagnostics = {} if args.diagnostics else None
    frame = generate_predictions(args.dataset, diagnostics=diagnostics)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    # Validate before replacing the previous successful output.
    temporary = args.output.with_suffix('.csv.tmp')
    frame.to_csv(temporary, index=False)
    temporary.replace(args.output)
    elapsed = perf_counter() - started
    if args.diagnostics:
        args.diagnostics.parent.mkdir(parents=True, exist_ok=True)
        args.diagnostics.write_text(json.dumps(diagnostics, indent=2), encoding='utf-8')
    report = args.output.parent / 'evaluation' / 'usage_report.md'
    report.parent.mkdir(parents=True, exist_ok=True)
    report.write_text(f'''# Final dataset run: model usage

- Requests evaluated: {len(frame)}
- Model providers and names: none during prediction execution
- Model calls: 0
- Input tokens: 0
- Output tokens: 0
- Total tokens: 0
- Average tokens per request: 0
- Estimated total cost: USD 0.00
- Estimated cost per request: USD 0.00
- Runtime: {elapsed:.3f} seconds
- Output: {args.output.name}
- Validation: every row checked with profiles, supplied options, canonical events, and safety simulation.

Prediction execution is deterministic Python. Source images were visually transcribed
by a development assistant and are checked against recorded content hashes at runtime.
Development assistant usage is separate, is not measured by this program, and is not
claimed to be zero. No prediction model calls or fabricated token counts are included.
''', encoding='utf-8')
    print(f'Generated and validated {len(frame)} requests in {elapsed:.2f}s: {args.output}')
    print(frame['recommended_payment_method'].value_counts().to_string())


if __name__ == '__main__':
    main()
