# Measurement contract — version 1.0.0

## Common rules

Currency: USD. Persist money as integer cents; never round intermediate contribution totals to dollars. The simulator rounds its assumed 2.9% payment charge to the nearest cent, half up, then adds 30 cents. Affiliate commissions round down to cents once at campaign/day; their split between two creatives preserves the exact total.

Timestamps: UTC with offsets. Reporting dates: America/New_York, including daylight saving. The cutoff is an inclusive information boundary: an event must have occurred and become available by `as_of`. Later refunds change a purchase-date result only in a later-cutoff run. Raw files intentionally include future records; never use raw files directly as forecasting features.

Order economics use local purchase date. Media spend uses delivery date. Campaign/day ROAS is therefore period reporting: purchases occurring that day divided by spend incurred that day. It is not same-click-cohort ROAS. Aggregate period ratios by summing numerators and denominators, never averaging daily ratios.

## Implemented economics

- Booked product revenue = gross product revenue − allocated product discount, for fulfilled lines only.
- Net product revenue = booked product revenue − refunds known by cutoff. Tax and customer shipping charges are outside the simulation.
- Original COGS = fulfilled quantity × the explicitly supplied unit cost for the SKU on the local purchase date.
- Net COGS = original COGS − recoverable returned-inventory value known by cutoff. A goodwill refund with no physical return does not reverse COGS.
- Net payment fees = original fees − known fee refunds.
- Contribution before media = net product revenue − net COGS − outbound fulfillment − net payment fees − return handling.
- Contribution after media = contribution before media − media expense. This excludes fixed overhead and is not net profit.
- Affiliate commissions belong only in media expense. The simulator assumes a 6% commission on eligible pre-refund attributed product revenue, with no later clawback. This is an invented contract, not a claim about any partner program.

Cancelled lines contribute zero revenue, COGS and fees and are excluded from fulfilled-order counts. Orders have immutable statuses in this release: cancellation is known in the initial record, not a later lifecycle transition. Returned orders remain fulfilled-order counts; refund and returned-unit values are separate.

Refunds aggregate by order/line before joining. Daily costs must have unique SKU/date keys; missing costs are not filled from future days. Missing unit cost makes the affected line's COGS and contribution NULL. If any contributing line has a missing cost, the complete campaign contribution is NULL. `known_contribution_cents` is explicitly a partial total, never a substitute for complete contribution.

Missing media makes spend and contribution after media NULL. `UNATTRIBUTED` has no allocated media expense (zero), which does not imply those customers were acquired without marketing cost. A zero or missing denominator yields NULL, not infinity or zero efficiency. Refunds exceeding booked revenue fail validation rather than producing unsupported negative revenue.

## Implemented allocation and ratios

**Business allocation:** one order receives one last observed paid-click allocation. Eligible touch: same synthetic journey, visible by cutoff, no later than purchase, and within seven elapsed days (168 hours), inclusive. Latest touch wins; equal timestamps use descending session ID as a deterministic tie-break. Organic sessions do not overwrite a qualifying paid touch. No view-through credit. No eligible touch → UNATTRIBUTED. Multiple lines share the order allocation.

**Platform reporting:** each source claims independently under its configured click window: Google and affiliate 30 days; Meta seven days. These are simulated choices, not defaults. The latest snapshot available at cutoff replaces previous snapshots for each source/campaign/date. Sources can claim the same order; their summed claims are explicitly labeled overlapping claims, not unique sales. Platform revenue is net of discount before refunds, on purchase date.

- Business net ROAS = business-allocated net product revenue / media expense for the selected reporting dates.
- CTR = clicks / impressions; affiliate impressions and CTR are NULL because no impression measure is supplied.
- CPC in USD = spend cents / 100 / clicks.
- Pacing ratio = observed spend / dated planned spend for the same dates. A ratio above 1 means spending above plan, not automatic overspending or poor performance.
- Reconciliation tracks distinct fulfilled commerce orders, distinct commerce orders with visible purchase events, their gap, and separately labeled overlapping platform claims. Tracking gaps are observations, not proof of a particular failure cause. Zero-sales reporting days remain present.

## Implemented Milestone 3 decision definitions

- Conversion-mature orders have an attributed paid touch at least 14 elapsed days before the information cutoff.
- Return-mature orders were purchased at least 36 elapsed days before the cutoff. Only reporting dates through that boundary enter mature period economics.
- Stress contribution = mature observed contribution after media − 10% of mature net COGS − 5% of mature booked revenue. The stress terms are explicit policy assumptions, not predicted costs or returns.
- Baseline spend is the sum of the last seven complete selected campaign days. A candidate ceiling is baseline × 1.10, rounded to integer cents. It is a policy bound, not a forecast or optimum.
- A tracking alert requires at least 10 site-wide commerce orders and an untracked share above 20%. The alert is site-wide because missing purchase events cannot be assigned reliably to campaigns.

## Frozen definitions for later milestones (not calculated yet)

- CPM = USD media spend / impressions × 1,000.
- Site conversion rate = distinct observed sessions with a purchase event / eligible observed sessions, grouped by session date. Returning purchasers and multiple orders in one session count once in the numerator. Only observed tracking can be measured; a tracking outage biases the result.
- Platform ROAS = latest source-claimed revenue / the same source's media expense and date range. Label the source revenue and date basis beside the result; do not compare it as though it equals business net ROAS.
- Break-even net-revenue ROAS = 1 / pre-media contribution margin rate, where that rate = contribution before media / net revenue and both are positive. Otherwise undefined. This describes observed unit economics, not profitable marginal scaling.
- Reported new-customer CAC = media spend / distinct newly acquired customers allocated under the business rule. Newness requires prior customer history. The generator creates synthetic customers before purchases, so a first session is not proof of a first purchase. The 30-day warmup alone cannot establish lifetime newness; later analysis must label observed-history newness or use explicit simulator history, and real imports with insufficient history must report unknown.
- Future-return provision = expected remaining returns, estimated from earlier mature cohorts or explicit user assumptions. Never subtract all expected returns in addition to already deducted actual returns.

Incrementality is unmeasured throughout these milestones. Attribution, return differences and positive contribution do not establish how outcomes respond to an advertising budget change.

## Implemented Milestone 4 forecast and scenario definitions

- Seven-day point baseline = sum of seven daily forecasts, each using the mean of up to four prior matching weekdays within a 28-day lookback.
- Forecast error = actual − forecast. Positive bias means actual seven-day totals exceeded the baseline on average.
- WAPE = sum of absolute seven-day total errors / sum of absolute actual seven-day totals on later evaluation origins. A zero denominator yields NULL.
- Empirical interval = point forecast plus the 10th and 90th percentiles of errors from earlier calibration origins. Coverage is measured only on later evaluation origins.
- Scenario order change = spend change / user-assumed marginal cost per order, capped by user-assumed incremental inventory capacity for increases and by baseline forecast orders for decreases.
- Scenario contribution change = assumed order change × user-assumed pre-media contribution per order − spend change.

Revenue and contribution forecasts continue values reported at the dataset cutoff; they do not model final return-cohort outcomes. Scenario ranges carry baseline forecast error forward but attach no probability model to user assumptions.
