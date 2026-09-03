"""Accessible read-only tables without a native Arrow runtime dependency."""
from html import escape
from numbers import Number

import pandas as pd
import streamlit as st


def table(frame, money_columns=(), ratio_columns=(), max_rows=100):
    if frame.empty:
        st.caption('No rows match this selection.')
        return
    headers = ''.join(f'<th scope="col">{escape(str(column))}</th>' for column in frame.columns)
    rows = []
    for row in frame.head(max_rows).itertuples(index=False,name=None):
        cells = []
        for column,value in zip(frame.columns,row):
            if pd.isna(value):
                text = 'Unknown'
            elif column in money_columns:
                text = f'-${abs(value):,.2f}' if value < 0 else f'${value:,.2f}'
            elif column in ratio_columns:
                text = f'{value:.2f}x'
            elif isinstance(value, pd.Timestamp):
                text = value.isoformat(sep=' ')
            elif isinstance(value,Number) and not isinstance(value,bool):
                text = f'{value:,.0f}' if float(value).is_integer() else f'{value:,.4f}'
            else:
                text = str(value)
            numeric = ' class="number"' if isinstance(value,Number) else ''
            cells.append(f'<td{numeric}>{escape(text)}</td>')
        rows.append('<tr>'+''.join(cells)+'</tr>')
    # CSS is scoped to this table; it does not target Streamlit's internal DOM.
    st.html('''<style>
      .luxe-data {overflow:auto; max-height:440px; border:1px solid #DCDFD5; border-radius:8px;}
      .luxe-data table {border-collapse:collapse; width:max-content; min-width:100%; font-size:14px; color:#24372F; background:#FCFBF8;}
      .luxe-data th {position:sticky; top:0; background:#EEF1EA; text-align:left; font-weight:600; white-space:nowrap;}
      .luxe-data td,.luxe-data th {padding:13px 15px; border-bottom:1px solid #E4E8DF;}
      .luxe-data tr:last-child td {border-bottom:0;}
      .luxe-data tr:hover td {background:#F2F5EF;}
      .luxe-data .number {font-variant-numeric:tabular-nums; text-align:right; white-space:nowrap;}
    </style><div class="luxe-data" tabindex="0" role="region" aria-label="Data table, scroll for more columns">
    <table><thead><tr>'''+headers+'</tr></thead><tbody>'+''.join(rows)+'</tbody></table></div>')
    if len(frame)>max_rows:
        st.caption(f'Showing the first {max_rows:,} of {len(frame):,} rows. Search to narrow the table; the download contains all matching rows.')


def plot(figure, **kwargs):
    st.plotly_chart(figure,width='stretch',theme=None,
        config={'displaylogo':False,'modeBarButtonsToRemove':['lasso2d','select2d'],'scrollZoom':False},**kwargs)
