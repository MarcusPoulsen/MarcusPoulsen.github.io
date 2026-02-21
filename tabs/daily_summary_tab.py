import streamlit as st

def render(df, from_date, to_date, _filter_df_by_view_range):
    view_range = st.date_input('Filtrer på en bestemt periode', value=(from_date, to_date), key='filter_tab4')
    df_tab = _filter_df_by_view_range(df, view_range)
    daily_summary = df_tab.groupby(df_tab['time'].dt.date).agg({
        'usage_kwh': 'sum',
        'total_udgift': 'sum',
        'spot_pris': 'mean'
    }).reset_index()
    daily_summary['gennemsnits strømpris alt inklusiv'] = daily_summary['total_udgift'] / daily_summary['usage_kwh']
    daily_summary.columns = [
        'dato',
        'forbrug (kwh)',
        'total udgift kr',
        'gennemsnits spotpris betalt',
        'gennemsnits strømpris alt inklusiv'
    ]
    st.dataframe(daily_summary, width='stretch')
