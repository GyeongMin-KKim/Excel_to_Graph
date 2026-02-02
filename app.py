import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import openpyxl

st.set_page_config(layout="wide", page_title="데이터 분석기")

st.title("엑셀 데이터 시각화")
st.markdown("엑셀 파일을 업로드하면 사이클을 분석하고 경과 시간으로 변환해줍니다.")

uploaded_file = st.file_uploader("여기에 엑셀/CSV 파일을 드래그하세요", type=['xlsx', 'xls', 'csv'])

if uploaded_file is not None:
    try:
        if uploaded_file.name.endswith('.csv'):
            df = pd.read_csv(uploaded_file, header=None)
        else:
            df = pd.read_excel(uploaded_file, header=None, engine='openpyxl')

        df_plot = df.iloc[:, [0, 1, 2]].copy()
        df_plot.columns = ['Time', 'PV', 'SP']
        df_plot['Time'] = pd.to_datetime(df_plot['Time'], errors='coerce')
        df_plot = df_plot.dropna(subset=['Time']).sort_values(by='Time')
        df_plot['PV'] = pd.to_numeric(df_plot['PV'], errors='coerce')
        df_plot['SP'] = pd.to_numeric(df_plot['SP'], errors='coerce')

        threshold = 50
        is_high = df_plot['SP'] > threshold
        cycle_starts = df_plot[is_high & (~is_high.shift(1).fillna(False))]

        if (len(df_plot) > 0) and (df_plot['SP'].iloc[0] > threshold):
            if (len(cycle_starts) == 0) or (cycle_starts.index[0] != df_plot.index[0]):
                cycle_starts = pd.concat([df_plot.iloc[[0]], cycle_starts])

        if len(cycle_starts) > 0:
            base_time = cycle_starts['Time'].iloc[0]
        else:
            base_time = df_plot['Time'].iloc[0]

        df_plot['Elapsed_Min'] = (df_plot['Time'] - base_time).dt.total_seconds() / 60

        def format_hover(minutes):
            m = int(minutes)
            s = int((minutes - m) * 60)
            return f"{m}분 {s}초"

        df_plot['Hover_Text'] = df_plot['Elapsed_Min'].apply(format_hover)

        cycle_times_min = (cycle_starts['Time'] - base_time).dt.total_seconds() / 60
        cycle_times_min = cycle_times_min.tolist()
        total_cycles = len(cycle_times_min)

        st.success(f"분석 완료! 총 {total_cycles}개의 사이클을 찾았습니다.")

        cycle_shapes = []
        for i in range(total_cycles):
            start_min = cycle_times_min[i]
            cycle_shapes.append(
                dict(
                    type="line",
                    x0=start_min,
                    x1=start_min,
                    y0=0,
                    y1=1,
                    xref="x",
                    yref="paper",
                    line=dict(color="Gray", width=1, dash="dot")
                )
            )

        header_annotations = [
            dict(x=0.0, y=1.12, xref="paper", yref="paper", text="<b>사이클 선택</b>", showarrow=False, font=dict(size=12), xanchor="left"),
            dict(x=0.3, y=1.12, xref="paper", yref="paper", text="<b>눈금 간격</b>", showarrow=False, font=dict(size=12), xanchor="left")
        ]

        all_cycle_texts = []
        for i in range(total_cycles):
            start_min = cycle_times_min[i]
            if i < total_cycles - 1:
                end_min = cycle_times_min[i + 1]
            else:
                end_min = df_plot['Elapsed_Min'].iloc[-1]
            mid_min = start_min + (end_min - start_min) / 2
            all_cycle_texts.append(
                dict(
                    x=mid_min,
                    y=160,
                    text=f"<b>Cycle {i+1}</b>",
                    showarrow=False,
                    font=dict(size=14, color="blue"),
                    bgcolor="rgba(255, 255, 255, 0.6)"
                )
            )

        buttons = []
        buttons.append(
            dict(
                method="update",
                label="전체 보기",
                args=[
                    {"visible": [True, True]},
                    {
                        "xaxis.range": [df_plot['Elapsed_Min'].min(), df_plot['Elapsed_Min'].max()],
                        "xaxis.autorange": True,
                        "title.text": "전체 그래프 (경과 시간)",
                        "annotations": header_annotations
                    }
                ]
            )
        )

        margin_zoom = 5
        for i in range(total_cycles):
            start_min = cycle_times_min[i]
            if i < total_cycles - 1:
                end_min = cycle_times_min[i + 1]
            else:
                end_min = df_plot['Elapsed_Min'].iloc[-1]
            buttons.append(
                dict(
                    method="update",
                    label=f"Cycle {i+1}",
                    args=[
                        {"visible": [True, True]},
                        {
                            "xaxis.range": [start_min - margin_zoom, end_min + margin_zoom],
                            "xaxis.autorange": False,
                            "title.text": f"Cycle {i+1} 상세 보기",
                            "annotations": header_annotations + all_cycle_texts
                        }
                    ]
                )
            )

        tick_buttons = [
            dict(method="relayout", label=f"{val}도", args=[{"yaxis.dtick": val}])
            for val in [5, 10, 20, 50]
        ]

        fig = go.Figure()
        fig.add_trace(
            go.Scatter(
                x=df_plot['Elapsed_Min'],
                y=df_plot['PV'],
                name='PV',
                line=dict(width=1.5),
                text=df_plot['Hover_Text'],
                hovertemplate="경과시간: %{text}<br>온도: %{y}도<extra></extra>"
            )
        )
        fig.add_trace(
            go.Scatter(
                x=df_plot['Elapsed_Min'],
                y=df_plot['SP'],
                name='SP',
                line=dict(width=1.5, dash='dash'),
                hoverinfo='skip'
            )
        )

        fig.update_layout(
            title=dict(text=f"결과 그래프: {uploaded_file.name}", y=0.98, x=0.5, xanchor='center', yanchor='top'),
            shapes=cycle_shapes,
            annotations=header_annotations,
            yaxis=dict(range=[-60, 170], tickmode='linear', dtick=10),
            template='plotly_white',
            hovermode='x unified',
            height=700,
            margin=dict(t=150),
            xaxis=dict(
                title="경과 시간 (분)",
                ticksuffix="분",
                rangeslider=dict(visible=True, thickness=0.05)
            ),
            updatemenus=[
                dict(type="dropdown", direction="down", active=0, x=0.0, y=1.05, showactive=True, buttons=buttons),
                dict(type="dropdown", direction="down", active=1, x=0.3, y=1.05, showactive=True, buttons=tick_buttons)
            ]
        )

        st.plotly_chart(fig, use_container_width=True)

    except Exception as e:
        st.error(f"파일을 읽는 도중 오류가 발생했습니다: {e}")
        st.write("혹시 파일이 암호화되어 있거나, 첫 번째 열이 날짜 형식이 아닌지 확인해주세요.")
