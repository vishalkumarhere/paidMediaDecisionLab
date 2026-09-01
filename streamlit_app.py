"""Luxe Café: a read-only, synthetic paid-media analytics interface."""
from datetime import date, timedelta

import pandas as pd
import streamlit as st

from dashboard import charts
from dashboard.presentation import plot, table
from dashboard.data import (
    CAMPAIGN_NAMES, campaign_export, campaign_summary, discover_runs, economics_steps,
    filter_campaigns, filter_dates, load_dataset, period_summary, ratio, revision, strict_sum, summarize,
)
from luxe_lab.storage import ROOT

st.set_page_config(page_title='Luxe Café | Paid media lab',page_icon=':material/coffee:',layout='wide')


@st.cache_data(ttl=600,max_entries=6,show_spinner=False)
def cached_dataset(path, version):
    return load_dataset(path)


def money(cents, decimals=0):
    if cents is None or pd.isna(cents):
        return 'Unknown'
    value = cents/100
    return f'-${abs(value):,.{decimals}f}' if value < 0 else f'${value:,.{decimals}f}'


def metric_cards(frame, prefix=''):
    totals = summarize(frame)
    daily = period_summary(frame,'Weekly')
    fields = [('Media spend','spend_cents',':material/ads_click:'),
              ('Net product revenue','net_revenue_cents',':material/payments:'),
              ('Contribution','contribution_after_media_cents',':material/account_balance_wallet:'),
              ('Business net ROAS','business_net_roas',':material/query_stats:')]
    for col,(label,field,icon) in zip(st.columns(4,gap='small'),fields):
        with col:
            value = totals[field]
            display = ('Unknown' if value is None else f'{value:.2f}x') if field=='business_net_roas' else money(value)
            series = daily[field].dropna().tolist() if field in daily else []
            st.metric(label,display,icon=icon,border=True,width='stretch',height='stretch',
                      chart_data=series or None,chart_type='line',
                      help='Realized-to-date synthetic data. Contribution subtracts product costs, fulfillment, fees, returns and media expense; fixed overhead is excluded. Unknown inputs remain unknown.')
    pacing = totals['pacing_ratio']
    st.caption(f"{totals['orders']:,} fulfilled orders  ·  "
               + (f"{pacing:.0%} of dated media plan  ·  " if pacing is not None else '')
               + 'Purchase-date revenue / delivery-date spend. No causal lift is measured.')
    if totals['missing_cost_lines'] or totals['contribution_after_media_cents'] is None:
        st.warning('Some cost or media inputs are missing. Complete contribution is unknown; no missing value has been replaced with zero.',icon=':material/warning:')
    return totals


def performance_table(summary,compact=False):
    cols = ['campaign','channel','orders','spend_cents','net_revenue_cents','business_net_roas','contribution_after_media_cents','status']
    display = summary[cols].copy()
    display = display.rename(columns={'campaign':'Campaign','channel':'Channel','orders':'Orders',
        'spend_cents':'Spend','net_revenue_cents':'Net revenue','business_net_roas':'Net ROAS',
        'contribution_after_media_cents':'Contribution','status':'Economics'})
    for column in ('Spend','Net revenue','Contribution'):
        display[column] = pd.to_numeric(display[column],errors='coerce')/100
    if compact:
        display = display[['Campaign','Net ROAS','Contribution']]
    table(display,money_columns=['Spend','Net revenue','Contribution'],ratio_columns=['Net ROAS'])


def show_waterfall(order_rows, media_spend):
    steps = economics_steps(order_rows,media_spend)
    if steps is None:
        st.info('The waterfall needs complete unit costs and media spend. Known revenue remains visible in the data view.')
    else:
        plot(charts.waterfall(steps))
        st.caption('Product cost is net of recovered returned inventory. Affiliate commission is counted once, in media expense.')


with st.sidebar:
    st.title(':material/coffee: Luxe Café')
    st.caption('PAID MEDIA DECISION LAB')
    st.badge('Independent portfolio',color='green')
    runs = discover_runs()
    if not runs:
        st.error('No validated dataset found. Generate a run first with python -m luxe_lab build.')
        st.stop()
    default_run = next((i for i,p in enumerate(runs) if p.name=='demo-final'),0)
    selected_run = st.selectbox('Dataset',runs,index=default_run,format_func=lambda p:p.name.replace('-',' ').capitalize(),key='dataset')

