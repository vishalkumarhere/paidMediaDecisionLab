CREATE TABLE mart.campaign_daily AS
WITH delivery AS (
 SELECT report_date, campaign_id, sum(impressions) AS impressions, sum(clicks) AS clicks,
   sum(spend_cents) AS spend_cents
 FROM stg.media GROUP BY report_date, campaign_id
), commerce AS (
 SELECT e.report_date, a.campaign_id,
   count(DISTINCT e.order_id) FILTER (WHERE e.status='fulfilled') AS orders,
   sum(e.net_revenue_cents) AS net_revenue_cents,
   sum(e.booked_revenue_cents) AS booked_revenue_cents,
   count(*) FILTER (WHERE e.cost_missing) AS missing_cost_lines,
   sum(coalesce(e.contribution_before_media_cents, 0)) AS known_contribution_cents,
   CASE WHEN bool_or(e.cost_missing) THEN NULL ELSE sum(e.contribution_before_media_cents) END AS contribution_before_media_cents
 FROM mart.order_economics e JOIN mart.order_attribution a USING (order_id)
 GROUP BY e.report_date, a.campaign_id
), combined AS (
 SELECT coalesce(d.report_date, c.report_date) AS report_date,
   coalesce(d.campaign_id, c.campaign_id) AS campaign_id,
   d.impressions, d.clicks,
   CASE WHEN c.campaign_id='UNATTRIBUTED' THEN 0 ELSE d.spend_cents END AS spend_cents,
   d.campaign_id IS NOT NULL AS media_present,
   coalesce(c.orders, 0) AS orders, coalesce(c.net_revenue_cents, 0) AS net_revenue_cents,
   coalesce(c.booked_revenue_cents, 0) AS booked_revenue_cents,
   coalesce(c.missing_cost_lines, 0) AS missing_cost_lines,
   coalesce(c.known_contribution_cents, 0) AS known_contribution_cents,
   CASE WHEN c.missing_cost_lines > 0 THEN NULL ELSE coalesce(c.contribution_before_media_cents, 0) END AS contribution_before_media_cents
 FROM delivery d FULL OUTER JOIN commerce c USING (report_date, campaign_id)
)
SELECT c.*, c.contribution_before_media_cents-c.spend_cents AS contribution_after_media_cents,
  c.net_revenue_cents::DOUBLE/nullif(c.spend_cents,0) AS business_net_roas,
  c.clicks::DOUBLE/nullif(c.impressions,0) AS ctr,
  c.spend_cents/100.0/nullif(c.clicks,0) AS cpc_usd,
  b.planned_spend_cents,
  c.spend_cents::DOUBLE/nullif(b.planned_spend_cents,0) AS pacing_ratio,
  'derived_result' AS source_class
FROM combined c CROSS JOIN params p
LEFT JOIN stg.budgets b USING (report_date, campaign_id)
WHERE c.report_date BETWEEN p.report_start AND p.report_end;

-- Directional purchase-date comparison. Platform sums are deliberately not total sales.
CREATE TABLE mart.reconciliation_daily AS
WITH calendar AS (
 SELECT unnest(generate_series(report_start,
   least(report_end,timezone(reporting_timezone,as_of)::DATE), INTERVAL '1 day'))::DATE AS report_date
 FROM params
), commerce AS (
 SELECT report_date, count(DISTINCT order_id) FILTER (WHERE status='fulfilled') AS commerce_orders,
   sum(booked_revenue_cents) AS commerce_booked_cents,
   sum(net_revenue_cents) AS commerce_net_cents
 FROM mart.order_economics GROUP BY report_date
), tracking AS (
 SELECT e.report_date, count(DISTINCT e.order_id) AS tracked_orders
 FROM mart.order_economics e JOIN stg.purchases t USING (order_id)
 WHERE e.status='fulfilled' GROUP BY e.report_date
), platform AS (
 SELECT report_date, sum(conversions) AS overlapping_platform_claims,
   sum(revenue_cents) AS overlapping_platform_revenue_claims_cents
 FROM mart.platform_latest GROUP BY report_date
)
SELECT d.report_date, coalesce(c.commerce_orders,0) AS commerce_orders,
  coalesce(c.commerce_booked_cents,0) AS commerce_booked_cents,
  coalesce(c.commerce_net_cents,0) AS commerce_net_cents,
  coalesce(t.tracked_orders,0) AS tracked_orders,
  coalesce(c.commerce_orders,0)-coalesce(t.tracked_orders,0) AS untracked_orders,
  p.overlapping_platform_claims, p.overlapping_platform_revenue_claims_cents,
  'platform claims can overlap; not additive sales or causal impact' AS limitation,
  'derived_result' AS source_class
FROM calendar d LEFT JOIN commerce c USING (report_date)
LEFT JOIN tracking t USING (report_date)
LEFT JOIN platform p USING (report_date) CROSS JOIN params cfg
WHERE d.report_date BETWEEN cfg.report_start AND cfg.report_end;
