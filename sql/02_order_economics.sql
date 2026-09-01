-- Aggregate refund events before joining to order lines. Keep integer cents.
CREATE TABLE mart.order_economics AS
WITH refunds AS (
  SELECT order_id, line_id, sum(refund_cents) AS refunded_cents,
    sum(recovered_inventory_cents) AS recovered_cents,
    sum(handling_cents) AS return_handling_cents,
    sum(fee_refund_cents) AS fee_refunded_cents,
    sum(returned_quantity) AS returned_quantity
  FROM stg.refunds GROUP BY order_id, line_id
), calculated AS (
  SELECT o.order_id, o.line_id, o.journey_id, o.customer_id, o.sku,
    o.purchased_at, o.available_at, o.status, o.quantity,
    timezone(p.reporting_timezone, o.purchased_at)::DATE AS report_date,
    CASE WHEN o.status = 'cancelled' THEN 0 ELSE o.gross_cents - o.discount_cents END AS booked_revenue_cents,
    CASE WHEN o.status = 'cancelled' THEN 0 ELSE coalesce(r.refunded_cents, 0) END AS refunded_cents,
    CASE WHEN o.status = 'cancelled' THEN 0
      ELSE o.gross_cents - o.discount_cents - coalesce(r.refunded_cents, 0) END AS net_revenue_cents,
    CASE WHEN o.status = 'cancelled' THEN 0
      ELSE o.quantity * c.unit_cost_cents - coalesce(r.recovered_cents, 0) END AS net_cogs_cents,
    CASE WHEN o.status = 'cancelled' THEN 0 ELSE o.fulfillment_cents END AS fulfillment_cents,
    CASE WHEN o.status = 'cancelled' THEN 0 ELSE o.fee_cents - coalesce(r.fee_refunded_cents, 0) END AS net_fee_cents,
    coalesce(r.return_handling_cents, 0) AS return_handling_cents,
    o.status = 'fulfilled' AND c.unit_cost_cents IS NULL AS cost_missing,
    'derived_result' AS source_class
  FROM stg.orders o CROSS JOIN params p
  LEFT JOIN refunds r USING (order_id, line_id)
  LEFT JOIN stg.costs c ON c.sku = o.sku
    AND c.cost_date = timezone(p.reporting_timezone, o.purchased_at)::DATE
)
SELECT *, net_revenue_cents - net_cogs_cents - fulfillment_cents
  - net_fee_cents - return_handling_cents AS contribution_before_media_cents
FROM calculated;

-- One attribution allocation per order, not one credit per source or order line.
CREATE TABLE mart.order_attribution AS
WITH headers AS (
  SELECT DISTINCT order_id, journey_id, purchased_at FROM stg.orders
), candidates AS (
  SELECT o.order_id, s.campaign_id, s.session_id AS touch_session_id,
    s.event_at AS touch_at,
    row_number() OVER (PARTITION BY o.order_id ORDER BY s.event_at DESC, s.session_id DESC) AS rank
  FROM headers o CROSS JOIN params p
  LEFT JOIN stg.sessions s ON s.journey_id = o.journey_id
    AND s.campaign_id IS NOT NULL
    AND s.event_at <= o.purchased_at
    AND s.event_at >= o.purchased_at - p.click_window_days * INTERVAL '1 day'
)
SELECT order_id, coalesce(campaign_id, 'UNATTRIBUTED') AS campaign_id,
  touch_session_id, touch_at, '7-day last observed paid click; reporting allocation, not causal' AS method,
  'derived_result' AS source_class
FROM candidates WHERE rank = 1;

