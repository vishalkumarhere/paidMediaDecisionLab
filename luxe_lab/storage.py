"""Explicit contracts and deterministic, dependency-light Parquet I/O."""
import hashlib
import json
from datetime import date, datetime
from pathlib import Path
import duckdb

ROOT = Path(__file__).resolve().parents[1]
SCHEMA = {
    "campaigns": "campaign_id VARCHAR, channel VARCHAR, objective VARCHAR, click_window_days INTEGER, source_class VARCHAR",
    "creatives": "ad_id VARCHAR, campaign_id VARCHAR, message VARCHAR, format VARCHAR, source_class VARCHAR",
    "media": "report_date DATE, campaign_id VARCHAR, ad_id VARCHAR, impressions BIGINT, clicks BIGINT, spend_cents BIGINT, available_at TIMESTAMPTZ, source_class VARCHAR",
    "sessions": "session_id VARCHAR, journey_id VARCHAR, customer_id VARCHAR, campaign_id VARCHAR, ad_id VARCHAR, event_at TIMESTAMPTZ, available_at TIMESTAMPTZ, source_class VARCHAR",
    "purchases": "event_id VARCHAR, session_id VARCHAR, order_id VARCHAR, event_at TIMESTAMPTZ, available_at TIMESTAMPTZ, source_class VARCHAR",
    "orders": "order_id VARCHAR, line_id VARCHAR, journey_id VARCHAR, customer_id VARCHAR, sku VARCHAR, purchased_at TIMESTAMPTZ, available_at TIMESTAMPTZ, status VARCHAR, quantity INTEGER, gross_cents BIGINT, discount_cents BIGINT, fulfillment_cents BIGINT, fee_cents BIGINT, source_class VARCHAR",
    "refunds": "refund_id VARCHAR, order_id VARCHAR, line_id VARCHAR, event_at TIMESTAMPTZ, available_at TIMESTAMPTZ, refund_cents BIGINT, returned_quantity INTEGER, recovered_inventory_cents BIGINT, handling_cents BIGINT, fee_refund_cents BIGINT, source_class VARCHAR",
    "costs": "cost_date DATE, sku VARCHAR, unit_cost_cents BIGINT, available_at TIMESTAMPTZ, source_class VARCHAR",
    "inventory": "report_date DATE, sku VARCHAR, available_units INTEGER, available_at TIMESTAMPTZ, source_class VARCHAR",
    "promotions": "promotion_id VARCHAR, start_date DATE, end_date DATE, discount_cents BIGINT, available_at TIMESTAMPTZ, source_class VARCHAR",
    "budgets": "report_date DATE, campaign_id VARCHAR, planned_spend_cents BIGINT, available_at TIMESTAMPTZ, source_class VARCHAR",
    "platform_snapshots": "channel VARCHAR, campaign_id VARCHAR, report_date DATE, snapshot_at TIMESTAMPTZ, conversions BIGINT, revenue_cents BIGINT, date_basis VARCHAR, revenue_basis VARCHAR, source_class VARCHAR",
}
KEYS = {
    "campaigns": ["campaign_id"], "creatives": ["ad_id"],
    "media": ["report_date", "campaign_id", "ad_id"], "sessions": ["session_id"],
    "purchases": ["event_id"], "orders": ["order_id", "line_id"],
    "refunds": ["refund_id"], "costs": ["cost_date", "sku"],
    "inventory": ["report_date", "sku"], "promotions": ["promotion_id"],
    "budgets": ["report_date", "campaign_id"],
    "platform_snapshots": ["channel", "campaign_id", "report_date", "snapshot_at"],
}

def literal(value):
    return "'" + str(value).replace("'", "''") + "'"

def normalize(value):
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    return value

def content_hash(columns, rows):
    # Hash logical content, not compression metadata or a machine-specific path.
    normalized = [[normalize(v) for v in row] for row in rows]
    normalized.sort(key=lambda row: json.dumps(row, ensure_ascii=True, separators=(",", ":")))
    payload = json.dumps({"columns": columns, "rows": normalized}, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode()).hexdigest()

def table_info(con, table):
    result = con.execute(f"SELECT * FROM {table}")
    columns = [c[0] for c in result.description]
    rows = result.fetchall()
    return {"rows": len(rows), "logical_sha256": content_hash(columns, rows)}

def load_rows(con, data, schema="raw"):
    con.execute(f"CREATE SCHEMA {schema}")
    for name, definition in SCHEMA.items():
        con.execute(f"CREATE TABLE {schema}.{name} ({definition})")
        rows = data.get(name, [])
        if rows:
            marks = ",".join("?" for _ in definition.split(","))
            # Batch values instead of committing one Python execute per record.
            for offset in range(0, len(rows), 500):
                batch = rows[offset:offset + 500]
                values = ','.join(f'({marks})' for _ in batch)
                con.execute(f"INSERT INTO {schema}.{name} VALUES {values}",
                            [value for row in batch for value in row])

def write_raw(data, destination):
    destination = Path(destination)
    destination.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect()
    con.execute("SET TimeZone='UTC'")
    con.execute("SET threads=1")
    try:
        load_rows(con, data)
        result = {}
        for name in SCHEMA:
            ordering = ",".join(KEYS[name])
            path = destination / f"{name}.parquet"
            con.execute(f"COPY (SELECT * FROM raw.{name} ORDER BY {ordering}) TO {literal(path)} (FORMAT PARQUET, COMPRESSION ZSTD)")
            result[name] = table_info(con, f"raw.{name}")
            result[name]["file_sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
        return result
    finally:
        con.close()

def load_raw(con, directory):
    con.execute("CREATE SCHEMA raw")
    for name, definition in SCHEMA.items():
        con.execute(f"CREATE TABLE raw.{name} ({definition})")
        # Explicit target schema avoids inferring empty fixtures incorrectly.
        con.execute(f"INSERT INTO raw.{name} SELECT * FROM read_parquet(?)", [str(Path(directory) / f"{name}.parquet")])

def source_hash():
    files = [*ROOT.glob("luxe_lab/*.py"), *ROOT.glob("sql/*.sql"), *ROOT.glob("config/*.json"),
             ROOT/'pyproject.toml', ROOT/'requirements.txt']
    h = hashlib.sha256()
    for file in sorted(files):
        h.update(file.relative_to(ROOT).as_posix().encode())
        h.update(file.read_bytes())
    return h.hexdigest()
