# Data dictionary

Executable field names and SQL types are centralized in `luxe_lab/storage.py:SCHEMA`; primary keys are in `KEYS`. Raw files preserve those column orders. The prose below defines grain and meaning. All monetary columns ending `_cents` are integer USD cents. Timestamps include timezones, dates are New York reporting dates, and all rows identify `source_class`.

## Raw contracts

**campaigns:** one row per `campaign_id`. `channel` and `objective` describe the invented campaign; `click_window_days` is its simulated platform reporting window. Funnel role is defined by objective in the product contract, not inferred from conversion rates.

**creatives:** one row per `ad_id`, referencing a campaign. `message` and `format` are invented creative tags. No real creative assets or proprietary campaign names are included.

**media:** one row per `(report_date, campaign_id, ad_id)`. Impressions, clicks, spend and `available_at`. Impressions may be NULL for affiliate; clicks and spend are required and nonnegative. This is the only source of media expense, including affiliate commission. A missing row is not a zero-spend row.

**sessions:** one row per `session_id`. Stable artificial `journey_id` and `customer_id`, paid campaign/ad where observed, event time and availability. Campaign and ad may both be NULL for organic/direct touches. A journey can have several touches, including previous paid channels and a later organic conversion session.

**purchases:** one row per `event_id`. References a session and commerce order, with event and availability times. These are observed purchase-tracking events, not the commerce ledger. Deliberately missing events simulate tracking loss. Distinct order counting prevents repeated tracking events from multiplying order totals.

**orders:** one row per `(order_id, line_id)`. Journey/customer, SKU, purchase/availability times, immutable fulfilled/cancelled status, quantity, gross product revenue, allocated discount, outbound fulfillment and original payment fees. Header fields must agree across lines. The generator emits one line per order and sometimes two units on that line; the SQL contract supports multiple lines.

**refunds:** one row per `refund_id`, attached to an order/line. Event and availability times, refunded product revenue, physically returned quantity, recoverable inventory value, handling cost, and refunded payment fees. Multiple partial events are permitted. Total refunds, returned units and fee refunds cannot exceed their original amounts. Inventory recovery requires a physical return and cannot exceed original unit cost when known.

**costs:** one row per `(cost_date, sku)`, with unit cost and availability. Daily effective cost assumption: exact local purchase date must match, not a future-value fill. `unit_cost_cents` may be NULL, and a missing date also means unknown cost. This version does not accept successive revisions of one daily cost key; revision history requires a later adapter.

**inventory:** one row per `(report_date, sku)`, available units and availability time. A nonnegative availability observation; not a full inventory movement ledger. Zero denotes a simulated stock constraint. This release does not reconcile purchases against opening stock, restocks and shrinkage.

**promotions:** one row per `promotion_id`, inclusive start/end dates, per-unit discount assumption and availability. The generated prospecting offer is an additional disclosed assumption in the generator, not a second real campaign promotion. Future promotion plans can be known before their start dates.

**budgets:** one row per `(report_date, campaign_id)`, planned spend and availability. A dated nonnegative plan, known in advance in this simulation. Budget revisions are not modeled.

**platform_snapshots:** one row per `(channel, campaign_id, report_date, snapshot_at)`. Claimed conversions and revenue as known at extraction. `snapshot_at` is the availability cutoff; `date_basis` must be `purchase_date`; `revenue_basis` must be `net_of_discount_before_refunds`. The window comes from campaigns. New snapshots replace older ones, not add to them.

## Analytical contracts

**order_economics:** one row per visible order/line, including warmup. Contains purchase date, fulfilled/cancelled status, booked/refunded/net revenue, net COGS, fulfillment, net payment fees, return handling, missing-cost flag and contribution before media. No future refund is included.

**order_attribution:** one row per visible order. Contains allocated campaign (or UNATTRIBUTED), the selected touch ID/time and an explicit method label. This grain prevents multiple order lines receiving multiple campaign credits.

**campaign_daily:** one row per reporting date/campaign with observed media or commerce. Contains delivery totals, spend, media-presence flag, fulfilled orders, revenues, missing-cost line count, explicitly partial known contribution, full contribution before/after media, business net ROAS, CTR, CPC, plan and pacing. There is no synthetic zero row for an entirely absent campaign/day; future data completeness checks must use an expected delivery calendar.

**platform_latest:** one latest available source/campaign/day snapshot inside the report period. Still source claims, not business allocations. It retains `synthetic_observation` as provenance because no economic transformation occurs.

**reconciliation_daily:** one row per reporting date through the cutoff, including zero-sales days. Distinct commerce and tracked orders, tracking gap, commerce booked/net revenue, separately named overlapping platform claims and a limitation label. A missing platform observation remains NULL. Commerce zeros mean no visible orders in the complete simulator ledger; real imports need a separate ingestion-completeness signal.

## Missing values and input failures

Only documented nullable raw values are allowed: media impressions; session campaign/ad as a pair; unit costs. Unknown quantities, spend, primary keys and references fail validation. Dates/timestamps and monetary types must parse into the explicit schema. Unknown fields are not automatically mapped from external platforms.

Every primary key is checked for nulls and duplicates. Foreign keys, creative ownership, journey/customer consistency, economic bounds, chronology and source definitions are checked before transformation. Complete contribution is never silently replaced by its partial known total. Manifest warnings expose missing cost and media coverage.
