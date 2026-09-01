-- A reporting cutoff is an information boundary, not just a purchase-date filter.
CREATE SCHEMA stg;
CREATE TABLE stg.campaigns AS SELECT * FROM raw.campaigns;
CREATE TABLE stg.creatives AS SELECT * FROM raw.creatives;
CREATE TABLE stg.orders AS SELECT o.* FROM raw.orders o, params p
WHERE o.available_at <= p.as_of AND o.purchased_at <= p.as_of;
CREATE TABLE stg.refunds AS SELECT r.* FROM raw.refunds r, params p
WHERE r.available_at <= p.as_of AND r.event_at <= p.as_of;
CREATE TABLE stg.sessions AS SELECT s.* FROM raw.sessions s, params p
WHERE s.available_at <= p.as_of AND s.event_at <= p.as_of;
CREATE TABLE stg.purchases AS SELECT e.* FROM raw.purchases e, params p
WHERE e.available_at <= p.as_of AND e.event_at <= p.as_of;
CREATE TABLE stg.costs AS SELECT c.* FROM raw.costs c, params p
WHERE c.available_at <= p.as_of AND c.cost_date <= timezone(p.reporting_timezone, p.as_of)::DATE;
CREATE TABLE stg.media AS SELECT m.* FROM raw.media m, params p
WHERE m.available_at <= p.as_of AND m.report_date <= timezone(p.reporting_timezone, p.as_of)::DATE;
CREATE TABLE stg.budgets AS SELECT b.* FROM raw.budgets b, params p
WHERE b.available_at <= p.as_of;
CREATE TABLE stg.inventory AS SELECT i.* FROM raw.inventory i, params p
WHERE i.available_at <= p.as_of AND i.report_date <= timezone(p.reporting_timezone, p.as_of)::DATE;
CREATE TABLE stg.promotions AS SELECT x.* FROM raw.promotions x, params p
WHERE x.available_at <= p.as_of;

CREATE SCHEMA mart;
CREATE TABLE mart.platform_latest AS
SELECT s.* FROM raw.platform_snapshots s, params p
WHERE s.snapshot_at <= p.as_of
  AND s.report_date BETWEEN p.report_start AND p.report_end
  AND s.report_date <= timezone(p.reporting_timezone, p.as_of)::DATE
QUALIFY row_number() OVER (
  PARTITION BY s.channel, s.campaign_id, s.report_date ORDER BY s.snapshot_at DESC
) = 1;

