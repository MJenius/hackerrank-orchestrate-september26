# Exact public regression

All six fields: 2/25.

| Field | Exact matches |
|---|---:|
| amount_safe_to_pay | 2/25 |
| affordability_status | 17/25 |
| recommended_payment_method | 18/25 |
| payment_plan | 17/25 |
| earliest_date_for_full_payment | 15/25 |
| spending_changes_needed | 19/25 |

## Mismatches

Each failing request has its starting balance, canonical cash flows, full balance trajectory, earliest date, accepted candidates with ranking tuples, and rejected base schedules in `sample_diagnostics.json`.

### request_02

| Field | Expected | Actual |
|---|---|---|
| amount_safe_to_pay | 17229139.2 | 17804602.11 |

### request_03

| Field | Expected | Actual |
|---|---|---|
| amount_safe_to_pay | 873000 | 939645.58 |

### request_04

| Field | Expected | Actual |
|---|---|---|
| amount_safe_to_pay | 8401800 | 10372964.85 |

### request_05

| Field | Expected | Actual |
|---|---|---|
| amount_safe_to_pay | 737 | 0.0 |

### request_06

| Field | Expected | Actual |
|---|---|---|
| amount_safe_to_pay | 603.3 | 511.96 |
| affordability_status | affordable_with_plan | not_affordable |
| recommended_payment_method | full_payment | not_recommended |
| payment_plan | 2026-01-03:620.40 | none |
| earliest_date_for_full_payment | 2026-01-15 | 2026-02-15 |
| spending_changes_needed | stop:event_476 | none |

### request_07

| Field | Expected | Actual |
|---|---|---|
| amount_safe_to_pay | 87170.56 | 85246.5 |
| spending_changes_needed | none | reduce_to:event_614:2835 |

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
| amount_safe_to_pay | 166.61 | 0.0 |
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
| amount_safe_to_pay | 12510645 | 12035360.73 |
| affordability_status | affordable_with_plan | affordable_later |
| recommended_payment_method | full_payment | wait |
| payment_plan | 2025-05-03:13110000 | 2025-05-15:13110000 |
| earliest_date_for_full_payment | 2025-07-15 | 2025-05-15 |
| spending_changes_needed | reduce_to:event_989:665950 | none |

### request_12

| Field | Expected | Actual |
|---|---|---|
| amount_safe_to_pay | 65164 | 57497.31 |
| affordability_status | affordable_with_plan | not_affordable |
| recommended_payment_method | installments | not_recommended |
| payment_plan | 2026-04-19:22590.19; 2026-05-20:22590.19; 2026-06-20:22590.19 | none |
| earliest_date_for_full_payment | 2026-04-05 |  |

### request_13

| Field | Expected | Actual |
|---|---|---|
| amount_safe_to_pay | 433.4 | 458.76 |
| affordability_status | affordable_later | not_affordable |
| recommended_payment_method | wait | not_recommended |
| payment_plan | 2024-05-15:941.60 | none |
| earliest_date_for_full_payment | 2024-05-15 |  |

### request_14

| Field | Expected | Actual |
|---|---|---|
| amount_safe_to_pay | 597.74 | 580.45 |

### request_15

| Field | Expected | Actual |
|---|---|---|
| amount_safe_to_pay | 83.05 | 0.0 |

### request_17

| Field | Expected | Actual |
|---|---|---|
| amount_safe_to_pay | 243849.58 | 237967.71 |
| earliest_date_for_full_payment | 2026-03-15 | 2026-04-15 |
| spending_changes_needed | none | reduce_to:event_1542:2935 |

### request_18

| Field | Expected | Actual |
|---|---|---|
| amount_safe_to_pay | 462 | 543.67 |

### request_19

| Field | Expected | Actual |
|---|---|---|
| amount_safe_to_pay | 28820 | 24657.99 |
| payment_plan | 2024-09-04:28820; 2024-09-15:10840 | 2024-09-04:24657.99; 2024-09-15:15002.01 |

### request_20

| Field | Expected | Actual |
|---|---|---|
| amount_safe_to_pay | 5400 | 8014.03 |

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
| amount_safe_to_pay | 475.46 | 459.2 |
| earliest_date_for_full_payment | 2025-01-15 | 2025-02-15 |
| spending_changes_needed | none | stop:event_1892 |

### request_23

| Field | Expected | Actual |
|---|---|---|
| amount_safe_to_pay | 9152 | 8327.91 |
| affordability_status | affordable_later | not_affordable |
| recommended_payment_method | wait | not_recommended |
| payment_plan | 2025-07-15:38016 | none |
| earliest_date_for_full_payment | 2025-07-15 |  |

### request_24

| Field | Expected | Actual |
|---|---|---|
| amount_safe_to_pay | 13420 | 12992.39 |

### request_25

| Field | Expected | Actual |
|---|---|---|
| amount_safe_to_pay | 1425000 | 61612.15 |
