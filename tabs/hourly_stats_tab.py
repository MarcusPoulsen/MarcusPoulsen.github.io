import streamlit as st
import plotly.graph_objects as go

def render(df, from_date, to_date, _filter_df_by_view_range):
    df_tab = df.copy()
    hourly_stats = df_tab.copy()
    hourly_stats['hour_of_day'] = hourly_stats['time'].dt.hour
    avg_by_hour = hourly_stats.groupby('hour_of_day').agg({
        'usage_kwh': 'mean',
        'spot_pris': 'mean',
        'tarif_pris': 'first',
        'total_pris_per_kwh': 'mean',
        'total_udgift': 'mean'
    }).reset_index()
    avg_by_hour['gennemsnits strømpris alt inklusiv'] = avg_by_hour['total_udgift'] / avg_by_hour['usage_kwh']
    avg_by_hour.columns = [
        'time',
        'forbrug (kwh)',
        'gennemsnits spotpris betalt',
        'tarif pris',
        'gennemsnits strømpris alt inklusiv',
        'total udgift kr'
    ]
    st.dataframe(avg_by_hour, width='stretch')
    fig = go.Figure()
    fig.add_trace(go.Bar(x=avg_by_hour['Hour'], y=avg_by_hour['Avg Usage (kWh)'], name='Avg Usage (kWh)'))
    fig.update_layout(title='Average Usage by Hour of Day', xaxis_title='Hour', yaxis_title='Avg Usage (kWh)', height=400)
    st.plotly_chart(fig, width='stretch')
    st.markdown('**Insights:**')
    if not hourly_stats.empty:
        peak_hour = avg_by_hour.loc[avg_by_hour['Avg Spot Pris'].idxmax(), 'Hour']
        peak_price = avg_by_hour.loc[avg_by_hour['Avg Spot Pris'].idxmax(), 'Avg Spot Pris']
        st.info(f'⚠️ Most expensive hour: {peak_hour}:00 (avg Spot Pris {peak_price:.3f} DKK/kWh)')
