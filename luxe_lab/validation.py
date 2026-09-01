"""Fail on broken source contracts; expose missing costs without inventing them."""
from .storage import KEYS, SCHEMA, literal

class ContractError(ValueError):
    pass

def validate_raw(con, reporting_timezone='America/New_York'):
    checks = []
    def check(name, sql):
        violations = int(con.execute(sql).fetchone()[0])
        checks.append({"check": name, "violations": violations})
    for table, keys in KEYS.items():
        key_sql = ','.join(keys)
        null_sql = ' OR '.join(f'{k} IS NULL' for k in keys)
        check(f"{table}: nonnull keys", f"SELECT count(*) FROM raw.{table} WHERE {null_sql}")
        check(f"{table}: unique keys", f"SELECT count(*) FROM (SELECT {key_sql} FROM raw.{table} GROUP BY {key_sql} HAVING count(*)>1)")
        check(f"{table}: source class", f"SELECT count(*) FROM raw.{table} WHERE source_class IS NULL OR source_class NOT IN ('synthetic_observation','user_assumption')")
        # All required non-key fields are explicit; only documented nullable values pass.
        nullable = {"media": {"impressions"}, "sessions": {"campaign_id","ad_id"}, "costs": {"unit_cost_cents"}}.get(table, set())
        cols = [d.strip().split()[0] for d in SCHEMA[table].split(',')]
        required = [c for c in cols if c not in nullable]
        check(f"{table}: required fields", f"SELECT count(*) FROM raw.{table} WHERE " + ' OR '.join(f'{c} IS NULL' for c in required))
    for table, col in [("creatives","campaign_id"),("media","campaign_id"),("sessions","campaign_id"),("budgets","campaign_id"),("platform_snapshots","campaign_id")]:
        check(f"{table}: campaign foreign key", f"SELECT count(*) FROM raw.{table} x LEFT JOIN raw.campaigns c ON x.{col}=c.campaign_id WHERE x.{col} IS NOT NULL AND c.campaign_id IS NULL")
    for table in ("media", "sessions"):
        check(f"{table}: creative belongs to campaign", f"SELECT count(*) FROM raw.{table} x LEFT JOIN raw.creatives c ON x.ad_id=c.ad_id AND x.campaign_id=c.campaign_id WHERE (x.campaign_id IS NOT NULL AND c.ad_id IS NULL) OR (x.campaign_id IS NULL AND x.ad_id IS NOT NULL)")
    check("refunds: order line foreign key", "SELECT count(*) FROM raw.refunds r LEFT JOIN raw.orders o USING(order_id,line_id) WHERE o.order_id IS NULL")
    check("purchases: order and session foreign keys", "SELECT count(*) FROM raw.purchases p LEFT JOIN raw.orders o USING(order_id) LEFT JOIN raw.sessions s USING(session_id) WHERE o.order_id IS NULL OR s.session_id IS NULL OR s.journey_id<>o.journey_id")
    check("orders: consistent headers", "SELECT count(*) FROM (SELECT order_id FROM raw.orders GROUP BY order_id HAVING count(DISTINCT (journey_id,customer_id,purchased_at,status))>1)")
    check("orders: valid economics", "SELECT count(*) FROM raw.orders WHERE quantity<=0 OR status NOT IN ('fulfilled','cancelled') OR gross_cents<0 OR discount_cents<0 OR discount_cents>gross_cents OR fulfillment_cents<0 OR fee_cents<0 OR (status='cancelled' AND (fulfillment_cents<>0 OR fee_cents<>0))")
    check("refunds: bounds", """SELECT count(*) FROM (
      SELECT r.order_id,r.line_id,sum(refund_cents) AS refund,sum(returned_quantity) AS qty,
        sum(recovered_inventory_cents) AS recovered,sum(fee_refund_cents) AS fees
      FROM raw.refunds r GROUP BY r.order_id,r.line_id
    ) r JOIN raw.orders o USING(order_id,line_id)
    WHERE r.refund>o.gross_cents-o.discount_cents OR r.qty>o.quantity OR r.fees>o.fee_cents
      OR o.status='cancelled'""")
    check("refunds: nonnegative and physical recovery", "SELECT count(*) FROM raw.refunds WHERE refund_cents<0 OR returned_quantity<0 OR recovered_inventory_cents<0 OR handling_cents<0 OR fee_refund_cents<0 OR (returned_quantity=0 AND recovered_inventory_cents<>0)")
    check("refunds: recovery bounded by original unit cost", f"""SELECT count(*)
      FROM raw.refunds r JOIN raw.orders o USING(order_id,line_id)
      JOIN raw.costs c ON c.sku=o.sku AND c.cost_date=timezone({literal(reporting_timezone)},o.purchased_at)::DATE
      WHERE r.recovered_inventory_cents>r.returned_quantity*c.unit_cost_cents""")
    check("sessions: consistent journey customer", "SELECT count(*) FROM (SELECT journey_id FROM raw.sessions GROUP BY journey_id HAVING count(DISTINCT customer_id)>1)")
    check("orders: matching journey customer", "SELECT count(*) FROM raw.orders o JOIN raw.sessions s USING(journey_id) WHERE o.customer_id<>s.customer_id")
    check("purchases: event chronology", "SELECT count(*) FROM raw.purchases p JOIN raw.orders o USING(order_id) JOIN raw.sessions s USING(session_id) WHERE p.event_at<o.purchased_at OR p.event_at<s.event_at OR o.status='cancelled'")
    check("media: valid delivery", "SELECT count(*) FROM raw.media WHERE clicks<0 OR spend_cents<0 OR impressions<clicks")
    check("costs: nonnegative", "SELECT count(*) FROM raw.costs WHERE unit_cost_cents<0")
    check("inventory: nonnegative", "SELECT count(*) FROM raw.inventory WHERE available_units<0")
    check("budgets: nonnegative", "SELECT count(*) FROM raw.budgets WHERE planned_spend_cents<0")
    check("promotions: bounds", "SELECT count(*) FROM raw.promotions WHERE start_date>end_date OR discount_cents<0")
    check("platform: documented basis", "SELECT count(*) FROM raw.platform_snapshots WHERE conversions<0 OR revenue_cents<0 OR date_basis<>'purchase_date' OR revenue_basis<>'net_of_discount_before_refunds'")
    check("platform: matching channel", "SELECT count(*) FROM raw.platform_snapshots p JOIN raw.campaigns c USING(campaign_id) WHERE p.channel<>c.channel")
    for table, event in [("orders","purchased_at"),("sessions","event_at"),("refunds","event_at"),("purchases","event_at")]:
        check(f"{table}: availability chronology", f"SELECT count(*) FROM raw.{table} WHERE available_at<{event}")
    check("refunds: after purchase", "SELECT count(*) FROM raw.refunds r JOIN raw.orders o USING(order_id,line_id) WHERE r.event_at<o.purchased_at")
    failures = [c for c in checks if c["violations"]]
    if failures:
        raise ContractError(str(failures))
    return checks

