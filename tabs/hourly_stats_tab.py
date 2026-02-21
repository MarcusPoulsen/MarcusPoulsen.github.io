import streamlit as st
import plotly.graph_objects as go

def render(df, from_date, to_date, _filter_df_by_view_range):
    df_tab = df.copy()
    hourly_stats = df_tab.copy()
    hourly_stats['hour_of_day'] = hourly_stats['time'].dt.hour
    grouped = hourly_stats.groupby('hour_of_day').agg({
        'usage_kwh': 'sum',
        'spot_cost_dkk': 'sum',
        'tarif_pris': 'first',
        'total_pris_per_kwh': 'mean',
        'total_udgift': 'mean'
    }).reset_index()
    grouped['spot_pris_betalt'] = grouped['spot_cost_dkk'] / grouped['usage_kwh']
    avg_by_hour = grouped
    avg_by_hour['gennemsnits strømpris alt inklusiv'] = avg_by_hour['total_udgift'] / avg_by_hour['usage_kwh']
    avg_by_hour = avg_by_hour.rename(columns={
        'hour_of_day': 'time',
        'usage_kwh': 'forbrug (kwh)',
        'spot_pris': 'gennemsnits spotpris betalt',
        'tarif_pris': 'tarif pris',
        'total_pris_per_kwh': 'gennemsnits strømpris alt inklusiv (beregnet)',
        'total_udgift': 'total udgift kr'
    })
    st.dataframe(avg_by_hour, width='stretch')
    fig = go.Figure()
    fig.add_trace(go.Bar(x=avg_by_hour['time'], y=avg_by_hour['forbrug (kwh)'], name='Forbrug (kwh)'))
    fig.update_layout(title='Gennemsnitligt forbrug pr. time', xaxis_title='Time', yaxis_title='Forbrug (kwh)', height=400)
    st.plotly_chart(fig, width='stretch')