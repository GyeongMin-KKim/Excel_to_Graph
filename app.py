import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import numpy as np

# 1. 페이지 설정
st.set_page_config(layout="wide", page_title="데이터 분석기")

st.title("📈 엑셀 데이터 시각화")
uploaded_file = st.file_uploader("엑셀/CSV 파일을 여기에 드래그하세요", type=['xlsx', 'xls', 'csv'])

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
        df_plot.replace(-999, np.nan, inplace=True)

        # 사이클 감지
        threshold = 50 
        valid_sp = df_plot[(df_plot['SP'] >= -100) & (df_plot['SP'] <= 220)]['SP']
        if len(valid_sp) > 0:
            threshold = int((valid_sp.max() + valid_sp.min()) / 2)

        is_high = df_plot['SP'] > threshold
        cycle_starts = df_plot[is_high & (~is_high.shift(1).fillna(False))]
        
        if len(cycle_starts) > 0: base_time = cycle_starts['Time'].iloc[0]
        else: base_time = df_plot['Time'].iloc[0]

        df_plot['Elapsed_Min'] = (df_plot['Time'] - base_time).dt.total_seconds() / 60
        cycle_times_min = ((cycle_starts['Time'] - base_time).dt.total_seconds() / 60).tolist()
        total_cycles = len(cycle_times_min)

        # 사이드바 설정 (온도 범위에 따라 텍스트 높이 조절)
        st.sidebar.header("⚙️ 그래프 설정")
        y_min_input = st.sidebar.number_input("최소 온도", value=-50)
        y_max_input = st.sidebar.number_input("최대 온도", value=150)
        text_y_pos = y_max_input - (y_max_input - y_min_input) * 0.1

        # 필터링 함수: 테두리 제거 버전
        def get_filtered_layout(step):
            filtered_shapes = []
            filtered_annots = []
            
            for i in range(0, total_cycles, step):
                s_min = cycle_times_min[i]
                # 다음 사이클 시작 전까지만 배경을 칠함
                e_min = cycle_times_min[i+1] if i < total_cycles - 1 else df_plot['Elapsed_Min'].iloc[-1]
                
                # 배경 회색 칸 (테두리 0)
                filtered_shapes.append(dict(
                    type="rect", x0=s_min, x1=e_min, y0=0, y1=1,
                    xref="x", yref="paper", 
                    fillcolor="rgba(180, 180, 180, 0.25)",
                    line_width=0, # 테두리 제거
                    layer="below"
                ))
                
                # 점선 구분선
                filtered_shapes.append(dict(
                    type="line", x0=s_min, x1=s_min, y0=0, y1=1, 
                    xref="x", yref="paper", 
                    line=dict(color="rgba(100, 100, 100, 0.4)", width=1, dash="dot")
                ))
                
                # 사이클 텍스트
                filtered_annots.append(dict(
                    x=s_min + (e_min - s_min)/2, y=text_y_pos, 
                    text=f"<b>Cycle {i+1}</b>", showarrow=False, 
                    font=dict(size=14, color="blue"), bgcolor="rgba(255, 255, 255, 0.6)"
                ))

            header_annots = [
                dict(x=0.0, y=1.12, xref="paper", yref="paper", text="<b>1. 줌(Zoom)</b>", showarrow=False, xanchor="left"),
                dict(x=0.35, y=1.12, xref="paper", yref="paper", text="<b>2. 온도 눈금</b>", showarrow=False, xanchor="left"),
                dict(x=0.7, y=1.12, xref="paper", yref="paper", text="<b>3. 사이클 간격</b>", showarrow=False, xanchor="left")
            ]
            return filtered_shapes, header_annots + filtered_annots

        # 드롭다운 메뉴
        zoom_buttons = [dict(method="relayout", label="전체 보기", args=[{"xaxis.autorange": True}])]
        y_tick_buttons = [dict(method="relayout", label=f"{val}도", args=[{"yaxis.dtick": val}]) for val in [5, 10, 20, 50]]
        step_buttons = []
        for s in [1, 5, 10, 20, 50]:
            shapes, annots = get_filtered_layout(s)
            step_buttons.append(dict(
                method="relayout", 
                label=f"{s}개씩", 
                args=[{"shapes": shapes, "annotations": annots}]
            ))

        fig = go.Figure()
        fig.add_trace(go.Scatter(x=df_plot['Elapsed_Min'], y=df_plot['PV'], name='PV', line=dict(color='blue')))
        fig.add_trace(go.Scatter(x=df_plot['Elapsed_Min'], y=df_plot['SP'], name='SP', line=dict(color='red', dash='dash')))

        # 초기 화면: 1개씩 보기
        init_shapes, init_annots = get_filtered_layout(1)
        
        fig.update_layout(
            shapes=init_shapes, 
            annotations=init_annots,
            yaxis=dict(range=[y_min_input, y_max_input]),
            xaxis=dict(title="경과 시간 (분)", rangeslider=dict(visible=True, thickness=0.05)),
            template='plotly_white', 
            height=700, 
            margin=dict(t=160),
            updatemenus=[
                dict(type="dropdown", direction="down", x=0.0, y=1.08, buttons=zoom_buttons),
                dict(type="dropdown", direction="down", x=0.35, y=1.08, buttons=y_tick_buttons),
                dict(type="dropdown", direction="down", x=0.7, y=1.08, buttons=step_buttons)
            ]
        )
        st.plotly_chart(fig, use_container_width=True)

    except Exception as e:
        st.error(f"오류가 발생했습니다: {e}")
