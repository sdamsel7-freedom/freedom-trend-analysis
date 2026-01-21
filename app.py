import streamlit as st
import pandas as pd
import urllib.request
import json
from datetime import datetime
import io

# 1. 보안 설정: Streamlit Cloud의 Secrets 메뉴에 입력한 정보를 불러옵니다.
# [Security] Use st.secrets to protect your API keys from public exposure.
try:
    CLIENT_ID = st.secrets["NAVER_CLIENT_ID"]
    CLIENT_SECRET = st.secrets["NAVER_CLIENT_SECRET"]
except KeyError:
    st.error("Error: NAVER_CLIENT_ID and NAVER_CLIENT_SECRET must be set in Streamlit Secrets.")
    st.stop()

st.set_page_config(page_title="Freedom Trend Analysis Dashboard", layout="wide")

# UI 제목 및 설명
st.title("🏃‍♂️ Freedom Trend Analysis Dashboard")
st.markdown("### 19~44세 남녀 트렌드 분석 및 스케일 보정 도구")
st.info("엑셀 파일의 첫 번째 행이 모든 분석의 '기준점(Anchor)'이 됩니다.")

# 2. API 호출 함수 (Naver DataLab API)
def get_api_data(all_groups, gender):
    url = "https://openapi.naver.com/v1/datalab/search"
    body = {
        "startDate": "2023-01-01", 
        "endDate": "2025-12-31",
        "timeUnit": "month", 
        "keywordGroups": all_groups,
        "device": "", 
        "ages": ["3", "4", "5", "6", "7"], # 19~44세 필터
        "gender": gender
    }
    
    req = urllib.request.Request(url)
    req.add_header("X-Naver-Client-Id", CLIENT_ID)
    req.add_header("X-Naver-Client-Secret", CLIENT_SECRET)
    req.add_header("Content-Type", "application/json")
    
    try:
        res = urllib.request.urlopen(req, data=json.dumps(body).encode("utf-8"))
        result = json.loads(res.read().decode('utf-8'))
        data_list = []
        for group in result['results']:
            for entry in group['data']:
                data_list.append({
                    'Date': entry['period'], 
                    'Keyword_Group': group['title'], 
                    'Ratio': entry['ratio'], 
                    'Gender': 'Male' if gender == 'm' else 'Female'
                })
        return pd.DataFrame(data_list)
    except Exception as e:
        st.error(f"API Error: {e}")
        return pd.DataFrame()

# 3. 사이드바: 파일 업로드
st.sidebar.header("Upload Data")
uploaded_file = st.sidebar.file_uploader("분석할 키워드 엑셀(keywords_input.xlsx)을 업로드하세요.", type=["xlsx"])

if uploaded_file is not None:
    # 엑셀 데이터 로드 및 키워드 전처리
    df_input = pd.read_excel(uploaded_file)
    all_keyword_groups = []
    
    for _, row in df_input.iterrows():
        g_name = str(row['GroupName']).strip()
        # [Fallback Logic] B열(Keywords)이 비어있으면 A열(GroupName)을 검색어로 사용
        if pd.isna(row['Keywords']) or str(row['Keywords']).strip() == "":
            keywords = [g_name]
        else:
            keywords = [k.strip() for k in str(row['Keywords']).split(',')]
        all_keyword_groups.append({"groupName": g_name, "keywords": keywords})

    # 기준점(Anchor) 설정
    anchor_group = all_keyword_groups[0]
    anchor_name = anchor_group['groupName']
    other_groups = all_keyword_groups[1:]

    # 분석 실행 버튼
    if st.sidebar.button("Run Analysis (분석 시작)"):
        final_df = pd.DataFrame()
        reference_data = pd.DataFrame()
        
        progress_bar = st.progress(0)
        
        # 4개씩 끊어서 호출 (기준점 1개 + 동적 키워드 4개 = 총 5개 제한 준수)
        num_batches = (len(other_groups) + 3) // 4 if other_groups else 1
        
        for i in range(0, len(other_groups) if other_groups else 1, 4):
            chunk = other_groups[i:i+4]
            current_batch = [anchor_group] + chunk
            
            # 남성/여성 데이터 수집
            batch_res = pd.concat([get_api_data(current_batch, 'm'), get_api_data(current_batch, 'f')], ignore_index=True)
            
            if i == 0:
                # 첫 번째 배치의 기준점 데이터를 레퍼런스로 고정
                reference_data = batch_res[batch_res['Keyword_Group'] == anchor_name].drop_duplicates(subset=['Date', 'Gender']).copy()
                final_df = batch_res
            else:
                # 스케일 보정(Rescaling) 과정
                curr_fixed = batch_res[batch_res['Keyword_Group'] == anchor_name].drop_duplicates(subset=['Date', 'Gender']).copy()
                scale_merge = pd.merge(curr_fixed, reference_data, on=['Date', 'Gender'], suffixes=('_curr', '_ref'))
                scale_merge['Scale_Factor'] = scale_merge['Ratio_ref'] / scale_merge['Ratio_curr']
                
                batch_res = pd.merge(batch_res, scale_merge[['Date', 'Gender', 'Scale_Factor']], on=['Date', 'Gender'])
                batch_res['Ratio'] = batch_res['Ratio'] * batch_res['Scale_Factor']
                
                # 기준점 중복 제거 후 병합
                final_df = pd.concat([final_df, batch_res[batch_res['Keyword_Group'] != anchor_name]], ignore_index=True)
            
            progress_bar.progress(min((i + 4) / (len(other_groups) + 1) if other_groups else 1.0, 1.0))

        if not final_df.empty:
            final_df = final_df.drop_duplicates(subset=['Date', 'Keyword_Group', 'Gender'])
            
            # 결과 화면 출력
            col1, col2 = st.columns([2, 1])
            
            with col1:
                st.subheader(f"📊 {anchor_name} 대비 상대 검색량 트렌드")
                # 시각화를 위해 피벗 (성별 평균값 기준)
                chart_data = final_df.pivot_table(index='Date', columns='Keyword_Group', values='Ratio', aggfunc='mean')
                st.line_chart(chart_data)
            
            with col2:
                st.subheader("📋 성별 검색 비중 (평균)")
                gender_pie = final_df.groupby('Gender')['Ratio'].sum()
                st.write(gender_pie)

            # 데이터 테이블
            st.subheader("전체 분석 데이터")
            st.dataframe(final_df, use_container_width=True)

            # 엑셀 다운로드 파일 생성
            output = io.BytesIO()
            with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                final_df.to_excel(writer, index=False, sheet_name='Analysis_Result')
            
            st.download_button(
                label="📥 분석 결과 엑셀 다운로드 (Download Excel)",
                data=output.getvalue(),
                file_name=f"freedom_trend_{datetime.now().strftime('%Y%m%d')}.xlsx",
                mime="application/vnd.ms-excel"
            )
else:
    st.warning("분석을 시작하려면 왼쪽 사이드바에서 엑셀 파일을 업로드해 주세요.")