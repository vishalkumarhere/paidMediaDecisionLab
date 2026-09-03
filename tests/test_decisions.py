import pandas as pd

from dashboard.decisions import decision_export, load_policy, screen_campaigns, validate_policy
from dashboard.data import CAMPAIGN_NAMES, load_dataset
from luxe_lab.pipeline import analyze_rows
from luxe_lab.storage import ROOT


def sample_screen():
    bundle = load_dataset(ROOT/'data/demo-final')
    tables = bundle['tables']
    manifest = bundle['manifest']
    daily = tables['campaign_daily'][tables['campaign_daily'].campaign_id!='UNATTRIBUTED']
    return screen_campaigns(
        daily, tables['order_economics'], tables['reconciliation_daily'], tables['inventory'],
        pd.Timestamp('2026-05-04').date(), pd.Timestamp('2026-08-23').date(),
        manifest['config']['as_of'], load_policy(), manifest['checks'],
    ), manifest


def test_sample_screen_is_traceable_and_never_reads_labels():
    records, manifest = sample_screen()
    assert set(records.campaign_id) == {'C01','C02','C03','C04','C05','C06'}
    assert set(records.decision) <= {'Investigate','Hold','Controlled test candidate'}
    assert records.evidence_id.str.match(r'M3-C\d\d-20260824').all()
    assert records.required_analyst_review.all()
    assert records.source_class.eq('policy_screen_from_synthetic_data').all()
    assert records.maximum_test_spend_cents[records.decision!='Controlled test candidate'].isna().all()
    exported = decision_export(records,'2026-05-04','2026-08-23',manifest).decode('utf-8-sig')
    assert manifest['dataset_sha256'] in exported
    assert 'no causal lift estimate' in exported
    assert 'evaluation_only' not in exported


def test_gate_priority_investigate_before_hold():
    bundle = load_dataset(ROOT/'data/demo-final')
    tables, manifest = bundle['tables'], bundle['manifest']
    daily = tables['campaign_daily'][tables['campaign_daily'].campaign_id=='C01'].copy()
    daily.loc[daily.index[0], 'contribution_after_media_cents'] = -10**9
    result = screen_campaigns(daily,tables['order_economics'],tables['reconciliation_daily'],tables['inventory'],
        daily.report_date.min().date(),daily.report_date.max().date(),manifest['config']['as_of'],load_policy())
    assert result.iloc[0].decision == 'Investigate'
    assert result.iloc[0].reason_codes.split('|')[0] == 'NEGATIVE_CONTRIBUTION'


def test_tracking_and_inventory_issues_block_growth():
    records, manifest = sample_screen()
    bundle = load_dataset(ROOT/'data/demo-final')
    tables = bundle['tables']
    daily = tables['campaign_daily'][tables['campaign_daily'].campaign_id=='C01'].copy()
    reconciliation = pd.DataFrame([{'report_date':daily.report_date.min(),'commerce_orders':10,'untracked_orders':3}])
    inventory = pd.DataFrame([{'report_date':daily.report_date.max(),'available_units':0}])
    result = screen_campaigns(daily,tables['order_economics'],reconciliation,inventory,
        daily.report_date.min().date(),daily.report_date.max().date(),manifest['config']['as_of'],load_policy())
    assert result.iloc[0].decision == 'Investigate'
    assert 'OUT_OF_STOCK' in result.iloc[0].reason_codes
    assert 'TRACKING_GAP' in result.iloc[0].reason_codes


def test_policy_validation_rejects_invalid_fraction():
    policy = load_policy()
    policy['tracking_gap_fraction'] = 1.1
    try:
        validate_policy(policy)
    except ValueError as exc:
        assert 'between zero and one' in str(exc)
    else:
        raise AssertionError('invalid policy was accepted')


def test_hand_fixture_screens_equal_roas_different_economics(financial, config):
    con, _, _ = analyze_rows(financial,config)
    try:
        daily = con.execute("SELECT * FROM mart.campaign_daily WHERE report_date='2026-07-06'").df()
        orders = con.execute("""SELECT e.*,a.campaign_id,a.touch_at
            FROM mart.order_economics e JOIN mart.order_attribution a USING(order_id)
            WHERE e.report_date='2026-07-06'""").df()
        reconciliation = con.execute("SELECT * FROM mart.reconciliation_daily WHERE report_date='2026-07-06'").df()
    finally:
        con.close()
    daily['campaign'] = daily.campaign_id.map(CAMPAIGN_NAMES)
    inventory = pd.DataFrame([{'report_date':pd.Timestamp('2026-07-06'),'available_units':100}])
    result = screen_campaigns(daily,orders,reconciliation,inventory,
        pd.Timestamp('2026-07-06').date(),pd.Timestamp('2026-07-06').date(),config['as_of'],load_policy())
    c01 = result[result.campaign_id=='C01'].iloc[0]
    c06 = result[result.campaign_id=='C06'].iloc[0]
    assert c01.decision == 'Investigate'
    assert c01.reason_codes.startswith('NEGATIVE_CONTRIBUTION')
    assert c06.decision == 'Hold'
    assert c06.reason_codes.startswith('CONVERSION_SAMPLE')
