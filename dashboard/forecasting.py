"""Leakage-safe seasonal baselines and bounded, assumption-driven scenarios."""
from __future__ import annotations

import hashlib
import json
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path

import pandas as pd

from luxe_lab.storage import ROOT

TARGETS = ('orders','spend_cents','net_revenue_cents','contribution_after_media_cents')
TARGET_LABELS = {
    'orders':'Orders', 'spend_cents':'Media spend', 'net_revenue_cents':'Net revenue',
    'contribution_after_media_cents':'Contribution after media',
}


class ForecastUnavailable(ValueError):
    pass


def validate_forecast_policy(policy):
    if not 0 < float(policy['interval_coverage']) < 1:
        raise ValueError('Forecast interval coverage must be between zero and one.')
    if not 0 < float(policy['calibration_fraction']) < 1:
        raise ValueError('Calibration fraction must be between zero and one.')
    if float(policy['minimum_spend_change_fraction']) > 0 or float(policy['maximum_spend_change_fraction']) < 0:
        raise ValueError('Spend bounds must include zero.')
    for name in ('horizon_days','lookback_days','minimum_history_days','minimum_backtest_origins'):
        if int(policy[name]) <= 0:
            raise ValueError('Forecast day and origin thresholds must be positive.')
    return policy


def load_forecast_policy(path: Path = ROOT/'config/forecast-policy.json'):
    return validate_forecast_policy(json.loads(Path(path).read_text(encoding='utf-8')))


def forecast_policy_sha256(policy):
    payload = json.dumps(policy,sort_keys=True,separators=(',',':')).encode()
    return hashlib.sha256(payload).hexdigest()


def aggregate_daily(frame):
    """Create one complete calendar series while preserving unknown totals."""
    if frame.empty:
        raise ForecastUnavailable('No paid-campaign history is available for this selection.')
    rows = []
    for day, group in frame.groupby('report_date',sort=True):
        row = {'period':pd.Timestamp(day).normalize()}
        for target in TARGETS:
            values = group[target]
            row[target] = None if values.isna().any() else float(values.sum())
        rows.append(row)
    daily = pd.DataFrame(rows).sort_values('period').reset_index(drop=True)
    expected = pd.date_range(daily.period.min(),daily.period.max(),freq='D')
    if daily.period.tolist() != expected.tolist():
        raise ForecastUnavailable('The forecast requires a continuous daily campaign series; missing dates cannot be filled as zero.')
    return daily


def _predict(train, forecast_date, target, lookback_days):
    recent = train[(train.period < forecast_date) &
                   (train.period >= forecast_date-pd.Timedelta(days=lookback_days))]
    same_weekday = recent[recent.period.dt.weekday == forecast_date.weekday()].tail(4)
    source = same_weekday if len(same_weekday) >= 2 else recent
    if source.empty or source[target].isna().any():
        raise ForecastUnavailable(f'{TARGET_LABELS[target]} has incomplete history in the model window.')
    return float(source[target].mean())


def _quantile(series, quantile):
    return float(pd.Series(series,dtype='float64').quantile(quantile,interpolation='linear'))


