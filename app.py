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
        cycle_starts = df_plot[is_high
