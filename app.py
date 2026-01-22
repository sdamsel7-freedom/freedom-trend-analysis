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
            st.sidebar.download_button(label="📁 엑셀 양식 다운로드", data=file, file_name="keywords_input.xlsx")
    except:
        st.sidebar.warning("양식 파일이 GitHub에 없습니다.")

# 3. API 보안 키 (Streamlit Secrets)
client_id = st.secrets["NAVER_CLIENT_ID"]
client_secret = st.secrets["NAVER_CLIENT_SECRET"]

# 4. 데이터 업로드 및 로직 처리
st.subheader("1. 데이터 업로드")
uploaded_file = st.file_uploader("수정한 엑셀 파일을 업로드하세요", type=["xlsx"])

if uploaded_file:
    df_input = pd.read_excel(uploaded_file)
    
    # [핵심 수정] GroupName 컬럼이 있는지 확인
    if 'GroupName' in df_input.columns:
        # 중복 제거된 그룹명 리스트
        group_list = df_input['GroupName'].dropna().unique().tolist()
        selected_group = st.selectbox("분석할 그룹을 선택하세요:", group_list)
        
        if selected_group:
            # 선택된 그룹의 데이터 행 가져오기
            row = df_input[df_input['GroupName'] == selected_group].iloc[0]
            
            # [사용자 요청 로직] Keywords가 공란이면 GroupName 사용, 값이 있으면 Keywords 사용
            raw_keywords = str(row['Keywords']).strip() if 'Keywords' in df_input.columns and pd.notnull(row['Keywords']) else ""
            
            if not raw_keywords or raw_keywords == "nan":
                search_keywords = [selected_group]
                display_msg = f"'{selected_group}'(그룹명)으로 검색을 진행합니다."
            else:
                # 콤마(,)로 구분된 여러 키워드가 있을 경우 처리
                search_keywords = [k.strip() for k in raw_keywords.split(',')]
                display_msg = f"그룹: '{selected_group}', 키워드: {search_keywords}로 분석합니다."
            
            st.info(display_msg)
            
            # 네이버 API 호출 (프리덤 타겟: 19-44세)
            url = "https://openapi.naver.com/v1/datalab/search"
            body = {
                "startDate": "2025-01-01",
                "endDate": "2026-01-22",
                "timeUnit": "month",
                "keywordGroups": [{"groupName": selected_group, "keywords": search_keywords}],
                "device": "mo",
                "ages": ["4", "5", "6", "7", "8"], # 19-44세 타겟팅
                "gender": ""
            }
            headers = {
                "X-Naver-Client-Id": client_id, 
                "X-Naver-Client-Secret": client_secret, 
                "Content-Type": "application/json"
            }
            
            response = requests.post(url, headers=headers, data=json.dumps(body))
            if response.status_code == 200:
                data = response.json()['results'][0]['data']
                df_res = pd.DataFrame(data)
                if not df_res.empty:
                    df_res['period'] = pd.to_datetime(df_res['period'])
                    
                    # 시각화
                    fig, ax = plt.subplots(figsize=(10, 4))
                    ax.plot(df_res['period'], df_res['ratio'], marker='o', color='#ff4b4b', linewidth=2)
                    ax.set_title(f"Trend Analysis: {selected_group}")
                    st.pyplot(fig)
                    st.dataframe(df_res)
                else:
                    st.warning("데이터가 존재하지 않습니다.")
            else:
                st.error(f"API 호출 실패 (코드: {response.status_code})")
    else:
        st.error("엑셀 파일에 'GroupName' 컬럼이 없습니다.")
        st.write("감지된 제목들:", df_input.columns.tolist())
