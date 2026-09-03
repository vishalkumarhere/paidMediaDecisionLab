# Milestone 3 — decision-screen methodology, domain notes and build hurdles

## Purpose and claim boundary

Milestone 3 turns the trusted measurement layer into a repeatable weekly screen for a performance marketing analyst. For each paid campaign, it returns one of three states: **Investigate**, **Hold**, or **Controlled test candidate**. The state is a policy result, not a causal recommendation, prediction, confidence score, or authorization to change a live budget.

The screen answers a narrower question than “will more spend create more profit?” It asks whether the currently observed evidence is complete, mature, economically resilient, operationally feasible, and sufficiently recent to justify human review of a small test. Analyst review remains mandatory for every state.

All thresholds live in `config/decision-policy.json`. Every record includes the policy version, policy hash, screen version, evidence ID, next check, and stop condition. The screen never reads `evaluation_only/ground_truth.json`.

## Evaluation order

Rules run in this order because a later-stage economic judgment is not credible when earlier evidence is broken:

1. **Investigate:** unresolved data checks, missing cost or media, negative selected-period contribution, unavailable inventory, or a material site-wide tracking gap.
2. **Hold:** insufficient mature orders, an incomplete seven-day media baseline, unavailable mature economics, or a sensitivity reversal.
3. **Controlled test candidate:** every declared gate passes. This still requires analyst review, a fresh stock check, and a written stop condition.

The first failing rule becomes the primary reason; every failing rule remains in `reason_codes`. This prevents a convenient downstream metric from hiding an upstream measurement problem. The overview shows the first deterministic record as an example, not a performance ranking.

## Grain, dates and maturity

Campaign reporting combines purchase-date order economics with delivery-date media spend. It is period reporting rather than a matched causal cohort. Ratios are therefore calculated from summed numerators and denominators, never from an average of daily ratios.

The information cutoff is fixed by the selected dataset. UI date filters change the reporting scope but never reveal later events. Conversion maturity uses the attributed paid touch timestamp and a 14-day elapsed-time threshold. Return maturity uses the purchase timestamp and a 36-day threshold, which covers the simulator's maximum 35-day return delay plus one reporting day.

Recent realized results remain visible in the dashboard, but only reporting dates old enough for the return horizon enter the screen's mature contribution and stress calculation. This avoids forcing the entire account to “Hold” simply because new sales occur every day, while keeping recent, right-censored return outcomes out of the qualifying economics.

The requirement of 30 mature fulfilled orders is a prototype operating threshold. It is not a statistical power calculation and does not imply a specific confidence level.

## Economics and sensitivity

Observed mature contribution after media is:

`net product revenue − net COGS − fulfillment − net payment fees − return handling − media expense`

It excludes fixed overhead and is not net profit. Affiliate commission is already included once in media expense.

The adverse sensitivity subtracts two explicit assumptions from observed mature contribution:

`stress penalty = 10% × mature net COGS + 5% × mature booked revenue`

`stress contribution = observed mature contribution after media − stress penalty`

The 10% cost shock and five-percentage-point additional-refund provision are user assumptions, not estimates from SharkNinja data. The additional-refund term is applied to booked revenue and represents incremental refund exposure beyond refunds already observed. A negative stress result forces **Hold**. This is a robustness screen, not a probability model.

## Tracking, inventory and baseline rules

Tracking reconciliation is site-wide because the processed source can identify commerce orders without visible purchase events but cannot reliably assign those missing events to a campaign. A tracking investigation begins only when at least 10 commerce orders exist in scope and more than 20% lack a visible purchase event. Platform claim overlap is reported separately and never treated as tracking loss.

Inventory is SKU-level rather than campaign-level. The screen uses the latest inventory observation available by the selected end date. Zero units triggers **Investigate** for every campaign because additional paid demand cannot be responsibly screened while the product is unavailable. This does not model inventory movements, channel reservations, replenishment lead time, or marketplace stock.

The budget reference is the prior seven complete campaign reporting days. Missing media makes the baseline incomplete. A passing campaign may show a ceiling equal to baseline spend plus 10%. That ceiling defines the largest reviewed test allowed by policy; it is not a forecast or optimal budget. The test must pause if cumulative contribution becomes negative, inventory becomes unavailable, or the tracking gap breaches policy.

## Performance-marketing domain guide

**Attribution versus incrementality.** Attribution assigns observed sales to touches under a rule. Incrementality asks what would have happened without the advertising. Last-click allocation, platform claims, positive ROAS, and positive contribution do not establish incremental lift.