try:
    with st.spinner('Opening verified campaign data…'):
        bundle = cached_dataset(str(selected_run),revision(selected_run))
except (OSError,ValueError,KeyError) as exc:
    st.error(f'Dataset unavailable: {exc}')
    st.caption('Keep the original sample intact, or create a fresh validated run. No data is modified by this app.')
    st.stop()

manifest = bundle['manifest']
tables = bundle['tables']
dimension = bundle['dimension']
cfg = manifest['config']
minimum = date.fromisoformat(cfg['report_start'])
maximum = min(date.fromisoformat(cfg['report_end']),pd.Timestamp(cfg['as_of']).tz_convert(cfg['timezone']).date())
if st.session_state.get('_run') != str(selected_run):
    for key in ('dates','period','campaigns','channel','include_unattributed','detail_campaign','order_choice'):
        st.session_state.pop(key,None)
    st.session_state['_run'] = str(selected_run)

with st.sidebar:
    st.subheader('Explore the data')
    preset = st.selectbox('Reporting window',['Full history','Last 28 days','Last 7 days','Custom'],key='period')
    if preset=='Custom':
        bounds = st.date_input('Dates',(minimum,maximum),min_value=minimum,max_value=maximum,key='dates')
        if len(bounds)!=2:
            st.info('Choose an end date to complete the range.')
            st.stop()
        start,end = bounds
    else:
        end = maximum
        start = minimum if preset=='Full history' else max(minimum,maximum-timedelta(days=27 if preset=='Last 28 days' else 6))
    channel = st.selectbox('Channel',['All paid channels','Google','Meta','Affiliate'],key='channel')
    include_unattributed = st.checkbox('Include unattributed sales',key='include_unattributed',help='These sales have no eligible observed paid click. Their inclusion changes the revenue scope.')
    available = dimension[dimension.channel!='Unattributed']
    if channel!='All paid channels':
        available = available[available.channel==channel]
    options = available.campaign_id.tolist()+(['UNATTRIBUTED'] if include_unattributed else [])
    if 'campaigns' in st.session_state:
        st.session_state['campaigns'] = [cid for cid in st.session_state['campaigns'] if cid in options]
        if st.session_state.get('_channel') != (channel,include_unattributed):
            st.session_state['campaigns'] = options
    st.session_state['_channel'] = (channel,include_unattributed)
    selected = st.multiselect('Campaigns',options,default=None if 'campaigns' in st.session_state else options,format_func=lambda cid:CAMPAIGN_NAMES.get(cid,cid),key='campaigns')
    if st.button('Reset filters',icon=':material/restart_alt:',width='stretch'):
        for key in ('period','dates','channel','campaigns','include_unattributed','detail_campaign','order_choice'):
            st.session_state.pop(key,None)
        st.rerun()
    st.space('small')
    st.caption(f"Known as of {pd.Timestamp(cfg['as_of']).tz_convert(cfg['timezone']).strftime('%b %d, %Y · %I:%M %p %Z')}")
    st.caption('USD · US market · ES601\n\nSynthetic observations, not SharkNinja results.')

st.caption('NINJA LUXE CAFÉ PREMIER  /  US PAID MEDIA  /  SYNTHETIC PORTFOLIO')
st.title('Every dollar. A clearer picture.')
st.write('Explore what your campaigns earn, what they cost, and what the numbers leave out.')
with st.container(horizontal=True,gap='small'):
    st.badge('Synthetic data',icon=':material/science:',color='orange')
    st.badge(f'{len(manifest["checks"])} build checks passed',icon=':material/verified:',color='green')
    st.badge(f'{start:%b %d} – {end:%b %d, %Y}',icon=':material/calendar_today:',color='gray')
st.caption('Independent project. Not affiliated with SharkNinja. Returns are realized only through the dataset cutoff; recent purchases may still be refunded.')

view = st.segmented_control('View',['Overview','Campaigns','Order economics','Data & methodology'],
                            default='Overview',required=True,key='view',label_visibility='collapsed',width='stretch')
if not selected:
    st.info('Select at least one campaign in the sidebar to see its data.',icon=':material/filter_alt:')
    st.stop()
