# Milestone 4 — forecast, scenario methodology, domain notes and hurdles

## Purpose and claim boundary

Milestone 4 adds a seven-day baseline forecast and a bounded budget scenario to the paid-media decision lab. The baseline answers, “What would the next seven reported days look like if recent weekday patterns broadly continued?” The scenario answers, “What would the arithmetic look like under the analyst’s stated marginal-cost, contribution, and inventory assumptions?”

Neither calculation estimates causal lift, an optimal budget, platform auction response, or the probability of a business outcome. The scenario cannot authorize spend. If the Milestone 3 screen returns **Investigate** or **Hold**, the app labels the scenario as sensitivity exploration only.

All forecasting settings live in `config/forecast-policy.json`. Exports contain the forecast-policy version and hash, dataset hash, selected campaigns, forecast origin, scenario assumptions, and claim boundary.

## Baseline model

The model is deliberately simple and auditable. For each forecast date and metric, it uses the mean of the previous four matching weekdays inside a 28-day lookback. If fewer than two matching weekdays exist, it falls back to the complete available lookback. The four targets are:

- fulfilled paid-attributed orders;
- media spend;
- business-allocated net product revenue reported at the cutoff;
- contribution after media reported at the cutoff.

Campaigns are aggregated after the user’s paid-campaign selection. Calendar dates must be continuous. Missing dates and unknown target values cause the forecast to stop; the model does not convert missing observations to zero or statistically impute them.

This seasonal-naive model is a benchmark. It captures weekly rhythm without claiming that a larger model is justified by 112 synthetic days. It does not use promotions, inventory, platform claims, incident labels, future raw records, or evaluation-only labels as features.

## Time-ordered backtesting

Each rolling origin trains only on dates at or before that origin and forecasts the next seven days. An origin is eligible after at least 28 complete history days and only when all seven actual evaluation days already exist.

Origins are split chronologically: the first 70% calibrate empirical error ranges and the last 30% evaluate the frozen baseline and intervals. This prevents later evaluation errors from setting the interval they are used to judge.

The app reports:

- **WAPE:** sum of absolute seven-day errors divided by sum of absolute actual seven-day totals. It is undefined when all evaluation actuals are zero.
- **Seven-day MAE:** mean absolute error of seven-day totals, in the target’s original unit.
- **Bias:** mean `actual − forecast` for seven-day totals. Positive bias means the baseline tended to underforecast.
- **Empirical coverage:** share of later evaluation totals inside the nominal 80% error interval.

The nominal 80% interval uses the 10th and 90th percentiles of earlier calibration errors. It is an empirical range, not a parametric confidence interval. The interface warns when later coverage falls more than ten percentage points below the nominal target.

## Reported-to-cutoff economics and right censoring

Spend and orders are observed period measures, but net revenue and contribution include only refunds available by the dataset cutoff. Recent purchase cohorts have had less time to return, so their reported economics are right-censored. The forecast continues that reported-to-cutoff series; it does not estimate final cohort revenue or final contribution.

The interface displays this limitation beside the forecast. The scenario’s default pre-media contribution per order uses the return-mature history rather than the recent forecast series. A future-return model remains separate work because it would require explicit cohort estimation and a rule preventing double deduction of already observed returns.

## Budget scenario arithmetic

The scenario begins with the seven-day point forecasts for spend, orders, and contribution. The analyst can change spend from −10% to +10%, matching the bounded policy. Three editable assumptions drive the response:

1. **Marginal cost per extra order:** incremental spend required for one added order. The default is forecast spend divided by forecast orders; this is an observed-average starting point, not a marginal estimate.
2. **Pre-media contribution per incremental order:** contribution available before paying for media. The default comes from selected return-mature observed economics.
3. **Incremental-order inventory capacity:** maximum additional orders supportable in the scenario. The default conservatively subtracts forecast orders from the latest available units under an explicit one-unit-per-order approximation.

For a spend increase:

`unconstrained incremental orders = incremental spend / assumed marginal cost per order`

`scenario incremental orders = minimum(unconstrained orders, inventory capacity)`

`incremental contribution = incremental orders × assumed pre-media contribution per order − incremental spend`

For a decrease, the same marginal assumption estimates orders lost, capped so scenario orders cannot fall below zero. Saved spend offsets lost pre-media contribution. The baseline contribution interval is shifted by the fixed scenario arithmetic; the scenario assumptions add no probability distribution, so the resulting range is not a complete scenario-risk interval.

The break-even assumed marginal cost per order equals assumed pre-media contribution per incremental order. If marginal acquisition cost is higher, added spend reduces contribution under the user’s assumptions.

## Performance-marketing domain guide

