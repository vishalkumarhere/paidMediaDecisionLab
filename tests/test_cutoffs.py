from copy import deepcopy
from datetime import datetime, timezone
import pytest
from luxe_lab.generator import utc
from luxe_lab.pipeline import MARTS, analyze_rows
from luxe_lab.storage import table_info

def signatures(data, config):
    con,_,_ = analyze_rows(data,config)
    try:
        return {t:table_info(con,f'mart.{t}')['logical_sha256'] for t in MARTS}
    finally:
        con.close()

def test_future_refund_and_snapshot_cannot_change_past(financial,config):
    config['as_of']='2026-07-08T12:30:00+00:00'
    before=signatures(financial,config)
    financial['refunds'][0][5] = 10000  # Occurred, but not yet available at 12:30.
    financial['refunds'][1][7] = 15000
    financial['platform_snapshots'][1][5] = 50000
    assert signatures(financial,config) == before

def test_future_cost_and_order_cannot_change_past(financial,config):
    config['as_of']='2026-07-07T10:30:00+00:00'
    financial['costs'][1][3] = '2026-07-09T00:00:00Z'
    before=signatures(financial,config)
    financial['costs'][1][2] = 19000
    financial['orders'][3][9] = 70000
    assert signatures(financial,config) == before

def test_refund_becomes_visible_only_when_available(financial,config):
    config['as_of']='2026-07-08T12:30:00+00:00'
    con,_,_ = analyze_rows(financial,config)
    assert con.execute("SELECT refunded_cents FROM mart.order_economics WHERE order_id='O1'").fetchone()[0] == 0
    con.close()
    config['as_of']='2026-07-08T13:00:00+00:00'
    con,_,_ = analyze_rows(financial,config)
    assert con.execute("SELECT refunded_cents FROM mart.order_economics WHERE order_id='O1'").fetchone()[0] == 20000
    con.close()

@pytest.mark.parametrize('at,expected',[('2026-06-29T15:00:00Z','C01'),('2026-06-29T14:59:59Z','UNATTRIBUTED')])
def test_seven_day_boundary(financial,config,at,expected):
    # O2 purchases July 6 at 15:00 UTC; eligible exactly seven elapsed days earlier.
    s=financial['sessions'][1]
    s[3]='C01';s[4]='A1';s[5]=at;s[6]=at
    con,_,_=analyze_rows(financial,config)
    try:
        assert con.execute("SELECT campaign_id FROM mart.order_attribution WHERE order_id='O2'").fetchone()[0] == expected
    finally:
        con.close()

def test_latest_touch_and_no_post_purchase_credit(financial,config):
    s=financial['sessions'][0][:]
    s[0]='SX';s[3]='C06';s[4]='B1';s[5]='2026-07-06T13:59:00Z';s[6]=s[5]
    financial['sessions'].append(s)
    later=s[:];later[0]='SY';later[3]='C01';later[4]='A1';later[5]='2026-07-06T14:01:00Z';later[6]=later[5]
    financial['sessions'].append(later)
    con,_,_=analyze_rows(financial,config)
    try:
        assert con.execute("SELECT campaign_id FROM mart.order_attribution WHERE order_id='O1'").fetchone()[0] == 'C06'
    finally:
        con.close()

def test_dst_and_midnight_reporting_date(financial,config):
    assert utc(datetime(2026,1,5).date(),12).hour == 17
    assert utc(datetime(2026,7,5).date(),12).hour == 16
    # UTC July 7 01:00 is still July 6 in New York; use that day's costs.
    financial['orders'][0][5]='2026-07-07T01:00:00Z'
    financial['orders'][0][6]='2026-07-07T02:00:00Z'
    con,_,_=analyze_rows(financial,config)
    try:
        assert str(con.execute("SELECT report_date FROM mart.order_economics WHERE order_id='O1'").fetchone()[0]) == '2026-07-06'
    finally:
        con.close()

