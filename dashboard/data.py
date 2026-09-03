"""UI data access and aggregation; unknown costs must never become zero."""
import hashlib
import json
from pathlib import Path

import pandas as pd
import duckdb

from luxe_lab.pipeline import MARTS
from luxe_lab.storage import ROOT

CAMPAIGN_NAMES = {
    'C01': 'Branded search', 'C02': 'Nonbrand search', 'C03': 'Shopping',
    'C04': 'Prospecting', 'C05': 'Retargeting', 'C06': 'Affiliate partners',
    'UNATTRIBUTED': 'Unattributed sales',
}
CHANNEL_NAMES = {'google': 'Google', 'meta': 'Meta', 'affiliate': 'Affiliate'}
UI_RAW = ('campaigns', 'inventory', 'promotions')


def discover_runs(data_dir=ROOT/'data'):
    runs = []
    for path in sorted(Path(data_dir).glob('*/manifest.json')):
        try:
            manifest = json.loads(path.read_text(encoding='utf-8'))
            if manifest.get('status') == 'validated' and all(
                (path.parent/'processed'/f'{name}.parquet').is_file() for name in MARTS
            ):
                runs.append(path.parent)
        except (ValueError, OSError):
            continue
    return runs


def revision(run):
    """Invalidate cached data when any displayed source file changes."""
    paths = [Path(run)/'manifest.json']
    paths += [Path(run)/'processed'/f'{name}.parquet' for name in MARTS]
    paths += [Path(run)/'raw'/f'{name}.parquet' for name in UI_RAW]
    return tuple((p.stat().st_mtime_ns, p.stat().st_size) for p in paths)


def load_dataset(run):
    run = Path(run)
    manifest = json.loads((run/'manifest.json').read_text(encoding='utf-8'))
    if manifest.get('status') != 'validated':
        raise ValueError('This run has not passed its data checks.')
    frames = {}
    for group, names in [('processed', MARTS), ('raw', UI_RAW)]:
        for name in names:
            file = run/group/f'{name}.parquet'
            expected = manifest[group][name]['file_sha256']
            if hashlib.sha256(file.read_bytes()).hexdigest() != expected:
                raise ValueError(f'{name} has changed since validation. Rebuild the run before displaying it.')
            # Use the already validated DuckDB reader. No PyArrow native binary is loaded.
            con = duckdb.connect()
            try:
                con.execute("SET TimeZone='UTC'")
                frames[name] = con.execute('SELECT * FROM read_parquet(?)',[str(file)]).df().convert_dtypes()
            finally:
                con.close()
    cutoff = pd.Timestamp(manifest['config']['as_of'])
    local_day = cutoff.tz_convert(manifest['config']['timezone']).date()
    for name in ('inventory', 'promotions'):
        frame = frames[name]
        frame = frame[pd.to_datetime(frame.available_at, utc=True) <= cutoff].copy()
        if name == 'inventory':
            frame = frame[pd.to_datetime(frame.report_date).dt.date <= local_day]
        frames[name] = frame
    for name, frame in frames.items():
        if 'report_date' in frame:
            frame['report_date'] = pd.to_datetime(frame.report_date).dt.normalize()
    dimension = frames['campaigns'][['campaign_id', 'channel']].copy()
    dimension['channel'] = dimension.channel.map(CHANNEL_NAMES).fillna(dimension.channel)
    dimension = pd.concat([dimension, pd.DataFrame([{'campaign_id':'UNATTRIBUTED', 'channel':'Unattributed'}])], ignore_index=True)
    dimension['campaign'] = dimension.campaign_id.map(CAMPAIGN_NAMES).fillna(dimension.campaign_id)
    frames['campaign_daily'] = frames['campaign_daily'].merge(dimension, on='campaign_id', validate='many_to_one')
    frames['order_economics'] = frames['order_economics'].merge(
        frames['order_attribution'][['order_id','campaign_id','touch_session_id','touch_at']], on='order_id', validate='many_to_one'
    ).merge(dimension, on='campaign_id', validate='many_to_one')
    return {'manifest':manifest, 'tables':frames, 'dimension':dimension}