def validate_marts(con):
    checks = []
    def equal(name, left, right):
        a, b = con.execute(left).fetchone()[0], con.execute(right).fetchone()[0]
        if a != b:
            raise ContractError(f"{name}: {a} != {b}")
        checks.append({"check": name, "violations": 0})
    equal("attribution: one row per visible order", "SELECT count(*) FROM mart.order_attribution", "SELECT count(DISTINCT order_id) FROM stg.orders")
    equal("net revenue conserved", "SELECT coalesce(sum(net_revenue_cents),0) FROM mart.campaign_daily", "SELECT coalesce(sum(net_revenue_cents),0) FROM mart.order_economics,params WHERE report_date BETWEEN report_start AND report_end")
    equal("spend conserved", "SELECT coalesce(sum(spend_cents),0) FROM mart.campaign_daily", "SELECT coalesce(sum(spend_cents),0) FROM stg.media,params WHERE report_date BETWEEN report_start AND report_end")
    missing = int(con.execute("SELECT count(*) FROM mart.order_economics WHERE cost_missing").fetchone()[0])
    missing_media = int(con.execute("SELECT count(*) FROM mart.campaign_daily WHERE NOT media_present AND campaign_id<>'UNATTRIBUTED'").fetchone()[0])
    warnings = []
    if missing:
        warnings.append({"code": "MISSING_COST", "order_lines": missing, "effect": "contribution is null, not zero"})
    if missing_media:
        warnings.append({"code": "MISSING_MEDIA", "campaign_days": missing_media, "effect": "spend and after-media contribution are null"})
    return checks, warnings
