import json
from pathlib import Path
import pytest
from luxe_lab.pipeline import analyze_rows
from luxe_lab.validation import ContractError
from luxe_lab.pipeline import MARTS
from luxe_lab.storage import literal, table_info

def dict_rows(con, query):
    cur = con.execute(query)
    columns = [d[0] for d in cur.description]
    return [dict(zip(columns,row)) for row in cur.fetchall()]

def test_independent_hand_calculation(financial, config):
    expected = json.loads((Path(__file__).parent/'fixtures/expected.json').read_text())
    con, _, warnings = analyze_rows(financial,config)
    try:
        for row in dict_rows(con,'SELECT * FROM mart.order_economics'):
            for key,value in expected['orders'][row['order_id']].items():
                assert row[key] == value
        for row in dict_rows(con,"SELECT * FROM mart.campaign_daily WHERE report_date='2026-07-06'"):
            for key,value in expected['campaigns_july_6'][row['campaign_id']].items():
                assert row[key] == value
        assert warnings == [{'code':'MISSING_COST','order_lines':1,'effect':'contribution is null, not zero'}]
        # Affiliate expense appears once, despite multiple order and media rows.
        assert con.execute('SELECT sum(spend_cents) FROM mart.campaign_daily').fetchone()[0] == 21000
        assert con.execute("SELECT contribution_before_media_cents FROM mart.campaign_daily WHERE report_date='2026-07-07'").fetchone()[0] is None
    finally:
        con.close()

def test_latest_snapshot_is_replacement(financial, config):
    con,_,_ = analyze_rows(financial,config)
    try:
        assert con.execute("SELECT conversions,revenue_cents FROM mart.platform_latest WHERE campaign_id='C01'").fetchone() == (1,100000)
    finally:
        con.close()

def test_multiple_lines_do_not_duplicate_orders_or_spend(financial, config):
    # Split O1's original quantities and charges across two lines; keep its refunds on line 1.
    first = financial['orders'][0]
    first[8:13] = [1,60000,10000,1000,1500]
    second = first[:]
    second[1] = '2'
    financial['orders'].append(second)
    con,_,_ = analyze_rows(financial, config)
    try:
        assert con.execute("SELECT orders,spend_cents,net_revenue_cents,contribution_after_media_cents FROM mart.campaign_daily WHERE campaign_id='C01'").fetchone() == (1,10000,50000,-5500)
        assert con.execute("SELECT count(*) FROM mart.order_attribution WHERE order_id='O1'").fetchone()[0] == 1
    finally:
        con.close()

def test_missing_media_stays_unknown(financial, config):
    financial['media'] = [r for r in financial['media'] if r[1] != 'C01']
    con,_,warnings = analyze_rows(financial, config)
    try:
        assert con.execute("SELECT spend_cents,contribution_after_media_cents FROM mart.campaign_daily WHERE campaign_id='C01'").fetchone() == (None,None)
        assert any(w['code'] == 'MISSING_MEDIA' for w in warnings)
    finally:
        con.close()

def test_zero_sales_day_remains_visible(financial, config):
    con,_,_ = analyze_rows(financial, config)
    try:
        assert con.execute("SELECT commerce_orders,commerce_net_cents,tracked_orders FROM mart.reconciliation_daily WHERE report_date='2026-07-08'").fetchone() == (0,0,0)
    finally:
        con.close()

def test_parquet_preserves_exact_values_and_money_types(financial, config, tmp_path):
    con,_,_ = analyze_rows(financial, config)
    try:
        for table in MARTS:
            path = tmp_path / f'{table}.parquet'
            before = table_info(con, f'mart.{table}')
            con.execute(f'COPY mart.{table} TO {literal(path)} (FORMAT PARQUET)')
            con.execute('CREATE OR REPLACE TABLE reloaded AS SELECT * FROM read_parquet(?)', [str(path)])
            assert table_info(con, 'reloaded') == before
            for name, kind, *_ in con.execute('DESCRIBE reloaded').fetchall():
                if name.endswith('_cents'):
                    assert kind == 'BIGINT', (table,name,kind)
    finally:
        con.close()

@pytest.mark.parametrize('mutation', ['duplicate_order','duplicate_cost','excess_refund','orphan_refund','negative_spend','recovery_without_return','excess_recovery','wrong_ad','unknown_platform_basis','inconsistent_order_header'])
def test_invalid_contracts_fail(financial,config,mutation):
    if mutation == 'duplicate_order': financial['orders'].append(financial['orders'][0][:])
    elif mutation == 'duplicate_cost': financial['costs'].append(financial['costs'][0][:])
    elif mutation == 'excess_refund': financial['refunds'][0][5] = 999999
    elif mutation == 'orphan_refund': financial['refunds'][0][1] = 'missing'
    elif mutation == 'negative_spend': financial['media'][0][5] = -1
    elif mutation == 'recovery_without_return': financial['refunds'][0][7] = 1
    elif mutation == 'excess_recovery': financial['refunds'][1][7] = 30001
    elif mutation == 'wrong_ad': financial['media'][0][2] = 'B1'
    elif mutation == 'unknown_platform_basis': financial['platform_snapshots'][0][6] = 'click_date'
    elif mutation == 'inconsistent_order_header':
        row=financial['orders'][0][:]; row[1]='2'; row[3]='someone_else'; financial['orders'].append(row)
    with pytest.raises(ContractError):
        analyze_rows(financial,config)

def test_unattributed_not_lost_and_zero_spend_not_infinite(financial,config):
    financial['sessions'] = [s for s in financial['sessions'] if s[1] != 'J2']
    financial['media'][0][5] = 0
    financial['media'][1][5] = 0
    con,_,_ = analyze_rows(financial,config)
    try:
        assert con.execute("SELECT campaign_id FROM mart.order_attribution WHERE order_id='O2'").fetchone()[0] == 'UNATTRIBUTED'
        assert con.execute("SELECT business_net_roas FROM mart.campaign_daily WHERE campaign_id='C01'").fetchone()[0] is None
        assert con.execute("SELECT net_revenue_cents FROM mart.campaign_daily WHERE campaign_id='UNATTRIBUTED'").fetchone()[0] == 50000
    finally:
        con.close()
