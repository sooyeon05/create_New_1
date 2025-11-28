import streamlit as st
import pandas as pd
import pydeck as pdk

st.set_page_config(page_title="서울시 AED 지도", layout="wide")
st.title("🧯 서울시 AED 위치 지도 (기본 버전)")

# 1. 데이터 불러오기
@st.cache_data
def load_data():
    # 파일명은 여러분이 가진 파일명으로 맞춰주세요
    df = pd.read_csv("aed_seoul.csv", encoding="cp949")
    # 위도/경도 컬럼 이름이 실제 파일과 같은지 꼭 확인!
    df = df.dropna(subset=["위도", "경도"])
    df["위도"] = df["위도"].astype(float)
    df["경도"] = df["경도"].astype(float)
    return df

df = load_data()

st.write("데이터 미리보기")
st.dataframe(df.head())

# 2. 초기 지도 중심(서울 시청 근처)
view_state = pdk.ViewState(
    latitude=37.5665,
    longitude=126.9780,
    zoom=11,
    pitch=0,
)

# 3. AED 점(동그라미) 레이어
aed_layer = pdk.Layer(
    "ScatterplotLayer",
    data=df,
    get_position="[경도, 위도]",  # 경도, 위도 순서!
    get_radius=50,
    radius_min_pixels=2,
    radius_max_pixels=10,
    get_fill_color="[0, 0, 255, 150]",  # 파란 점
    pickable=True,
)

tooltip = {
    "html": "<b>{설치기관명}</b><br/>{설치기관주소}",
    "style": {"backgroundColor": "white", "color": "black"},
}

deck = pdk.Deck(
    map_style=None,          # 기본 지도 스타일 사용 (토큰 필요 없음)
    initial_view_state=view_state,
    layers=[aed_layer],
    tooltip=tooltip,
)

st.pydeck_chart(deck)
