import json
import shutil
from io import BytesIO

import pandas as pd
import pytest

from dashboard.data import (
    CAMPAIGN_NAMES, campaign_export, campaign_summary, economics_steps,
    filter_campaigns, load_dataset, period_summary, ratio, strict_sum, summarize,
)
from luxe_lab.pipeline import analyze_rows
from luxe_lab.storage import ROOT


def fixture_frames(financial, config):
    con,_,_ = analyze_rows(financial,config)
    try:
        daily = con.execute('SELECT * FROM mart.campaign_daily').df()
        orders = con.execute('SELECT * FROM mart.order_economics').df()
    finally:
        con.close()
    daily['campaign'] = daily.campaign_id.map(CAMPAIGN_NAMES)
    daily['channel'] = daily.campaign_id.map({'C01':'Google','C06':'Affiliate'})
    return daily,orders


def test_dashboard_reconciles_hand_fixture_and_preserves_unknowns(financial,config):
    daily,orders = fixture_frames(financial,config)
    july6 = filter_campaigns(daily,'2026-07-06','2026-07-06',['C01','C06'])
    result = summarize(july6)
    assert result['orders'] == 2
    assert result['net_revenue_cents'] == 100000
    assert result['spend_cents'] == 20000
    assert result['contribution_after_media_cents'] == 2000
    assert result['business_net_roas'] == 5
    assert summarize(daily)['contribution_after_media_cents'] is None
    steps = economics_steps(orders[orders.report_date==pd.Timestamp('2026-07-06')],20000)
    assert steps.iloc[-1]['end'] == 20
    assert economics_steps(orders,21000) is None


def test_ratios_use_summed_numerators_not_average_daily_ratios(financial,config):
    daily,_ = fixture_frames(financial,config)
    rows = daily[daily.report_date==pd.Timestamp('2026-07-06')].copy()
    rows.loc[rows.campaign_id=='C06','spend_cents'] = 1000
    assert summarize(rows)['business_net_roas'] == pytest.approx(100000/11000)
    assert period_summary(rows,'Weekly').iloc[0].business_net_roas == pytest.approx(100000/11000)
    assert ratio(500,0) is None
    assert strict_sum(pd.Series([100,None])) is None


def test_campaign_filters_and_exports_match(financial,config):
    daily,_ = fixture_frames(financial,config)
    filtered = filter_campaigns(daily,'2026-07-06','2026-07-06',['C06'])
    report = campaign_summary(filtered)
    assert report.iloc[0].contribution_after_media_cents == 7500
    manifest = {'config':config,'dataset_sha256':'test-hash'}
    downloaded = pd.read_csv(BytesIO(campaign_export(report,'2026-07-06','2026-07-06',manifest)))
    assert downloaded.campaign_id.tolist() == ['C06']
    assert downloaded.spend_cents.sum() == 10000
    assert downloaded.as_of.iloc[0] == config['as_of']
    assert downloaded.source_class.iloc[0] == 'derived_from_synthetic_data'
    assert downloaded.dataset_sha256.iloc[0] == 'test-hash'


def test_sample_loader_respects_cutoff_and_ignores_hidden_labels(monkeypatch):
    original = type(ROOT).read_text
    def safe_read(path,*args,**kwargs):
        assert 'evaluation_only' not in path.parts
        return original(path,*args,**kwargs)
    monkeypatch.setattr(type(ROOT),'read_text',safe_read)
    result = load_dataset(ROOT/'data/demo-final')
    cutoff = pd.Timestamp(result['manifest']['config']['as_of'])
    for key in ('inventory','promotions'):
        assert (pd.to_datetime(result['tables'][key].available_at,utc=True)<=cutoff).all()
    assert result['tables']['order_economics'].order_id.nunique() == 1846


def test_changed_data_is_rejected_before_display(tmp_path):
    source = ROOT/'data/demo-final'
    shutil.copy2(source/'manifest.json',tmp_path/'manifest.json')
    (tmp_path/'processed').mkdir()
    # First file loaded: tamper without touching the real sample.
    (tmp_path/'processed/order_economics.parquet').write_bytes(b'changed data')
    with pytest.raises(ValueError,match='changed since validation'):
        load_dataset(tmp_path)
