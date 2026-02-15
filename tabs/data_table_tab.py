import streamlit as st

def render(df, from_date, to_date, _filter_df_by_view_range):
    view_range = st.date_input('Vis periode (filter)', value=(from_date, to_date), key='filter_tab3')
    df_tab = _filter_df_by_view_range(df, view_range)
    st.dataframe(df_tab, width='stretch', height=600)
    csv = df_tab.to_csv(index=False)
    st.download_button(
        label='📥 Download as CSV',
        data=csv,
        file_name=f'power_usage_{from_date}_to_{to_date}.csv',
        mime='text/csv'
    )
