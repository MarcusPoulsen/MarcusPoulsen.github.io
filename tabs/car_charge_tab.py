import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime

def render(df, from_date, to_date, _filter_df_by_view_range):
    view_range = st.date_input('Vis periode (filter)', value=(from_date, to_date), key='filter_tab1')
    df_tab = _filter_df_by_view_range(df, view_range)

    df_car = df_tab.copy()
    if 'car_kwh' not in df_car.columns:
        df_car['car_kwh'] = 0.0
    afgift_series = df_car['afgift_pris'].fillna(0) if 'afgift_pris' in df_car.columns else 0.0
    df_car['car_cost'] = df_car['car_kwh'] * (df_car['spot_pris'].fillna(0) + df_car['tarif_pris'].fillna(0) + afgift_series)
    daily_car = df_car.groupby(df_car['time'].dt.date).agg({'car_cost': 'sum', 'car_kwh': 'sum'}).reset_index()
    daily_car.columns = ['date', 'total_charge_cost', 'total_charge_kwh']
    c1, c2, c3 = st.columns(3)
    with c1:
        st.metric('Total opladningspris for periode', f"{daily_car['total_charge_cost'].sum():.2f} DKK")
    with c2:
        st.metric('Total kwH opladet i periode', f"{daily_car['total_charge_kwh'].sum():.2f} kWh")
    with c3:
        total_kwh = daily_car['total_charge_kwh'].sum()
        total_cost = daily_car['total_charge_cost'].sum()
        avg_price = (total_cost / total_kwh) if total_kwh > 0 else 0.0
        st.metric('Gennemsnitlig kWh-pris for bil', f"{avg_price:.2f} DKK/kWh")
    st.divider()
    # --- Monthly aggregation for new bar chart ---
    monthly_car = df_car.set_index('time').resample('ME').agg({'car_kwh': 'sum', 'car_cost': 'sum'}).reset_index()
    if not monthly_car.empty:
        monthly_car['month'] = monthly_car['time'].dt.strftime('%m-%y')
        monthly_car['avg_price'] = monthly_car.apply(lambda r: (r['car_cost'] / r['car_kwh']) if r['car_kwh'] > 0 else 0.0, axis=1)
        # Calculate total cost and total clever reimbursement per month
        monthly_agg = monthly_car.copy()
        # Use clever_kwh and clever_rate from merged (already aligned by month)
        # The merged DataFrame is created below, so we need to move the bar chart after merged is created
        # So, move the bar chart code to after merged is defined
    # ...existing code...
    if not monthly_car.empty:
        monthly_car['month'] = monthly_car['time'].dt.strftime('%m-%y')
        monthly_car['avg_price'] = monthly_car.apply(lambda r: (r['car_cost'] / r['car_kwh']) if r['car_kwh'] > 0 else 0.0, axis=1)
        monthly_table = monthly_car[['month', 'car_kwh', 'avg_price', 'car_cost']].copy()
        monthly_table.columns = ['month', 'kWh opladet (automatisk detekteret)', 'average_price', 'total_price']
        st.markdown('### Månedligt opladningsoversigt')
        clever_sats_df = pd.read_csv('clever_tilbagebetaling.csv')
        clever_sats_df['month'] = clever_sats_df['month'].astype(str)
        merged = pd.merge(monthly_table, clever_sats_df, on='month', how='left')
        merged['sats'] = merged['sats'].astype(float).fillna(0.0)
        merged = merged.rename(columns={'sats': 'clever_rate'})
        clever_kwh_col = []
        udeladning_kwh_col = []
        for i, r in merged.iterrows():
            m = r['month']
            key_kwh = f'clever_kwh_{m}'
            key_udelad = f'udeladning_kwh_{m}'
            clever_kwh_col.append(float(st.session_state.get(key_kwh, r['kWh opladet (automatisk detekteret)'])))
            udeladning_kwh_col.append(float(st.session_state.get(key_udelad, 0.0)))
        merged['clever_kwh'] = clever_kwh_col
        merged['udeladning_kwh'] = udeladning_kwh_col
        # --- Bar chart logic moved here, after merged is defined ---
        # Use adjusted_total for the bar chart (matches table and CSV)
        monthly_agg = merged.copy()
        fig_car = go.Figure()
        fig_car.add_trace(go.Bar(
            x=monthly_agg['month'],
            y=monthly_agg['adjusted_total'],
            name='Opladningspris (DKK, justeret)',
            marker_color='green',
        ))
        fig_car.add_trace(go.Bar(
            x=monthly_agg['month'],
            y=monthly_agg['reimbursed'],
            name='Clever refusion (DKK)',
            marker_color='blue',
        ))
        fig_car.update_layout(
            barmode='group',
            title='Månedlig opladningspris og Clever refusion',
            xaxis_title='Måned',
            yaxis_title='DKK',
            height=450
        )
        st.plotly_chart(fig_car, width='stretch')
        # --- End bar chart logic ---
        # Move input fields to the bottom table (data_editor)
        display_table = merged.copy()
        display_table['korrektion_kwh_clever'] = display_table['clever_kwh'] - display_table['kWh opladet (automatisk detekteret)']
        display_table['korrektion_cost'] = display_table['korrektion_kwh_clever'] * display_table['average_price']
        display_table['udeladning_cost'] = display_table['udeladning_kwh'] * 3.5
        display_table['adjusted_total'] = display_table['total_price'] + display_table['korrektion_cost']
        display_table['reimbursed'] = display_table['clever_kwh'] * display_table['clever_rate']
        display_table['net_price'] = display_table['adjusted_total'] - display_table['reimbursed']
        display_table['clever_abbonnemnt'] = 799.0
        display_table['total_udgift_ved_clever_abbonemnt'] = display_table['net_price'] + display_table['clever_abbonnemnt']
        edited = st.data_editor(
            display_table,
            column_config={
                'clever_rate': st.column_config.NumberColumn('Clever sats (DKK/kWh)', min_value=0.0, step=0.01, format='%.2f', disabled=True),
                'clever_kwh': st.column_config.NumberColumn('kWh ifølge Clever', min_value=0.0, step=0.01, format='%.2f'),
                'udeladning_kwh': st.column_config.NumberColumn('Udeladning kWh', min_value=0.0, step=0.01, format='%.2f'),
            },
            disabled=['month', 'kWh opladet (automatisk detekteret)', 'average_price', 'total_price', 'korrektion_kwh_clever', 'korrektion_cost', 'adjusted_total', 'reimbursed', 'net_price', 'clever_abbonnemnt', 'total_udgift_ved_clever_abbonemnt', 'udeladning_cost'],
            hide_index=True,
            width='stretch',
            key='monthly_car_editor'
        )
        for i, r in edited.iterrows():
            m = r['month']
            st.session_state[f'clever_kwh_{m}'] = r['clever_kwh']
            st.session_state[f'udeladning_kwh_{m}'] = r['udeladning_kwh']
        csv = edited[[
            'month', 'kWh opladet (automatisk detekteret)', 'clever_kwh', 'korrektion_kwh_clever',
            'average_price', 'total_price', 'korrektion_cost', 'adjusted_total',
            'reimbursed', 'net_price', 'clever_abbonnemnt', 'total_udgift_ved_clever_abbonemnt',
            'udeladning_kwh', 'udeladning_cost'
        ]].to_csv(index=False)
        st.download_button('📥 Download monthly CSV', csv, file_name=f'monthly_car_{datetime.now().date()}.csv', mime='text/csv')
    else:
        st.info('Ingen månedlig opladningsdata i valgt periode')
