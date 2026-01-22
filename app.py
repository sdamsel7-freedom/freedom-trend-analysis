import streamlit as st
import pandas as pd
import requests
import json
from datetime import datetime
import io
import matplotlib.pyplot as plt

# 1. 페이지 설정
st.set_page_config(page_title="프리덤 트렌드 분석 대시보드", layout="wide")
st.title("🏃‍♂️ Freedom Trend Analysis Dashboard")
st.markdown("### 19~44세 남녀 트렌드 분석 및 스케일 보정 도구")

# 2. 보안 설정 (Secrets)
try:
    CLIENT_ID = st.secrets["NAVER_CLIENT_ID"]
    CLIENT_SECRET = st.secrets["NAVER_CLIENT_SECRET"]
except KeyError:
    st.error("오류: Streamlit Secrets에 NAVER_CLIENT_ID와 NAVER_CLIENT_SECRET을 설정해주세요.")
    st.stop()

# 3. Naver API 호출 함수
def get_api_data(keyword_groups, gender):
    url = "https://openapi.naver.com/v1/datalab/search"
    headers = {
        "X-Naver-Client-Id": CLIENT_ID,
        "X-Naver-Client-Secret": CLIENT_SECRET,
        "Content-Type": "application/json"
    }
    body = {
        "startDate": "2024-01-01",
        "endDate": datetime.now().strftime("%Y-%m-%d"),
        "timeUnit": "month",
        "keywordGroups": keyword_groups,
        "device": "",
        "ages": ["3", "4", "5", "6", "7"], # 19~44세
        "gender": gender
    }
    
    response = requests.post(url, headers=headers, data=json.dumps(body))
    if response.status_code == 200:
        res_json = response.json()
        data_list = []
        for group in res_json['results']:
            for entry in group['data']:
                data_list.append({
                    'Date': entry['period'],
                    'Keyword_Group': group['title'],
                    'Ratio': entry['ratio'],
                    'Gender': 'Male' if gender == 'm' else 'Female'
                })
        return pd.DataFrame(data_list)
    else:
        st.error(f"API 에러: {response.status_code}")
        return pd.DataFrame()

# 4. 사이드바: 파일 업로드 및 양식 다운로드
with st.sidebar:
    st.header("📁 데이터 관리")
    
    # 양식 다운로드 버튼 (롸크초이님, GitHub에 keywords_input.xlsx가 있어야 작동합니다)
    try:
        with open("keywords_input.xlsx", "rb") as f:
            st.download_button("📊 엑셀 양식 다운로드", f, file_name="keywords_input.xlsx")
    except:
        pass

    uploaded_file = st.file_uploader("분석할 엑셀 파일을 업로드하세요", type=["xlsx"])

# 5. 메인 로직
if uploaded_file:
    df_input = pd.read_excel(uploaded_file)
    
    # 컬럼명 유연하게 인식 (GroupName, Keywords)
    if 'GroupName' in df_input.columns:
        all_groups = []
        for _, row in df_input.iterrows():
            g_name = str(row['GroupName']).strip()
            # Keywords가 없으면 GroupName을 검색어로 사용 (Fallback Logic)
            kw_val = str(row['Keywords']).strip() if 'Keywords' in df_input.columns and pd.notnull(row['Keywords']) else ""
            keywords = [k.strip() for k in kw_val.split(',')] if kw_val and kw_val != "nan" else [g_name]
            all_groups.append({"groupName": g_name, "keywords": keywords})

        anchor_group = all_groups[0]
        anchor_name = anchor_group['groupName']
        other_groups = all_groups[1:]

        if st.sidebar.button("🚀 분석 시작 (Run Analysis)"):
            final_df = pd.DataFrame()
            reference_data = pd.DataFrame()
            progress = st.progress(0)
            
            # 4개씩 묶어서 호출 (기준점 1개 + 동적 키워드 4개 = 총 5개 제한)
            batch_size = 4
            for i in range(0, len(other_groups) if other_groups else 1, batch_size):
                chunk = other_groups[i:i+batch_size]
                current_batch = [anchor_group] + chunk
                
                # 남/녀 데이터 통합 호출
                batch_res = pd.concat([get_api_data(current_batch, 'm'), get_api_data(current_batch, 'f')], ignore_index=True)
                
                if i == 0:
                    # 첫 번째 배치의 기준점 데이터를 레퍼런스로 고정
                    reference_data = batch_res[batch_res['Keyword_Group'] == anchor_name].copy()
                    final_df = batch_res
                else:
                    # 스케일 보정 (Rescaling)
                    curr_anchor = batch_res[batch_res['Keyword_Group'] == anchor_name].copy()
                    scale_merge = pd.merge(curr_anchor, reference_data, on=['Date', 'Gender'], suffixes=('_curr', '_ref'))
                    
                    # 보정 계수 계산: Ratio_ref / Ratio_curr
                    scale_merge['Factor'] = scale_merge['Ratio_ref'] / scale_merge['Ratio_curr']
                    
                    batch_res = pd.merge(batch_res, scale_merge[['Date', 'Gender', 'Factor']], on=['Date', 'Gender'])
                    batch_res['Ratio'] = batch_res['Ratio'] * batch_res['Factor']
                    
                    # 기준점 제외하고 결과에 병합
                    final_df = pd.concat([final_df, batch_res[batch_res['Keyword_Group'] != anchor_name]], ignore_index=True)
                
                progress.progress(min((i + batch_size) / (len(other_groups) + 1) if other_groups else 1.0, 1.0))

            # 결과 출력
            if not final_df.empty:
                st.success("분석이 완료되었습니다!")
                
                col1, col2 = st.columns([3, 1])
                with col1:
                    st.subheader(f"📈 {anchor_name} 대비 상대 검색량")
                    chart_data = final_df.pivot_table(index='Date', columns='Keyword_Group', values='Ratio', aggfunc='mean')
                    st.line_chart(chart_data)
                
                with col2:
                    st.subheader("👥 성별 비중")
                    gender_stats = final_df.groupby('Gender')['Ratio'].mean()
                    st.write(gender_stats)

                st.subheader("📋 상세 데이터 테이블")
                st.dataframe(final_df, use_container_width=True)

                # 엑셀 다운로드
                output = io.BytesIO()
                with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                    final_df.to_excel(writer, index=False, sheet_name='Result')
                
                st.download_button("📥 분석 결과 엑셀 다운로드", output.getvalue(), 
                                   file_name=f"freedom_trend_{datetime.now().strftime('%Y%m%d')}.xlsx")
    else:
        st.error("엑셀 파일에 'GroupName' 컬럼이 필요합니다.")
else:
    st.info("왼쪽 사이드바에서 'keywords_input.xlsx' 파일을 업로드하고 '분석 시작'을 눌러주세요.")
