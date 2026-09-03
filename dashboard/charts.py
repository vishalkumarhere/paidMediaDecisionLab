"""Browser-rendered Plotly charts: JSON transport, no Arrow serialization."""
import pandas as pd
import plotly.graph_objects as go

GREEN = '#2F6653'
ORANGE = '#B76C3C'
SAGE = '#8AA798'
RED = '#B64E47'
PALETTE = [GREEN,ORANGE,SAGE,'#7C7896','#BCA66B','#538DA1','#99958C']


def values(series, divisor=1):
    return [None if pd.isna(v) else float(v)/divisor for v in series]


def finish(chart, height=300):
    chart.update_layout(height=height,paper_bgcolor='rgba(0,0,0,0)',plot_bgcolor='rgba(0,0,0,0)',
        font=dict(family='Arial, sans-serif',size=12,color='#3D4D44'),
        margin=dict(l=65,r=20,t=40,b=55),hoverlabel=dict(bgcolor='#FFFFFF',font_color='#24372F'),
        legend=dict(orientation='h',y=1.15,x=0,title=None),hovermode='x unified')
    chart.update_xaxes(showgrid=False,zeroline=False,automargin=True)
    chart.update_yaxes(gridcolor='#E7E9E4',zerolinecolor='#BAC4B7',automargin=True)
    return chart


def trend(frame, mode='Revenue & spend'):
    mapping = {'Revenue & spend':{'net_revenue_cents':'Net revenue','spend_cents':'Media spend'},
               'Contribution':{'contribution_after_media_cents':'Contribution after media'},
               'Orders':{'orders':'Fulfilled orders'}}[mode]
    figure = go.Figure()
    for index,(column,label) in enumerate(mapping.items()):
        figure.add_trace(go.Scatter(x=[v.isoformat() for v in frame.period],
            y=values(frame[column],1 if mode=='Orders' else 100),name=label,mode='lines+markers',
            line=dict(color=[GREEN,ORANGE][index],width=3),marker=dict(size=5),connectgaps=False,
            hovertemplate=('%{y:,.0f}' if mode=='Orders' else '$%{y:,.2f}')+'<extra>'+label+'</extra>'))
    finish(figure)
    figure.update_xaxes(tickformat='%b %d',nticks=6)
    figure.update_yaxes(title_text='Orders' if mode=='Orders' else 'USD',tickprefix='' if mode=='Orders' else '$')
    return figure


def spend_mix(summary):
    data = summary.sort_values('spend_cents',ascending=True,na_position='first')
    figure = go.Figure(go.Bar(x=values(data.spend_cents,100),y=data.campaign.tolist(),orientation='h',
        marker=dict(color=PALETTE[:len(data)],cornerradius=4),
        hovertemplate='%{y}<br>$%{x:,.2f}<extra></extra>'))
    finish(figure)
    figure.update_layout(hovermode='closest',bargap=0.4)
    figure.update_xaxes(tickprefix='$')
    figure.update_yaxes(showgrid=False)
    return figure


def contribution_bars(summary):
    data = summary.sort_values('contribution_after_media_cents',ascending=True,na_position='first')
    amounts = values(data.contribution_after_media_cents,100)
    figure = go.Figure(go.Bar(x=amounts,y=data.campaign.tolist(),orientation='h',
        marker=dict(color=[RED if v is not None and v<0 else GREEN for v in amounts],cornerradius=4),
        hovertemplate='%{y}<br>$%{x:,.2f}<extra></extra>'))
    finish(figure)
    figure.update_layout(hovermode='closest',bargap=0.4)
    figure.update_xaxes(tickprefix='$',title_text='Contribution after media (USD)')
    figure.update_yaxes(showgrid=False)
    return figure


def waterfall(steps):
    figure = go.Figure(go.Waterfall(x=steps.step.tolist(),y=values(steps.amount),
        measure=['relative']*(len(steps)-1)+['total'],
        increasing=dict(marker_color=SAGE),decreasing=dict(marker_color=ORANGE),totals=dict(marker_color=GREEN),
        connector=dict(line=dict(color='#BDC9BF',width=1)),hovertemplate='%{x}<br>$%{y:,.2f}<extra></extra>'))
    finish(figure,340)
    figure.update_layout(hovermode='closest',showlegend=False)
    figure.update_yaxes(tickprefix='$',title_text='USD')
    return figure


def tracking(frame):
    figure = go.Figure()
    for column,label,color in [('commerce_orders','Commerce orders',GREEN),('tracked_orders','Tracked orders',ORANGE)]:
        figure.add_trace(go.Scatter(x=[v.isoformat() for v in frame.report_date],y=values(frame[column]),
            name=label,mode='lines',line=dict(color=color,width=2.5),hovertemplate='%{y:,.0f}<extra>'+label+'</extra>'))
    finish(figure)
    figure.update_xaxes(tickformat='%b %d',nticks=6)
    figure.update_yaxes(title_text='Orders')
    return figure


def forecast(history, future, target, label):
    divisor = 1 if target == 'orders' else 100
    recent = history.tail(42)
    figure = go.Figure()
    figure.add_trace(go.Scatter(x=[v.isoformat() for v in future.period],
        y=values(future[f'{target}_upper'],divisor),name='80% range',mode='lines',
        line=dict(width=0),hoverinfo='skip',showlegend=False))
    figure.add_trace(go.Scatter(x=[v.isoformat() for v in future.period],
        y=values(future[f'{target}_lower'],divisor),name='80% empirical range',mode='lines',
        line=dict(width=0),fill='tonexty',fillcolor='rgba(138,167,152,0.24)',hoverinfo='skip'))
    figure.add_trace(go.Scatter(x=[v.isoformat() for v in recent.period],y=values(recent[target],divisor),
        name='Observed',mode='lines+markers',line=dict(color=GREEN,width=2.5),marker=dict(size=4),
        hovertemplate=('%{y:,.1f}' if target=='orders' else '$%{y:,.2f}')+'<extra>Observed</extra>'))
    figure.add_trace(go.Scatter(x=[v.isoformat() for v in future.period],
        y=values(future[f'{target}_point'],divisor),name='Baseline forecast',mode='lines+markers',
        line=dict(color=ORANGE,width=3,dash='dash'),marker=dict(size=6),
        hovertemplate=('%{y:,.1f}' if target=='orders' else '$%{y:,.2f}')+'<extra>Baseline forecast</extra>'))
    finish(figure,360)
    figure.update_layout(hovermode='x unified')
    figure.update_xaxes(tickformat='%b %d',nticks=8)
    figure.update_yaxes(title_text=label,tickprefix='' if target=='orders' else '$')
    return figure
