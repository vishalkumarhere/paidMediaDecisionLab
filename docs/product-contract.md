# Product contract — version 1.0.0

## Decision and audience

Audience: a performance marketing analyst reviewing one product's campaign groups each week. Product: a fictional US Ninja Luxe Café Premier ES601 campaign. Business question: should the analyst investigate, hold, or propose a small controlled budget test, and what evidence would change that judgment?

Milestones 1–2 establish trusted inputs and calculations. They do not answer that question automatically yet. Portfolio success at this stage means another analyst can reproduce the financial example, inspect the SQL, and regenerate the data without private company access.

## Data and claims

Public fact: product identity and its cited product-page URL in `config/sources.json`. Synthetic observation: invented campaign delivery, sessions, customers, orders, refunds and inventory. User assumption: simulated unit costs, spend plans, promotions and policy. Derived result: calculations from those inputs. Evaluation-only: incident labels retained outside analytical inputs.

The assumed $599.99 list price and $270 unit cost do not describe actual historical prices or SharkNinja margins. No customer, employer or advertising account data is used. Stable synthetic IDs simplify linkage; they are not evidence that real platforms expose equivalent identifiers.

## Campaign taxonomy

- C01: Google branded search; capture existing expressed brand interest.
- C02: Google nonbranded search; capture category interest.
- C03: Google Shopping; product comparison / shopping intent.
- C04: Meta prospecting; reach potential new buyers.
- C05: Meta retargeting; re-engage previous visitors.
- C06: affiliate partner; partner-referred demand.

These objectives describe campaign roles, not proven incrementality or customer newness. Campaign IDs do not contain incident labels. Each campaign has two invented demo creatives, tagged `guided brewing` and `at-home routine`. Richer offer/customer-question tagging belongs to later evidence views.

Organic or ineligible touch histories remain `UNATTRIBUTED`. They are included in commerce totals and are never silently discarded to improve paid-media metrics.

## Prototype policy for milestone 3

Policy is specified here but **not implemented as a decision engine**. Numeric values are prototype choices, not platform defaults or statistical guarantees.

1. Investigate before growth if integrity checks fail, costs/media are missing, units available are zero, or contribution after media is negative. A reconciliation alert requires at least 10 commerce orders and an observed tracking gap greater than 20%; platform claim overlap alone is not a tracking-loss diagnosis.
2. Hold when conversion cohorts are younger than 14 days, return cohorts are younger than 36 days, there are fewer than 30 fulfilled mature orders, or cost/return sensitivity reverses the proposed decision.
3. A candidate budget test must pass those gates and remain nonnegative after media under all declared sensitivity assumptions. The initial increase cap is 10%; baseline is the prior seven complete reporting days. Require analyst review, a stock check and a stated stop condition before execution.

The return horizon covers the simulator's maximum 35-day return delay plus reporting delay. These age thresholds cannot establish real-world maturity. The 30-order threshold is not a power calculation. Reconciliation tolerances, stop rules and sensitivity inputs must be evaluated in later milestones before any automated recommendation is presented.

`config/default.json` records the numeric policy inputs. Rule evaluation order will be investigate → hold → test candidate, with reasons and evidence IDs. No confidence percentage or causal profit claim is permitted.

## Four view sketches

These are reading-order sketches, not implemented UI.

**1. Decision overview.** Top: independent/synthetic notice, information cutoff, reporting dates and filters. Main area: one priority action with reason, next check and evidence link. Below: campaign comparisons for spend, business net ROAS, contribution and quality/maturity status. Empty filters show an explanation, not zero performance.

**2. Campaign evidence.** Top: selected campaign and attribution/date definitions. Main: contribution waterfall and observed funnel. Below: commerce versus tracked events versus separate platform claims, dated stock/promotion annotations and source record IDs. Missing costs remain visible and suppress complete contribution totals.

**3. Forecast and budget scenarios.** Top: observed versus forecast versus hypothetical labels. Main: seven-day baseline forecast with uncertainty and evaluation. Controls: bounded spend change, marginal cost per extra order, contribution assumptions and available inventory. Invalid inputs show an error. This view will not call a sensitivity calculation a causal estimate.

**4. Methodology and exports.** Top: source classes, assumptions, cutoff and metric version. Main: formulas, representative SQL, integrity checks and limitations. Below: later workbook/memo downloads reflecting the exact selected state. Raw evaluation labels are not included in a future public download by default.

All views require readable laptop layouts and phone stacking, clear NULL/zero distinction, and no official-branding implication.

## Exit gates

Milestone 1: the fixture can be calculated from its written inputs without reading implementation code; source classes, attribution, date basis, missing-value policy and four views are specified.

Milestone 2: one documented command regenerates the same data hashes under the pinned runtime, validates source keys and financial conservation, respects the reporting cutoff, and separates hidden labels. A machine-readable validation report accompanies the sample. No app/deployment is part of either gate.
