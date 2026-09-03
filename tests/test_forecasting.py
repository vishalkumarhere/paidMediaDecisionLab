import pandas as pd
import pytest

from dashboard.forecasting import (
    ForecastUnavailable, build_forecast, build_scenario, load_forecast_policy,
    validate_forecast_policy,
)


def weekly_history(days=84):
    dates = pd.date_range('2026-01-01',periods=days,freq='D')
    pattern = [8,9,10,11,12,14,13]
    return pd.DataFrame({
        'report_date':dates,
        'campaign_id':'C01',
        'orders':[pattern[d.weekday()] for d in dates],
        'spend_cents':[10000+100*d.weekday() for d in dates],
        'net_revenue_cents':[50000+500*d.weekday() for d in dates],
        'contribution_after_media_cents':[20000+200*d.weekday() for d in dates],
    })


def test_weekday_baseline_and_time_ordered_evaluation_are_exact():
    result = build_forecast(weekly_history(),pd.Timestamp('2026-03-25'),load_forecast_policy())
    assert len(result['future']) == 7
    assert (result['summary'].wape == 0).all()
    assert (result['summary'].mae == 0).all()
    assert (result['summary'].empirical_coverage == 1).all()
    assert (result['backtest'].forecast_date > result['backtest'].origin).all()


def test_rows_after_origin_cannot_change_forecast():
    frame = weekly_history()
    origin = pd.Timestamp('2026-03-01')
    first = build_forecast(frame,origin,load_forecast_policy())['future']
    changed = frame.copy()
    changed.loc[changed.report_date>origin,['orders','spend_cents','net_revenue_cents','contribution_after_media_cents']] = 10**9
    second = build_forecast(changed,origin,load_forecast_policy())['future']
    pd.testing.assert_frame_equal(first,second)


def test_unknown_history_is_not_imputed():
    frame = weekly_history()
    frame.loc[20,'contribution_after_media_cents'] = None
    with pytest.raises(ForecastUnavailable,match='unknown values'):
        build_forecast(frame,frame.report_date.max(),load_forecast_policy())


def test_scenario_respects_inventory_and_keeps_assumptions_explicit():
    summary = pd.DataFrame([
        {'target':'orders','point':20,'lower':10,'upper':30},
        {'target':'spend_cents','point':100000,'lower':90000,'upper':110000},
        {'target':'net_revenue_cents','point':400000,'lower':300000,'upper':500000},
        {'target':'contribution_after_media_cents','point':50000,'lower':30000,'upper':70000},
    ])
    policy = load_forecast_policy()
    scenario = build_scenario(summary,.10,1000,5000,3,policy)
    assert scenario['unconstrained_incremental_orders'] == 10
    assert scenario['incremental_orders'] == 3
    assert scenario['inventory_limited'] is True
    assert scenario['scenario_contribution_cents'] == 55000
    assert scenario['scenario_type'] == 'hypothetical_assumption_not_causal'
    reduction = build_scenario(summary,-.10,1000,5000,100,policy)
    assert reduction['incremental_orders'] == -10
    assert reduction['scenario_contribution_cents'] == 10000


def test_invalid_forecast_policy_and_scenario_are_rejected():
    policy = load_forecast_policy()
    invalid = dict(policy,interval_coverage=1)
    with pytest.raises(ValueError,match='between zero and one'):
        validate_forecast_policy(invalid)
    summary = pd.DataFrame([
        {'target':'orders','point':20,'lower':10,'upper':30},
        {'target':'spend_cents','point':100000,'lower':90000,'upper':110000},
        {'target':'net_revenue_cents','point':400000,'lower':300000,'upper':500000},
        {'target':'contribution_after_media_cents','point':50000,'lower':30000,'upper':70000},
    ])
    with pytest.raises(ValueError,match='between'):
        build_scenario(summary,.20,1000,5000,10,policy)
