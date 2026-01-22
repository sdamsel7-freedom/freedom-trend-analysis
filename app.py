import streamlit as st
import pandas as pd
import requests
import json
import matplotlib.pyplot as plt

# 1. 페이지 설정 및 제목
st.set_page_config(page_title="프리덤 MD 트렌드 분석기", layout="wide")
st.title("🏃‍♂️ Freedom MD Trend Analysis Tool")
st.sidebar.header("설정 및 도구")

# 2. 엑셀 양식 다운로드 기능
# 롸크초이님, GitHub에 'keywords_input.xlsx' 파일이 먼저 업로드되어 있어야 작동합니다.
st.sidebar.subheader("1. 양식 관리")
try:
    with open("keywords_input.xlsx", "rb") as file:
        st.sidebar.download_button(
            label="📊 엑셀 양식 다운로드",
            data=file,
            file_name="keywords_input.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
except FileNotFoundError:
    st.sidebar.warning("GitHub에 keywords_input.xlsx 파일을 먼저 올려주세요.")

# 3. 네이버 API 인증 정보 (Secrets에서 불러오기)
# Streamlit Cloud의 Advanced settings -> Secrets에 저장한 값을 사용합니다.
client_id = st.secrets["NAVER_CLIENT_ID"]
client_secret = st.secrets["NAVER_CLIENT_SECRET"]

# 4. 파일 업로드 섹션
st.subheader("2. 키워드 데이터 업로드")
uploaded_file = st.file_uploader("수정한 엑셀 파일을 업로드하세요", type=["xlsx"])

if uploaded_file:
    # 엑셀 데이터 읽기
    df_input = pd.read_excel(uploaded_file)
    st.success("파일 업로드 완료!")
    st.write("분석할 키워드 목록:", df_input['keyword'].tolist())

    # 5. 네이버 데이터랩 API 호출 로직
    # 19-44세 타겟 설정
    url = "https://openapi.naver.com/v1/datalab/search"
    
    # 예시로 첫 번째 키워드 분석 (롸크초이님의 업무 로직에 맞게 확장 가능)
    target_keyword = df_input['keyword'].iloc[0]
    
    body = {
        "startDate": "2025-01-01",
        "endDate": "2026-01-20",
        "timeUnit": "month",
        "keywordGroups": [{"groupName": target_keyword, "keywords": [target_keyword]}],
        "device": "mo", # 모바일 위주 분석
        "ages": ["4", "5", "6", "7", "8"], # 19세~44세 구간
        "gender": "" # 전체
    }

    headers = {
        "X-Naver-Client-Id": client_id,
        "X-Naver-Client-Secret": client_secret,
        "Content-Type": "application/json"
    }

    response = requests.post(url, headers=headers, data=json.dumps(body))
    
    if response.status_code == 200:
        res_data = response.json()
        
        # 데이터 가공 및 시각화
        data = res_data['results'][0]['data']
        df_result = pd.DataFrame(data)
        df_result['period'] = pd.to_datetime(df_result['period'])
        
        st.subheader(f"📈 '{target_keyword}' 검색 트렌드 분석 (19-44세)")
        
        # 차트 출력
        fig, ax = plt.subplots(figsize=(10, 5))
        ax.plot(df_result['period'], df_result['ratio'], marker='o', color='#ff4b4b')
        ax.set_title(f"Monthly Trend: {target_keyword}")
        ax.set_ylabel("Search Ratio")
        st.pyplot(fig)
        
        st.dataframe(df_result)
    else:
        st.error(f"API 호출 실패: {response.status_code}")
        st.write("Secrets에 입력된 API 키를 확인해 주세요.")

else:
    st.info("왼쪽에서 양식을 다운로드하여 키워드를 입력한 후 업로드해 주세요.")
