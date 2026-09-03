"""Milestone 3 policy screen: deterministic evidence, never a causal recommendation."""
from __future__ import annotations

import json
import hashlib
from pathlib import Path

import pandas as pd

from dashboard.data import strict_sum, summarize
from luxe_lab.storage import ROOT

DECISION_ORDER = {'Investigate': 0, 'Hold': 1, 'Controlled test candidate': 2}
RECORD_COLUMNS = ['campaign_id','campaign','decision','primary_reason','reason_codes','next_check','evidence_id',
    'conversion_mature_orders','return_mature_orders','available_units','tracking_gap_fraction',
    'mature_contribution_cents','stress_contribution_cents','baseline_spend_cents','maximum_test_spend_cents',
    'required_analyst_review','stop_condition','policy_version','policy_sha256','screen_version','source_class']


def policy_sha256(policy):
    payload = json.dumps(policy,sort_keys=True,separators=(',',':')).encode()
    return hashlib.sha256(payload).hexdigest()


def validate_policy(policy):
    fractions = ('maximum_test_budget_change_fraction', 'tracking_gap_fraction',
                 'unit_cost_stress_fraction', 'additional_refund_stress_fraction')
    if any(not 0 <= float(policy[name]) <= 1 for name in fractions):
        raise ValueError('Decision-policy fractions must be between zero and one.')
    if any(int(policy[name]) <= 0 for name in ('minimum_mature_orders', 'conversion_maturity_days',
                                                'return_maturity_days', 'budget_baseline_complete_days')):
        raise ValueError('Decision-policy day and order thresholds must be positive.')
    return policy


def load_policy(path: Path = ROOT/'config/decision-policy.json'):
    return validate_policy(json.loads(Path(path).read_text(encoding='utf-8')))


def _latest_inventory(inventory, end):
    eligible = inventory[pd.to_datetime(inventory.report_date).dt.date <= end]
    if eligible.empty:
        return None
    latest = eligible[pd.to_datetime(eligible.report_date) == pd.to_datetime(eligible.report_date).max()]
    return None if latest.available_units.isna().any() else int(latest.available_units.sum())


def _tracking_evidence(reconciliation, start, end):
    dates = pd.to_datetime(reconciliation.report_date).dt.date
    scoped = reconciliation[dates.between(start, end)]
    commerce = int(scoped.commerce_orders.sum()) if not scoped.empty else 0
    untracked = int(scoped.untracked_orders.sum()) if not scoped.empty else 0
    return commerce, untracked, (untracked / commerce if commerce else None)


def _distinct_orders(frame):
    return int(frame.order_id.nunique()) if not frame.empty else 0


