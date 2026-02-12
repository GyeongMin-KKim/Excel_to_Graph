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

        # -----------------------------------------------------------------------
        # [핵심] 1. 사이클 기준 온도 자동 계산
        # -----------------------------------------------------------------------
        # SP 중에서 "정상 범위(-100 ~ 220)" 안에 들어오는 값만 골라서 계산에 사용
        valid_sp_condition = (df_plot['SP'] >= VALID_MIN_TEMP) & (df_plot['SP'] <= VALID_MAX_TEMP)
        valid_sp_data = df_plot[valid_sp_condition]['SP']

        if len(valid_sp_data) > 0:
            sp_max = valid_sp_data.max()
            sp_min = valid_sp_data.min()
            
            # 정상적인 값들의 중간값으로 설정
            threshold = int((sp_max + sp_min) / 2)
            
            # 만약 편차가 너무 작으면 기본값 50으로 설정
            if (sp_max - sp_min) < 10: 
                threshold = 50
        else:
            # 정상 범위 데이터가 하나도 없으면 기본값
            threshold = 50

        # -----------------------------------------------------------------------
        # 사이클 감지 로직
        # -----------------------------------------------------------------------
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
        # 2. 사이드바 설정 (Y축 조절 기능)
        # -----------------------------------------------------------------------
        st.sidebar.header("⚙️ 그래프 설정")

        # Y축(온도) 범위 자동 계산 시에도 "정상 범위" 데이터만 참고함
        valid_pv_condition = (df_plot['PV'] >= VALID_MIN_TEMP) & (df_plot['PV'] <= VALID_MAX_TEMP)
        
        valid_pv = df_plot[valid_pv_condition]['PV']
        valid_sp = df_plot[valid_sp_condition]['SP']
        
        # 기본적으로 보여줄 Y축 범위 계산
        if len(valid_pv) > 0 and len(valid_sp) > 0:
            global_min = min(valid_pv.min(), valid_sp.min())
            global_max = max(valid_pv.max(), valid_sp.max())
            default_min = int(global_min - 10)
            default_max = int(global_max + 10)
        else:
            default_min, default_max = -50, 200

        st.sidebar.subheader("🌡️ 온도 범위 (Y축)")
        
        # 사용자가 입력할 수 있는 Y축 최소/최대
        y_min_input = st.sidebar.number_input("최소 온도 (Bottom)", value=default_min, step=10)
        y_max_input = st.sidebar.number_input("최대 온도 (Top)", value=default_max, step=10)

        st.sidebar.markdown("---") 

        # 시간 눈금 입력
        st.sidebar.subheader("⏱️ 시간 눈금 (X축)")
        time_tick_input = st.sidebar.number_input(
            "시간 간격 (분)", 
            min_value=0, max_value=1000, value=30, step=10,
            help="0 입력 시 자동"
        )
        
        st.sidebar.markdown("---")
        # 분석 결과 정보 표시
        st.sidebar.info(f"🤖 자동 분석 결과\n\n- 정상 범위: **-100℃ ~ 220℃**\n- 계산된 기준: **{threshold}℃**\n- 발견된 사이클: **{total_cycles}개**")

        # -----------------------------------------------------------------------
        # 3. 그래프 그리기
        # -----------------------------------------------------------------------
        
        # 사이클 선/글자 준비
        all_shapes = []
        all_annots = []
        
        # 글자 위치 (Top보다 살짝 아래)
        text_y_pos = y_max_input - (y_max_input - y_min_input) * 0.1

        for i in range(total_cycles):
            start_min = cycle_times_min[i]
            all_shapes.append(dict(type="line", x0=start_min, x1=start_min, y0=0, y1=1, xref="x", yref="paper", line=dict(color="Gray", width=1, dash="dot")))
            
            if i < total_cycles - 1: end_min = cycle_times_min[i+1]
            else: end_min = df_plot['Elapsed_Min'].iloc[-1]
            
            all_annots.append(dict(x=start_min + (end_min - start_min)/2, y=text_y_pos, text=f"<b>Cycle {i+1}</b>", showarrow=False, font=dict(size=14, color="blue"), bgcolor="rgba(255, 255, 255, 0.6)"))

        # 필터링 함수
        def get_filtered_layout(step):
            filtered_shapes = [s for i, s in enumerate(all_shapes) if (i % step == 0)]
            filtered_annots = [a for i, a in enumerate(all_annots) if (i % step == 0)]
            
            header_annotations = [
                dict(x=0.0, y=1.12, xref="paper", yref="paper", text="<b>1. 줌(Zoom)</b>", showarrow=False, xanchor="left"),
                dict(x=0.35, y=1.12, xref="paper", yref="paper", text="<b>2. 온도 눈금</b>", showarrow=False, xanchor="left"),
                dict(x=0.7, y=1.12, xref="paper", yref="paper", text="<b>3. 사이클 간격</b>", showarrow=False, xanchor="left")
            ]
            return filtered_shapes, header_annotations + filtered_annots

        # 버튼 생성
        zoom_buttons = [dict(method="relayout", label="전체 보기", args=[{"xaxis.autorange": True, "title.text": "전체 그래프"}])]
        for i in range(total_cycles):
            s = cycle_times_min[i]
            e = cycle_times_min[i+1] if i < total_cycles-1 else df_plot['Elapsed_Min'].max()
            zoom_buttons.append(dict(method="relayout", label=f"Cycle {i+1}", args=[{"xaxis.range": [s-5, e+5], "title.text": f"Cycle {i+1} 상세"}]))

        y_tick_buttons = [dict(method="relayout", label=f"{val}도", args=[{"yaxis.dtick": val}]) for val in [5, 10, 20, 50]]

        step_buttons = []
        for step in [1, 5, 10, 20, 50, 100]:
            shapes_f, annots_f = get_filtered_layout(step)
            step_buttons.append(dict(method="relayout", label=f"{step}개씩", args=[{"shapes": shapes_f, "annotations": annots_f}]))
        step_buttons.append(dict(method="relayout", label="숨기기", args=[{"shapes": [], "annotations": get_filtered_layout(1)[1][:3]}]))

        # 그래프 생성
        fig = go.Figure()
        
        # PV/SP 그리기 (여기서는 전체 데이터를 다 그립니다. 에러값이 있다면 그래프 밖으로 나가서 안 보일 뿐입니다)
        fig.add_trace(go.Scatter(x=df_plot['Elapsed_Min'], y=df_plot['PV'], name='PV', hovertemplate="%{x:.1f}분<br>%{y}도"))
        fig.add_trace(go.Scatter(x=df_plot['Elapsed_Min'], y=df_plot['SP'], name='SP', line=dict(dash='dash'), hoverinfo='skip'))

        init_shapes, init_annots = get_filtered_layout(1)
        dtick_value = time_tick_input if time_tick_input > 0 else None

        fig.update_layout(
            title=dict(text=f"결과 그래프: {uploaded_file.name}", y=0.98, x=0.5, xanchor='center', yanchor='top'),
            shapes=init_shapes, 
            annotations=init_annots,
            
            # [핵심] Y축 범위 설정 (사용자 입력값 반영)
            yaxis=dict(range=[y_min_input, y_max_input], tickmode='linear', dtick=10),
            
            xaxis=dict(title="경과 시간 (분)", ticksuffix="분", tick0=0, dtick=dtick_value, rangeslider=dict(visible=True, thickness=0.05)),
            template='plotly_white', hovermode='x unified', height=700, margin=dict(t=160),
            updatemenus=[
                dict(type="dropdown", direction="down", x=0.0, y=1.08, showactive=True, buttons=zoom_buttons),
                dict(type="dropdown", direction="down", x=0.35, y=1.08, showactive=True, buttons=y_tick_buttons),
                dict(type="dropdown", direction="down", x=0.7, y=1.08, showactive=True, buttons=step_buttons)
            ]
        )

        st.plotly_chart(fig, use_container_width=True)

    except Exception as e:
        st.error(f"오류가 발생했습니다: {e}")

else:
    st.info("👆 데이터를 분석하려면 엑셀 파일을 업로드해주세요.")
