import streamlit as st
import plotly.graph_objects as go

def render(df, from_date, to_date, _filter_df_by_view_range):
    view_range = st.date_input('Vis periode (filter)', value=(from_date, to_date), key='filter_tab2')
    df_tab = _filter_df_by_view_range(df, view_range)
    col1, col2 = st.columns(2)
    with col1:
        fig1 = go.Figure()
        fig1.add_trace(go.Scatter(x=df_tab['time'], y=df_tab['usage_kwh'], mode='lines', name='Usage', fill='tozeroy'))
        fig1.update_layout(title='Hourly Power Usage', xaxis_title='Time', yaxis_title='Usage (kWh)', height=400)
        st.plotly_chart(fig1, use_container_width=True)
    with col2:
        fig2 = go.Figure()
        fig2.add_trace(go.Scatter(x=df_tab['time'], y=df_tab['spot_pris'], mode='lines', name='Spot Pris', line=dict(color='orange')))
        fig2.add_trace(go.Scatter(x=df_tab['time'], y=df_tab['tarif_pris'], mode='lines', name='Tarif Pris', line=dict(color='blue')))
        if 'afgift_pris' in df_tab.columns:
            fig2.add_trace(go.Scatter(x=df_tab['time'], y=df_tab['afgift_pris'], mode='lines', name='Afgift (tax)', line=dict(color='purple', dash='dot')))
        fig2.add_trace(go.Scatter(x=df_tab['time'], y=df_tab['total_pris_per_kwh'], mode='lines', name='Total Pris (DKK/kWh)', line=dict(color='black', width=2)))
        fig2.update_layout(title='Hourly Electricity Prices', xaxis_title='Time', yaxis_title='Price (DKK/kWh)', height=400)
        st.plotly_chart(fig2, use_container_width=True)
    daily_cost = df_tab.groupby(df_tab['time'].dt.date).agg({
        'total_udgift': 'sum',
        'usage_kwh': 'sum',
        'spot_pris': 'mean',
        'tarif_pris': 'mean',
        'total_pris_per_kwh': 'mean'
    }).reset_index()
    daily_cost.columns = ['date', 'total_cost', 'usage_kwh', 'avg_spot', 'avg_tarif', 'avg_total_pris']
    fig3 = go.Figure()
    fig3.add_trace(go.Bar(x=daily_cost['date'], y=daily_cost['total_cost'], name='Daily Cost'))
    fig3.update_layout(title='Daily Total Cost Trend', xaxis_title='Date', yaxis_title='Cost (DKK)', height=400)
    st.plotly_chart(fig3, use_container_width=True)
