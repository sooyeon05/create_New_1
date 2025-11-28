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

st.title(" 🚨서울시 AED(자동심장충격기) 위치 대시보드")
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
st.sidebar.markdown("또는 아래에 **직접 위도/경도**를 입력할 수도 있습니다.")
manual_lat = st.sidebar.number_input("위도 직접 입력 (선택)", value=0.0, format="%.6f")
manual_lon = st.sidebar.number_input("경도 직접 입력 (선택)", value=0.0, format="%.6f")
use_manual = st.sidebar.checkbox("직접 입력한 위도/경도 사용", value=False)

find_button = st.sidebar.button("가장 가까운 AED 찾기")


# =========================================
# 4. 주소 → 좌표 변환 (지오코딩)
# =========================================
def geocode(query: str):
    """주소/장소명 → (위도, 경도) 변환 (OpenStreetMap Nominatim 사용)"""
    if not query:
        return None

    url = "https://nominatim.openstreetmap.org/search"
    params = {
        "q": query,
        "format": "json",
        "limit": 1,
        "countrycodes": "kr",  # 한국 안에서만 검색
    }
    headers = {"User-Agent": "aed-streamlit-demo"}

    try:
        res = requests.get(url, params=params, headers=headers, timeout=5)
        res.raise_for_status()
        data = res.json()
        if not data:
            return None
        lat = float(data[0]["lat"])
        lon = float(data[0]["lon"])
        return lat, lon
    except Exception:
        return None


user_lat, user_lon = None, None
info_msg = ""

if find_button:
    if use_manual and manual_lat != 0.0 and manual_lon != 0.0:
        # 직접 입력 좌표 사용
        user_lat, user_lon = manual_lat, manual_lon
        info_msg = f"직접 입력하신 좌표를 사용합니다. (위도 {user_lat:.6f}, 경도 {user_lon:.6f})"
    else:
        # 주소/장소명으로 검색
        if search_text.strip() == "":
            info_msg = "검색어가 비어 있습니다. 주소나 장소명을 입력하거나, 위도·경도를 직접 입력해 주세요."
        else:
            result = geocode(search_text)
            if result is None:
                info_msg = "검색어로 좌표를 찾지 못했습니다. 다른 표현으로 다시 시도해 보시거나, 위도·경도를 직접 입력해 주세요."
            else:
                user_lat, user_lon = result
                info_msg = f"검색 결과 좌표: 위도 {user_lat:.6f}, 경도 {user_lon:.6f}"

if info_msg:
    st.info(info_msg)


# =========================================
# 5. 현재 위치 기준 가장 가까운 AED 찾기
# =========================================
nearest_row = None
nearest_df = None

if user_lat is not None and user_lon is not None:
    df_distance = df.copy()
    df_distance["distance_km"] = df_distance.apply(
        lambda row: haversine(user_lat, user_lon, row["위도"], row["경도"]),
        axis=1,
    )
    df_distance = df_distance.sort_values("distance_km")
    nearest_row = df_distance.iloc[0]
    nearest_df = df_distance.head(5)

# =========================================
# 6. 지도 그리기 (pydeck) - 고급 스타일 버전
# =========================================
st.subheader("🗺 서울시 AED 위치 지도 (고급 스타일)")

# 모드 선택
view_mode = st.radio(
    "지도 모드 선택",
    ["요약 보기 (3D 분포)", "상세 보기 (개별 AED)"],
    horizontal=True,
)

# 기본 뷰
initial_view = pdk.ViewState(
    latitude=37.5665,
    longitude=126.9780,
    zoom=11,
    pitch=45,
    bearing=15,
)

layers = []

# ==================================================
# (1) 요약 보기 — 3D HexagonLayer
# ==================================================
if view_mode == "요약 보기 (3D 분포)":
    hex_layer = pdk.Layer(
        "HexagonLayer",
        data=df,
        get_position="[경도, 위도]",
        radius=200,          # 육각형 크기
        elevation_scale=80,   # 높이 비율
        elevation_range=[0, 1500],
        extruded=True,        # 3D 활성화
        coverage=0.85,
        pickable=True,
        opacity=0.6,          # 반투명
    )
    layers.append(hex_layer)

# ==================================================
# (2) 상세 보기 — ScatterplotLayer(민트/블루)
# ==================================================
if view_mode == "상세 보기 (개별 AED)":
    aed_layer = pdk.Layer(
        "ScatterplotLayer",
        data=df,
        get_position="[경도, 위도]",
        get_radius=14,
        radius_min_pixels=2,
        radius_max_pixels=7,
        get_fill_color="[30, 144, 255, 150]",  # 도화지에서 튀지 않는 파스텔 블루
        pickable=True,
    )
    layers.append(aed_layer)


# ==================================================
# (3) 사용자 위치 + 가장 가까운 AED 표시
# ==================================================
if user_lat is not None and user_lon is not None and nearest_row is not None:
    user_layer = pdk.Layer(
        "ScatterplotLayer",
        data=pd.DataFrame([{"위도": user_lat, "경도": user_lon}]),
        get_position="[경도, 위도]",
        get_radius=80,
        radius_min_pixels=7,
        get_fill_color="[255, 77, 77, 230]",  # Red
    )
    nearest_layer = pdk.Layer(
        "ScatterplotLayer",
        data=pd.DataFrame(
            [{"위도": nearest_row["위도"], "경도": nearest_row["경도"]}]
        ),
        get_position="[경도, 위도]",
        get_radius=100,
        radius_min_pixels=7,
        get_fill_color="[0, 200, 140, 250]",  # Mint Green
    )
    layers.extend([user_layer, nearest_layer])

    # Zoom 조절
    initial_view = pdk.ViewState(
        latitude=user_lat,
        longitude=user_lon,
        zoom=14 if view_mode == "상세 보기 (개별 AED)" else 12,
    pitch=45,
    bearing=15,
)


# =========================================
# 7. 가장 가까운 AED 상세 정보
# =========================================
if nearest_row is not None:
    st.subheader("📍 현재 위치에서 가장 가까운 AED 정보")

    col1, col2 = st.columns(2)

    # ⚠️ 여기서도 컬럼 이름은 CSV에 맞게 조정 가능
    with col1:
        st.markdown(f"**설치기관명:** {nearest_row.get('설치기관명', '정보 없음')}")
        st.markdown(f"**설치위치:** {nearest_row.get('설치위치', '정보 없음')}")
        st.markdown(f"**주소:** {nearest_row.get('설치기관주소', '정보 없음')}")

    with col2:
        st.markdown(f"**관리책임자:** {nearest_row.get('관리책임자명', '정보 없음')}")
        st.markdown(f"**연락처:** {nearest_row.get('관리자연락처', '정보 없음')}")
        st.markdown(f"**예상 거리:** {nearest_row['distance_km']:.2f} km")

    st.markdown("#### 주변 상위 5개 AED 목록 (거리 순)")
    show_cols = ["설치기관명", "설치기관주소", "설치위치", "distance_km"]
    existing_cols = [c for c in show_cols if c in nearest_df.columns]

    st.dataframe(
        nearest_df[existing_cols]
        .rename(columns={"distance_km": "거리(km)"})
        .style.format({"거리(km)": "{:.2f}"})
    )
else:
    st.info("좌측 사이드바에서 주소 또는 위도/경도를 입력한 뒤 **[가장 가까운 AED 찾기]** 버튼을 눌러보세요.")
