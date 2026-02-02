import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import numpy as np
import openpyxl

# --------------------------------------------------------------------------------
# 1. 페이지 및 사이드바 설정
# --------------------------------------------------------------------------------
st.set_page_config(layout="wide", page_title="데이터 분석기")

# [사이드바] 여기가 사용자가 입력하는 컨트롤 패널입니다
st.sidebar.header("⚙️ 분석 설정")

# 1. 기준 온도 입력
input_threshold = st.sidebar.number_input(
    "1️⃣ 사이클 감지 기준 온도 (℃)", 
    min_value=0, max_value=500, value=50, step=1
)

st.sidebar.markdown("---") # 구분선

# 2. 시간 눈금 입력 (여기가 원하시는 입력창!)
st.sidebar.header("⏱️ 그래프 시간 눈금")
time_tick_input = st.sidebar.number_input(
    "2️⃣ 시간 간격 (분 단위 입력)", 
    min_value=0, max_value=1000, value=30, step=10,
    help="0을 입력하면 자동으로 설정됩니다."
)
st.sidebar.info(f"현재 그래프는 **{time_tick_input}분** 간격으로 표시됩니다.")


# 메인 화면
st.title("📈 엑셀 데이터 시각화 (Web Ver.)")
uploaded_file = st.file_uploader("엑셀/CSV 파일을 드래그하세요", type=['xlsx', 'xls', 'csv'])

