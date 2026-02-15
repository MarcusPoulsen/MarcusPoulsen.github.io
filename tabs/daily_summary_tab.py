import streamlit as st

def render(df, from_date, to_date, _filter_df_by_view_range):
    view_range = st.date_input('Vis periode (filter)', value=(from_date, to_date), key='filter_tab4')
    df_tab = _filter_df_by_view_range(df, view_range)
    daily_summary = df_tab.groupby(df_tab['time'].dt.date).agg({
        'usage_kwh': 'sum',
        'total_udgift': 'sum',
        'spot_pris': 'mean',
        'tarif_pris': 'first'
    }).reset_index()
    daily_summary.columns = ['Date', 'Usage (kWh)', 'Total Cost (DKK)', 'Avg Spot Pris', 'Tarif Pris']
    st.dataframe(daily_summary, width='stretch')
