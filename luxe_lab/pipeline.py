import hashlib
import json
import platform
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo
import duckdb
from .generator import generate
from .storage import ROOT, SCHEMA, literal, load_raw, load_rows, source_hash, table_info, write_raw
from .validation import validate_marts, validate_raw

MARTS = ("order_economics", "order_attribution", "campaign_daily", "platform_latest", "reconciliation_daily")

def check_config(config):
    start, end = date.fromisoformat(config['report_start']), date.fromisoformat(config['report_end'])
    cutoff = datetime.fromisoformat(config['as_of'])
    if cutoff.tzinfo is None:
        raise ValueError('as_of must include a timezone offset')
    if start > end or cutoff.date() < start:
        raise ValueError('Invalid reporting range or cutoff before reporting start')
    ZoneInfo(config['timezone'])
    if config['business_click_window_days'] != 7:
        raise ValueError('Metric version 1.0.0 specifies a seven-day business window')
    if config['warmup_days'] < 30 or config['sessions_per_campaign_day'] < 1:
        raise ValueError('Use at least 30 warmup days and positive session volume')
    if config['synthetic_list_price_cents'] < 14000 or config['synthetic_unit_cost_cents'] < 0:
        raise ValueError('Price must cover simulated offers (14000 cents); unit cost cannot be negative')

def transform(con, config):
    check_config(config)
    con.execute("SET TimeZone='UTC'")
    con.execute("SET threads=1")
    checks = validate_raw(con, config['timezone'])
    con.execute("CREATE TABLE params (report_start DATE, report_end DATE, as_of TIMESTAMPTZ, reporting_timezone VARCHAR, click_window_days INTEGER)")
    con.execute("INSERT INTO params VALUES (?,?,?,?,?)", [config['report_start'],config['report_end'],config['as_of'],config['timezone'],config['business_click_window_days']])
    for sql in sorted((ROOT/'sql').glob('*.sql')):
        con.execute(sql.read_text(encoding='utf-8'))
    # DuckDB SUM(BIGINT) produces HUGEINT; Parquet would serialize it as DOUBLE.
    # Keep the persisted contract in signed 64-bit integer cents and fail on overflow.
    for table in MARTS:
        columns = con.execute(f'DESCRIBE mart.{table}').fetchall()
        if any(column[1] == 'HUGEINT' for column in columns):
            selection = ','.join(f'CAST({name} AS BIGINT) AS {name}' if kind == 'HUGEINT' else name
                                 for name, kind, *_ in columns)
            con.execute(f'CREATE OR REPLACE TABLE mart.{table} AS SELECT {selection} FROM mart.{table}')
    more, warnings = validate_marts(con)
    return checks + more, warnings

def analyze_rows(data, config):
    con = duckdb.connect()
    try:
        load_rows(con, data)
        checks, warnings = transform(con, config)
        return con, checks, warnings
    except Exception:
        con.close()
        raise

def build(config, output):
    check_config(config)
    output = Path(output)
    # Never overwrite existing user files or silently reuse a failed run.
    if output.exists() and any(output.iterdir()):
        raise FileExistsError(f'{output} is not empty. Choose a new --output directory.')
    output.mkdir(parents=True, exist_ok=True)
    data, truth = generate(config)
    raw_info = write_raw(data, output/'raw')
    evaluation = output/'evaluation_only'
    evaluation.mkdir()
    (evaluation/'ground_truth.json').write_text(json.dumps(truth,indent=2)+'\n',encoding='utf-8')
    con = duckdb.connect()
    try:
        load_raw(con,output/'raw')
        checks,warnings = transform(con,config)
        processed = output/'processed'
        processed.mkdir()
        info = {}
        for table in MARTS:
            path = processed/f'{table}.parquet'
            con.execute(f'COPY (SELECT * FROM mart.{table} ORDER BY ALL) TO {literal(path)} (FORMAT PARQUET, COMPRESSION ZSTD)')
            info[table] = table_info(con,f'mart.{table}')
            info[table]['file_sha256'] = hashlib.sha256(path.read_bytes()).hexdigest()
        manifest = {
            'status':'validated','source_class':'synthetic_portfolio_data',
            'disclaimer':'Not SharkNinja performance. No causal effects or recommendations have been estimated.',
            'config':config,'source_code_sha256':source_hash(),
            'runtime':{'python':platform.python_version(),'duckdb':duckdb.__version__},
            'raw':raw_info,'processed':info,'checks':checks,'warnings':warnings,
            'evaluation_policy':'evaluation_only is never read by staging or analytical SQL; raw source records may include future data; only processed outputs respect the information cutoff',
        }
        manifest['dataset_sha256'] = hashlib.sha256(json.dumps({k:v['logical_sha256'] for k,v in raw_info.items()},sort_keys=True).encode()).hexdigest()
        # Written last: its presence indicates that the run completed successfully.
        (output/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n',encoding='utf-8')
        return manifest
    finally:
        con.close()
