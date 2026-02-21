import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime

def render(df, from_date, to_date, _filter_df_by_view_range, udeladning_pris):
    # Removed date filter, use full range
    df_tab = df.copy()

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

    total_kwh = daily_car['total_charge_kwh'].sum()
    total_cost = daily_car['total_charge_cost'].sum()
    avg_price = (total_cost / total_kwh) if total_kwh > 0 else 0.0
    st.markdown(f"#### Hjemmeopladning af elbil – samlet oversigt for perioden")
    # Use session_state to persist net_label/net_value after editing, so we can show the info box at the top
    net_label_top = st.session_state.get('car_charge_net_label', '')
    net_value_top = st.session_state.get('car_charge_net_value', '')
    st.markdown(f"<div style='background-color:#f0f2f6;padding:10px;border-radius:5px;'>Du har opladet <b>{total_kwh:.2f} kWh</b> i perioden, og det har i gennemsnit kostet <b>{avg_price:.2f} kr./kWh</b>. {net_label_top} ({net_value_top})</div>", unsafe_allow_html=True)
    # Divider after summary info box
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
        clever_sats_df = pd.read_csv('clever_tilbagebetaling.csv')
        clever_sats_df['month'] = clever_sats_df['month'].astype(str)
        merged = pd.merge(monthly_table, clever_sats_df, on='month', how='left')
        merged['sats'] = merged['sats'].astype(float).fillna(0.0)
        merged = merged.rename(columns={'sats': 'clever_rate'})
        clever_kwh_col = []
        udeladning_kwh_col = []
        st.markdown('#### For at få det mest præcise estimat, indtast værdier fra Clever-appen og udeladning for hver måned:')
        input_cols = st.columns(2)
        for i, r in merged.iterrows():
            m = r['month']
            key_kwh = f'clever_kwh_{m}'
            key_udelad = f'udeladning_kwh_{m}'
            default_kwh = float(st.session_state.get(key_kwh, r['kWh opladet (automatisk detekteret)']))
            default_udelad = float(st.session_state.get(key_udelad, 0.0))
            with input_cols[0]:
                clever_kwh_val = st.number_input(f"kWh ifølge Clever ({m})", min_value=0.0, value=default_kwh, step=0.01, key=key_kwh)
            with input_cols[1]:
                udeladning_kwh_val = st.number_input(f"Udeladning kWh ({m})", min_value=0.0, value=default_udelad, step=0.01, key=key_udelad)
            clever_kwh_col.append(clever_kwh_val)
            udeladning_kwh_col.append(udeladning_kwh_val)
        st.divider()
        merged['clever_kwh'] = clever_kwh_col
        merged['udeladning_kwh'] = udeladning_kwh_col
        # Calculate corrections and adjusted total on merged before using in bar chart
        merged['korrektion_kwh_clever'] = merged['clever_kwh'] - merged['kWh opladet (automatisk detekteret)']
        merged['korrektion_cost'] = merged['korrektion_kwh_clever'] * merged['average_price']
        merged['adjusted_total'] = merged['total_price'] + merged['korrektion_cost']
        merged['reimbursed'] = merged['clever_kwh'] * merged['clever_rate']
        # --- Bar chart logic (single instance) ---
        monthly_agg = merged.copy()
        fig_car = go.Figure()
        fig_car.add_trace(go.Bar(
            x=monthly_agg['month'],
            y=monthly_agg['adjusted_total'],
            name='Estimeret opladningspris (kr.)',
            marker_color='red',
            text=monthly_agg['adjusted_total'].round(0),
            textposition='inside',
        ))
        fig_car.add_trace(go.Bar(
            x=monthly_agg['month'],
            y=monthly_agg['reimbursed'],
            name='Clever-refusion (kr.)',
            marker_color='green',
            text=monthly_agg['reimbursed'].round(0),
            textposition='inside',
        ))
        fig_car.update_layout(
            barmode='group',
            title='Sammenlign, hvad du selv har betalt for hjemmeopladning af bilen, med hvad Clever har refunderet:',
            xaxis_title='Periode',
            yaxis_title='kr.',
            height=450
        )
        st.markdown('### Månedlig opladningspris vs. Clever-refusion')
        st.plotly_chart(fig_car, width='stretch', key='car_charge_bar_chart')

        # --- Prepare display table (single instance) ---
        display_table = merged.copy()
        display_table['korrektion_kwh_clever'] = display_table['clever_kwh'] - display_table['kWh opladet (automatisk detekteret)']
        display_table['korrektion_cost'] = display_table['korrektion_kwh_clever'] * display_table['average_price']
        display_table['udeladning_cost'] = display_table['udeladning_kwh'] * udeladning_pris
        display_table['adjusted_total'] = display_table['total_price'] + display_table['korrektion_cost']
        display_table['reimbursed'] = display_table['clever_kwh'] * display_table['clever_rate']
        display_table['net_price'] = display_table['adjusted_total'] - display_table['reimbursed']
        display_table['clever_abbonnemnt'] = 799.0
        display_table['total_udgift_ved_clever_abbonemnt'] = display_table['net_price'] + display_table['clever_abbonnemnt']
        # Afgift er 0,9 kr med moms i 2025 og tidligere, i 2026 er den næsten nul, og du får ingen refusion
        def get_clever_multiplier(month_str):
            # month_str is in format 'MM-YY'
            try:
                year = int('20' + month_str.split('-')[1])
                return 0.9 if year < 2026 else 0.0
            except Exception:
                return 0.9

        clever_multiplier = display_table['month'].apply(get_clever_multiplier)
        display_table['total_udgift_uden_clever_abbonemnt'] = display_table['adjusted_total'] + 70 - display_table['clever_kwh'] * clever_multiplier + display_table['udeladning_cost']

        # --- New bar chart: Price with and without Clever ---
        st.markdown('### Månedlig udgift: med og uden Clever')
        fig_with_without = go.Figure()
        fig_with_without.add_trace(go.Bar(
            x=display_table['month'],
            y=display_table['total_udgift_uden_clever_abbonemnt'],
            name='Uden Clever',
            marker_color='red',
            text=display_table['total_udgift_uden_clever_abbonemnt'].round(0),
            textposition='inside',
        ))
        fig_with_without.add_trace(go.Bar(
            x=display_table['month'],
            y=display_table['total_udgift_ved_clever_abbonemnt'],
            name='Med Clever',
            marker_color='green',
            text=display_table['total_udgift_ved_clever_abbonemnt'].round(0),
            textposition='inside',
        ))
        fig_with_without.update_layout(
            barmode='group',
            title='Sammenlign din totale udgift med og uden Clever, inklusive eventuel udeladning',
            xaxis_title='Måned',
            yaxis_title='kr.',
            height=400
        )
        st.plotly_chart(fig_with_without, use_container_width=True, key='with_without_clever_bar_chart')

        display_table = display_table.rename(columns={
            'month': 'Periode',
            'kWh opladet (automatisk detekteret)': 'KWh auto detekteret',
            'clever_kwh': 'KwH Iflg. Clever',
            'korrektion_kwh_clever': 'ikke detekteret kWh',
            'average_price': 'Gns. KWh pris',
            'clever_rate': 'Clever tilbagebetaling pr KWh',
            'total_price': 'Total udgift',
            'adjusted_total': 'Totaludgift inkl. ikke detekteret',
            'reimbursed': 'Tilbagebetalt fra Clever',
            'net_price': 'Netto strøm pris',
            'clever_abbonnemnt': 'Clever fastpris',
            'total_udgift_ved_clever_abbonemnt': 'Total udgift med Clever',
            'total_udgift_uden_clever_abbonemnt': 'Total udgift uden Clever',
        })
        display_columns = [
            'Periode',
            'KWh auto detekteret',
            'KwH Iflg. Clever',
            'ikke detekteret kWh',
            'udeladning_kwh',
            'Total udgift med Clever',
            'Total udgift uden Clever',
            'udeladning_cost',
            'Gns. KWh pris',
            'Clever tilbagebetaling pr KWh',
            'Total udgift',
            'Totaludgift inkl. ikke detekteret',
            'Tilbagebetalt fra Clever',
            'Netto strøm pris',
            'Clever fastpris',
        ]
        st.markdown('#### Månedlig udgiftsoversigt (detaljeret tabel)')
        st.markdown('Du kan nu indtaste værdierne ovenfor. Tabellen herunder opdateres automatisk.')
        edited = st.data_editor(
            display_table[display_columns],
            column_config={
                'Periode': st.column_config.TextColumn('Periode'),
                'KWh auto detekteret': st.column_config.NumberColumn('KWh\nauto\ndetekteret'),
                'KwH Iflg. Clever': st.column_config.NumberColumn('KwH\nIflg.\nClever', disabled=True),
                'ikke detekteret kWh': st.column_config.NumberColumn('ikke\ndetekteret\nkWh'),
                'Gns. KWh pris': st.column_config.NumberColumn('Gns.\nKWh\npris'),
                'Clever tilbagebetaling pr KWh': st.column_config.NumberColumn('Clever\ntilbagebetaling\npr KWh', min_value=0.0, step=0.01, format='%.2f', disabled=True),
                'Total udgift': st.column_config.NumberColumn('Total\nudgift'),
                'Totaludgift inkl. ikke detekteret': st.column_config.NumberColumn('Totaludgift\ninkl.\nikke\ndetekteret'),
                'Tilbagebetalt fra Clever': st.column_config.NumberColumn('Tilbagebetalt\nfra\nClever'),
                'Netto strøm pris': st.column_config.NumberColumn('Netto\nstrøm\npris'),
                'Clever fastpris': st.column_config.NumberColumn('Clever\nfastpris'),
                'Total udgift med Clever': st.column_config.NumberColumn('Total\nudgift\nmed\nClever'),
                'udeladning_kwh': st.column_config.NumberColumn('Udeladning\nKWh', disabled=True),
                'udeladning_cost': st.column_config.NumberColumn('Udeladning\nudgift'),
                'total_udgift_uden_Clever': st.column_config.NumberColumn('Total\nudgift\nuden\nClever'),
            },
            disabled=[
                'Periode',
                'KWh auto detekteret',
                'KwH Iflg. Clever',
                'Gns. KWh pris',
                'Total udgift',
                'ikke detekteret kWh',
                'Totaludgift inkl. ikke detekteret',
                'Tilbagebetalt fra Clever',
                'Netto strøm pris',
                'Clever fastpris',
                'Total udgift med Clever',
                'udeladning_kwh',
                'udeladning_cost',
                'Total udgift uden Clever',
            ],
            hide_index=True,
            width='stretch',
            key='monthly_car_editor'
        )
        # Calculate net_price_total from the visible/edited table and show the metric here
        if 'Netto strøm pris' in edited.columns:
            net_price_total = edited['Netto strøm pris'].sum()
            if net_price_total < 0:
                net_label = 'Clever har tilbagebetalt mere end du har betalt for strøm til bilen'
            else:
                net_label = 'Clever har tilbagebetalt mindre end du har betalt for strøm til bilen'
            net_value = f"{net_price_total:.2f} DKK"
        # Store the latest net_label/net_value in session_state for the next rerun
        st.session_state['car_charge_net_label'] = net_label
        st.session_state['car_charge_net_value'] = net_value
        
        # Export CSV with new column order and names
        csv = edited[[
            'Periode',
            'KWh auto detekteret',
            'KwH Iflg. Clever',
            'ikke detekteret kWh',
            'Gns. KWh pris',
            'Clever tilbagebetaling pr KWh',
            'Total udgift',
            'Totaludgift inkl. ikke detekteret',
            'Tilbagebetalt fra Clever',
            'Netto strøm pris',
            'Clever fastpris',
            'Total udgift med Clever',
            'udeladning_kwh',
            'udeladning_cost',
            'Total udgift uden Clever',
        ]].to_csv(index=False)
        st.download_button('📥 Download monthly CSV', csv, file_name=f'monthly_car_{datetime.now().date()}.csv', mime='text/csv')
    else:
        # If no monthly data, still show the net_price metric (fallback to N/A)
        st.session_state['car_charge_net_label'] = net_label
        st.session_state['car_charge_net_value'] = net_value
        st.info('Ingen månedlig opladningsdata i den valgte periode')