# --------------------------------------------------------------------------------
# 2. 데이터 처리 로직
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
        df_plot.replace(-999, np.nan, inplace=True)

        # 사이클 감지
        threshold = input_threshold
        is_high = df_plot['SP'] > threshold
        cycle_starts = df_plot[is_high & (~is_high.shift(1).fillna(False))]
        
        if (len(df_plot) > 0) and (df_plot['SP'].iloc[0] > threshold):
             if (len(cycle_starts) == 0) or (cycle_starts.index[0] != df_plot.index[0]):
                 cycle_starts = pd.concat([df_plot.iloc[[0]], cycle_starts])

        # 시간 변환
        if len(cycle_starts) > 0:
             base_time = cycle_starts['Time'].iloc[0]
        else:
             base_time = df_plot['Time'].iloc[0]

        df_plot['Elapsed_Min'] = (df_plot['Time'] - base_time).dt.total_seconds() / 60
        cycle_times_min = ((cycle_starts['Time'] - base_time).dt.total_seconds() / 60).tolist()
        total_cycles = len(cycle_times_min)
        
        st.success(f"✅ 분석 완료! 총 {total_cycles}개의 사이클을 찾았습니다.")

        # --------------------------------------------------------------------------------
        # 3. 그래프 그리기
        # --------------------------------------------------------------------------------

        # Y축 범위 자동 계산
        ERROR_CUTOFF = -200
        valid_pv = df_plot[df_plot['PV'] > ERROR_CUTOFF]['PV']
        valid_sp = df_plot[df_plot['SP'] > ERROR_CUTOFF]['SP']
        if len(valid_pv) > 0:
            y_min, y_max = min(valid_pv.min(), valid_sp.min()) - 20, max(valid_pv.max(), valid_sp.max()) + 20
        else:
            y_min, y_max = -65, 205

        # 사이클 선/글자 준비
        all_shapes = []
        all_annots = []
        for i in range(total_cycles):
            start_min = cycle_times_min[i]
            all_shapes.append(dict(type="line", x0=start_min, x1=start_min, y0=0, y1=1, xref="x", yref="paper", line=dict(color="Gray", width=1, dash="dot")))
            
            if i < total_cycles - 1: end_min = cycle_times_min[i+1]
            else: end_min = df_plot['Elapsed_Min'].iloc[-1]
            
            all_annots.append(dict(x=start_min + (end_min - start_min)/2, y=160, text=f"<b>Cycle {i+1}</b>", showarrow=False, font=dict(size=14, color="blue"), bgcolor="rgba(255, 255, 255, 0.6)"))

        # 필터링 함수
        def get_filtered_layout(step):
            filtered_shapes = [s for i, s in enumerate(all_shapes) if (i % step == 0)]
            filtered_annots = [a for i, a in enumerate(all_annots) if (i % step == 0)]
            
            # 헤더 설명글 (그래프 위 설명)
            # 여기서는 '시간 눈금' 버튼을 뺐습니다 (사이드바에서 입력하니까요!)
            header_annotations = [
                dict(x=0.0, y=1.12, xref="paper", yref="paper", text="<b>1. 줌(Zoom)</b>", showarrow=False, xanchor="left"),
                dict(x=0.35, y=1.12, xref="paper", yref="paper", text="<b>2. 온도 눈금</b>", showarrow=False, xanchor="left"),
                dict(x=0.7, y=1.12, xref="paper", yref="paper", text="<b>3. 사이클 간격</b>", showarrow=False, xanchor="left")
            ]
            return filtered_shapes, header_annotations + filtered_annots

        # --- 버튼 생성 (시간 눈금 버튼은 제거하고 사이드바 입력으로 대체) ---

        # 1. 줌 버튼
        zoom_buttons = [dict(method="relayout", label="전체 보기", args=[{"xaxis.autorange": True, "title.text": "전체 그래프"}])]
        for i in range(total_cycles):
            s = cycle_times_min[i]
            e = cycle_times_min[i+1] if i < total_cycles-1 else df_plot['Elapsed_Min'].max()
            zoom_buttons.append(dict(method="relayout", label=f"Cycle {i+1}", args=[{"xaxis.range": [s-5, e+5], "title.text": f"Cycle {i+1} 상세"}]))

        # 2. 온도 눈금 버튼
        y_tick_buttons = [dict(method="relayout", label=f"{val}도", args=[{"yaxis.dtick": val}]) for val in [5, 10, 20, 50]]

        # 3. 사이클 간격 버튼
        step_buttons = []
        for step in [1, 5, 10, 20, 50, 100]:
            shapes_f, annots_f = get_filtered_layout(step)
            step_buttons.append(dict(method="relayout", label=f"{step}개씩", args=[{"shapes": shapes_f, "annotations": annots_f}]))
        step_buttons.append(dict(method="relayout", label="숨기기", args=[{"shapes": [], "annotations": get_filtered_layout(1)[1][:3]}]))

        # --- 그래프 그리기 ---
        fig = go.Figure()
        
        # PV/SP 그리기
        fig.add_trace(go.Scatter(x=df_plot['Elapsed_Min'], y=df_plot['PV'], name='PV', hovertemplate="%{x:.1f}분<br>%{y}도"))
        fig.add_trace(go.Scatter(x=df_plot['Elapsed_Min'], y=df_plot['SP'], name='SP', line=dict(dash='dash'), hoverinfo='skip'))

        init_shapes, init_annots = get_filtered_layout(1)

        # 사용자가 입력한 시간 간격 적용
        # 0이거나 음수면 Auto(None) 처리
        dtick_value = time_tick_input if time_tick_input > 0 else None

        fig.update_layout(
            title=dict(text=f"결과 그래프: {uploaded_file.name}", y=0.98, x=0.5, xanchor='center', yanchor='top'),
            shapes=init_shapes, 
            annotations=init_annots,
            yaxis=dict(range=[y_axis_min, y_axis_max], tickmode='linear', dtick=10),
            
            # [중요] 사이드바에서 입력한 값(dtick_value)을 여기서 적용!
            xaxis=dict(title="경과 시간 (분)", ticksuffix="분", tick0=0, dtick=dtick_value, rangeslider=dict(visible=True, thickness=0.05)),
            
            template='plotly_white', hovermode='x unified', height=700, margin=dict(t=160),
            
            # 버튼 메뉴 배치 (3개로 줄어듦: 시간 버튼은 사이드바로 이동)
            updatemenus=[
                dict(type="dropdown", direction="down", x=0.0, y=1.08, showactive=True, buttons=zoom_buttons),     # 1. 줌
                dict(type="dropdown", direction="down", x=0.35, y=1.08, showactive=True, buttons=y_tick_buttons),   # 2. 온도
                dict(type="dropdown", direction="down", x=0.7, y=1.08, showactive=True, buttons=step_buttons)    # 3. 사이클 간격
            ]
        )

        st.plotly_chart(fig, use_container_width=True)

    except Exception as e:
        st.error(f"오류가 발생했습니다: {e}")