def forecast_target(daily, target, end, policy):
    end = pd.Timestamp(end).normalize()
    history = daily[daily.period <= end].copy()
    horizon = int(policy['horizon_days'])
    minimum = int(policy['minimum_history_days'])
    if len(history) < minimum + horizon:
        raise ForecastUnavailable(f'{TARGET_LABELS[target]} needs at least {minimum+horizon} complete days for training and backtesting.')
    if history[target].isna().any():
        raise ForecastUnavailable(f'{TARGET_LABELS[target]} contains unknown values; the app will not impute them.')

    origins = history.period.iloc[minimum-1:len(history)-horizon].tolist()
    if len(origins) < int(policy['minimum_backtest_origins']):
        raise ForecastUnavailable('Too few rolling forecast origins are available for time-ordered evaluation.')
    backtest = []
    for origin in origins:
        train = history[history.period <= origin]
        for step in range(1,horizon+1):
            forecast_date = origin + pd.Timedelta(days=step)
            predicted = _predict(train,forecast_date,target,int(policy['lookback_days']))
            actual = float(history.loc[history.period==forecast_date,target].iloc[0])
            backtest.append({'origin':origin,'horizon_day':step,'forecast_date':forecast_date,
                             'predicted':predicted,'actual':actual,'error':actual-predicted})
    backtest = pd.DataFrame(backtest)
    origin_values = sorted(backtest.origin.unique())
    calibration_count = max(1,min(len(origin_values)-1,round(len(origin_values)*float(policy['calibration_fraction']))))
    calibration_origins = set(origin_values[:calibration_count])
    calibration = backtest[backtest.origin.isin(calibration_origins)]
    evaluation = backtest[~backtest.origin.isin(calibration_origins)]
    alpha = (1-float(policy['interval_coverage']))/2

    future = []
    for step in range(1,horizon+1):
        forecast_date = end + pd.Timedelta(days=step)
        predicted = _predict(history,forecast_date,target,int(policy['lookback_days']))
        errors = calibration.loc[calibration.horizon_day==step,'error']
        lower = predicted + _quantile(errors,alpha)
        upper = predicted + _quantile(errors,1-alpha)
        if target != 'contribution_after_media_cents':
            lower, upper = max(0,lower), max(0,upper)
        future.append({'period':forecast_date,'point':predicted,'lower':min(lower,upper),'upper':max(lower,upper)})
    future = pd.DataFrame(future)

    cal_totals = calibration.groupby('origin').agg(predicted=('predicted','sum'),actual=('actual','sum'))
    cal_total_errors = cal_totals.actual-cal_totals.predicted
    total_point = float(future.point.sum())
    total_lower = total_point + _quantile(cal_total_errors,alpha)
    total_upper = total_point + _quantile(cal_total_errors,1-alpha)
    if target != 'contribution_after_media_cents':
        total_lower, total_upper = max(0,total_lower), max(0,total_upper)
    eval_totals = evaluation.groupby('origin').agg(predicted=('predicted','sum'),actual=('actual','sum'))
    eval_errors = eval_totals.actual-eval_totals.predicted
    lower_error = _quantile(cal_total_errors,alpha)
    upper_error = _quantile(cal_total_errors,1-alpha)
    denominator = float(eval_totals.actual.abs().sum())
    summary = {
        'target':target, 'label':TARGET_LABELS[target], 'point':total_point,
        'lower':min(total_lower,total_upper), 'upper':max(total_lower,total_upper),
        'wape':None if denominator == 0 else float(eval_errors.abs().sum()/denominator),
        'mae':float(eval_errors.abs().mean()), 'bias':float(eval_errors.mean()),
        'empirical_coverage':float(((eval_totals.actual >= eval_totals.predicted+lower_error) &
                                    (eval_totals.actual <= eval_totals.predicted+upper_error)).mean()),
        'calibration_origins':len(calibration_origins),
        'evaluation_origins':int(evaluation.origin.nunique()),
    }
    return future, summary, backtest


def build_forecast(frame, end, policy):
    daily = aggregate_daily(frame)
    future = None
    summaries, backtests = [], []
    for target in TARGETS:
        target_future, summary, backtest = forecast_target(daily,target,end,policy)
        renamed = target_future.rename(columns={name:f'{target}_{name}' for name in ('point','lower','upper')})
        future = renamed if future is None else future.merge(renamed,on='period',validate='one_to_one')
        summaries.append(summary)
        backtest['target'] = target
        backtests.append(backtest)
    return {'history':daily,'future':future,'summary':pd.DataFrame(summaries),'backtest':pd.concat(backtests,ignore_index=True)}


def _cents(value):
    return int(Decimal(str(value)).quantize(Decimal('1'),rounding=ROUND_HALF_UP))


