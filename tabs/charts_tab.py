
import streamlit as st
import plotly.graph_objects as go
import pandas as pd

def render(df, from_date, to_date, _filter_df_by_view_range):

    df_tab = df.copy()

    # Månedlig aggregering
    df_tab['month'] = df_tab['time'].dt.to_period('M')
    # Sorter efter måned
    df_tab = df_tab.sort_values('month')
    print(df_tab.columns)
    # Total pris for bil og resten (udregnet fra kWh og pris)
    if 'car_kwh' in df_tab.columns and 'house_kwh' in df_tab.columns:
        df_tab['car_cost'] = df_tab['car_kwh'] * df_tab['total_pris_per_kwh']
        df_tab['house_cost'] = df_tab['house_kwh'] * df_tab['total_pris_per_kwh']
        monthly = df_tab.groupby('month').agg({
            'car_cost': 'sum',
            'house_cost': 'sum'
        }).reset_index()
        monthly['month_str'] = monthly['month'].dt.strftime('%b %Y')
        fig1 = go.Figure()
        fig1.add_trace(go.Bar(
            x=monthly['month_str'],
            y=monthly['car_cost'],
            name='Bil opladning (kr.)',
            marker_color='green',
            text=monthly['car_cost'].round(0),
            textposition='inside'
        ))
        fig1.add_trace(go.Bar(
            x=monthly['month_str'],
            y=monthly['house_cost'],
            name='Resten af forbruget (kr.)',
            marker_color='red',
            text=monthly['house_cost'].round(0),
            textposition='inside'
        ))
        fig1.update_layout(
            barmode='group',
            title='Månedlig totaludgift: bil vs. resten',
            xaxis_title='Måned',
            yaxis_title='Total pris (kr.)',
            height=400
        )
        st.plotly_chart(fig1, use_container_width=True)

    # Månedlig gennemsnitlig spotpris og totalpris
    if 'spot_pris' in df_tab.columns and 'total_pris_per_kwh' in df_tab.columns:
        agg_dict = {
            'spot_pris': 'mean',
            'total_pris_per_kwh': 'mean'
        }
        if 'usage_kwh' in df_tab.columns:
            agg_dict['usage_kwh'] = 'sum'
        monthly_avg = df_tab.groupby('month').agg(agg_dict).reset_index()
        monthly_avg['month_str'] = monthly_avg['month'].dt.strftime('%b %Y')
        fig2 = go.Figure()
        fig2.add_trace(go.Scatter(
            x=monthly_avg['month_str'],
            y=monthly_avg['spot_pris'],
            mode='lines+markers+text',
            name='Gns. spotpris (kr./kWh)',
            line=dict(color='green'),
            text=monthly_avg['spot_pris'].round(2),
            textposition='top center',
            textfont=dict(color='green')
        ))
        fig2.add_trace(go.Scatter(
            x=monthly_avg['month_str'],
            y=monthly_avg['total_pris_per_kwh'],
            mode='lines+markers+text',
            name='Gns. totalpris (kr./kWh)',
            line=dict(color='black'),
            text=monthly_avg['total_pris_per_kwh'].round(2),
            textposition='top center',
            textfont=dict(color='black')
        ))
        if 'usage_kwh' in monthly_avg.columns:
            fig2.add_trace(go.Bar(
                x=monthly_avg['month_str'],
                y=monthly_avg['usage_kwh'],
                name='Forbrug (kWh)',
                marker_color='blue',
                yaxis='y2',
                opacity=0.4,
                text=monthly_avg['usage_kwh'].round(0),
                textposition='inside',
                textfont=dict(color='white')
            ))
            fig2.update_layout(
                yaxis=dict(title='Pris (kr./kWh)'),
                yaxis2=dict(title='Forbrug (kWh)', overlaying='y', side='right', showgrid=False),
            )
        fig2.update_layout(
            title='Månedlig gennemsnitlig spotpris, totalpris og forbrug',
            xaxis_title='Måned',
            height=400
        )
        st.plotly_chart(fig2, use_container_width=True)
    else:
        st.warning('Data mangler for spotpris og/eller totalpris. Grafen kan ikke vises.')
