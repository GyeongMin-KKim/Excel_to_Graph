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
        
        VALID_MIN_TEMP = -100
        VALID_MAX_TEMP = 220
        df_plot.replace(-999, np.nan, inplace=True)

        valid_sp_condition = (df_plot['SP'] >= VALID_MIN_TEMP) & (df_plot['SP'] <= VALID_MAX_TEMP)
        valid_sp_data = df_plot[valid_sp_condition]['SP']

        if len(valid_sp_data) > 0:
            sp_max = valid_sp_data.max()
            sp_min = valid_sp_data.min()
            threshold = int((sp_max + sp_min) / 2)
            if (sp_max - sp_min) < 10: threshold = 50
        else:
            threshold = 50

        is_high = df_plot['SP'] > threshold
        cycle_starts = df_plot[is_high & (~is_high.shift(1).fillna(False))]
        
        if (len(df_plot) > 0) and (df_plot['SP'].iloc[0] > threshold):
             if (len(cycle_starts) == 0) or (cycle_starts.index[0] != df_plot.index[0]):
                 cycle_starts = pd.concat([df_plot.iloc[[0]], cycle_starts])

        if len(cycle_starts) > 0: base_time = cycle_starts['Time'].iloc[0]
        else: base_time = df_plot['Time'].iloc[0]

        df_plot['Elapsed_Min'] = (df_plot['Time'] - base_time).dt.total_seconds() / 60
        cycle_times_min = ((cycle_starts['Time'] - base_time).dt.total_seconds() / 60).tolist()
        total_cycles = len(cycle_times_min)

        # -----------------------------------------------------------------------
        # 2. 사이드바 설정 (구간 설정 기능 추가)
        # -----------------------------------------------------------------------
        st.sidebar.header("⚙️ 그래프 설정")

        # [추가] 사이클 구간 빠른 이동
        st.sidebar.subheader("🔍 사이클 구간 바로가기")
        col1, col2 = st.sidebar.columns(2)
        with col1:
            start_cyc = st.number_input("시작 사이클", min_value=1, max_value=total_cycles, value=1)
        with col2:
            end_cyc = st.number_input("끝 사이클", min_value=start_cyc, max_value=total_cycles, value=total_cycles)

        # X축 범위 계산
        x_min_range = cycle_times_min[start_cyc-1]
        if end_cyc < total_cycles:
            x_max_range = cycle_times_min[end_cyc]
        else:
            x_max_range = df_plot['Elapsed_Min'].max()

        st.sidebar.markdown("---")
        
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
        time_tick_input = st.sidebar.number_input("시간 간격 (분)", min_value=0, value=30, step=10)
        
        st.sidebar.info(f"🤖 자동 분석 결과\n\n- 정상 범위: **-100℃ ~ 220℃**\n- 발견된 사이클: **{total_cycles}개**")

        # -----------------------------------------------------------------------
        # 3. 그래프 데이터 구성
        # -----------------------------------------------------------------------
        all_shapes = []
        all_annots = []
        text_y_pos = y_max_input - (y_max_input - y_min_input) * 0.1

        for i in range(total_cycles):
            s_min = cycle_times_min[i]
            e_min = cycle_times_min[i+1] if i < total_cycles - 1 else df_plot['Elapsed_Min'].iloc[-1]

            if (i + 1) % 2 == 0:
                all_shapes.append(dict(
                    type="rect", x0=s_min, x1=e_min, y0=0, y1=1,
                    xref="x", yref="paper", fillcolor="rgba(180, 180, 180, 0.25)",
                    line_width=0, layer="below"
                ))

            all_shapes.append(dict(
                type="line", x0=s_min, x1=s_min, y0=0, y1=1, 
                xref="x", yref="paper", line=dict(color="rgba(100, 100, 100, 0.6)", width=1, dash="dot")
            ))
            
            all_annots.append(dict(
                x=s_min + (e_min - s_min)/2, y=text_y_pos, 
                text=f"<b>Cycle {i+1}</b>", showarrow=False, 
                font=dict(size=14, color="blue"), bgcolor="rgba(255, 255, 255, 0.6)"
            ))

        def get_filtered_layout(step):
            rects = [s for s in all_shapes if s['type'] == 'rect']
            lines = [s for i, s in enumerate([s for s in all_shapes if s['type'] == 'line']) if (i % step == 0)]
            filtered_annots = [a for i, a in enumerate(all_annots) if (i % step == 0)]
            header_annotations = [
                dict(x=0.0, y=1.12, xref="paper", yref="paper", text="<b>1. 줌(Zoom)</b>", showarrow=False, xanchor="left"),
                dict(x=0.35, y=1.12, xref="paper", yref="paper", text="<b>2. 온도 눈금</b>", showarrow=False, xanchor="left"),
                dict(x=0.7, y=1.12, xref="paper", yref="paper", text="<b>3. 사이클 간격</b>", showarrow=False, xanchor="left")
            ]
            return rects + lines, header_annotations + filtered_annots

        # 드롭다운 버튼 설정 (기존 유지)
        zoom_buttons = [dict(method="relayout", label="전체 보기", args=[{"xaxis.autorange": True}])]
        for i in range(total_cycles):
            s, e = cycle_times_min[i], (cycle_times_min[i+1] if i < total_cycles-1 else df_plot['Elapsed_Min'].max())
            zoom_buttons.append(dict(method="relayout", label=f"Cycle {i+1}", args=[{"xaxis.range": [s-5, e+5]}]))

        y_tick_buttons = [dict(method="relayout", label=f"{val}도", args=[{"yaxis.dtick": val}]) for val in [5, 10, 20, 50]]
        step_buttons = [dict(method="relayout", label=f"{step}개씩", args=[{"shapes": get_filtered_layout(step)[0], "annotations": get_filtered_layout(step)[1]}]) for step in [1, 5, 10, 20, 50]]

        # 그래프 그리기
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=df_plot['Elapsed_Min'], y=df_plot['PV'], name='PV', hovertemplate="%{x:.1f}분<br>%{y}도"))
        fig.add_trace(go.Scatter(x=df_plot['Elapsed_Min'], y=df_plot['SP'], name='SP', line=dict(dash='dash'), hoverinfo='skip'))

        init_shapes, init_annots = get_filtered_layout(1)

        fig.update_layout(
            title=dict(text=f"결과 그래프: {uploaded_file.name}", x=0.5, y=0.98),
            shapes=init_shapes, annotations=init_annots,
            yaxis=dict(range=[y_min_input, y_max_input], dtick=10),
            # [수정 포인트] 사이드바 입력값을 xaxis range에 적용
            xaxis=dict(
                title="경과 시간 (분)", 
                range=[x_min_range, x_max_range], 
                dtick=time_tick_input if time_tick_input > 0 else None, 
                rangeslider=dict(visible=True, thickness=0.05)
            ),
            template='plotly_white', hovermode='x unified', height=700, margin=dict(t=160),
            updatemenus=[
                dict(type="dropdown", direction="down", x=0.0, y=1.08, buttons=zoom_buttons),
                dict(type="dropdown", direction="down", x=0.35, y=1.08, buttons=y_tick_buttons),
                dict(type="dropdown", direction="down", x=0.7, y=1.08, buttons=step_buttons)
            ]
        )

        st.plotly_chart(fig, use_container_width=True)

    except Exception as e:
        st.error(f"오류가 발생했습니다: {e}")
else:
    st.info("👆 데이터를 분석하려면 엑셀 파일을 업로드해주세요.")
