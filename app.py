import streamlit as st
import pandas as pd
import requests
import json
import matplotlib.pyplot as plt

# 1. 페이지 설정
st.set_page_config(page_title="프리덤 MD 트렌드 분석기", layout="wide")
st.title("🏃‍♂️ Freedom MD Trend Analysis Tool")

# 2. 엑셀 양식 다운로드 (사이드바)
with st.sidebar:
    st.header("📊 분석 설정")
    try:
        with open("keywords_input.xlsx", "rb") as file:
            st.download_button(label="📁 엑셀 양식 다운로드", data=file, file_name="keywords_input.xlsx")
    except:
        st.warning("양식 파일(keywords_input.xlsx)이 GitHub에 없습니다.")

# 3. API 보안 키 (Streamlit Secrets)
client_id = st.secrets["NAVER_CLIENT_ID"]
client_secret = st.secrets["NAVER_CLIENT_SECRET"]

# 4. 파일 업로드 및 유연한 컬럼 인식
st.subheader("1. 데이터 업로드")
uploaded_file = st.file_uploader("수정한 엑셀 파일을 업로드하세요", type=["xlsx"])

if uploaded_file:
    df_input = pd.read_excel(uploaded_file)
    
    # [핵심 수정] 'keyword' 혹은 '키워드' 중 하나라도 있으면 인식함
    target_col = None
    for col in ['keyword', '키워드', 'Keyword', '단어']:
        if col in df_input.columns:
            target_col = col
            break
            
    if target_col:
        keywords = df_input[target_col].dropna().unique().tolist()
        
        # [핵심 수정] 사용자가 선택한 키워드에 따라 데이터를 가져옴
        selected_keyword = st.selectbox("분석할 키워드를 선택하세요:", keywords)
        
        if selected_keyword:
            # 네이버 API 호출 (프리덤 타겟: 19-44세)
            url = "https://openapi.naver.com/v1/datalab/search"
            body = {
                "startDate": "2025-01-01",
                "endDate": "2026-01-22",
                "timeUnit": "month",
                "keywordGroups": [{"groupName": selected_keyword, "keywords": [selected_keyword]}],
                "device": "mo",
                "ages": ["4", "5", "6", "7", "8"], # 19-44세
                "gender": ""
            }
            headers = {"X-Naver-Client-Id": client_id, "X-Naver-Client-Secret": client_secret, "Content-Type": "application/json"}
            
            response = requests.post(url, headers=headers, data=json.dumps(body))
            if response.status_code == 200:
                data = response.json()['results'][0]['data']
                df_res = pd.DataFrame(data)
                if not df_res.empty:
                    df_res['period'] = pd.to_datetime(df_res['period'])
                    
                    # 시각화
                    fig, ax = plt.subplots(figsize=(10, 4))
                    ax.plot(df_res['period'], df_res['ratio'], marker='o', color='#ff4b4b')
                    ax.set_title(f"Trend: {selected_keyword}")
                    st.pyplot(fig)
                    st.dataframe(df_res)
            else:
                st.error("API 연결 실패. Secrets 설정을 확인해 주세요.")
    else:
        st.error("엑셀 파일에 'keyword' 또는 '키워드' 제목이 없습니다.")
        st.write("현재 확인된 제목들:", df_input.columns.tolist())
