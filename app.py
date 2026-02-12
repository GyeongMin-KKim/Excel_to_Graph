import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import numpy as np
import openpyxl

# --------------------------------------------------------------------------------
# 1. 페이지 설정
# --------------------------------------------------------------------------------
st.set_page_config(layout="wide", page_title="데이터 분석기")

st.title("📈 엑셀 데이터 시각화")
uploaded_file = st.file_uploader("엑셀/CSV 파일을 여기에 드래그하세요", type=['xlsx', 'xls', 'csv'])

# --------------------------------------------------------------------------------
# 2. 데이터 처리
# --------------------------------------------------------------------------------
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
        
        # [중요] 사용자가 지정한 정상 범위 (-100 ~ 220)
        VALID_MIN_TEMP = -100
        VALID_MAX_TEMP = 220

        # -999 같은 에러 코드는 일단 NaN으로 처리
        df_plot.replace(-999, np.nan, inplace=True)

        # SP 중에서 "정상 범위(-100 ~ 220)" 안에 들어오는 값만 골라서 계산에 사용
        valid_sp_condition = (df_plot['SP'] >= VALID_MIN_TEMP) & (df_plot['SP'] <= VALID_MAX_TEMP)
        valid_sp_data = df_plot[valid_sp_condition]['SP']

        if len(valid_sp_data) > 0:
            sp_max = valid_sp_data.max()
            sp_min = valid_sp_data.min()
            threshold = int((sp_max + sp_min) / 2)
            if (sp_max - sp_min) < 10: 
                threshold = 50
        else:
            threshold = 50

        # 사이클 감지 로직
        is_high = df_plot['SP'] > threshold
        cycle_starts = df_plot[is_high & (~is_high.shift(1).fillna(False))]
        
        if (len(df_plot) > 0) and (df_plot['SP'].iloc[0] > threshold):
             if (len(cycle_starts) == 0) or (cycle_starts.index[0] != df_plot.index[0]):
                 cycle_starts = pd.concat([df_plot.iloc[[0]], cycle_starts])

        # 시간 변환
        if len(cycle_starts) > 0: base_time = cycle_starts['Time'].iloc[0]
        else: base_time = df_plot['Time'].iloc[0]

        df_plot['Elapsed_Min'] = (df_plot['Time'] - base_time).dt.total_seconds() / 60
        cycle_times_min = ((cycle_starts['Time'] - base_time).dt.total_seconds() / 60).tolist()
        total_cycles = len(cycle_times_min)

        # -----------------------------------------------------------------------
        # [추가] 사이드바 구간 설정 (Slider)
        # -----------------------------------------------------------------------
        st.sidebar.header("⚙️ 그래프 설정")
        
        st.sidebar.subheader("🔄 사이클 구간 설정")
        if total_cycles > 1:
            # 보려는 사이클의 시작과 끝을 선택
            selected_cycles = st.sidebar.slider(
                "표시할 사이클 범위 선택",
                1, total_cycles, (1, total_cycles)
            )
            # X축 범위를 선택된 사이클에 맞게 계산
            c_start_idx = selected_cycles[0] - 1
            c_end_idx = selected_cycles[1] - 1
            x_min_range = cycle_times_min[c_start_idx]
            x_max_range = cycle_times_min[c_end_idx + 1] if (c_end_idx + 1) < total_cycles else df_plot['Elapsed_Min'].max()
        else:
            selected_cycles = (1, 1)
            x_min_range, x_max_range = df_plot['Elapsed_Min'].min(), df_plot['Elapsed_Min'].max()

        # 온도 범위 (Y축)
        valid_pv_condition = (df_plot['PV'] >= VALID_MIN_TEMP) & (df_plot['PV'] <= VALID_MAX_TEMP)
        valid_pv = df_plot[valid_pv_condition]['PV']
        valid_sp = df_plot[valid_sp_condition]['SP']
        
        if len(valid_pv) > 0 and len(valid_sp) > 0:
            global_min, global_max = min(valid_pv.min(), valid_sp.min()), max(valid_pv.max(), valid_sp.max())
            default_min, default_max = int(global_min - 10), int(global_max + 10)
        else:
            default_min, default_max = -50, 200

        st.sidebar.subheader("🌡️ 온도 범위 (Y축)")
        y_min_input = st.sidebar.number_input("최소 온도 (Bottom)", value=default_min, step=10)
        y_max_input = st.sidebar.number_input("최대 온도 (Top)", value=default_max, step=10)

        st.sidebar.subheader("⏱️ 시간 눈금 (X축)")
        time_tick_input = st.sidebar.number_input("시간 간격 (분)", min_value=0, max_value=1000, value=30, step=10)
        
        st.sidebar.info(f"🤖 자동 분석 결과\n\n- 정상 범위: **-100℃ ~ 220℃**\n- 발견된 사이클: **{total_cycles}개**")

        # -----------------------------------------------------------------------
        # 3. 그래프 그리기
        # -----------------------------------------------------------------------
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=df_plot['Elapsed_Min'], y=df_plot['PV'], name='PV'))
        fig.add_trace(go.Scatter(x=df_plot['Elapsed_Min'], y=df_plot['SP'], name='SP', line=dict(dash='dash')))

        # [추가/수정] 사이클 배경색 및 선 설정
        text_y_pos = y_max_input - (y_max_input - y_min_input) * 0.1

        for i in range(total_cycles):
            start_min = cycle_times_min[i]
            end_min = cycle_times_min[i+1] if i < total_cycles - 1 else df_plot['Elapsed_Min'].iloc[-1]
            
            # [추가] 짝수번째 사이클에만 연한 회색 배경 추가
            if (i + 1) % 2 == 0:
                fig.add_vrect(
                    x0=start_min, x1=end_min,
                    fillcolor="rgba(200, 200, 200, 0.1)", # 지이이인짜 연한 회색
                    layer="below", line_width=0,
                )
            
            # 사이클 구분선
            fig.add_vline(x=start_min, line=dict(color="Gray", width=1, dash="dot"))
            
            # 사이클 번호 표시 (선택 범위 내에 있을 때만)
            if selected_cycles[0] <= i+1 <= selected_cycles[1]:
                fig.add_annotation(
                    x=start_min + (end_min - start_min)/2, y=text_y_pos,
                    text=f"<b>Cycle {i+1}</b>", showarrow=False,
                    font=dict(size=14, color="blue"), bgcolor="rgba(255, 255, 255, 0.6)"
                )

        # 레이아웃 설정 (구간 설정 반영)
        dtick_value = time_tick_input if time_tick_input > 0 else None
        fig.update_layout(
            title=dict(text=f"결과 그래프: {uploaded_file.name}", x=0.5),
            yaxis=dict(range=[y_min_input, y_max_input], dtick=10),
            xaxis=dict(
                title="경과 시간 (분)", 
                range=[x_min_range, x_max_range], # [추가] 슬라이더로 선택한 구간 적용
                dtick=dtick_value, 
                rangeslider=dict(visible=True, thickness=0.05)
            ),
            template='plotly_white', hovermode='x unified', height=700
        )

        st.plotly_chart(fig, use_container_width=True)

    except Exception as e:
        st.error(f"오류가 발생했습니다: {e}")
else:
    st.info("👆 데이터를 분석하려면 엑셀 파일을 업로드해주세요.")
