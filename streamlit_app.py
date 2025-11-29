import streamlit as st
import pandas as pd
import pydeck as pdk
import requests
import math

st.set_page_config(
    page_title="서울시 AED 대시보드",
    page_icon="💓",
    layout="wide",
)

# 공통 스타일
st.markdown(
    """
    <style>
    /* 전체 배경 & 여백 */
    .main {
        background-color: #f5f7fb;
    }
    .block-container {
        padding-top: 1.5rem;
        padding-bottom: 2rem;
        padding-left: 3rem;
        padding-right: 3rem;
    }

    /* 기본 글꼴 크기 조금 키우기 */
    html, body, [class*="css"]  {
        font-family: -apple-system, BlinkMacSystemFont, "Noto Sans KR", system-ui, sans-serif;
        font-size: 15px;
    }

    /* 상단 큰 제목 스타일 */
    .big-title {
        font-size: 2.1rem;
        font-weight: 800;
        margin-bottom: 0.1rem;
    }
    .subtitle {
        font-size: 0.95rem;
        color: #4b5563;
        margin-bottom: 1.0rem;
    }

    /* 카드 스타일 */
    .card {
        background: #ffffff;
        padding: 1rem 1.3rem;
        border-radius: 0.9rem;
        box-shadow: 0 4px 12px rgba(15, 23, 42, 0.05);
        border: 1px solid #edf1f7;
    }

    /* 섹션 제목 */
    .section-title {
        font-size: 1.15rem;
        font-weight: 700;
        margin-top: 0.5rem;
        margin-bottom: 0.4rem;
    }
    </style>
    """,
    unsafe_allow_html=True,
)








# ========================================
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
# 6. 지도 & 행정동 분석 (탭)
# =========================================

tab_map, tab_dong = st.tabs(["🗺 지도 / 접근성", "📊 행정동 분석"])

# -------------------------------
# 탭 1 : 지도 + 접근성 분석
# -------------------------------
with tab_map:
    st.subheader("🗺 서울시 AED 위치 지도 (개별 AED + 접근성 분석)")

    # 기본 뷰
    initial_view = pdk.ViewState(
        latitude=37.5665,
        longitude=126.9780,
        zoom=12,
        pitch=0,
        bearing=0,
    )

    layers = []

    # 🔵 개별 AED 점 레이어
    aed_layer = pdk.Layer(
        "ScatterplotLayer",
        data=df,
        get_position="[경도, 위도]",
        get_radius=20,
        radius_min_pixels=3,
        radius_max_pixels=6,
        get_fill_color="[0, 120, 255, 160]",  # 파란 점
        pickable=True,
    )
    layers.append(aed_layer)

    # ----- 현재 위치 기반 접근성 분석 -----
    access_counts = None      # 화면에 보여줄 숫자
    buffer_df = None          # 동심원(버퍼) 그리기용

    if user_lat is not None and user_lon is not None:
        # AED까지 거리 (m 단위)
        df_dist = df.copy()
        df_dist["distance_m"] = df_dist.apply(
            lambda row: haversine(user_lat, user_lon, row["위도"], row["경도"]) * 1000,
            axis=1,
        )

        # 반경별 AED 개수
        r_list = [100, 300, 500]
        counts = []
        for r in r_list:
            counts.append(int((df_dist["distance_m"] <= r).sum()))
        access_counts = dict(zip(r_list, counts))

        # 동심원 데이터 (100m / 300m / 500m)
        buffer_df = pd.DataFrame(
            [
                {"위도": user_lat, "경도": user_lon, "radius_m": 100, "label": "100m"},
                {"위도": user_lat, "경도": user_lon, "radius_m": 300, "label": "300m"},
                {"위도": user_lat, "경도": user_lon, "radius_m": 500, "label": "500m"},
            ]
        )

        # 현재 위치 기준으로 뷰 이동
        initial_view = pdk.ViewState(
            latitude=user_lat,
            longitude=user_lon,
            zoom=14,
            pitch=0,
            bearing=0,
        )

    # 현재 위치 + 가장 가까운 AED + 동심원 레이어
    if user_lat is not None and user_lon is not None:
        # 현재 위치 (빨간 점)
        user_layer = pdk.Layer(
            "ScatterplotLayer",
            data=pd.DataFrame([{"위도": user_lat, "경도": user_lon}]),
            get_position="[경도, 위도]",
            get_radius=80,
            radius_min_pixels=6,
            get_fill_color="[255, 77, 77, 230]",
        )
        layers.append(user_layer)

        # 가장 가까운 AED (초록 점)
        if nearest_row is not None:
            nearest_layer = pdk.Layer(
                "ScatterplotLayer",
                data=pd.DataFrame(
                    [{"위도": nearest_row["위도"], "경도": nearest_row["경도"]}]
                ),
                get_position="[경도, 위도]",
                get_radius=100,
                radius_min_pixels=7,
                get_fill_color="[0, 200, 140, 250]",
            )
            layers.append(nearest_layer)

        # 동심원 (접근성 버퍼)
        if buffer_df is not None:
            buffer_layer = pdk.Layer(
                "ScatterplotLayer",
                data=buffer_df,
                get_position="[경도, 위도]",
                get_radius="radius_m",
                get_fill_color="[0, 0, 0, 0]",          # 안은 투명
                stroked=True,
                get_line_color="[255, 99, 71, 160]",    # 테두리 색
                line_width_min_pixels=2,
                pickable=False,
            )
            layers.append(buffer_layer)

    # 지도 렌더링
    tooltip = {
        "html": """
        <b>{설치기관명}</b><br/>
        {설치기관주소}<br/>
        설치위치: {설치위치}
        """,
        "style": {"backgroundColor": "white", "color": "black"},
    }

    deck = pdk.Deck(
        map_style=None,
        initial_view_state=initial_view,
        layers=layers,
        tooltip=tooltip,
    )

    st.pydeck_chart(deck)

    # 접근성 숫자 출력
    if access_counts is not None:
        st.markdown("### 🚶 현재 위치 기준 AED 접근성")

        c1, c2, c3 = st.columns(3)
        c1.metric("반경 100m 이내 AED 수", f"{access_counts[100]} 개")
        c2.metric("반경 300m 이내 AED 수", f"{access_counts[300]} 개")
        c3.metric("반경 500m 이내 AED 수", f"{access_counts[500]} 개")

        st.caption(
            "※ 반경 거리는 위경도 기반 직선거리(하버사인)로 계산한 값입니다. "
            "실제 도보 이동 거리와는 차이가 있을 수 있습니다."
        )
    else:
        st.info("좌측 사이드바에서 현재 위치를 입력한 뒤 **[가장 가까운 AED 찾기]** 버튼을 누르면, 접근성 분석 결과가 표시됩니다.")


