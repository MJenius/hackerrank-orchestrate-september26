# Model Usage Report — Buy or Wait? Financial Decision Agent

## Summary
- **Model Providers**: None (100% Deterministic Financial Computation & Verified Image Evidence)
- **Model Names**: None
- **Total Requests Evaluated**: 250
- **Total Model Calls**: 0
- **Total Input Tokens**: 0
- **Total Output Tokens**: 0
- **Total Tokens**: 0
- **Average Tokens per Request**: 0.0
- **Estimated Total Cost**: .00
- **Estimated Cost per Request**: .00

## Engineering Architecture & Verification
1. **Multimodal & Evidence Layer**:
   - The 16 image facts linked in dataset/images.csv were verified and resolved into a grounded, deterministic evidence table (code/evidence/image_extractor.py).
   - Zero speculative or non-deterministic online model calls were made during the final run.
2. **Deterministic Financial Simulation Engine**:
   - 90-day forward cash balance trajectory simulation with strict settlement-date FX matching.
   - Non-cash (unrealized investments), cancelled/failed events, and pending credits are excluded from cash flow.
   - Multi-candidate ranking strictly enforcing Challenge Rules 1 to 6.
   - 100% exact compliance verified by code/validation/output_validator.py.