**Business ROAS versus platform ROAS.** Business net ROAS uses one business allocation and revenue after known refunds. Platform snapshots use source-specific click windows and pre-refund revenue. Multiple platforms may claim the same order, so claims cannot be added as unique sales.

**ROAS versus contribution.** ROAS ignores product cost, fulfillment, payment fees, handling, and the mix of refunds. Two campaigns can have identical ROAS and different contribution. Contribution after media is closer to the operating decision but still excludes overhead and does not prove marginal response.

**Average versus marginal efficiency.** The app observes average historical economics. A budget test concerns the next dollar, whose response may be worse than the average because high-intent audiences saturate. The 10% cap controls exposure. Milestone 4 subsequently added a baseline forecast and assumption-driven scenario, but causal response and experiment design remain unimplemented.

**Cohort maturity and right censoring.** Recent purchases have had less time to return. Comparing recent realized return rates with older cohorts can make performance look artificially strong. The maturity boundary prevents that comparison from qualifying a test.

**Data latency.** Events can occur before they become available in a report. The inclusive `as_of` cutoff checks both event time and availability time, preventing later refunds or snapshots from leaking into an earlier decision.

**Tracking gaps.** A missing tracked purchase can result from consent, browser restrictions, implementation failure, reporting delay, or identity loss. The app labels the observation and asks for investigation; it does not infer a cause.

**Promotions and stock.** Discounts can raise conversion while weakening margin, and stock constraints can make otherwise efficient media wasteful. Promotion annotations remain contextual evidence; current SKU availability is an explicit growth gate.

**Pacing.** Spend divided by dated planned spend indicates delivery against plan. A value above 100% is not automatically bad performance, and a value below 100% is not automatically an opportunity to spend more.

## Hurdles and resolutions

### Mixed date grains

Orders are measured on purchase date while media is measured on delivery date. Allocating daily spend to individual orders would invent precision. The app retains campaign/day spend, order-line economics, and clearly labels their different grains. The decision screen uses mature period economics rather than fabricated order-level media cost.

### Continuous new cohorts

Requiring every selected order to be 36 days old would make an active campaign permanently immature. The screen instead isolates a mature measurement window and counts mature orders, while keeping recent realized outcomes visible but nonqualifying.

### Missing-event attribution

Untracked commerce cannot be reliably assigned to a paid campaign. The tracking gate is therefore site-wide. The interface states that campaign filters do not apply to this evidence and avoids blaming a channel without support.

### Policy provenance separate from data provenance

The sample dataset was built before the Milestone 3 screen existed. Rewriting its manifest would misrepresent historical provenance. Decision thresholds therefore live in a separate versioned policy file, and every screen record carries its policy hash alongside the immutable dataset hash in exports.

### Evaluation-label leakage

The simulator contains hidden incident labels for tests. Using them to produce a good-looking decision would make the demonstration circular. The loader and tests prevent the public screen from reading the evaluation directory. Detectors must rely only on observable evidence.

### Windows native-library restriction

Windows Application Control blocks the PyArrow native library installed transitively with Streamlit. Security policy and package internals were left unchanged. DuckDB reads Parquet, Plotly sends ordinary JSON lists to the browser, and escaped read-only HTML renders tables. This preserves the app while respecting the host policy.

### Dependency-file sprawl

The project originally used three requirement files: a minimal pipeline base, a UI extension, and a testing extension. That is useful when the pipeline is deployed independently, but this portfolio is shipped and reviewed as one application. The three files caused duplicate installation commands and made setup less obvious. Milestone 3 consolidates all pinned packages into one `requirements.txt`; environment markers keep the Windows-only helper conditional.

### Synthetic benchmark risk

Synthetic ROAS and margins can look realistic without being calibrated to a real account. The UI and exports label source classes, avoid employer-performance claims, and frame decisions as demonstrations of analytical process. Neutral and held-out simulator cases are still required before detector-quality claims.

## Validation boundary and remaining work

Automated tests cover gate priority, policy validation, provenance fields, inventory and tracking blocks, safe Streamlit rendering, data cutoffs, financial conservation, and reproducibility. Browser review checks the actual layout and decision evidence.

Milestone 3 does not evaluate causal lift, marginal response, forecast accuracy, experiment power, optimal allocation, or live platform actions. Milestone 4 later added an evaluated seven-day baseline and bounded hypothetical scenarios while retaining these claim limits. See `docs/milestone-4-forecast-methodology.md`.
