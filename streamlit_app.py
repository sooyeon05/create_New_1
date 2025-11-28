import streamlit as st
import pandas as pd
import pydeck as pdk
import requests
import math

# =========================================
# 0. 기본 설정
# =========================================
st.set_page_config(
    page_title="서울시 AED 위치 대시보드",
    layout="wide",
)

st.title("🧯 서울시 AED(자동심장충격기) 위치 대시보드")
st.caption("서울시 AED 공개 데이터를 이용해 지도에 표시하고, 현재 위치 기준 가장 가까운 AED를 찾아주는 대시보드입니다.")

# GitHub에 올려둔 CSV 파일 이름 (파일명 다르면 여기만 바꾸세요)
CSV_FILE = "aed_seoul.csv.csv"
CSV_ENCODING = "cp949"   # 공공데이터 한글 파일은 보통 cp949


# =========================================
# 1. 데이터 불러오기
# =========================================
@st.cache_data
def load_aed_data(path: str) -> pd.DataFrame:
    df = pd.read_csv(path, encoding=CSV_ENCODING)

    # ⚠️ 아래 컬럼 이름은 CSV 파일에 맞게 한 번 확인해 보세요.
    # 예시) '설치기관명', '설치기관주소', '설치위치', '위도', '경도', '관리책임자명', '관리자연락처'
    # 만약 KeyError 나면, st.dataframe(df.head())로 컬럼명을 확인 후 아래 이름들을 맞춰주세요.

    # 위도/경도 결측치 제거 및 숫자형 변환
    df = df.dropna(subset=["위도", "경도"])
    df["위도"] = df["위도"].astype(float)
    df["경도"] = df["경도"].astype(float)

    return df


try:
    df = load_aed_data(CSV_FILE)
except FileNotFoundError:
    st.error(f"CSV 파일을 찾을 수 없습니다: {CSV_FILE}\n\nGitHub 저장소의 root 위치에 같은 이름으로 올려주세요.")
    st.stop()

st.success(f"AED 데이터 로드 완료 ✅ (총 {len(df):,}개 지점)")
with st.expander("데이터 컬럼 미리보기"):
    st.dataframe(df.head())


# =========================================
# 2. 거리 계산 함수 (하버사인)
# =========================================
def haversine(lat1, lon1, lat2, lon2):
    """두 좌표(위도,경도) 사이의 거리를 km 단위로 계산"""
    R = 6371  # 지구 반지름(km)
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)

    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c


# =========================================
# 3. 사이드바: 현재 위치 입력
# =========================================
st.sidebar.header("🔍 현재 위치 / 검색 옵션")

search_text = st.sidebar.text_input(
    "현재 위치를 주소 또는 장소명으로 입력하세요\n(예: 강남역, 서울특별시 중구 세종대로 110)",
    value="",
)

st.sidebar.markdown("---")
st.sideb