daily = filter_campaigns(tables['campaign_daily'],start,end,selected)
order_rows = filter_campaigns(tables['order_economics'],start,end,selected)
if daily.empty:
    st.info('No campaign observations match these filters. Try a wider date range or reset the filters.')
    st.stop()
summary = campaign_summary(daily)

if view=='Overview':
    metric_cards(daily)
    trend_col,mix_col = st.columns([1.8,1],gap='medium')
    with trend_col.container(border=True):
        st.subheader('Performance over time')
        control_a,control_b = st.columns([1.5,1])
        mode = control_a.selectbox('Chart metric',['Revenue & spend','Contribution','Orders'],key='trend_metric',label_visibility='collapsed')
        frequency = control_b.segmented_control('Frequency',['Weekly','Daily'],default='Weekly',required=True,key='trend_frequency',label_visibility='collapsed')
        plot(charts.trend(period_summary(daily,frequency),mode))
        st.caption('Hover to inspect values. Drag to zoom. Weekly totals include only the selected dates.')
    with mix_col.container(border=True):
        st.subheader('Where the spend goes')
        st.caption('Actual media expense by campaign')
        plot(charts.spend_mix(summary))
    with st.container(border=True):
        st.subheader('Campaign scorecard')
        st.caption('Equal ROAS does not mean equal contribution. These are observed economics, not budget recommendations.')
        performance_table(summary)
        st.download_button('Download this comparison',campaign_export(summary,start,end,manifest),
            file_name=f'luxe-cafe-campaigns-{start}-{end}.csv',mime='text/csv',icon=':material/download:',on_click='ignore')

elif view=='Campaigns':
    st.subheader('Look beyond the headline ROAS')
    left,right = st.columns([1.2,1],gap='medium')
    with left.container(border=True):
        st.markdown('**Contribution by campaign**')
        plot(charts.contribution_bars(summary))
        st.caption('After known returns, variable costs and media. Fixed overhead is excluded.')
    with right.container(border=True):
        st.markdown('**Compare the economics**')
        performance_table(summary,compact=True)
    campaign_id = st.selectbox('Campaign to inspect',selected,format_func=lambda cid:CAMPAIGN_NAMES.get(cid,cid),key='detail_campaign')
    campaign_days = daily[daily.campaign_id==campaign_id]
    campaign_orders = order_rows[order_rows.campaign_id==campaign_id]
    if campaign_days.empty:
        st.info('This campaign has no rows in the selected period.')
    else:
        totals = metric_cards(campaign_days)
        with st.container(border=True):
            st.subheader(f'{CAMPAIGN_NAMES.get(campaign_id,campaign_id)} · the revenue-to-contribution bridge')
            if campaign_orders.empty:
                st.info('No orders in this selection. Media spend still appears in the campaign totals.')
            else:
                show_waterfall(campaign_orders,totals['spend_cents'])
        claims = filter_campaigns(tables['platform_latest'],start,end,[campaign_id])
        if not claims.empty:
            with st.expander('Why platform reporting can differ',icon=':material/compare_arrows:'):
                platform_revenue = strict_sum(claims.revenue_cents)
                st.write(f"The latest available platform snapshots claim **{money(platform_revenue,2)}** before refunds. "
                         f"The business allocation reports **{money(totals['net_revenue_cents'],2)}** after known refunds.")
                st.caption('Different click windows and overlapping source claims prevent treating this as an exact causal bridge. Snapshots replace earlier observations; they are not added together.')