**Baseline forecast versus response curve.** A time-series baseline projects what the measured account might report under continuation. A response curve estimates how outcomes change when spend changes. The first cannot substitute for the second.

**Observed average CPA versus marginal CPA.** Historical spend divided by orders describes average attributed cost. The next order may cost more because high-intent audiences saturate, auction prices change, or reach expands. The scenario therefore exposes marginal cost as an assumption.

**Correlation versus causation.** Spend and orders moving together does not identify incremental response. Seasonality, offers, inventory, brand demand, and platform allocation can affect both. No coefficient in this milestone is labeled causal.

**Forecast error versus business uncertainty.** Backtest error measures how this baseline missed historical synthetic observations. It does not include all future shocks, policy changes, creative fatigue, competitor actions, measurement changes, or the uncertainty in marginal assumptions.

**WAPE limitations.** WAPE is scale-weighted and easy to explain, but large days dominate it. It can look favorable on high-volume series while smaller campaigns remain poorly predicted. The app also reports MAE, bias, and interval coverage.

**Interval calibration.** An 80% empirical interval should contain roughly 80% of comparable future totals if the error process remains stable. Under-coverage signals that the range is too narrow or the process changed; it is not repaired by relabeling it “high confidence.”

**Inventory as a constraint.** More media cannot create fulfillable demand beyond available stock. The current source provides snapshot units, not reservations, inbound purchase orders, channel allocation, or multi-unit demand, so inventory remains an editable capacity assumption.

**Negative spend scenarios.** Reducing spend saves media cost but may also lose attributed orders and their pre-media contribution. The arithmetic makes both effects visible rather than assuming every saved media dollar becomes profit.

## Hurdles and resolutions

### Preventing temporal leakage

The raw simulator intentionally contains future events, and the dashboard dataset contains an entire historical reporting range. A conventional random train/test split would let future seasonal information influence earlier predictions. Rolling origins, strict origin filters, and a dedicated test that changes post-origin values without changing the forecast prevent this leakage.

### Separating interval calibration from evaluation

Using all historical residuals to build an interval and then reporting coverage on the same residuals would be circular. Earlier origins calibrate the range; later origins evaluate it. The smaller evaluation set is shown explicitly and limits how strongly coverage can be interpreted.

### Sparse sample versus model complexity

The project has 112 reporting days and six synthetic campaigns. A feature-rich machine-learning model could fit planted patterns while producing weak out-of-sample evidence. The weekday baseline establishes a transparent benchmark that a later model must beat in time-ordered evaluation.

### Right-censored returns

Recent net revenue and contribution are incomplete because future refunds are unknown at the cutoff. Rather than silently treating them as final, the app labels the forecast as reported-to-cutoff and uses mature economics for the editable scenario-margin default. A proper final-outcome forecast remains future work.

### Scenario semantics

Applying historical ROAS to additional spend would imply constant marginal efficiency and create a disguised causal claim. The scenario instead asks the analyst for marginal cost and pre-media contribution assumptions, shows the break-even relationship, and labels every output hypothetical.

### Inventory unit mismatch

Inventory is measured in units while the forecast target is orders. Orders may contain more than one unit, and future reservations are unknown. The default one-unit-per-order subtraction is deliberately visible and editable; it is not embedded as an invisible truth.

### Interactive computation cost

Rolling-origin backtests evaluate four targets across many origins. Recomputing them for every slider movement would make the UI slow. Streamlit caches the immutable forecast bundle by selected history, end date, and policy; scenario arithmetic remains immediate and uncached.

### Browser reset state

The original reset implementation removed widget keys and forced a rerun. Streamlit's automated test harness accepted it, but the live browser could submit the previous date selection again during the rerun. A widget callback now applies defaults before controls are recreated. Browser validation confirms the visible reporting window and calculations reset together.

### Native Arrow restriction

The existing Windows Application Control restriction still prevents loading PyArrow’s native library. The forecast uses pandas and ordinary Python objects, Plotly receives JSON-compatible lists, and tables use escaped HTML. No security setting or package binary was modified.

## Validation boundary and next work

Tests verify exact weekly-pattern forecasts, strict post-origin isolation, refusal to impute unknown values, policy bounds, inventory caps, positive and negative spend arithmetic, Streamlit interaction, and Milestone 3 gate awareness. Browser validation checks chart labels, scenario controls, warnings, and downloads.

Milestone 4 does not estimate final return cohorts, causal response, creative fatigue, auction dynamics, optimal allocation, experiment power, or cross-channel incrementality. The next milestone should add a future-return provision or a causal experiment-design layer only after specifying data requirements, evaluation rules, and failure states. Workbook/memo exports and outreach packaging can then reflect the exact selected state.