# -------------------------------
# 탭 2 : 행정동 분석
# -------------------------------
with tab_dong:
    st.subheader("📊 행정동 단위 AED 분포 분석")

    # 1) 행정동 컬럼 만들기
    df_dong = df.copy()
    addr_col = "설치기관주소"

    if addr_col in df_dong.columns:
        addr = df_dong[addr_col].astype(str)

        # 1단계: 괄호 안 '○○동' 추출 (예: 167(장안동) → 장안동)
        dong_in_paren = addr.str.extract(r"\(([^()\s]*동)\)")[0]

        # 2단계: '○○구 ○○동' 패턴에서 동 추출 (예: 종로구 사직동 9 → 사직동)
        dong_after_gu = addr.str.extract(r"\S+구\s+(\S*동)")[0]

        # 우선순위: 괄호 안 → 구 뒤 동
        df_dong["행정동"] = dong_in_paren.fillna(dong_after_gu)

    else:
        df_dong["행정동"] = None

    # 2) 비정상 동명 제거 (건물 동 등)
    df_dong = df_dong.dropna(subset=["행정동"])
    df_dong["행정동"] = df_dong["행정동"].str.strip()

    # 숫자·영문 시작, '관리동', 그냥 '동', 너무 짧은 값 제거
    mask_bad = (
        df_dong["행정동"].str.match(r"^[0-9A-Za-z].*동")    # 101동, A동 등
        | df_dong["행정동"].str.contains("관리동")          # 관리동
        | (df_dong["행정동"] == "동")                      # 그냥 '동'
        | (df_dong["행정동"].str.len() <= 2)               # 한 글자/두 글자 이상한 값
    )
    df_dong = df_dong[~mask_bad]

    # 3) 행정동별 AED 개수 집계
    if df_dong.empty:
        st.warning("행정동 정보를 추출하지 못했습니다. 주소 형식을 확인해주세요.")
    else:
        dong_stats = (
            df_dong.groupby("행정동")
            .agg(AED수=("행정동", "size"))
            .reset_index()
            .sort_values("AED수", ascending=False)
        )

        st.markdown("#### 🔝 행정동별 AED 개수 (내림차순)")
        st.dataframe(dong_stats, use_container_width=True)

        # 4) 상위 N개 막대 그래프 (내림차순)
        max_n = min(30, len(dong_stats))
        default_n = 8 if max_n >= 8 else max_n

        st.markdown("#### 📈 상위 행정동 AED 수")
        top_n = st.slider("막대그래프로 볼 상위 행정동 수", 3, max_n, default_n, step=1)

        top_stats = dong_stats.head(top_n)                 # 이미 AED수 내림차순
        top_stats = top_stats.sort_values("AED수", ascending=False)

        chart_data = top_stats.set_index("행정동")["AED수"]
        st.bar_chart(chart_data)

        # 5) 특정 행정동 상세 보기
        st.markdown("#### 🔍 행정동별 AED 상세 목록")
        selected_dong = st.selectbox("행정동 선택", dong_stats["행정동"].tolist())

        dong_detail = df_dong[df_dong["행정동"] == selected_dong]

        show_cols = [c for c in ["설치기관명", "설치기관주소", "설치위치"] if c in dong_detail.columns]

        st.write(f"**{selected_dong} AED 목록 (총 {len(dong_detail)}개)**")
        st.dataframe(dong_detail[show_cols], use_container_width=True)




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
