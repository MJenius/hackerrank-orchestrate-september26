# Exact public regression

All six fields: 2/25.

| Field | Exact matches |
|---|---:|
| amount_safe_to_pay | 2/25 |
| affordability_status | 19/25 |
| recommended_payment_method | 20/25 |
| payment_plan | 19/25 |
| earliest_date_for_full_payment | 18/25 |
| spending_changes_needed | 21/25 |

## Mismatches

Each failing request has its starting balance, canonical cash flows, full balance trajectory, earliest date, accepted candidates with ranking tuples, and rejected base schedules in `sample_diagnostics.json`.

### request_02

| Field | Expected | Actual |
|---|---|---|
| amount_safe_to_pay | 17229139.2 | 17953975.41 |

### request_03

| Field | Expected | Actual |
|---|---|---|
| amount_safe_to_pay | 873000 | 980907.82 |

### request_04

| Field | Expected | Actual |
|---|---|---|
| amount_safe_to_pay | 8401800 | 10724951.13 |

### request_05

| Field | Expected | Actual |
|---|---|---|
| amount_safe_to_pay | 737 | 0.0 |

### request_06

| Field | Expected | Actual |
|---|---|---|
| amount_safe_to_pay | 603.3 | 521.63 |
| affordability_status | affordable_with_plan | not_affordable |
| recommended_payment_method | full_payment | not_recommended |
| payment_plan | 2026-01-03:620.40 | none |
| spending_changes_needed | stop:event_476 | none |

### request_07

| Field | Expected | Actual |
|---|---|---|
| amount_safe_to_pay | 87170.56 | 86703.56 |

### request_08

| Field | Expected | Actual |
|---|---|---|
| amount_safe_to_pay | 284.57 | 0.0 |
| affordability_status | affordable_later | not_affordable |
| recommended_payment_method | wait | not_recommended |
| payment_plan | 2025-04-15:996.60 | none |
| earliest_date_for_full_payment | 2025-04-15 |  |

### request_09

| Field | Expected | Actual |
|---|---|---|
| amount_safe_to_pay | 166.61 | 26.17 |
| affordability_status | affordable_now | not_affordable |
| recommended_payment_method | full_payment | not_recommended |
| payment_plan | 2026-07-04:166.61 | none |
| earliest_date_for_full_payment | 2026-07-04 |  |

### request_10

| Field | Expected | Actual |
|---|---|---|
| amount_safe_to_pay | 12700 | 0.0 |

### request_11

| Field | Expected | Actual |
|---|---|---|
| amount_safe_to_pay | 12510645 | 12373047.91 |
| affordability_status | affordable_with_plan | affordable_later |
| recommended_payment_method | full_payment | wait |
| payment_plan | 2025-05-03:13110000 | 2025-05-15:13110000 |
| earliest_date_for_full_payment | 2025-07-15 | 2025-05-15 |
| spending_changes_needed | reduce_to:event_989:665950 | none |

### request_12

| Field | Expected | Actual |
|---|---|---|
| amount_safe_to_pay | 65164 | 62814.46 |
| earliest_date_for_full_payment | 2026-04-05 |  |
| spending_changes_needed | none | reduce_to:event_1054:1072.50; stop:event_1016 |

### request_13

| Field | Expected | Actual |
|---|---|---|
| amount_safe_to_pay | 433.4 | 577.51 |
| affordability_status | affordable_later | not_affordable |
| recommended_payment_method | wait | not_recommended |
| payment_plan | 2024-05-15:941.60 | none |
| earliest_date_for_full_payment | 2024-05-15 |  |

### request_14

| Field | Expected | Actual |
|---|---|---|
| amount_safe_to_pay | 597.74 | 607.3 |

### request_15

| Field | Expected | Actual |
|---|---|---|
| amount_safe_to_pay | 83.05 | 12.25 |

### request_17

| Field | Expected | Actual |
|---|---|---|
| amount_safe_to_pay | 243849.58 | 241663.69 |
| earliest_date_for_full_payment | 2026-03-15 | 2026-04-15 |

### request_18

| Field | Expected | Actual |
|---|---|---|
| amount_safe_to_pay | 462 | 558.87 |

### request_19

| Field | Expected | Actual |
|---|---|---|
| amount_safe_to_pay | 28820 | 25896.68 |
| payment_plan | 2024-09-04:28820; 2024-09-15:10840 | 2024-09-04:25896.68; 2024-09-15:13763.32 |

### request_20

| Field | Expected | Actual |
|---|---|---|
| amount_safe_to_pay | 5400 | 8266.31 |

### request_21

| Field | Expected | Actual |
|---|---|---|
| amount_safe_to_pay | 1543.35 | 1574.4 |
| affordability_status | affordable_with_plan | affordable_now |
| earliest_date_for_full_payment | 2026-04-15 | 2026-04-03 |
| spending_changes_needed | stop:event_1815; reduce_to:event_1816:23.50 | none |

### request_22

| Field | Expected | Actual |
|---|---|---|
| amount_safe_to_pay | 475.46 | 464.05 |

### request_23

| Field | Expected | Actual |
|---|---|---|
| amount_safe_to_pay | 9152 | 8532.21 |

### request_24

| Field | Expected | Actual |
|---|---|---|
| amount_safe_to_pay | 13420 | 13555.64 |

### request_25

| Field | Expected | Actual |
|---|---|---|
| amount_safe_to_pay | 1425000 | 221174.45 |
