import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import numpy as np
import openpyxl

# --------------------------------------------------------------------------------
# 1. 페이지 설정
# --------------------------------------------------------------------------------
st.set_page_config(layout="wide", page_title="데이터 분석기")

st.title("📈 엑셀 데이터 시각화 (사이클 필터링)")
uploaded_file = st.file_uploader("엑셀/CSV 파일을 여기에 드래그하세요", type=['xlsx', 'xls', 'csv'])

if uploaded_file is not None:
    try:
        # 데이터 로드
        if uploaded_file.name.endswith('.csv'):
            df = pd.read_csv(uploaded_file, header=None)
        else:
            df = pd.read_excel(uploaded_file, header=None, engine='openpyxl')

        # 전처리
        df_plot = df.iloc[:, [0, 1, 2]].copy()
        df_plot.columns = ['Time', 'PV', 'SP']
        df_plot['Time'] = pd.to_datetime(df_plot['Time'], errors='coerce')
        df_plot = df_plot.dropna(subset=['Time']).sort_values(by='Time')
        
        df_plot['PV'] = pd.to_numeric(df_plot['PV'], errors='coerce')
        df_plot['SP'] = pd.to_numeric(df_plot['SP'], errors='coerce')
        
        VALID_MIN_TEMP, VALID_MAX_TEMP = -100, 220
        df_plot.replace(-999, np.nan, inplace=True)

        # 사이클 기준 온도 자동 계산
        valid_sp_data = df_plot[(df_plot['SP'] >= VALID_MIN_TEMP) & (df_plot['SP'] <= VALID_MAX_TEMP)]['SP']
        threshold = int((valid_sp_data.max() + valid_sp_data.min()) / 2) if len(valid_sp_data) > 0 else 50
        if len(valid_sp_data) > 0 and (valid_sp_data.max() - valid_sp_data.min()) < 10: threshold = 50

        # 사이클 감지
        is_high = df_plot['SP'] > threshold
        cycle_starts = df_plot[is_high & (~is_high.shift(1).fillna(False))]
        if (len(df_plot) > 0) and (df_plot['SP'].iloc[0] > threshold):
            if (len(cycle_starts) == 0) or (cycle_starts.index[0] != df_plot.index[0]):
                cycle_starts = pd.concat([df_plot.iloc[[0]], cycle_starts])

        base_time = cycle_starts['Time'].iloc[0] if len(cycle_starts) > 0 else df_plot['Time'].iloc[0]
        df_plot['Elapsed_Min'] = (df_plot['Time'] - base_time).dt.total_seconds() / 60
        cycle_times_min = ((cycle_starts['Time'] - base_time).dt.total_seconds() / 60).tolist()
        total_cycles = len(cycle_times_min)

        # -----------------------------------------------------------------------
        # 사이드바 설정
        # -----------------------------------------------------------------------
        st.sidebar.header("⚙️ 그래프 설정")
        
        # 1. 사이클 구간 선택 (Slider)
        st.sidebar.subheader("🔄 사이클 구간 설정")
        if total_cycles > 1:
            selected_cycle_range = st.sidebar.slider(
                "표시할 사이클 범위",
                1, total_cycles, (1, min(total_cycles, 20))
            )
        else:
            selected_cycle_range = (1, 1)

        # 2. 온도 범위 (Y축)
        valid_pv = df_plot[(df_plot['PV'] >= VALID_MIN_TEMP) & (df_plot['PV'] <= VALID_MAX_TEMP)]['PV']
        default_min = int(valid_pv.min() - 10) if len(valid_pv) > 0 else -50
        default_max = int(valid_pv.max() + 10) if len(valid_pv) > 0 else 200
        
        y_min_input = st.sidebar.number_input("최소 온도", value=default_min, step=10)
        y_max_input = st.sidebar.number_input("최대 온도", value=default_max, step=10)

        # 3. 시간 눈금 (X축)
        time_tick_input = st.sidebar.number_input("시간 간격 (분)", min_value=0, value=30, step=10)

        # -----------------------------------------------------------------------
        # 그래프 데이터 필터링 (선택된 사이클 구간에 따라)
        # -----------------------------------------------------------------------
        start_idx = selected_cycle_range[0] - 1
        end_idx = selected_cycle_range[1] - 1
        
        # X축 범위 설정
        x_start_limit = cycle_times_min[start_idx]
        x_end_limit = cycle_times_min[end_idx + 1] if end_idx + 1 < total_cycles else df_plot['Elapsed_Min'].max()

        # -----------------------------------------------------------------------
        # 그래프 생성
        # -----------------------------------------------------------------------
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=df_plot['Elapsed_Min'], y=df_plot['PV'], name='PV', line=dict(color='#1f77b4')))
        fig.add_trace(go.Scatter(x=df_plot['Elapsed_Min'], y=df_plot['SP'], name='SP', line=dict(dash='dash', color='#ff7f0e')))

        # 사이클 배경색 및 라벨링
        text_y_pos = y_max_input - (y_max_input - y_min_input) * 0.05
        
        for i in range(total_cycles):
            s_min = cycle_times_min[i]
            e_min = cycle_times_min[i+1] if i < total_cycles - 1 else df_plot['Elapsed_Min'].max()
            
            # 짝수 번째 사이클에만 아주 연한 회색 배경 추가 (vrect 사용)
            if (i + 1) % 2 == 0:
                fig.add_vrect(
                    x0=s_min, x1=e_min,
                    fillcolor="rgba(200, 200, 200, 0.15)", # 아주 연한 회색
                    layer="below", line_width=0,
                )
            
            # 사이클 구분 점선
            fig.add_vline(x=s_min, line=dict(color="rgba(128, 128, 128, 0.3)", width=1, dash="dot"))
            
            # 사이클 번호 텍스트 (현재 선택된 범위 내에 있을 때만)
            if start_idx <= i <= end_idx:
                fig.add_annotation(
                    x=s_min + (e_min - s_min)/2, y=text_y_pos,
                    text=f"C{i+1}", showarrow=False,
                    font=dict(size=11, color="rgba(50, 50, 50, 0.8)"),
                    bgcolor="rgba(255, 255, 255, 0.5)"
                )

        # 레이아웃 업데이트
        fig.update_layout(
            title=dict(text=f"Cycle {selected_cycle_range[0]} ~ {selected_cycle_range[1]} 분석", x=0.5),
            xaxis=dict(
                title="경과 시간 (분)", 
                range=[x_start_limit, x_end_limit], # 슬라이더 범위 적용
                dtick=time_tick_input if time_tick_input > 0 else None,
                rangeslider=dict(visible=True)
            ),
            yaxis=dict(title="온도 (℃)", range=[y_min_input, y_max_input]),
            template='plotly_white',
            height=650,
            margin=dict(t=100),
            hovermode='x unified'
        )

        st.plotly_chart(fig, use_container_width=True)
        st.sidebar.success(f"✅ 사이클 {total_cycles}개 중 {selected_cycle_range[1]-selected_cycle_range[0]+1}개 표시 중")

    except Exception as e:
        st.error(f"오류가 발생했습니다: {e}")
else:
    st.info("👆 데이터를 분석하려면 엑셀 파일을 업로드해주세요.")
