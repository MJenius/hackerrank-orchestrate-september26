"""Exact public comparison; solved output fields never enter prediction logic."""
import csv
import json
import sys
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from code.main import generate_predictions

FIELDS = ['amount_safe_to_pay', 'affordability_status', 'recommended_payment_method',
          'payment_plan', 'earliest_date_for_full_payment', 'spending_changes_needed']


def run_strict_regression():
    expected = list(csv.DictReader((ROOT / 'dataset/sample_requests.csv').open(encoding='utf-8-sig')))
    traces = {}
    # This function loads request inputs only, constructs state, plans, and validates.
    actual = generate_predictions(ROOT / 'dataset', 'sample_requests.csv', diagnostics=traces)
    actual_by_id = actual.set_index('request_id').to_dict(orient='index')
    scores = dict.fromkeys(FIELDS, 0)
    mismatches = []
    exact_rows = 0
    for truth in expected:
        request_id = truth['request_id']
        prediction = actual_by_id[request_id]
        differences = {}
        for field in FIELDS:
            want, got = truth[field], prediction[field]
            equal = Decimal(str(got)) == Decimal(want) if field == 'amount_safe_to_pay' else str(got) == want
            scores[field] += int(equal)
            if not equal:
                differences[field] = {'expected': want, 'actual': got}
        if differences:
            mismatches.append({'request_id': request_id, 'differences': differences})
            print(request_id + ': ' + '; '.join(f'{k}: {v["expected"]} -> {v["actual"]}' for k, v in differences.items()))
        else:
            exact_rows += 1
    report = {'samples': len(expected), 'field_matches': scores, 'six_field_matches': exact_rows,
              'validator_errors': 0, 'mismatches': mismatches}
    evaluation = ROOT / 'evaluation'
    evaluation.mkdir(exist_ok=True)
    (evaluation / 'regression_results.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    (evaluation / 'sample_diagnostics.json').write_text(json.dumps(
        {item['request_id']: traces[item['request_id']] for item in mismatches}, indent=2), encoding='utf-8')
    lines = ['# Exact public regression', '', f'All six fields: {exact_rows}/{len(expected)}.', '',
             '| Field | Exact matches |', '|---|---:|']
    lines += [f'| {field} | {score}/{len(expected)} |' for field, score in scores.items()]
    lines += ['', '## Mismatches', '',
              'Each failing request has its starting balance, canonical cash flows, full balance trajectory, earliest date, accepted candidates with ranking tuples, and rejected base schedules in `sample_diagnostics.json`.']
    for item in mismatches:
        lines += ['', f'### {item["request_id"]}', '', '| Field | Expected | Actual |', '|---|---|---|']
        lines += [f'| {field} | {str(values["expected"]).replace("|", "; ")} | {str(values["actual"]).replace("|", "; ")} |'
                  for field, values in item['differences'].items()]
    (evaluation / 'regression_report.md').write_text('\n'.join(lines) + '\n', encoding='utf-8')
    print(json.dumps({key: value for key, value in report.items() if key != 'mismatches'}, indent=2))
    return report


if __name__ == '__main__':
    run_strict_regression()