def build_scenario(summary, spend_change_fraction, marginal_cost_per_order_cents,
                   marginal_contribution_before_media_per_order_cents, incremental_order_capacity,
                   policy):
    minimum, maximum = float(policy['minimum_spend_change_fraction']), float(policy['maximum_spend_change_fraction'])
    change = float(spend_change_fraction)
    if not minimum <= change <= maximum:
        raise ValueError(f'Spend change must remain between {minimum:.0%} and {maximum:.0%}.')
    if marginal_cost_per_order_cents <= 0:
        raise ValueError('Marginal cost per extra order must be positive.')
    if marginal_contribution_before_media_per_order_cents < 0 or incremental_order_capacity < 0:
        raise ValueError('Contribution and inventory-capacity assumptions cannot be negative.')
    indexed = summary.set_index('target')
    baseline_spend = float(indexed.loc['spend_cents','point'])
    baseline_orders = float(indexed.loc['orders','point'])
    baseline_contribution = float(indexed.loc['contribution_after_media_cents','point'])
    contribution_lower = float(indexed.loc['contribution_after_media_cents','lower'])
    contribution_upper = float(indexed.loc['contribution_after_media_cents','upper'])
    spend_delta = _cents(baseline_spend*change)
    unconstrained_orders = spend_delta/float(marginal_cost_per_order_cents)
    if unconstrained_orders >= 0:
        order_delta = min(unconstrained_orders,float(incremental_order_capacity))
    else:
        order_delta = max(unconstrained_orders,-baseline_orders)
    inventory_limited = order_delta < unconstrained_orders
    contribution_delta = order_delta*float(marginal_contribution_before_media_per_order_cents)-spend_delta
    return {
        'baseline_spend_cents':_cents(baseline_spend), 'scenario_spend_cents':_cents(baseline_spend+spend_delta),
        'spend_change_fraction':change, 'spend_delta_cents':spend_delta,
        'baseline_orders':baseline_orders, 'scenario_orders':max(0,baseline_orders+order_delta),
        'incremental_orders':order_delta, 'unconstrained_incremental_orders':unconstrained_orders,
        'incremental_order_capacity':int(incremental_order_capacity), 'inventory_limited':inventory_limited,
        'marginal_cost_per_order_cents':int(marginal_cost_per_order_cents),
        'marginal_contribution_before_media_per_order_cents':int(marginal_contribution_before_media_per_order_cents),
        'baseline_contribution_cents':_cents(baseline_contribution),
        'scenario_contribution_cents':_cents(baseline_contribution+contribution_delta),
        'scenario_contribution_lower_cents':_cents(contribution_lower+contribution_delta),
        'scenario_contribution_upper_cents':_cents(contribution_upper+contribution_delta),
        'incremental_contribution_cents':_cents(contribution_delta),
        'break_even_marginal_cost_per_order_cents':int(marginal_contribution_before_media_per_order_cents),
        'scenario_type':'hypothetical_assumption_not_causal',
        'forecast_version':policy['forecast_version'], 'forecast_policy_sha256':forecast_policy_sha256(policy),
    }


def forecast_export(bundle, scenario, selected_campaigns, end, manifest, policy):
    result = bundle['future'].copy()
    result['forecast_origin'] = str(end)
    result['campaign_ids'] = '|'.join(selected_campaigns)
    result['as_of'] = manifest['config']['as_of']
    result['dataset_sha256'] = manifest['dataset_sha256']
    result['forecast_version'] = policy['forecast_version']
    result['forecast_policy_sha256'] = forecast_policy_sha256(policy)
    result['scenario_json'] = json.dumps(scenario,sort_keys=True,separators=(',',':'))
    result['claim_boundary'] = 'Baseline continuation forecast plus user-assumption scenario; no causal lift or spend authorization'
    return result.to_csv(index=False).encode('utf-8-sig')