elif view=='Order economics':
    st.subheader('Follow the money, line by line')
    if order_rows.empty:
        st.info('There are no orders for this campaign and date selection. Media expense remains visible in Overview.')
    else:
        totals = summarize(daily)
        cols = st.columns(3)
        cols[0].metric('Booked product revenue',money(strict_sum(order_rows.booked_revenue_cents)),border=True)
        cols[1].metric('Known product refunds',money(strict_sum(order_rows.refunded_cents)),border=True)
        cols[2].metric('Net product cost',money(strict_sum(order_rows.net_cogs_cents)),border=True)
        with st.container(border=True):
            st.subheader('From a sale to contribution')
            show_waterfall(order_rows,totals['spend_cents'])
        with st.expander('Inspect an individual order',expanded=True,icon=':material/receipt_long:'):
            ids = sorted(order_rows.order_id.unique().tolist())
            chosen_order = st.selectbox('Order',ids,key='order_choice')
            chosen = order_rows[order_rows.order_id==chosen_order]
            st.caption(f"{chosen.campaign.iloc[0]} · {chosen.report_date.iloc[0]:%b %d, %Y} · {chosen.status.iloc[0]}. Media is recorded at campaign/day grain, not arbitrarily allocated per order.")
            fields = ['order_id','line_id','quantity','booked_revenue_cents','refunded_cents','net_revenue_cents','net_cogs_cents','fulfillment_cents','net_fee_cents','return_handling_cents','contribution_before_media_cents','cost_missing']
            table(chosen[fields])
            st.caption('Exact source values above are in integer USD cents. Missing inputs appear as Unknown.')

else:
    st.subheader('Evidence you can inspect')
    st.caption('The table follows the date and campaign filters. Site-wide tracking checks below follow dates only.')
    source = st.selectbox('Dataset to explore',['Campaign days','Order lines','Platform snapshots'],key='explorer_source')
    data_view = {'Campaign days':daily,'Order lines':order_rows,'Platform snapshots':filter_campaigns(tables['platform_latest'],start,end,selected)}[source].copy()
    query = st.text_input('Find an ID, campaign or value',placeholder='e.g. C04 or O000125',key='search')
    if query.strip():
        mask = data_view.astype('string').apply(lambda c:c.str.contains(query.strip(),case=False,regex=False,na=False)).any(axis=1)
        data_view = data_view[mask]
    st.caption(f'{len(data_view):,} matching rows · money columns ending in _cents are integer USD cents')
    table(data_view)
    export = data_view.copy()
    export['report_start'] = str(start)
    export['report_end'] = str(end)
    export['as_of'] = cfg['as_of']
    export['dataset_sha256'] = manifest['dataset_sha256']
    export['data_notice'] = 'Synthetic portfolio data; not SharkNinja performance'
    st.download_button('Download filtered data',export.to_csv(index=False).encode('utf-8-sig'),
        file_name=f'luxe-cafe-{source.lower().replace(" ","-")}-{start}-{end}.csv',mime='text/csv',icon=':material/download:',on_click='ignore')
    with st.container(border=True):
        st.subheader('Tracking coverage · site-wide')
        st.caption('All commerce orders, including unattributed sales. Campaign and channel filters do not apply to this chart.')
        reconciliation = filter_dates(tables['reconciliation_daily'],start,end)
        plot(charts.tracking(reconciliation))
        gap = int(reconciliation.untracked_orders.sum())
        st.caption(f'{gap:,} fulfilled orders lack a visible purchase-tracking event at the cutoff. A gap is a prompt to investigate, not proof of a specific cause.')
    with st.expander('Definitions, assumptions and limits',icon=':material/menu_book:'):
        st.markdown('''**Business net ROAS** is allocated net product revenue divided by media expense. The allocation is seven-day last observed paid click, with no view-through credit.

**Contribution after media** subtracts net product cost, fulfillment, net payment fees, return handling and media. It is not net profit.

**Platform snapshots** use source-specific windows and pre-refund revenue. Platforms may claim the same order; those claims are not additive unique sales.

**Information cutoff** is fixed by the selected run. Date filters change the reporting window, not the cutoff. Recent orders may receive refunds later.

**Unknown is not zero.** Missing costs or media suppress complete contribution totals. Returned inventory only reverses the recoverable value supplied by the simulation.

The simulation is not calibrated to live advertising benchmarks. This interface is read-only and contains no forecasting, causal estimates or automated budget decisions.''')
        st.caption(f"Metric version {cfg['metric_version']} · data seed {cfg['seed']} · {manifest['source_class']}")
        st.code(manifest['dataset_sha256'],language=None)
    with st.expander('Build validation results',icon=':material/fact_check:'):
        st.caption('These checks ran when the dataset was built. The UI additionally verifies every file it loads against the saved checksum.')
        table(pd.DataFrame(manifest['checks']))
        if manifest['warnings']:
            st.json(manifest['warnings'])

st.caption('Luxe Café Paid Media Decision Lab · Built to make marketing analysis explainable · Synthetic data only')
