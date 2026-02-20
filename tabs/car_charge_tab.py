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
    # Calculate net_price for the period from the monthly table if available
    net_price_total = None
    net_label = 'Clever tilbagebetaling (netto)'
    net_value = 'N/A'
    # Try to get from merged table if it exists (after monthly_table is created)


    # We'll fill net_price_total after merged is created (monthly table)
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.metric('Total opladningspris for periode', f"{daily_car['total_charge_cost'].sum():.2f} DKK")
    with c2:
        st.metric('Total kwH opladet i periode', f"{daily_car['total_charge_kwh'].sum():.2f} kWh")
    with c3:
        total_kwh = daily_car['total_charge_kwh'].sum()
        total_cost = daily_car['total_charge_cost'].sum()
        avg_price = (total_cost / total_kwh) if total_kwh > 0 else 0.0
        st.metric('Gennemsnitlig kWh-pris for bil', f"{avg_price:.2f} DKK/kWh")
    # c4 will be filled after merged is created
    st.divider()
    # --- Monthly aggregation for new bar chart ---
    monthly_car = df_car.set_index('time').resample('ME').agg({'car_kwh': 'sum', 'car_cost': 'sum'}).reset_index()
    # (Bar chart logic is handled after merged table is created)
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
        # Calculate corrections and adjusted total on merged before using in bar chart
        merged['korrektion_kwh_clever'] = merged['clever_kwh'] - merged['kWh opladet (automatisk detekteret)']
        merged['korrektion_cost'] = merged['korrektion_kwh_clever'] * merged['average_price']
        merged['adjusted_total'] = merged['total_price'] + merged['korrektion_cost']
        merged['reimbursed'] = merged['clever_kwh'] * merged['clever_rate']
        # --- Bar chart logic ---
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
        st.plotly_chart(fig_car, width='stretch', key='car_charge_bar_chart')
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
        # Rearranged and renamed columns as requested
        display_table = display_table[[
            'month',
            'kWh opladet (automatisk detekteret)',
            'clever_kwh',
            'korrektion_kwh_clever',
            'average_price',
            'clever_rate',
            'total_price',
            'korrektion_cost',
            'adjusted_total',
            'reimbursed',
            'net_price',
            'clever_abbonnemnt',
            'total_udgift_ved_clever_abbonemnt',
            'udeladning_kwh',
            'udeladning_cost',
        ]]
        display_table = display_table.rename(columns={
            'month': 'Periode',
            'kWh opladet (automatisk detekteret)': 'KWh opladet automatisk detekteret',
            'clever_kwh': 'KwH Ifølge Clever',
            'korrektion_kwh_clever': 'Ekstra Kwh (ikke detekteret)',
            'average_price': 'Gennemsnits opladningspris',
            'clever_rate': 'Clever tilbagebetaling pr kwh',
            'total_price': 'Total opladningspris',
            'korrektion_cost': 'Ikke detekteret kwh total pris',
            'adjusted_total': 'Totalpris inklusiv ikke detekteret',
            'reimbursed': 'Tilbagebetalt fra Clever',
            'net_price': 'Netto strøm pris',
            'clever_abbonnemnt': 'Clever',
            'total_udgift_ved_clever_abbonemnt': 'Total udgift med Clever',
        })
        # --- Bar chart logic ---
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
        # --- End bar chart logic ---
        edited = st.data_editor(
            display_table,
            column_config={
                'Clever tilbagebetaling pr kwh': st.column_config.NumberColumn('Clever tilbagebetaling pr kWh', min_value=0.0, step=0.01, format='%.2f', disabled=True),
                'KwH Ifølge Clever': st.column_config.NumberColumn('kWh ifølge Clever', min_value=0.0, step=0.01, format='%.2f'),
                'udeladning_kwh': st.column_config.NumberColumn('Udeladning kWh', min_value=0.0, step=0.01, format='%.2f'),
            },
            disabled=[
                'Periode',
                'KWh opladet automatisk detekteret',
                'Gennemsnits opladningspris',
                'Total opladningspris',
                'Ekstra Kwh (ikke detekteret)',
                'Ikke detekteret kwh total pris',
                'Totalpris inklusiv ikke detekteret',
                'Tilbagebetalt fra Clever',
                'Netto strøm pris',
                'Clever',
                'Total udgift med Clever',
                'udeladning_cost',
            ],
            hide_index=True,
            width='stretch',
            key='monthly_car_editor'
        )
        # Calculate net_price_total from the visible/edited table and show the metric here
        if 'net_price' in edited.columns:
            net_price_total = edited['net_price'].sum()
            if net_price_total < 0:
                net_label = 'Clever har tilbagebetalt dig mere end du har betalt for din strøm til bilen'
            else:
                net_label = 'Clever har tilbagebetalt dig mindre end du har betalt for din strøm til bilen'
            net_value = f"{net_price_total:.2f} DKK"
        with c4:
            st.metric(net_label, net_value)
        # Update session state using renamed columns
        for i, r in edited.iterrows():
            m = r['Periode']
            st.session_state[f'clever_kwh_{m}'] = r['KwH Ifølge Clever']
            st.session_state[f'udeladning_kwh_{m}'] = r['udeladning_kwh']
        # Export CSV with new column order and names
        csv = edited[[
            'Periode',
            'KWh opladet automatisk detekteret',
            'KwH Ifølge Clever',
            'Ekstra Kwh (ikke detekteret)',
            'Gennemsnits opladningspris',
            'Clever tilbagebetaling pr kwh',
            'Total opladningspris',
            'Ikke detekteret kwh total pris',
            'Totalpris inklusiv ikke detekteret',
            'Tilbagebetalt fra Clever',
            'Netto strøm pris',
            'Clever',
            'Total udgift med Clever',
            'udeladning_kwh',
            'udeladning_cost',
        ]].to_csv(index=False)
        st.download_button('📥 Download monthly CSV', csv, file_name=f'monthly_car_{datetime.now().date()}.csv', mime='text/csv')
    else:
        # If no monthly data, still show the net_price metric (fallback to N/A)
        with c4:
            st.metric(net_label, net_value)
        st.info('Ingen månedlig opladningsdata i valgt periode')