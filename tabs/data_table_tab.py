import streamlit as st

def render(df, from_date, to_date, _filter_df_by_view_range):
    view_range = st.date_input('Vis periode (filter)', value=(from_date, to_date), key='filter_tab3')
    df_tab = _filter_df_by_view_range(df, view_range)
    # Reorder and rename columns
    col_map = {
        'usage_kwh': 'forbrug kwh',
        'spot_pris': 'spot pris',
        'tarif_pris': 'tarif pris',
        'afgift_pris': 'afgift pris',
        'total_pris_per_kwh': 'total pris per kwh',
        'total_udgift': 'udgift for time',
        'car_charging': 'bil oplader',
        'car_kwh': 'kwh opladet af bil',
        'house_kwh': 'kwh forbrugt af hus',
    }
    ordered_cols = [
        'usage_kwh',
        'spot_pris',
        'tarif_pris',
        'afgift_pris',
        'total_pris_per_kwh',
        'total_udgift',
        'car_charging',
        'car_kwh',
        'house_kwh',
    ]
    # Only keep columns that exist in df_tab
    ordered_cols = [col for col in ordered_cols if col in df_tab.columns]
    df_tab_renamed = df_tab[ordered_cols].rename(columns=col_map)
    st.dataframe(df_tab_renamed, width='stretch', height=600)
    csv = df_tab_renamed.to_csv(index=False)
    st.download_button(
        label='📥 Download as CSV',
        data=csv,
        file_name=f'power_usage_{from_date}_to_{to_date}.csv',
        mime='text/csv'
    )