def filter_dates(frame, start, end):
    return frame.loc[frame.report_date.between(pd.Timestamp(start),pd.Timestamp(end))].copy()


def filter_campaigns(frame, start, end, campaign_ids):
    return filter_dates(frame, start, end).loc[lambda f:f.campaign_id.isin(campaign_ids)].copy()


def strict_sum(values):
    """Preserve unknown totals, including mixed known/unknown values."""
    return None if len(values) == 0 or values.isna().any() else int(values.sum())


def ratio(numerator, denominator):
    if numerator is None or denominator is None or denominator <= 0:
        return None
    return numerator / denominator


def summarize(frame):
    result = {name:strict_sum(frame[name]) for name in (
        'spend_cents', 'net_revenue_cents', 'contribution_before_media_cents',
        'contribution_after_media_cents', 'booked_revenue_cents', 'planned_spend_cents',
    )}
    result['orders'] = int(frame.orders.sum())
    result['missing_cost_lines'] = int(frame.missing_cost_lines.sum())
    result['business_net_roas'] = ratio(result['net_revenue_cents'],result['spend_cents'])
    result['pacing_ratio'] = ratio(result['spend_cents'],result['planned_spend_cents'])
    return result


def campaign_summary(frame):
    rows = []
    for cid, group in frame.groupby('campaign_id',sort=False):
        row = summarize(group)
        row.update(campaign_id=cid,campaign=group.campaign.iloc[0],channel=group.channel.iloc[0])
        value = row['contribution_after_media_cents']
        row['status'] = 'Incomplete inputs' if value is None else ('Negative contribution' if value < 0 else 'Nonnegative contribution')
        rows.append(row)
    return pd.DataFrame(rows)


def period_summary(frame, frequency='Daily'):
    groups = frame.copy()
    groups['period'] = groups.report_date.dt.to_period('W-SUN').dt.start_time if frequency == 'Weekly' else groups.report_date
    rows = []
    for day, group in groups.groupby('period',sort=True):
        rows.append({'period':day, **summarize(group)})
    return pd.DataFrame(rows)


def economics_steps(orders, spend_cents):
    """A reconciled waterfall from booked revenue to contribution after media."""
    components = [('Booked revenue','booked_revenue_cents',1),('Refunds','refunded_cents',-1),
                  ('Product cost','net_cogs_cents',-1),('Fulfillment','fulfillment_cents',-1),
                  ('Payment fees','net_fee_cents',-1),('Return handling','return_handling_cents',-1)]
    rows, balance = [], 0
    for label, column, sign in components:
        value = strict_sum(orders[column])
        if value is None:
            return None
        delta = sign * value
        rows.append({'step':label,'start':balance/100,'end':(balance+delta)/100,'amount':delta/100,
                     'kind':'Revenue' if sign>0 else 'Cost'})
        balance += delta
    if spend_cents is None:
        return None
    rows.append({'step':'Media expense','start':balance/100,'end':(balance-spend_cents)/100,
                 'amount':-spend_cents/100,'kind':'Cost'})
    balance -= spend_cents
    rows.append({'step':'Contribution','start':0,'end':balance/100,'amount':balance/100,'kind':'Contribution'})
    return pd.DataFrame(rows)


def campaign_export(summary, start, end, manifest):
    result = summary.copy()
    result['report_start'] = str(start)
    result['report_end'] = str(end)
    result['as_of'] = manifest['config']['as_of']
    result['metric_version'] = manifest['config']['metric_version']
    result['dataset_sha256'] = manifest['dataset_sha256']
    result['source_class'] = 'derived_from_synthetic_data'
    result['attribution'] = '7-day last observed paid click; not causal'
    return result.to_csv(index=False).encode('utf-8-sig')
