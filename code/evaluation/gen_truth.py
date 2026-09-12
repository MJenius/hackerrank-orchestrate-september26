import pandas as pd
df = pd.read_csv('dataset/sample_requests.csv')
with open('code/evaluation/sample_truth.py', 'w', encoding='utf-8') as f:
    f.write('SAMPLE_GROUND_TRUTH = {\n')
    for _, r in df.iterrows():
        f.write(f'    \"{r.request_id}\": {{\n')
        f.write(f'        \"safe\": {r.amount_safe_to_pay},\n')
        f.write(f'        \"status\": \"{r.affordability_status}\",\n')
        f.write(f'        \"method\": \"{r.recommended_payment_method}\",\n')
        f.write(f'        \"plan\": \"{r.payment_plan}\",\n')
        earliest_val = '' if pd.isna(r.earliest_date_for_full_payment) else str(r.earliest_date_for_full_payment)
        f.write(f'        \"earliest\": \"{earliest_val}\",\n')
        f.write(f'        \"changes\": \"{r.spending_changes_needed}\",\n')
        exp_clean = str(r.decision_explanation).replace('\"', '\\\"')
        f.write(f'        \"explanation\": \"{exp_clean}\"\n')
        f.write('    },\n')
    f.write('}\n')
print('Wrote sample_truth.py successfully.')
