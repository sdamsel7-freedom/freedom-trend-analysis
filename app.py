import streamlit as st
import pandas as pd
import requests
import json
import matplotlib.pyplot as plt

# 1. 페이지 설정 (MD 팀장님의 넓은 시야를 위해 Wide 모드)
st.set_page_config(page_title="프리덤 MD 트렌드 분석기", layout="wide")
st.title("🏃‍♂️ Freedom MD Trend Analysis Tool")
st.sidebar.header("📊 분석 설정")

# 2. 엑셀 양식 다운로드 (사이드바)
with st.sidebar:
    try:
        with open("keywords_input.xlsx", "rb") as file:
            st.download_button(
                label="📁 엑셀 양식 다운로드",
                data=file,
                file_name="keywords_input.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
    except FileNotFoundError:
        st.warning("저장소에 keywords_input.xlsx가 없습니다.")

# 3. 네이버 API 인증 정보
client_id = st.secrets["NAVER_CLIENT_ID"]
client_secret = st.secrets["NAVER_CLIENT_SECRET"]

# 4. 파일 업로드 및 데이터 처리
st.subheader("1. 데이터 업로드")
uploaded_file = st.file_uploader("수정하신 엑셀 파일을 업로드하세요", type=["xlsx"])

if uploaded_file:
    df_input = pd.read_excel(uploaded_file)
    
    if 'keyword' in df_input.columns:
        # 비어있는 행 제외하고 키워드 리스트 추출
        keywords = df_input['keyword'].dropna().unique().tolist()
        
        # [핵심 수정] 사용자가 분석할 키워드를 직접 선택하게 함
        selected_keyword = st.selectbox("분석할 키워드를 선택하세요:", keywords)
        
        if selected_keyword:
            st.info(f"'{selected_keyword}' 키워드 분석을 시작합니다.")
            
            url = "https://openapi.naver.com/v1/datalab/search"
            body = {
                "startDate": "2025-01-01",
                "endDate": "2026-01-22",
                "timeUnit": "month",
                "keywordGroups": [{"groupName": selected_keyword, "keywords": [selected_keyword]}],
                "device": "mo",
                "ages": ["4", "5", "6", "7", "8"], # '프리덤' 타겟: 19세-44세
                "gender": "" 
            }

            headers = {
                "X-Naver-Client-Id": client_id,
                "X-Naver-Client-Secret": client_secret,
                "Content-Type": "application/json"
            }

            response = requests.post(url, headers=headers, data=json.dumps(body))
            
            if response.status_code == 200:
                res_data = response.json()
                data = res_data['results'][0]['data']
                df_result = pd.DataFrame(data)
                
                if not df_result.empty:
                    df_result['period'] = pd.to_datetime(df_result['period'])
                    
                    # 시각화 섹션
                    col1, col2 = st.columns([2, 1])
                    with col1:
                        st.subheader(f"📈 '{selected_keyword}' 월간 검색 추이")
                        fig, ax = plt.subplots(figsize=(10, 5))
                        ax.plot(df_result['period'], df_result['ratio'], marker='o', color='#ff4b4b', linewidth=2)
                        ax.grid(True, linestyle='--', alpha=0.6)
                        st.pyplot(fig)
                    
                    with col2:
                        st.subheader("📋 데이터 상세")
                        st.dataframe(df_result, use_container_width=True)
                else:
                    st.warning("선택한 키워드의 검색 데이터가 부족합니다.")
            else:
                st.error(f"API 호출 실패: {response.status_code}")
    else:
        st.error("엑셀 파일의 첫 줄에 'keyword'라는 제목이 없습니다.")
else:
    st.info("왼쪽에서 양식을 받아 키워드를 입력한 뒤 업로드해 주세요.")