def screen_campaigns(campaign_daily, order_economics, reconciliation, inventory,
                     start, end, as_of, policy, build_checks=()):
    """Apply investigate → hold → test-candidate gates to each paid campaign.

    Mature economics use only reporting dates old enough for the declared return
    horizon. Newer realized rows remain visible elsewhere but cannot qualify a test.
    """
    cutoff = pd.Timestamp(as_of)
    if cutoff.tzinfo is None:
        raise ValueError('as_of must have a timezone offset')
    return_boundary = (cutoff - pd.Timedelta(days=int(policy['return_maturity_days']))).date()
    conversion_boundary = cutoff - pd.Timedelta(days=int(policy['conversion_maturity_days']))
    available_units = _latest_inventory(inventory, end)
    commerce, untracked, tracking_gap = _tracking_evidence(reconciliation, start, end)
    tracking_alert = (commerce >= int(policy['tracking_gap_minimum_commerce_orders']) and
                      tracking_gap is not None and tracking_gap > float(policy['tracking_gap_fraction']))
    integrity_failures = [c for c in build_checks if int(c.get('violations', 0)) > 0]
    records = []
    daily_dates = pd.to_datetime(campaign_daily.report_date).dt.date
    scoped_daily = campaign_daily[daily_dates.between(start,end)]
    order_dates = pd.to_datetime(order_economics.report_date).dt.date
    scoped_orders = order_economics[order_dates.between(start,end)]
    for campaign_id, days in scoped_daily.groupby('campaign_id', sort=False):
        if campaign_id == 'UNATTRIBUTED':
            continue
        days = days.sort_values('report_date')
        orders = scoped_orders[scoped_orders.campaign_id == campaign_id].copy()
        order_headers = orders.drop_duplicates('order_id') if not orders.empty else orders
        purchase_time = pd.to_datetime(order_headers.purchased_at, utc=True) if not orders.empty else pd.Series(dtype='datetime64[ns, UTC]')
        touch_time = (pd.to_datetime(order_headers.touch_at, utc=True) if not orders.empty and 'touch_at' in order_headers
                      else pd.Series(pd.NaT, index=order_headers.index, dtype='datetime64[ns, UTC]'))
        conversion_mature_orders = _distinct_orders(order_headers[touch_time <= conversion_boundary])
        return_mature_orders = _distinct_orders(order_headers[purchase_time <= cutoff - pd.Timedelta(days=int(policy['return_maturity_days']))])
        mature_days = days[pd.to_datetime(days.report_date).dt.date <= min(end, return_boundary)]
        mature_totals = summarize(mature_days) if not mature_days.empty else None
        mature_lines = orders[pd.to_datetime(orders.purchased_at, utc=True) <= cutoff - pd.Timedelta(days=int(policy['return_maturity_days']))] if not orders.empty else orders
        baseline_days = days.tail(int(policy['budget_baseline_complete_days']))
        baseline_complete = (baseline_days.report_date.nunique() == int(policy['budget_baseline_complete_days']) and
                             baseline_days.media_present.fillna(False).all() and not baseline_days.spend_cents.isna().any())
        baseline_spend = strict_sum(baseline_days.spend_cents) if baseline_complete else None

        investigate = []
        if integrity_failures and policy['unresolved_data_errors_block_growth']:
            investigate.append(('DATA_INTEGRITY', 'A source-contract or build check is unresolved.'))
        if int(days.missing_cost_lines.sum()) and policy['missing_costs_block_growth']:
            investigate.append(('MISSING_COST', 'At least one selected order line has no known unit cost.'))
        if not days.media_present.fillna(False).all() or days.spend_cents.isna().any():
            investigate.append(('MISSING_MEDIA', 'At least one selected campaign day has no complete media record.'))
        selected_contribution = strict_sum(days.contribution_after_media_cents)
        if selected_contribution is not None and selected_contribution < 0:
            investigate.append(('NEGATIVE_CONTRIBUTION', 'Observed contribution after media is negative in the selected period.'))
        if available_units is None:
            investigate.append(('INVENTORY_UNKNOWN', 'No inventory observation is available by the selected end date.'))
        elif available_units == 0:
            investigate.append(('OUT_OF_STOCK', 'The latest available inventory observation is zero units.'))
        if tracking_alert:
            investigate.append(('TRACKING_GAP', f'{untracked} of {commerce} site-wide commerce orders lack a visible purchase event ({tracking_gap:.1%}).'))

        hold = []
        if conversion_mature_orders < int(policy['minimum_mature_orders']):
            hold.append(('CONVERSION_SAMPLE', f'{conversion_mature_orders} conversion-mature orders; policy requires {policy["minimum_mature_orders"]}.'))
        if return_mature_orders < int(policy['minimum_mature_orders']):
            hold.append(('RETURN_SAMPLE', f'{return_mature_orders} return-mature orders; policy requires {policy["minimum_mature_orders"]}.'))
        if not baseline_complete:
            hold.append(('BASELINE_INCOMPLETE', f'A complete {policy["budget_baseline_complete_days"]}-day media baseline is unavailable.'))

        stress_contribution = None
        if mature_totals and mature_totals['contribution_after_media_cents'] is not None:
            mature_cogs = strict_sum(mature_lines.net_cogs_cents) if not mature_lines.empty else 0
            mature_booked = mature_totals['booked_revenue_cents']
            if mature_cogs is not None and mature_booked is not None:
                stress_penalty = round(mature_cogs * float(policy['unit_cost_stress_fraction'])) + round(
                    mature_booked * float(policy['additional_refund_stress_fraction']))
                stress_contribution = mature_totals['contribution_after_media_cents'] - stress_penalty
                if stress_contribution < 0:
                    hold.append(('SENSITIVITY_REVERSAL', 'Contribution turns negative under the declared cost and additional-refund stress.'))
        else:
            hold.append(('MATURE_ECONOMICS_UNKNOWN', 'Complete contribution is unavailable for the return-mature measurement window.'))

        if investigate:
            decision, gates = 'Investigate', investigate + hold
            next_check = 'Resolve the first integrity or economics issue, then rerun the screen.'
        elif hold:
            decision, gates = 'Hold', hold
            next_check = 'Wait for mature evidence or complete the missing baseline, then rerun the screen.'
        else:
            decision, gates = 'Controlled test candidate', []
            next_check = 'Analyst review and a fresh stock check are required before any bounded test.'
        maximum_spend = (round(baseline_spend * (1 + float(policy['maximum_test_budget_change_fraction'])))
                         if decision == 'Controlled test candidate' else None)
        cid = str(campaign_id)
        records.append({
            'campaign_id': cid, 'campaign': days.campaign.iloc[0], 'decision': decision,
            'primary_reason': gates[0][1] if gates else 'All declared integrity, maturity, sensitivity and baseline gates pass.',
            'reason_codes': '|'.join(code for code, _ in gates) if gates else 'ALL_GATES_PASS',
            'next_check': next_check, 'evidence_id': f'M3-{cid}-{cutoff:%Y%m%d}',
            'conversion_mature_orders': conversion_mature_orders, 'return_mature_orders': return_mature_orders,
            'available_units': available_units, 'tracking_gap_fraction': tracking_gap,
            'mature_contribution_cents': None if mature_totals is None else mature_totals['contribution_after_media_cents'],
            'stress_contribution_cents': stress_contribution, 'baseline_spend_cents': baseline_spend,
            'maximum_test_spend_cents': maximum_spend,
            'required_analyst_review': True,
            'stop_condition': 'Pause if cumulative contribution becomes negative, inventory is unavailable, or the tracking gap breaches policy.',
            'policy_version': policy['policy_version'], 'policy_sha256': policy_sha256(policy),
            'screen_version': '1.0.0', 'source_class': 'policy_screen_from_synthetic_data',
        })
    if not records:
        return pd.DataFrame(columns=RECORD_COLUMNS)
    return pd.DataFrame(records,columns=RECORD_COLUMNS).sort_values(
        ['decision', 'campaign_id'], key=lambda s: s.map(DECISION_ORDER) if s.name == 'decision' else s
    ).reset_index(drop=True)


def decision_export(records, start, end, manifest):
    result = records.copy()
    result['report_start'] = str(start)
    result['report_end'] = str(end)
    result['as_of'] = manifest['config']['as_of']
    result['dataset_sha256'] = manifest['dataset_sha256']
    result['claim_boundary'] = 'Policy screen only; no causal lift estimate or authorization to change spend'
    return result.to_csv(index=False).encode('utf-8-sig')
