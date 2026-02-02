import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import numpy as np
import openpyxl

# --------------------------------------------------------------------------------
# 1. 페이지 및 사이드바 설정
# --------------------------------------------------------------------------------
st.set_page_config(layout="wide", page_title="데이터 분석기")

st.sidebar.header("⚙️ 분석 설정")
input_threshold = st.sidebar.number_input("사이클 감지 기준 온도 (℃)", min_value=0, max_value=500, value=50, step=1)
st.sidebar.info(f"현재 **{input_threshold}도**를 넘어가면 사이클 시작으로 봅니다.")

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
        
        # 숫자 변환 및 에러 처리 (-999 -> NaN)
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

        # 시간 변환 (분 단위)
        if len(cycle_starts) > 0:
             base_time = cycle_starts['Time'].iloc[0]
        else:
             base_time = df_plot['Time'].iloc[0]

        df_plot['Elapsed_Min'] = (df_plot['Time'] - base_time).dt.total_seconds() / 60
        cycle_times_min = ((cycle_starts['Time'] - base_time).dt.total_seconds() / 60).tolist()
        total_cycles = len(cycle_times_min)
        
        st.success(f"✅ 분석 완료! 총 {total_cycles}개의 사이클을 찾았습니다.")

        # --------------------------------------------------------------------------------
        # 3. 그래프 구성 요소 준비
        # --------------------------------------------------------------------------------

        # Y축 범위 계산 (에러값 -200 이하 제외)
        ERROR_CUTOFF = -200
        valid_pv = df_plot[df_plot['PV'] > ERROR_CUTOFF]['PV']
        valid_sp = df_plot[df_plot['SP'] > ERROR_CUTOFF]['SP']

        if len(valid_pv) > 0 and len(valid_sp) > 0:
            real_min = min(valid_pv.min(), valid_sp.min())
            real_max = max(valid_pv.max(), valid_sp.max())
        else:
            real_min, real_max = -65, 205

        y_axis_min = real_min - 20
        y_axis_max = real_max + 20

        # 사이클 선(Shapes)과 글자(Annotations) 미리 생성
        all_shapes = []
        all_annots = []
        for i in range(total_cycles):
            start_min = cycle_times_min[i]
            # 세로 점선
            all_shapes.append(dict(type="line", x0=start_min, x1=start_min, y0=0, y1=1, xref="x", yref="paper", line=dict(color="Gray", width=1, dash="dot")))
            
            # 사이클 이름 (Cycle 1, Cycle 2...)
            if i < total_cycles - 1: end_min = cycle_times_min[i+1]
            else: end_min = df_plot['Elapsed_Min'].iloc[-1]
            mid_min = start_min + (end_min - start_min) / 2
            
            all_annots.append(dict(x=mid_min, y=160, text=f"<b>Cycle {i+1}</b>", showarrow=False, font=dict(size=14, color="blue"), bgcolor="rgba(255, 255, 255, 0.6)"))

        # 필터링 함수 (Step별로 모양과 글자 걸러내기)
        def get_filtered_layout(step):
            filtered_shapes = [s for i, s in enumerate(all_shapes) if (i % step == 0)]
            filtered_annots = [a for i, a in enumerate(all_annots) if (i % step == 0)]
            
            # 헤더 설명글 (그래프 위 버튼 설명)
            header_annotations = [
                dict(x=0.0, y=1.12, xref="paper", yref="paper", text="<b>1. 줌(Zoom)</b>", showarrow=False, xanchor="left"),
                dict(x=0.25, y=1.12, xref="paper", yref="paper", text="<b>2. 온도 눈금</b>", showarrow=False, xanchor="left"),
                dict(x=0.50, y=1.12, xref="paper", yref="paper", text="<b>3. 시간 눈금(분)</b>", showarrow=False, xanchor="left"),
                dict(x=0.75, y=1.12, xref="paper", yref="paper", text="<b>4. 사이클 간격</b>", showarrow=False, xanchor="left")
            ]
            return filtered_shapes, header_annotations + filtered_annots

        # --------------------------------------------------------------------------------
        # 4. 버튼 메뉴 생성 (핵심 기능)
        # --------------------------------------------------------------------------------

        # [버튼 1] 줌 (Zoom)
        zoom_buttons = [dict(method="relayout", label="전체 보기", args=[{"xaxis.autorange": True, "title.text": "전체 그래프"}])]
        for i in range(total_cycles):
            s = cycle_times_min[i]
            e = cycle_times_min[i+1] if i < total_cycles-1 else df_plot['Elapsed_Min'].max()
            zoom_buttons.append(dict(method="relayout", label=f"Cycle {i+1}", args=[{"xaxis.range": [s-5, e+5], "title.text": f"Cycle {i+1} 상세"}]))

        # [버튼 2] 온도 눈금
        y_tick_buttons = [dict(method="relayout", label=f"{val}도", args=[{"yaxis.dtick": val}]) for val in [5, 10, 20, 50]]

        # [버튼 3] 시간 눈금 (대폭 추가: 1분 ~ 5시간)
        x_tick_buttons = []
        time_intervals = [1, 5, 10, 15, 20, 30, 40, 45, 50, 60, 90, 120, 150, 180, 240, 300]
        
        for val in time_intervals:
            label = f"{val}분"
            if val >= 60:
                if val % 60 == 0: label = f"{val//60}시간"
                else: label = f"{val//60}시간 {val%60}분"
            x_tick_buttons.append(dict(method="relayout", label=label, args=[{"xaxis.dtick": val}]))
        
        x_tick_buttons.append(dict(method="relayout", label="자동(Auto)", args=[{"xaxis.dtick": None}]))

        # [버튼 4] 사이클 표시 간격 (Step)
        step_buttons = []
        for step in [1, 5, 10, 20, 50, 100]:
            shapes_f, annots_f = get_filtered_layout(step)
            step_buttons.append(dict(method="relayout", label=f"{step}개씩", args=[{"shapes": shapes_f, "annotations": annots_f}]))
        # 다 숨기기 버튼
        step_buttons.append(dict(method="relayout", label="숨기기", args=[{"shapes": [], "annotations": get_filtered_layout(1)[1][:4]}]))

        # --------------------------------------------------------------------------------
        # 5. 그래프 그리기
        # --------------------------------------------------------------------------------
        fig = go.Figure()
        
        # PV (실선)
        fig.add_trace(go.Scatter(
            x=df_plot['Elapsed_Min'], y=df_plot['PV'], name='PV', 
            line=dict(width=1.5), 
            text=df_plot['Elapsed_Min'].apply(lambda x: f"{int(x)}분 {int((x-int(x))*60)}초"),
            hovertemplate="경과시간: %{text}<br>온도: %{y}도<extra></extra>"
        ))
        
        # SP (점선)
        fig.add_trace(go.Scatter(
            x=df_plot['Elapsed_Min'], y=df_plot['SP'], name='SP', 
            line=dict(width=1.5, dash='dash'), hoverinfo='skip'
        ))

        # 초기 상태 (1개씩 보기)
        init_shapes, init_annots = get_filtered_layout(1)

        fig.update_layout(
            title=dict(text=f"결과 그래프: {uploaded_file.name}", y=0.98, x=0.5, xanchor='center', yanchor='top'),
            shapes=init_shapes, 
            annotations=init_annots,
            yaxis=dict(range=[y_axis_min, y_axis_max], tickmode='linear', dtick=10),
            xaxis=dict(title="경과 시간 (분)", ticksuffix="분", tick0=0, rangeslider=dict(visible=True, thickness=0.05)),
            template='plotly_white', hovermode='x unified', height=700, margin=dict(t=160),
            
            # 버튼 배치 (4개)
            updatemenus=[
                dict(type="dropdown", direction="down", x=0.0, y=1.08, showactive=True, buttons=zoom_buttons),     # 1. 줌
                dict(type="dropdown", direction="down", x=0.25, y=1.08, showactive=True, buttons=y_tick_buttons),   # 2. 온도
                dict(type="dropdown", direction="down", x=0.50, y=1.08, showactive=True, buttons=x_tick_buttons),   # 3. 시간
                dict(type="dropdown", direction="down", x=0.75, y=1.08, showactive=True, buttons=step_buttons)    # 4. 사이클 간격
            ]
        )

        st.plotly_chart(fig, use_container_width=True)

    except Exception as e:
        st.error(f"오류가 발생했습니다: {e}")
